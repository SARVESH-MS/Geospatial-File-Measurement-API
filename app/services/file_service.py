"""Orchestrator service handling file processing, measurement calculation, and database persistence."""

import logging
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import FileNotFoundError, GeospatialAPIException
from app.models.file_record import UploadedFile, FeatureRecord
from app.schemas.file_schemas import (
    FileInfoResponse,
    FileMeasurementsResponse,
    FeatureMeasurementItem,
    MeasurementDetail,
    MeasurementSummary,
)
from app.services.kml_parser import KMLParser
from app.services.measurement_service import MeasurementService
from app.services.shapefile_parser import ShapefileParser

logger = logging.getLogger(__name__)


class FileProcessingService:
    """Coordinates parsing, projection, measurement calculation, and storage for geospatial files."""

    @classmethod
    def process_and_persist(
        cls,
        file_id: str,
        file_path: Path,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        db: Session,
    ) -> FileInfoResponse:
        """
        Parses geospatial file, calculates feature measurements, and persists all records to database.
        """
        file_record = UploadedFile(
            id=file_id,
            filename=original_filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            status="PROCESSING",
        )
        db.add(file_record)
        db.commit()

        try:
            # Parse based on file type
            if file_type == "shapefile":
                crs_str, parsed_features = ShapefileParser.parse_zip(file_path)
            else:
                crs_str, parsed_features = KMLParser.parse_file(file_path)

            file_record.crs = crs_str
            file_record.feature_count = len(parsed_features)

            # Calculate measurements and store feature records
            for feat in parsed_features:
                measurement, projected_crs = MeasurementService.calculate_measurement(
                    feat["shapely_geom"], crs_str
                )

                feature_record = FeatureRecord(
                    file_id=file_id,
                    feature_index=feat["feature_index"],
                    geometry_type=feat["geometry_type"],
                    geometry_geojson=feat["geometry"],
                    properties=feat["properties"],
                    crs=feat["crs"],
                    is_supported=measurement.supported,
                    projected_crs=projected_crs,
                    measurement_type=measurement.type,
                    measurement_value=measurement.value,
                    measurement_unit=measurement.unit,
                    measurement_details=measurement.model_dump(),
                )
                db.add(feature_record)

            file_record.status = "COMPLETED"
            db.commit()
            db.refresh(file_record)

            return FileInfoResponse(
                id=file_record.id,
                filename=file_record.filename,
                feature_count=file_record.feature_count,
                crs=file_record.crs,
                status=file_record.status,
            )

        except Exception as e:
            db.rollback()
            file_record.status = "FAILED"
            file_record.error_message = str(e)
            db.commit()
            logger.error("Failed processing file %s: %s", file_id, e, exc_info=True)
            if isinstance(e, GeospatialAPIException):
                raise
            raise GeospatialAPIException(f"Failed processing geospatial file: {str(e)}") from e

    @classmethod
    def get_file_info(cls, file_id: str, db: Session) -> FileInfoResponse:
        """Fetch basic file metadata matching problem specification."""
        file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file_record:
            raise FileNotFoundError(file_id)

        return FileInfoResponse(
            id=file_record.id,
            filename=file_record.filename,
            feature_count=file_record.feature_count,
            crs=file_record.crs,
            status=file_record.status,
        )

    @classmethod
    def get_file_measurements(cls, file_id: str, db: Session) -> FileMeasurementsResponse:
        """Retrieve full measurements and feature details for an uploaded file."""
        file_record = (
            db.query(UploadedFile)
            .options(joinedload(UploadedFile.features))
            .filter(UploadedFile.id == file_id)
            .first()
        )
        if not file_record:
            raise FileNotFoundError(file_id)

        items: list[FeatureMeasurementItem] = []
        total_area = 0.0
        total_length = 0.0
        poly_count = 0
        line_count = 0
        point_count = 0
        unsupported_count = 0

        for f in file_record.features:
            gtype = f.geometry_type
            if gtype in ("Polygon", "MultiPolygon"):
                poly_count += 1
                if f.measurement_value:
                    total_area += f.measurement_value
            elif gtype in ("LineString", "MultiLineString"):
                line_count += 1
                if f.measurement_value:
                    total_length += f.measurement_value
            elif gtype in ("Point", "MultiPoint"):
                point_count += 1
            else:
                unsupported_count += 1

            # Reconstruct MeasurementDetail schema
            meas_dict = f.measurement_details or {}
            meas_detail = MeasurementDetail(
                supported=f.is_supported,
                type=f.measurement_type,
                value=f.measurement_value,
                unit=f.measurement_unit,
                display=meas_dict.get("display"),
                status=meas_dict.get("status", "NOT_APPLICABLE"),
                message=meas_dict.get("message"),
            )

            items.append(
                FeatureMeasurementItem(
                    feature_index=f.feature_index,
                    geometry_type=f.geometry_type,
                    geometry=f.geometry_geojson,
                    crs=f.crs,
                    projected_crs=f.projected_crs,
                    properties=f.properties,
                    measurement=meas_detail,
                )
            )

        summary = MeasurementSummary(
            total_features=file_record.feature_count,
            polygon_count=poly_count,
            linestring_count=line_count,
            point_count=point_count,
            unsupported_count=unsupported_count,
            total_area_sq_meters=round(total_area, 4),
            total_length_meters=round(total_length, 4),
            total_area_hectares=round(total_area / 10_000.0, 4),
            total_length_km=round(total_length / 1000.0, 4),
        )

        return FileMeasurementsResponse(
            id=file_record.id,
            filename=file_record.filename,
            crs=file_record.crs,
            status=file_record.status,
            summary=summary,
            features=items,
        )

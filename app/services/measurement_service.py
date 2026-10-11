"""Measurement calculation service for geospatial geometries."""

import logging
from typing import Any
import shapely

from app.schemas.file_schemas import MeasurementDetail
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class MeasurementService:
    """Calculates metric measurements (area, length) on geospatial geometries with automatic CRS handling."""

    @classmethod
    def calculate_measurement(
        cls, geometry: shapely.Geometry, source_crs: str
    ) -> tuple[MeasurementDetail, str | None]:
        """
        Calculates measurement for a given geometry.
        Returns a tuple of (MeasurementDetail, projected_crs_used).
        Handles Polygon, MultiPolygon, LineString, MultiLineString, Point, and unsupported types gracefully.
        """
        if geometry is None or geometry.is_empty:
            return (
                MeasurementDetail(
                    supported=False,
                    type=None,
                    value=None,
                    unit=None,
                    display=None,
                    status="NOT_APPLICABLE",
                    message="Geometry is empty or null.",
                ),
                None,
            )

        geom_type = geometry.geom_type

        # 1. Point / MultiPoint - explicit specification: no measurement required
        if geom_type in ("Point", "MultiPoint"):
            return (
                MeasurementDetail(
                    supported=False,
                    type=None,
                    value=None,
                    unit=None,
                    display="N/A",
                    status="NOT_APPLICABLE",
                    message="Points have zero dimensions; no area or length measurement is required.",
                ),
                None,
            )

        # 2. Polygon & MultiPolygon - Area calculation
        if geom_type in ("Polygon", "MultiPolygon"):
            try:
                projected_crs = CRSService.determine_optimal_projected_crs(geometry, source_crs)
                projected_geom = CRSService.transform_to_crs(geometry, source_crs, projected_crs)

                area_sq_m = round(float(projected_geom.area), 4)
                hectares = round(area_sq_m / 10_000.0, 4)
                sq_km = round(area_sq_m / 1_000_000.0, 6)

                display_str = f"{area_sq_m:,.2f} m²"
                if area_sq_m >= 10_000:
                    display_str += f" ({hectares:,.2f} ha)"
                elif area_sq_m >= 1_000_000:
                    display_str += f" ({sq_km:,.4f} km²)"

                return (
                    MeasurementDetail(
                        supported=True,
                        type="area",
                        value=area_sq_m,
                        unit="square_meters",
                        display=display_str,
                        status="CALCULATED",
                        message=None,
                    ),
                    projected_crs,
                )
            except Exception as e:
                logger.error("Failed calculating area for %s: %s", geom_type, e, exc_info=True)
                return (
                    MeasurementDetail(
                        supported=True,
                        type="area",
                        value=None,
                        unit=None,
                        display=None,
                        status="ERROR",
                        message=f"Measurement calculation failed: {str(e)}",
                    ),
                    None,
                )

        # 3. LineString & MultiLineString - Length calculation
        if geom_type in ("LineString", "MultiLineString"):
            try:
                projected_crs = CRSService.determine_optimal_projected_crs(geometry, source_crs)
                projected_geom = CRSService.transform_to_crs(geometry, source_crs, projected_crs)

                length_m = round(float(projected_geom.length), 4)
                length_km = round(length_m / 1000.0, 4)

                display_str = f"{length_m:,.2f} m"
                if length_m >= 1000:
                    display_str += f" ({length_km:,.2f} km)"

                return (
                    MeasurementDetail(
                        supported=True,
                        type="length",
                        value=length_m,
                        unit="meters",
                        display=display_str,
                        status="CALCULATED",
                        message=None,
                    ),
                    projected_crs,
                )
            except Exception as e:
                logger.error("Failed calculating length for %s: %s", geom_type, e, exc_info=True)
                return (
                    MeasurementDetail(
                        supported=True,
                        type="length",
                        value=None,
                        unit=None,
                        display=None,
                        status="ERROR",
                        message=f"Measurement calculation failed: {str(e)}",
                    ),
                    None,
                )

        # 4. Graceful handling of unsupported geometry types (e.g. GeometryCollection)
        return (
            MeasurementDetail(
                supported=False,
                type=None,
                value=None,
                unit=None,
                display=None,
                status="UNSUPPORTED",
                message=f"Geometry type '{geom_type}' is not supported for standard measurement calculation.",
            ),
            None,
        )

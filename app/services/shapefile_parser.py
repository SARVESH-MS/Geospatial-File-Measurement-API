"""Shapefile parser supporting .zip extraction, Zip-Slip defense, PRJ parsing, and geometry extraction."""

import logging
from pathlib import Path
import shutil
import tempfile
import zipfile
from typing import Any
import shapefile
import shapely
import shapely.geometry

from app.core.exceptions import CorruptedFileError, SecurityViolationError
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class ShapefileParser:
    """Parses zipped ESRI Shapefiles into structured geospatial features."""

    @classmethod
    def parse_zip(cls, zip_file_path: Path) -> tuple[str, list[dict[str, Any]]]:
        """
        Extracts and parses a Shapefile from a zip archive.
        Returns:
            tuple[str, list[dict[str, Any]]]: (detected_crs, list of feature dictionaries)
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
        try:
            cls._safe_extract_zip(zip_file_path, temp_dir)
            shp_path = cls._find_shp_file(temp_dir)
            prj_path = shp_path.with_suffix(".prj")

            # Extract CRS from .prj if available
            crs_str = CRSService.DEFAULT_GEOGRAPHIC_CRS
            if prj_path.exists():
                try:
                    prj_text = prj_path.read_text(encoding="utf-8", errors="ignore")
                    crs_str = CRSService.parse_crs(prj_text)
                except Exception as e:
                    logger.warning("Failed parsing .prj file: %s. Defaulting to %s", e, crs_str)

            features = cls._read_shapefile(shp_path, crs_str)
            return crs_str, features

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    def _safe_extract_zip(cls, zip_path: Path, dest_dir: Path) -> None:
        """Extract zip archive with strict Zip-Slip protection."""
        if not zipfile.is_zipfile(zip_path):
            raise CorruptedFileError("Uploaded file is not a valid or readable ZIP archive.")

        with zipfile.ZipFile(zip_path, "r") as archive:
            dest_dir_resolved = dest_dir.resolve()
            for member in archive.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise SecurityViolationError(f"Potential directory traversal detected in path: {member.filename}")

                target_path = (dest_dir / member_path).resolve()
                if not target_path.is_relative_to(dest_dir_resolved):
                    raise SecurityViolationError(f"Zip extraction path points outside destination: {member.filename}")

            archive.extractall(dest_dir)

    @classmethod
    def _find_shp_file(cls, extract_dir: Path) -> Path:
        """Locates the primary .shp file in the extracted directory tree."""
        shp_candidates = list(extract_dir.rglob("*.shp"))
        if not shp_candidates:
            # Check case-insensitive
            shp_candidates = [p for p in extract_dir.rglob("*") if p.suffix.lower() == ".shp"]

        if not shp_candidates:
            raise CorruptedFileError(
                "No .shp file found within the uploaded zip archive. "
                "Ensure the zip contains .shp, .shx, and .dbf files."
            )

        # Prefer non-hidden, non-macOS __MACOSX files
        valid_candidates = [p for p in shp_candidates if "__MACOSX" not in p.parts and not p.name.startswith(".")]
        if not valid_candidates:
            valid_candidates = shp_candidates

        return valid_candidates[0]

    @classmethod
    def _read_shapefile(cls, shp_path: Path, crs_str: str) -> list[dict[str, Any]]:
        """Reads geometry and attribute records from an ESRI Shapefile using PyShp and Shapely."""
        features: list[dict[str, Any]] = []

        try:
            with shapefile.Reader(str(shp_path), encoding="utf-8", encodingErrors="replace") as sf:
                fields = [f[0] for f in sf.fields[1:]]  # Exclude deletion flag

                for index, shape_record in enumerate(sf.shapeRecords()):
                    # Extract attributes
                    record_dict = dict(zip(fields, shape_record.record))

                    # Extract geometry
                    shape_geo = shape_record.shape.__geo_interface__
                    if not shape_geo or not shape_geo.get("coordinates"):
                        continue

                    geom = shapely.geometry.shape(shape_geo)
                    if geom.is_empty:
                        continue

                    # Ensure valid geometry if possible
                    if not geom.is_valid:
                        geom = shapely.make_valid(geom)

                    features.append({
                        "feature_index": index,
                        "geometry_type": geom.geom_type,
                        "geometry": shapely.geometry.mapping(geom),
                        "shapely_geom": geom,
                        "crs": crs_str,
                        "properties": record_dict,
                    })

        except Exception as e:
            if isinstance(e, CorruptedFileError):
                raise
            logger.error("Error reading Shapefile: %s", e, exc_info=True)
            raise CorruptedFileError(f"Failed to read Shapefile contents: {str(e)}") from e

        return features

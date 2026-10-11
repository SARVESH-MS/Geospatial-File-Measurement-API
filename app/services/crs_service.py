"""Coordinate Reference System (CRS) inspection, selection, and transformation service."""

import math
from functools import lru_cache
import logging
from typing import Any
import numpy as np
import pyproj
import shapely

logger = logging.getLogger(__name__)


class CRSService:
    """Provides CRS analysis, dynamic projected CRS selection, and geometry transformation."""

    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    @lru_cache(maxsize=128)
    def get_transformer(cls, source_crs: str, target_crs: str) -> pyproj.Transformer:
        """Fetch or create a cached pyproj Transformer between two coordinate reference systems."""
        return pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

    @classmethod
    def parse_crs(cls, crs_input: str | None) -> str:
        """
        Normalize and validate a CRS string or WKT.
        Returns a canonical EPSG code string (e.g. 'EPSG:4326') or canonical WKT/PROJ string.
        Falls back to EPSG:4326 if unrecognized or missing.
        """
        if not crs_input or not crs_input.strip():
            return cls.DEFAULT_GEOGRAPHIC_CRS

        crs_clean = crs_input.strip()

        try:
            parsed = pyproj.CRS.from_user_input(crs_clean)
            epsg_code = parsed.to_epsg()
            if epsg_code:
                return f"EPSG:{epsg_code}"
            # If no EPSG code exists, return authoritative representation
            return parsed.to_string()
        except Exception as e:
            logger.warning("Could not parse CRS '%s': %s. Falling back to %s", crs_input, e, cls.DEFAULT_GEOGRAPHIC_CRS)
            return cls.DEFAULT_GEOGRAPHIC_CRS

    @classmethod
    def is_geographic(cls, crs_str: str) -> bool:
        """Check whether a given CRS is geographic (uses angular coordinates like degrees)."""
        try:
            crs = pyproj.CRS.from_user_input(crs_str)
            return crs.is_geographic
        except Exception:
            # Conservative assumption: treat unparseable as geographic to prevent degree calculations
            return True

    @classmethod
    def determine_optimal_projected_crs(cls, geometry: shapely.Geometry, source_crs: str) -> str:
        """
        Determine the optimal projected coordinate reference system (in metric units)
        for a geometry to calculate accurate areas and distances.

        Strategy:
        1. If the input CRS is already a non-distorting projected metric system (e.g. local UTM or State Plane),
           retain it. If it is Web Mercator (EPSG:3857), reproject to local UTM to eliminate high-latitude area distortion.
        2. If the input CRS is geographic (e.g. EPSG:4326 degrees):
           - Inspect the geometry centroid (or envelope centroid) in WGS 84.
           - Calculate the appropriate Universal Transverse Mercator (UTM) zone:
             Zone = floor((longitude + 180) / 6) + 1
             Hemisphere: Northern (EPSG:326XX) or Southern (EPSG:327XX).
           - For polar latitudes (> 84°N or < -80°S), use Universal Polar Stereographic (UPS: EPSG:32661 / EPSG:32761).
        """
        try:
            crs_obj = pyproj.CRS.from_user_input(source_crs)
            # If already projected in meters and not Web Mercator (which distorts areas severely away from equator)
            epsg = crs_obj.to_epsg()
            if crs_obj.is_projected and epsg != 3857:
                axis_unit = crs_obj.axis_info[0].unit_name.lower() if crs_obj.axis_info else "metre"
                if "metre" in axis_unit or "meter" in axis_unit:
                    return f"EPSG:{epsg}" if epsg else source_crs
        except Exception as e:
            logger.debug("CRS inspection error: %s", e)

        # Reproject centroid to WGS84 if needed
        lon, lat = cls._extract_wgs84_centroid(geometry, source_crs)

        # Clamp latitude and normalize longitude
        lon = ((lon + 180) % 360) - 180
        lat = max(-90.0, min(90.0, lat))

        # Handle Polar regions
        if lat > 84.0:
            return "EPSG:32661"  # WGS 84 / UPS North
        if lat < -80.0:
            return "EPSG:32761"  # WGS 84 / UPS South

        # Standard UTM calculation
        zone = int(math.floor((lon + 180) / 6)) + 1
        zone = max(1, min(60, zone))

        if lat >= 0:
            return f"EPSG:{32600 + zone}"
        return f"EPSG:{32700 + zone}"

    @classmethod
    def _extract_wgs84_centroid(cls, geometry: shapely.Geometry, source_crs: str) -> tuple[float, float]:
        """Extract WGS 84 (longitude, latitude) coordinates of the geometry centroid."""
        centroid = geometry.centroid
        if centroid.is_empty:
            return 0.0, 0.0

        if source_crs == cls.DEFAULT_GEOGRAPHIC_CRS:
            return float(centroid.x), float(centroid.y)

        try:
            transformer = cls.get_transformer(source_crs, cls.DEFAULT_GEOGRAPHIC_CRS)
            x_wgs, y_wgs = transformer.transform(centroid.x, centroid.y)
            return float(x_wgs), float(y_wgs)
        except Exception:
            return float(centroid.x), float(centroid.y)

    @classmethod
    def transform_to_crs(
        cls, geometry: shapely.Geometry, source_crs: str, target_crs: str
    ) -> shapely.Geometry:
        """
        Transform a Shapely geometry from source_crs to target_crs.
        Utilizes vectorized coordinates mapping and safely handles 2D and 3D geometries.
        """
        if source_crs == target_crs or geometry.is_empty:
            return geometry

        transformer = cls.get_transformer(source_crs, target_crs)

        def _vectorized_transform(coords: np.ndarray) -> np.ndarray:
            x, y = transformer.transform(coords[:, 0], coords[:, 1])
            return np.column_stack((x, y))

        return shapely.transform(geometry, _vectorized_transform, include_z=False)

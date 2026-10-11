"""Measurement calculation service for geospatial geometries with UTM and Geodesic support."""

import logging
from typing import Any
import pyproj
import shapely

from app.schemas.file_schemas import MeasurementDetail
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)

# WGS84 Geodetic calculator for ellipsoidal reference cross-validation
wgs84_geod = pyproj.Geod(ellps="WGS84")


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
                    area=None,
                    length=None,
                    geodesic_value=None,
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
                    area=None,
                    length=None,
                    geodesic_value=None,
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

                # Optional Geodesic calculation on WGS84 geometry
                geodesic_area: float | None = None
                try:
                    wgs_geom = (
                        CRSService.transform_to_crs(geometry, source_crs, "EPSG:4326")
                        if source_crs != "EPSG:4326"
                        else geometry
                    )
                    g_area, _ = wgs84_geod.geometry_area_perimeter(wgs_geom)
                    geodesic_area = round(abs(float(g_area)), 4)
                except Exception as e:
                    logger.debug("Geodesic area calculation skipped: %s", e)

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
                        area=area_sq_m,
                        length=None,
                        geodesic_value=geodesic_area,
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
                        area=None,
                        length=None,
                        geodesic_value=None,
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

                # Optional Geodesic calculation on WGS84 geometry
                geodesic_len: float | None = None
                try:
                    wgs_geom = (
                        CRSService.transform_to_crs(geometry, source_crs, "EPSG:4326")
                        if source_crs != "EPSG:4326"
                        else geometry
                    )
                    geodesic_len = round(float(wgs84_geod.geometry_length(wgs_geom)), 4)
                except Exception as e:
                    logger.debug("Geodesic length calculation skipped: %s", e)

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
                        area=None,
                        length=length_m,
                        geodesic_value=geodesic_len,
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
                        area=None,
                        length=None,
                        geodesic_value=None,
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
                area=None,
                length=None,
                geodesic_value=None,
                status="UNSUPPORTED",
                message=f"Geometry type '{geom_type}' is not supported for standard measurement calculation.",
            ),
            None,
        )

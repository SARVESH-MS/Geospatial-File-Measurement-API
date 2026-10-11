"""Pydantic schemas for request validation and response serialization."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class FileInfoResponse(BaseModel):
    """File metadata response matching exact problem specification."""

    id: str = Field(..., description="Unique identifier for uploaded file")
    filename: str = Field(..., description="Original filename")
    feature_count: int = Field(..., description="Number of extracted geospatial features")
    crs: str = Field(..., description="Coordinate Reference System of the file")
    status: str = Field(..., description="Current processing status (e.g. COMPLETED, FAILED)")

    class Config:
        from_attributes = True


class FileDetailResponse(FileInfoResponse):
    """Extended file information including timestamps and file size."""

    file_size_bytes: int = Field(0, description="Size in bytes")
    created_at: datetime | None = None
    error_message: str | None = None


class MeasurementDetail(BaseModel):
    """Measurement calculation results for an individual feature."""

    supported: bool = Field(..., description="Whether measurement calculation is supported for this geometry")
    type: str | None = Field(None, description="Measurement type: 'area', 'length', or None")
    value: float | None = Field(None, description="Calculated metric value in SI units (m² or m)")
    unit: str | None = Field(None, description="Measurement unit (e.g. 'square_meters', 'meters')")
    display: str | None = Field(None, description="Human-readable formatted measurement with secondary units")
    area: float | None = Field(None, description="Explicit area value in m² (populated for Polygons)")
    length: float | None = Field(None, description="Explicit length value in meters (populated for LineStrings)")
    geodesic_value: float | None = Field(None, description="Accurate WGS84 ellipsoidal geodesic measurement")
    status: str = Field(..., description="Calculation status: CALCULATED, NOT_APPLICABLE, UNSUPPORTED, or ERROR")
    message: str | None = Field(None, description="Additional context or reason if not calculated")


class FeatureMeasurementItem(BaseModel):
    """Feature details with geometry, properties, and measurement."""

    feature_index: int = Field(..., description="0-based index of feature in dataset")
    feature_id: int | str = Field(..., description="Feature ID or index identifier")
    id: int | str = Field(..., description="Direct alias for feature ID")
    geometry_type: str = Field(..., description="Geometry type (e.g. Polygon, LineString, Point)")
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry representation")
    crs: str = Field(..., description="Original CRS of the geometry")
    projected_crs: str | None = Field(None, description="Projected metric CRS utilized for measurement")
    properties: dict[str, Any] = Field(default_factory=dict, description="Feature attributes")
    measurement: MeasurementDetail = Field(..., description="Measurement result")


class MeasurementSummary(BaseModel):
    """Aggregated measurements across the entire geospatial dataset."""

    total_features: int = 0
    polygon_count: int = 0
    linestring_count: int = 0
    point_count: int = 0
    unsupported_count: int = 0
    total_area_sq_meters: float = 0.0
    total_length_meters: float = 0.0
    total_area: float = 0.0
    total_length: float = 0.0
    total_area_hectares: float = 0.0
    total_length_km: float = 0.0


class FileMeasurementsResponse(BaseModel):
    """Full measurements response for all features in a file."""

    id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    crs: str = Field(..., description="Source CRS")
    status: str = Field(..., description="Processing status")
    summary: MeasurementSummary = Field(..., description="Aggregate summary of measurements")
    features: list[FeatureMeasurementItem] = Field(..., description="List of feature measurement items")

"""Database models for uploaded geospatial files and extracted features."""

from datetime import datetime, timezone
from typing import Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UploadedFile(Base):
    """Represents an uploaded geospatial archive or file."""

    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # shapefile or kml
    file_size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    feature_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    crs: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="EPSG:4326")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    features: Mapped[list["FeatureRecord"]] = relationship(
        "FeatureRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureRecord.feature_index",
    )


class FeatureRecord(Base):
    """Represents an individual feature extracted from a geospatial file."""

    __tablename__ = "feature_records"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True
    )
    feature_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    geometry_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    geometry_geojson: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, default=dict)
    crs: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    # Measurement details
    is_supported: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    projected_crs: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    measurement_type: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)  # area, length, or None
    measurement_value: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    measurement_unit: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    measurement_details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)

    file: Mapped["UploadedFile"] = relationship("UploadedFile", back_populates="features")

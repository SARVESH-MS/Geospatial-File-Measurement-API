"""API routes for geospatial file upload, status inspection, and measurements."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.file_schemas import (
    FileInfoResponse,
    FileMeasurementsResponse,
)
from app.services.file_service import FileProcessingService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process geospatial file",
    description="Upload either a zipped ESRI Shapefile (.zip) or a Keyhole Markup Language (.kml) file for feature extraction and measurement calculation.",
)
async def upload_geospatial_file(
    file: UploadFile = File(..., description="Zipped Shapefile (.zip) or KML (.kml)"),
    db: Session = Depends(get_db),
) -> FileInfoResponse:
    """Uploads, validates, parses, projects, and calculates measurements for a geospatial file."""
    file_id, saved_path, file_type, size_bytes = await StorageService.save_upload(file)

    response = FileProcessingService.process_and_persist(
        file_id=file_id,
        file_path=saved_path,
        original_filename=file.filename or "unknown",
        file_type=file_type,
        file_size_bytes=size_bytes,
        db=db,
    )
    return response


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get file processing status and metadata",
    description="Returns metadata, extracted feature count, detected CRS, and status for an uploaded file.",
)
@router.get(
    "/{id}",
    response_model=FileInfoResponse,
    include_in_schema=False,
)
def get_file_information(
    id: str,
    db: Session = Depends(get_db),
) -> FileInfoResponse:
    """Returns information about the uploaded file by ID."""
    return FileProcessingService.get_file_info(file_id=id, db=db)


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get feature measurements",
    description="Returns calculated measurements (area for Polygons, length for LineStrings) with geometry and attribute details.",
)
@router.get(
    "/{id}/measurements",
    response_model=FileMeasurementsResponse,
    include_in_schema=False,
)
def get_file_measurements(
    id: str,
    db: Session = Depends(get_db),
) -> FileMeasurementsResponse:
    """Returns measurements for the features in the uploaded file."""
    return FileProcessingService.get_file_measurements(file_id=id, db=db)

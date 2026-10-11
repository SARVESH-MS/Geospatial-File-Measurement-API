"""Custom exceptions and centralized error handling for the Geospatial API."""

from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class GeospatialAPIException(Exception):
    """Base application exception for domain errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
        details: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class FileNotFoundError(GeospatialAPIException):
    """Raised when an uploaded file record cannot be located."""

    def __init__(self, file_id: str):
        super().__init__(
            message=f"File with ID '{file_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="FILE_NOT_FOUND",
        )


class UnsupportedFileFormatError(GeospatialAPIException):
    """Raised when an uploaded file extension is not supported."""

    def __init__(self, filename: str, supported: list[str]):
        super().__init__(
            message=f"Unsupported file format for '{filename}'. Allowed formats: {', '.join(supported)}",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="UNSUPPORTED_FORMAT",
        )


class FileSizeLimitExceededError(GeospatialAPIException):
    """Raised when an uploaded file exceeds the configured size limit."""

    def __init__(self, max_mb: int):
        super().__init__(
            message=f"File exceeds maximum allowed upload size of {max_mb} MB.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="FILE_TOO_LARGE",
        )


# Support both Starlette versions cleanly
STATUS_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY)


class CorruptedFileError(GeospatialAPIException):
    """Raised when an uploaded archive or document is corrupted or malformed."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=STATUS_UNPROCESSABLE,
            code="CORRUPTED_FILE",
        )


class SecurityViolationError(GeospatialAPIException):
    """Raised when an archive contains suspicious paths (e.g. Zip Slip)."""

    def __init__(self, message: str = "Security violation detected in uploaded archive."):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SECURITY_VIOLATION",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with FastAPI application."""

    @app.exception_handler(GeospatialAPIException)
    async def handle_geospatial_api_exception(
        request: Request, exc: GeospatialAPIException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

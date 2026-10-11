"""Secure file storage service managing uploads and file system validations."""

from pathlib import Path
import secrets
import shutil
from fastapi import UploadFile

from app.config import settings
from app.core.exceptions import (
    FileSizeLimitExceededError,
    UnsupportedFileFormatError,
)


class StorageService:
    """Manages file storage, unique ID generation, and validation."""

    @classmethod
    def generate_file_id(cls) -> str:
        """Generate a clean, collision-resistant identifier (e.g. 'abc123def456')."""
        return secrets.token_hex(4)

    @classmethod
    async def save_upload(cls, upload_file: UploadFile) -> tuple[str, Path, str, int]:
        """
        Validates and saves an uploaded file stream to the storage directory.
        Returns:
            tuple[str, Path, str, int]: (file_id, saved_path, file_type, size_in_bytes)
        """
        filename = upload_file.filename or "uploaded_file"
        suffix = Path(filename).suffix.lower()

        if suffix not in settings.ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatError(filename, list(settings.ALLOWED_EXTENSIONS))

        file_id = cls.generate_file_id()
        file_type = "shapefile" if suffix == ".zip" else "kml"
        destination_path = settings.UPLOAD_DIR / f"{file_id}_{Path(filename).name}"

        # Stream file to disk and enforce size limit
        total_bytes = 0
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        try:
            with open(destination_path, "wb") as buffer:
                while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise FileSizeLimitExceededError(settings.MAX_UPLOAD_SIZE_MB)
                    buffer.write(chunk)
        except Exception:
            if destination_path.exists():
                destination_path.unlink()
            raise

        return file_id, destination_path, file_type, total_bytes

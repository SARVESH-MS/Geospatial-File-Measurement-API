from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime settings and environment configurations."""

    APP_NAME: str = "Geospatial File Measurement API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/geospatial_api.db"

    # Upload Constraints
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set[str] = {".zip", ".kml"}

    # Default fallback CRS if unprojected and unidentified
    DEFAULT_GEOGRAPHIC_CRS: str = "EPSG:4326"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

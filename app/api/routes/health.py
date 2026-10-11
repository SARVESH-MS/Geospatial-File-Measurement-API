"""Health and readiness check endpoints."""

from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Service health status")
def health_check() -> dict[str, str]:
    """Basic health check probe returning application status and version."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

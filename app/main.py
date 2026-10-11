"""Main FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import files_router, health_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager initializing database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade RESTful API for accepting geospatial files (Shapefile .zip and KML .kml), "
        "extracting geospatial features, intelligently handling CRS re-projections (e.g. EPSG:4326 to UTM), "
        "and calculating accurate metric measurements (Area for Polygons, Length for LineStrings)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(files_router)
app.include_router(health_router)


@app.get("/", tags=["Root"])
def root_status() -> dict[str, str]:
    """Root endpoint providing service overview and documentation links."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_check": "/health",
        "upload_endpoint": "POST /api/files/",
    }

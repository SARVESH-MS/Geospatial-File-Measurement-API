"""Pytest fixtures and test environment configuration."""

from collections.abc import Generator
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

TEST_DB_FILE = settings.BASE_DIR / "test_geospatial.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test tables and clean up database file on teardown."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if TEST_DB_FILE.exists():
        try:
            TEST_DB_FILE.unlink()
        except Exception:
            pass


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh SQLAlchemy session for testing."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database session dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_kml_path() -> Path:
    """Path to sample KML dataset."""
    return settings.BASE_DIR / "sample_data" / "sample_kml.kml"


@pytest.fixture
def sample_shapefile_path() -> Path:
    """Path to sample Shapefile zip dataset."""
    return settings.BASE_DIR / "sample_data" / "sample_shapefile.zip"

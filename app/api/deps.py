"""FastAPI dependency injection utilities."""

from collections.abc import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

DBSessionDep = Depends(get_db)

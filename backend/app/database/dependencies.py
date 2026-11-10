"""
FastAPI dependencies for database session lifecycle management.
"""
from typing import Generator
from sqlalchemy.orm import Session
from app.database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Yields an isolated database session per request,
    ensuring cleanup and rollback on exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

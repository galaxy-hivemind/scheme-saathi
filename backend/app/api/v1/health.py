"""
Health check endpoint.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """
    Returns service health and basic metadata.
    Used by the frontend to verify the backend is reachable.
    """
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "error": None,
        "request_id": str(uuid.uuid4()),
    }

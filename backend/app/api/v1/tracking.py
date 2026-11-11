"""
API router for application tracking, status updates, and timeline audit trail.
"""
import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.tracking import (
    StatusTransitionCreate,
    ApplicationTimelineResponse,
)
from app.services import tracking_service

router = APIRouter()


@router.get(
    "/{application_id}/timeline",
    response_model=ApplicationTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get application timeline",
    description="Retrieve the chronological status transition history and audit trail for an application.",
)
def get_timeline(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationTimelineResponse:
    """Get full status timeline for an application with strict tenant isolation."""
    return tracking_service.get_status_timeline(
        db=db,
        current_user=current_user,
        application_id=application_id,
    )


@router.post(
    "/{application_id}/status",
    response_model=ApplicationTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Record status transition",
    description="Transition an application status, record an immutable audit log, and notify the citizen.",
)
def update_status(
    application_id: uuid.UUID,
    transition: StatusTransitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationTimelineResponse:
    """Record status transition and trigger citizen notification."""
    return tracking_service.record_status_transition(
        db=db,
        current_user=current_user,
        application_id=application_id,
        transition=transition,
    )


@router.post(
    "/{application_id}/sync",
    response_model=ApplicationTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize external portal status",
    description="Query official government tracking portal and update status timeline if changed.",
)
def sync_portal_status(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationTimelineResponse:
    """Sync external portal status using government reference number."""
    return tracking_service.check_external_status_sync(
        db=db,
        current_user=current_user,
        application_id=application_id,
    )

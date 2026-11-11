"""
API router for citizen notifications, action alerts, and unread badge counters.
"""
from typing import Optional, Dict
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter()


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List citizen notifications",
    description="Retrieve paginated list of notifications and alerts for current citizen.",
)
def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read/unread status"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    """List citizen notifications."""
    return notification_service.list_notifications(
        db=db,
        current_user=current_user,
        is_read=is_read,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unread notifications count",
    description="Retrieve the total count of unread notifications for badge counter.",
)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    """Get unread notification count for notification bell badge."""
    count = notification_service.get_unread_count(db=db, current_user=current_user)
    return UnreadCountResponse(unread_count=count)


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Mark a specific citizen notification as read.",
)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationResponse:
    """Mark single notification as read with tenant isolation."""
    return notification_service.mark_as_read(
        db=db,
        current_user=current_user,
        notification_id=notification_id,
    )


@router.put(
    "/read-all",
    response_model=Dict[str, int],
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark all unread notifications for current citizen as read.",
)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, int]:
    """Mark all unread notifications as read."""
    count = notification_service.mark_all_as_read(db=db, current_user=current_user)
    return {"updated_count": count}

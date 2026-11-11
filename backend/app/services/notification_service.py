"""
Notification service managing citizen alerts, in-app badges, action reminders, and multi-channel delivery.
"""
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy import select, and_, func, update
from sqlalchemy.orm import Session

from app.models.notification import Notification, VALID_NOTIFICATION_TYPES, VALID_PRIORITIES
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationListResponse, UnreadCountResponse
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: str = "status_update",
    priority: str = "NORMAL",
    application_id: Optional[uuid.UUID] = None,
    channels: Optional[List[str]] = None,
    commit: bool = True,
) -> Notification:
    """
    Create and dispatch a notification to a citizen.
    If external channels (SMS, WhatsApp) are requested, dispatches to delivery provider hooks.
    """
    if notification_type not in VALID_NOTIFICATION_TYPES:
        raise ValidationError(f"Invalid notification_type '{notification_type}'. Must be one of {VALID_NOTIFICATION_TYPES}.")
    if priority not in VALID_PRIORITIES:
        raise ValidationError(f"Invalid priority '{priority}'. Must be one of {VALID_PRIORITIES}.")

    active_channels = channels or ["in_app"]

    notification = Notification(
        user_id=user_id,
        application_id=application_id,
        title=title.strip(),
        message=message.strip(),
        notification_type=notification_type,
        priority=priority,
        channels=active_channels,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)

    if commit:
        db.commit()
        db.refresh(notification)

    # Multi-channel delivery hooks (SMS, WhatsApp)
    for channel in active_channels:
        if channel == "sms":
            _dispatch_sms_hook(user_id, title, message)
        elif channel == "whatsapp":
            _dispatch_whatsapp_hook(user_id, title, message)

    return notification


def _dispatch_sms_hook(user_id: uuid.UUID, title: str, message: str) -> None:
    """Pluggable delivery hook for SMS channel."""
    logger.info("Dispatched SMS alert to citizen %s: [%s] %s", user_id, title, message)


def _dispatch_whatsapp_hook(user_id: uuid.UUID, title: str, message: str) -> None:
    """Pluggable delivery hook for WhatsApp channel."""
    logger.info("Dispatched WhatsApp alert to citizen %s: [%s] %s", user_id, title, message)


def list_notifications(
    db: Session,
    current_user: User,
    is_read: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    """List citizen notifications with filtering, pagination, and unread count."""
    base_conditions = [Notification.user_id == current_user.id]

    if is_read is not None:
        base_conditions.append(Notification.is_read == is_read)
    if notification_type is not None:
        base_conditions.append(Notification.notification_type == notification_type.strip())

    total = db.scalar(
        select(func.count(Notification.id)).where(and_(*base_conditions))
    ) or 0

    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            and_(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        )
    ) or 0

    stmt = (
        select(Notification)
        .where(and_(*base_conditions))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    records = list(db.execute(stmt).scalars().all())

    items = [
        NotificationResponse.model_validate(r)
        for r in records
    ]
    return NotificationListResponse(items=items, total=total, unread_count=unread_count)


def get_unread_count(db: Session, current_user: User) -> int:
    """Get the total count of unread notifications for citizen."""
    count = db.scalar(
        select(func.count(Notification.id)).where(
            and_(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        )
    ) or 0
    return count


def mark_as_read(
    db: Session,
    current_user: User,
    notification_id: uuid.UUID,
) -> NotificationResponse:
    """Mark a specific notification as read, enforcing strict ownership."""
    notification = db.scalar(
        select(Notification).where(Notification.id == notification_id)
    )
    if not notification:
        raise NotFoundError("Notification not found.")

    if notification.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this notification.")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)

    return NotificationResponse.model_validate(notification)


def mark_all_as_read(db: Session, current_user: User) -> int:
    """Mark all unread notifications for current citizen as read."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(and_(Notification.user_id == current_user.id, Notification.is_read.is_(False)))
        .values(is_read=True, read_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0

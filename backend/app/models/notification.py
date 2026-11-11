"""
Notification model for citizen alerts, status updates, action requirements, and delivery channels.
"""
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.application_draft import ApplicationDraft

VALID_NOTIFICATION_TYPES = (
    "status_update",
    "document_expiry",
    "action_required",
    "system",
)

VALID_PRIORITIES = (
    "LOW",
    "NORMAL",
    "HIGH",
    "URGENT",
)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Target citizen account ID",
    )
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional linked application draft ID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Notification title or headline",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full notification body text",
    )
    notification_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="status_update",
        doc="status_update, document_expiry, action_required, system",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="NORMAL",
        doc="LOW, NORMAL, HIGH, URGENT",
    )
    channels: Mapped[List[str]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=lambda: ["in_app"],
        nullable=False,
        doc="Active delivery channels: in_app, sms, whatsapp",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether notification has been read by citizen",
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when citizen marked notification as read",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Creation timestamp",
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="notifications",
    )
    application: Mapped[Optional["ApplicationDraft"]] = orm_relationship(
        "ApplicationDraft",
        back_populates="notifications",
    )

    __table_args__ = (
        CheckConstraint(
            f"notification_type IN {VALID_NOTIFICATION_TYPES}",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            f"priority IN {VALID_PRIORITIES}",
            name="ck_notifications_priority",
        ),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

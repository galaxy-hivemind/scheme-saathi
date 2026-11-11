"""
Application Status History model representing immutable status transition events
and external portal synchronization audit trail for scheme application packages.
"""
from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.application_draft import ApplicationDraft

VALID_APPLICATION_STATUSES = (
    "DRAFT",
    "READY",
    "SUBMITTED",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "DISBURSED",
    "ARCHIVED",
)

VALID_STATUS_SOURCES = (
    "user_reported",
    "official_integration",
    "portal_sync",
    "admin_action",
)


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Target application draft ID",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Lifecycle status: DRAFT, READY, SUBMITTED, IN_REVIEW, APPROVED, REJECTED, DISBURSED, ARCHIVED",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="user_reported",
        doc="Status origin: user_reported, official_integration, portal_sync, admin_action",
    )
    source_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Government portal reference or tracking ID",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed remarks, rejection reason, or progress notes",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when status transition occurred",
    )

    # Relationships
    application: Mapped["ApplicationDraft"] = orm_relationship(
        "ApplicationDraft",
        back_populates="status_history",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {VALID_APPLICATION_STATUSES}",
            name="ck_status_history_status",
        ),
        CheckConstraint(
            f"source_type IN {VALID_STATUS_SOURCES}",
            name="ck_status_history_source",
        ),
        Index("ix_app_status_history_app_created", "application_id", "created_at"),
    )

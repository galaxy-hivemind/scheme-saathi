"""
ApplicationRecord ORM model for normalized Step 5 PostgreSQL persistence.
Strictly enforces citizen isolation (citizen_id / user_id) and separation between
internal application_id and official_reference_number.
"""
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ApplicationRecord(Base, TimestampMixin):
    __tablename__ = "application_records"
    __table_args__ = (
        UniqueConstraint("citizen_id", "application_id", name="uq_application_records_citizen_app"),
        Index("ix_application_records_citizen_status", "citizen_id", "application_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    application_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )
    citizen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheme_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scheme_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    scheme_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    official_reference_number: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    reference_source: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    submission_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    portal_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="https://www.india.gov.in/",
    )
    tracking_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    application_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="draft",
    )
    submission_method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="portal_assisted",
    )
    confirmation_version: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    confirmation_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    form_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
    )
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
    )

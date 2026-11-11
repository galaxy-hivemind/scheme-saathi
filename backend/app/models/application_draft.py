"""
Application Draft model for staging scheme application preparation packages,
prefilled demographic snapshots, attached documents, and government portal handoff instructions.
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime
import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.beneficiary_profile import BeneficiaryProfile
    from app.models.scheme import Scheme
    from app.models.application_status_history import ApplicationStatusHistory
    from app.models.notification import Notification


class ApplicationDraft(Base, TimestampMixin):
    __tablename__ = "application_drafts"

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
        doc="Owning account holder ID",
    )
    beneficiary_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beneficiary_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Target family beneficiary ID (null means account holder self)",
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Target welfare scheme ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        doc="Draft lifecycle status: DRAFT, READY, SUBMITTED, ARCHIVED",
    )
    prefilled_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
        doc="Demographic attributes and answers prefilled for scheme application",
    )
    attached_documents: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=list,
        nullable=False,
        doc="Array of linked citizen document metadata objects",
    )
    official_portal_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="External official government application or scheme portal URL",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Citizen notes or submission instructions",
    )
    external_reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Official acknowledgement or application reference number received post-submission",
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when citizen marked external submission complete",
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="application_drafts",
    )
    beneficiary: Mapped[Optional["BeneficiaryProfile"]] = orm_relationship(
        "BeneficiaryProfile",
        back_populates="application_drafts",
    )
    scheme: Mapped["Scheme"] = orm_relationship(
        "Scheme",
    )
    status_history: Mapped[List["ApplicationStatusHistory"]] = orm_relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStatusHistory.created_at.asc()",
    )
    notifications: Mapped[List["Notification"]] = orm_relationship(
        "Notification",
        back_populates="application",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'READY', 'SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED', 'ARCHIVED')",
            name="ck_application_drafts_status",
        ),
        Index(
            "ix_application_drafts_user_scheme_status",
            "user_id",
            "scheme_id",
            "status",
        ),
    )

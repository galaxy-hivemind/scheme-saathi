"""
User model representing system users / authentication accounts.
"""
from typing import TYPE_CHECKING, Optional, List
import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user_profile import UserProfile
    from app.models.user_consent import UserConsent
    from app.models.beneficiary_profile import BeneficiaryProfile
    from app.models.chat import ChatConversation, PendingAction
    from app.models.citizen_document import CitizenDocument
    from app.models.application_draft import ApplicationDraft


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    auth_provider_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        doc="Optional Supabase Auth UID or external auth provider identifier",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # Consents are retained for audit trail; deleting a user must not cascade delete consents
    consents: Mapped[List["UserConsent"]] = relationship(
        "UserConsent",
        back_populates="user",
        passive_deletes=True,
    )
    beneficiaries: Mapped[List["BeneficiaryProfile"]] = relationship(
        "BeneficiaryProfile",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[List["ChatConversation"]] = relationship(
        "ChatConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    pending_actions: Mapped[List["PendingAction"]] = relationship(
        "PendingAction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["CitizenDocument"]] = relationship(
        "CitizenDocument",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    application_drafts: Mapped[List["ApplicationDraft"]] = relationship(
        "ApplicationDraft",
        back_populates="user",
        cascade="all, delete-orphan",
    )

"""
Citizen Document model for storing uploaded document metadata, file paths, and verification states.
Supports both account holder documents and family beneficiary documents.
"""
from typing import TYPE_CHECKING, Optional, Dict, Any
import uuid
from sqlalchemy import String, Integer, Text, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.beneficiary_profile import BeneficiaryProfile


class CitizenDocument(Base, TimestampMixin):
    __tablename__ = "citizen_documents"

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
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Canonical type: aadhaar, pan, income_certificate, etc.",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Sanitized original client file name",
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Relative path or storage key",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="File size in bytes (max 10MB)",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Validated MIME type (application/pdf, image/jpeg, image/png)",
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Cryptographic SHA-256 hex digest for integrity and deduplication",
    )
    extracted_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
        doc="Extracted OCR or metadata attributes",
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        doc="Verification status: PENDING, VERIFIED, REJECTED, EXPIRED",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Reason if rejected",
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="documents",
    )
    beneficiary: Mapped[Optional["BeneficiaryProfile"]] = orm_relationship(
        "BeneficiaryProfile",
        back_populates="documents",
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(trim(document_type)) > 0",
            name="ck_citizen_documents_type_nonempty",
        ),
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="ck_citizen_documents_file_size",
        ),
        CheckConstraint(
            "mime_type IN ('application/pdf', 'image/jpeg', 'image/png')",
            name="ck_citizen_documents_mime",
        ),
        CheckConstraint(
            "verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')",
            name="ck_citizen_documents_status",
        ),
        Index("ix_citizen_documents_user_type", "user_id", "document_type"),
        Index("ix_citizen_documents_checksum", "user_id", "checksum_sha256"),
    )

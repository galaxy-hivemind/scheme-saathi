"""
SQLAlchemy model representing Scheme Document Requirements.
"""
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime
import uuid
from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.scheme import Scheme


class SchemeDocument(Base, TimestampMixin):
    __tablename__ = "scheme_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    alternatives: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    issuing_authority: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    guidance: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    scheme: Mapped["Scheme"] = relationship(
        "Scheme",
        back_populates="documents",
    )

    __table_args__ = (
        UniqueConstraint("scheme_id", "document_type", name="uq_scheme_documents_scheme_doc_type"),
        CheckConstraint("char_length(trim(document_type)) > 0", name="ck_scheme_documents_type_nonempty"),
    )


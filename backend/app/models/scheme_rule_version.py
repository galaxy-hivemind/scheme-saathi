"""
SQLAlchemy model representing Versioned Scheme Eligibility Rules.
"""
from typing import TYPE_CHECKING, Optional
from datetime import date
import uuid
from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    Date,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.scheme import Scheme


class SchemeRuleVersion(Base, TimestampMixin):
    __tablename__ = "scheme_rule_versions"

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
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    effective_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    effective_to: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    eligibility_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    # Relationships
    scheme: Mapped["Scheme"] = relationship(
        "Scheme",
        back_populates="rule_versions",
    )

    __table_args__ = (
        UniqueConstraint("scheme_id", "version", name="uq_scheme_rule_versions_scheme_version"),
        CheckConstraint("version >= 1", name="ck_scheme_rule_versions_version"),
        Index(
            "uq_scheme_rule_versions_active",
            "scheme_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


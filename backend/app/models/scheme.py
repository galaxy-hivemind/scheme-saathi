"""
SQLAlchemy model representing Government Schemes.
"""
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime
import uuid
from sqlalchemy import (
    String,
    Text,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.scheme_rule_version import SchemeRuleVersion
    from app.models.scheme_document import SchemeDocument


class Scheme(Base, TimestampMixin):
    __tablename__ = "schemes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scheme_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Canonical stable identifier for the scheme (e.g. PM-KISAN)",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    short_title: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    ministry: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    geographic_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="central",
    )
    target_beneficiaries: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )
    benefits: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    official_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    application_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    source_evidence: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    scheme_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending_verification",
    )
    last_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    rule_versions: Mapped[List["SchemeRuleVersion"]] = relationship(
        "SchemeRuleVersion",
        back_populates="scheme",
        passive_deletes=True,
        order_by="SchemeRuleVersion.version.desc()",
    )
    documents: Mapped[List["SchemeDocument"]] = relationship(
        "SchemeDocument",
        back_populates="scheme",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("scheme_code", name="uq_schemes_scheme_code"),
        CheckConstraint(
            "category IN ('agriculture', 'education', 'health', 'housing', 'employment', 'women_welfare', 'children_welfare', 'senior_citizens', 'disability', 'financial_inclusion', 'social_security', 'skill_development')",
            name="ck_schemes_category",
        ),
        CheckConstraint(
            "geographic_scope = 'central'",
            name="ck_schemes_geographic_scope",
        ),
        CheckConstraint(
            "scheme_status IN ('active', 'inactive', 'pending_verification')",
            name="ck_schemes_status",
        ),
        Index("ix_schemes_status_category", "scheme_status", "category"),
        Index(
            "ix_schemes_fts",
            text(
                "(to_tsvector('english', coalesce(scheme_code, '') || ' ' || coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(ministry, '') || ' ' || coalesce(category, '') || ' ' || coalesce(benefits, '')) || array_to_tsvector(target_beneficiaries))"
            ),
            postgresql_using="gin",
        ),
    )

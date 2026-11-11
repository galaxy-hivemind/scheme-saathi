"""
Beneficiary profile model for storing family members under an authenticated citizen account.
Used for determining welfare scheme eligibility for relatives (father, mother, spouse, children, etc.).
"""
from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy import String, Date, Numeric, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

ALLOWED_RELATIONSHIPS = (
    "father",
    "mother",
    "spouse",
    "son",
    "daughter",
    "sibling",
    "guardian",
    "other",
)


class BeneficiaryProfile(Base, TimestampMixin):
    __tablename__ = "beneficiary_profiles"

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
        doc="Owning authenticated account holder ID",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Family relationship: father, mother, spouse, son, daughter, sibling, guardian, other",
    )
    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    district: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    residence_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="'rural', 'urban', or 'semi_urban'",
    )
    occupation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    annual_family_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    # JSONB on Postgres with fallback to JSON
    profile_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="beneficiaries",
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(trim(full_name)) > 0",
            name="ck_beneficiary_profiles_full_name",
        ),
        CheckConstraint(
            f"relationship IN {ALLOWED_RELATIONSHIPS}",
            name="ck_beneficiary_profiles_relationship",
        ),
        CheckConstraint(
            "residence_type IS NULL OR residence_type IN ('rural', 'urban', 'semi_urban')",
            name="ck_beneficiary_profiles_residence_type",
        ),
        CheckConstraint(
            "annual_family_income IS NULL OR annual_family_income >= 0",
            name="ck_beneficiary_profiles_annual_income",
        ),
        Index("ix_beneficiary_profiles_user_rel", "user_id", "relationship"),
    )

"""
User profile model for storing citizen information used in welfare eligibility.
"""
from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy import String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
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
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        default="hi",
        nullable=False,
    )
    # JSONB on Postgres with fallback to JSON
    profile_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        default=dict,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="profile",
    )

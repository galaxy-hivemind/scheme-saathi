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

    @property
    def age(self) -> Optional[int]:
        """Calculates citizen age from profile_data or date_of_birth."""
        if self.profile_data and "age" in self.profile_data and self.profile_data["age"] is not None:
            try:
                return int(self.profile_data["age"])
            except (ValueError, TypeError):
                pass
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            )
        return None

    @age.setter
    def age(self, value: Optional[int]) -> None:
        if self.profile_data is None:
            self.profile_data = {}
        if value is not None:
            self.profile_data["age"] = int(value)
            if self.date_of_birth is None:
                self.date_of_birth = date(date.today().year - int(value), 1, 1)
        else:
            self.profile_data.pop("age", None)

    @property
    def annual_income(self) -> Optional[float]:
        """Returns citizen annual family income from column or profile_data."""
        if self.annual_family_income is not None:
            try:
                return float(self.annual_family_income)
            except (ValueError, TypeError):
                pass
        if self.profile_data and "annual_income" in self.profile_data:
            try:
                return float(self.profile_data["annual_income"])
            except (ValueError, TypeError):
                pass
        return None

    @annual_income.setter
    def annual_income(self, value: Optional[Any]) -> None:
        if value is not None:
            try:
                dec_val = Decimal(str(value))
                self.annual_family_income = dec_val
                if self.profile_data is None:
                    self.profile_data = {}
                self.profile_data["annual_income"] = float(dec_val)
            except Exception:
                pass
        else:
            self.annual_family_income = None
            if self.profile_data:
                self.profile_data.pop("annual_income", None)

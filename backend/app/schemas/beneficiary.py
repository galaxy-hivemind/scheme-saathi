"""
Beneficiary profile request and response schemas.
Supports both account holder (self) and family members (father, mother, spouse, children, etc.).
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid
from pydantic import BaseModel, Field, ConfigDict


class BeneficiaryRelationship(str, Enum):
    SELF = "self"
    FATHER = "father"
    MOTHER = "mother"
    SPOUSE = "spouse"
    SON = "son"
    DAUGHTER = "daughter"
    SIBLING = "sibling"
    GUARDIAN = "guardian"
    OTHER = "other"


# Relationships permitted when creating an additional family beneficiary
FAMILY_RELATIONSHIP_PATTERN = "^(father|mother|spouse|son|daughter|sibling|guardian|other)$"
RESIDENCE_TYPE_PATTERN = "^(rural|urban|semi_urban)$"


class BeneficiaryCreate(BaseModel):
    """Schema for registering a family beneficiary under an account."""
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of beneficiary")
    relationship: str = Field(
        ...,
        pattern=FAMILY_RELATIONSHIP_PATTERN,
        description="Relationship to account holder: father, mother, spouse, son, daughter, sibling, guardian, other",
    )
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern=RESIDENCE_TYPE_PATTERN)
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    profile_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BeneficiaryUpdate(BaseModel):
    """Schema for updating a beneficiary."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    relationship: Optional[str] = Field(None, pattern=FAMILY_RELATIONSHIP_PATTERN)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern=RESIDENCE_TYPE_PATTERN)
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    profile_data: Optional[Dict[str, Any]] = None


class BeneficiaryResponse(BaseModel):
    """Unified schema representing either the account holder (self) or a family member."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: Optional[str] = None
    relationship: str = Field(..., description="'self' for account holder, or family relation")
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    residence_type: Optional[str] = None
    occupation: Optional[str] = None
    annual_family_income: Optional[Decimal] = None
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

"""
User profile and consent request/response schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
import uuid
from pydantic import BaseModel, Field, ConfigDict


class UserProfileCreate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern="^(rural|urban|semi_urban)$")
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    preferred_language: str = Field(default="hi", pattern="^(hi|en)$")
    profile_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern="^(rural|urban|semi_urban)$")
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    preferred_language: Optional[str] = Field(None, pattern="^(hi|en)$")
    profile_data: Optional[Dict[str, Any]] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    residence_type: Optional[str] = None
    occupation: Optional[str] = None
    annual_family_income: Optional[Decimal] = None
    preferred_language: str = "hi"
    profile_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UserConsentCreate(BaseModel):
    consent_type: str = Field(..., min_length=2, max_length=100)
    consent_status: str = Field(default="given", pattern="^(given|revoked)$")


class UserConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    consent_type: str
    consent_status: str
    recorded_at: datetime
    revoked_at: Optional[datetime] = None

"""
Pydantic schemas for the allowlisted Tool Registry.
Defines strict inputs and outputs for read-only tools and action proposal tools.
"""
from typing import Optional, Dict, Any, List, Union
from datetime import date, datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, Field, ConfigDict, field_validator


class SearchSchemesInput(BaseModel):
    q: Optional[str] = Field(None, max_length=255, description="Search keyword or scheme title")
    category: Optional[str] = Field(None, max_length=100, description="Welfare category filter")
    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    limit: int = Field(default=10, ge=1, le=20, description="Results limit (max 20)")


class GetSchemeDetailsInput(BaseModel):
    scheme_id: Union[uuid.UUID, str] = Field(..., description="UUID of the scheme to retrieve")

    @field_validator("scheme_id")
    @classmethod
    def validate_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for scheme_id: {v}")


class ListBeneficiariesInput(BaseModel):
    pass


class GetBeneficiaryInput(BaseModel):
    beneficiary_id: Union[uuid.UUID, str] = Field(..., description="UUID of beneficiary to retrieve")

    @field_validator("beneficiary_id")
    @classmethod
    def validate_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class EvaluateEligibilityInput(BaseModel):
    scheme_id: Union[uuid.UUID, str] = Field(..., description="UUID of scheme to evaluate")
    beneficiary_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of target family beneficiary (null means account holder self)"
    )
    profile_override: Optional[Dict[str, Any]] = Field(
        None, description="Optional profile attribute overrides for what-if evaluation"
    )

    @field_validator("scheme_id")
    @classmethod
    def validate_scheme_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for scheme_id: {v}")

    @field_validator("beneficiary_id")
    @classmethod
    def validate_beneficiary_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class EvaluateAllSchemesInput(BaseModel):
    beneficiary_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of target beneficiary (null means account holder self)"
    )
    category: Optional[str] = Field(None, max_length=100, description="Optional category filter")
    profile_override: Optional[Dict[str, Any]] = Field(
        None, description="Optional profile attribute overrides"
    )

    @field_validator("beneficiary_id")
    @classmethod
    def validate_beneficiary_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class GetDocumentChecklistInput(BaseModel):
    scheme_id: Union[uuid.UUID, str] = Field(..., description="UUID of the scheme to get document checklist for")
    beneficiary_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of target family beneficiary (null means account holder self)"
    )

    @field_validator("scheme_id")
    @classmethod
    def validate_scheme_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for scheme_id: {v}")

    @field_validator("beneficiary_id")
    @classmethod
    def validate_beneficiary_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class GenerateApplicationDraftInput(BaseModel):
    scheme_id: Union[uuid.UUID, str] = Field(..., description="UUID of the scheme to prepare application draft for")
    beneficiary_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of target family beneficiary (null means account holder self)"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Optional application preparation notes")

    @field_validator("scheme_id")
    @classmethod
    def validate_scheme_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for scheme_id: {v}")

    @field_validator("beneficiary_id")
    @classmethod
    def validate_beneficiary_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class TrackApplicationStatusInput(BaseModel):
    application_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of the application draft to track"
    )
    external_reference_number: Optional[str] = Field(
        None, max_length=100, description="Optional official government portal application reference number"
    )
    scheme_id: Optional[Union[uuid.UUID, str]] = Field(
        None, description="Optional UUID of the scheme to look up the latest application for"
    )

    @field_validator("application_id")
    @classmethod
    def validate_app_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for application_id: {v}")

    @field_validator("scheme_id")
    @classmethod
    def validate_scheme_uuid(cls, v: Optional[Union[uuid.UUID, str]]) -> Optional[uuid.UUID]:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for scheme_id: {v}")


class ProposeCreateBeneficiaryInput(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of beneficiary")
    relationship: str = Field(
        ...,
        pattern="^(father|mother|spouse|son|daughter|sibling|guardian|other)$",
        description="Relationship to account holder: father, mother, spouse, son, daughter, sibling, guardian, other",
    )
    date_of_birth: Optional[date] = Field(None, description="Exact date of birth if known (do not invent from age)")
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern="^(rural|urban|semi_urban)$")
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    profile_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ProposeUpdateBeneficiaryInput(BaseModel):
    beneficiary_id: Union[uuid.UUID, str] = Field(..., description="UUID of family member beneficiary to update")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    relationship: Optional[str] = Field(None, pattern="^(father|mother|spouse|son|daughter|sibling|guardian|other)$")
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    residence_type: Optional[str] = Field(None, pattern="^(rural|urban|semi_urban)$")
    occupation: Optional[str] = Field(None, max_length=100)
    annual_family_income: Optional[Decimal] = Field(None, ge=0)
    profile_data: Optional[Dict[str, Any]] = None

    @field_validator("beneficiary_id")
    @classmethod
    def validate_uuid(cls, v: Union[uuid.UUID, str]) -> uuid.UUID:
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(str(v).strip())
        except ValueError:
            raise ValueError(f"Invalid UUID string for beneficiary_id: {v}")


class ProposeUpdateUserProfileInput(BaseModel):
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


class ToolResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    success: bool
    data: Any = None
    error: Optional[str] = None


class PendingActionProposalResult(BaseModel):
    status: str = "pending_confirmation"
    action_id: uuid.UUID
    action_type: str
    summary_en: str
    summary_hi: str
    expires_at: datetime
    proposed_payload: Dict[str, Any]

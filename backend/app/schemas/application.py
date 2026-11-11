"""
Pydantic schemas for Application Draft preparation, external government portal handoff,
and post-submission tracking.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ApplicationDraftCreate(BaseModel):
    scheme_id: uuid.UUID = Field(..., description="Target welfare scheme UUID")
    beneficiary_id: Optional[uuid.UUID] = Field(
        None, description="Optional family beneficiary UUID (null means account holder self)"
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Optional citizen notes")


class ApplicationDraftUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000, description="Updated notes")
    prefilled_data: Optional[Dict[str, Any]] = Field(
        None, description="Updated demographic form values"
    )


class ApplicationDraftSubmitRequest(BaseModel):
    external_reference_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Official government portal acknowledgement/application reference number",
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Submission notes")

    @field_validator("external_reference_number")
    @classmethod
    def validate_reference_number(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("external_reference_number cannot be empty or whitespace.")
        return s


class ApplicationDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    beneficiary_id: Optional[uuid.UUID] = None
    scheme_id: uuid.UUID
    scheme_code: str
    scheme_name: str
    target_name: str
    status: str = Field(..., description="DRAFT, READY, SUBMITTED, ARCHIVED")
    prefilled_data: Dict[str, Any]
    attached_documents: List[Dict[str, Any]]
    official_portal_url: str
    notes: Optional[str] = None
    external_reference_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ApplicationDraftListResponse(BaseModel):
    items: List[ApplicationDraftResponse]
    total: int

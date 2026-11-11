"""
Pydantic schemas for application status transitions, timeline audit trail, and portal synchronization.
"""
from typing import Optional, List
from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field


class StatusTransitionCreate(BaseModel):
    status: str = Field(
        ...,
        description="Target status: DRAFT, READY, SUBMITTED, IN_REVIEW, APPROVED, REJECTED, DISBURSED, ARCHIVED",
    )
    source_type: Optional[str] = Field(
        default="user_reported",
        description="Source type: user_reported, official_integration, portal_sync, admin_action",
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="Optional government reference number or tracking identifier",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional progress remarks or status transition context",
    )


class StatusHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    source_type: str
    source_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class ApplicationTimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    scheme_id: uuid.UUID
    scheme_name: str
    scheme_code: Optional[str] = None
    applicant_type: str
    target_name: str
    current_status: str
    external_reference_number: Optional[str] = None
    official_portal_url: str
    submitted_at: Optional[datetime] = None
    history: List[StatusHistoryItemResponse]
    created_at: datetime
    updated_at: datetime


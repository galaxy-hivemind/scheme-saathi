"""
Pydantic schemas for Citizen Document management, secure upload responses, and document checklists.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, Field, ConfigDict


CANONICAL_DOCUMENT_TYPES = [
    "aadhaar",
    "pan",
    "income_certificate",
    "caste_certificate",
    "domicile_certificate",
    "ration_card",
    "bank_passbook",
    "land_record",
    "disability_certificate",
    "other",
]


class CitizenDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique document ID")
    user_id: uuid.UUID = Field(..., description="Owning citizen account ID")
    beneficiary_id: Optional[uuid.UUID] = Field(
        None, description="Target family beneficiary ID (null means self)"
    )
    document_type: str = Field(..., description="Document type identifier")
    file_name: str = Field(..., description="Original client file name")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="Verified MIME type")
    checksum_sha256: str = Field(..., description="Cryptographic SHA-256 digest")
    verification_status: str = Field(..., description="PENDING, VERIFIED, REJECTED, EXPIRED")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason if applicable")
    extracted_metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted OCR or metadata attributes")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class DocumentListResponse(BaseModel):
    items: List[CitizenDocumentResponse]
    total: int


class DocumentChecklistItem(BaseModel):
    document_type: str
    title: str
    description: Optional[str] = None
    is_mandatory: bool
    status: str = Field(..., description="'UPLOADED' or 'MISSING'")
    guidance: Optional[str] = None
    issuing_authority: Optional[str] = None
    alternatives: Optional[List[str]] = None
    attached_document_id: Optional[uuid.UUID] = None
    attached_file_name: Optional[str] = None
    attached_verification_status: Optional[str] = None


class DocumentChecklistResponse(BaseModel):
    scheme_id: uuid.UUID
    scheme_code: str
    scheme_name: str
    beneficiary_id: Optional[uuid.UUID] = None
    target_name: str
    total_mandatory: int
    uploaded_mandatory: int
    is_complete: bool
    completion_percentage: float
    mandatory_documents: List[DocumentChecklistItem]
    optional_documents: List[DocumentChecklistItem]

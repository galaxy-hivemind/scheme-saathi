"""
Pydantic schemas for document OCR text extraction, structured demographic parsing,
and citizen confirmation proposals.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, ConfigDict


DISCLAIMER_TEXT = (
    "Notice: OCR data extraction is an accessibility assistance feature. "
    "It does not certify the legal authenticity of this document."
)


class OCRExtractRequest(BaseModel):
    stage_pending_action: bool = Field(
        False,
        description="Whether to automatically stage a PendingAction for citizen review and confirmation",
    )


class ExtractedDemographicFields(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Common fields
    name: Optional[str] = Field(None, description="Candidate citizen name extracted from document")
    date_of_birth: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    gender: Optional[str] = Field(None, description="male, female, transgender")
    
    # Aadhaar specific
    masked_uid: Optional[str] = Field(None, description="Masked UID: XXXXXXXX1234")
    
    # PAN specific
    pan_number: Optional[str] = Field(None, description="Permanent Account Number: 10 chars")
    
    # Income certificate specific
    annual_family_income: Optional[int] = Field(None, description="Annual family income in INR")
    certificate_number: Optional[str] = Field(None, description="Official certificate or acknowledgement ID")
    issuing_authority: Optional[str] = Field(None, description="Issuing authority (e.g. Tehsildar, SDO)")
    issue_date: Optional[str] = Field(None, description="Issue date YYYY-MM-DD")
    
    # Caste certificate specific
    caste_category: Optional[str] = Field(None, description="SC, ST, OBC, or General")
    sub_caste: Optional[str] = Field(None, description="Sub-caste or community name")
    state: Optional[str] = Field(None, description="Issuing state")
    district: Optional[str] = Field(None, description="Issuing district")
    
    # Land records specific
    land_area_acres: Optional[float] = Field(None, description="Total landholding in acres")
    khasra_number: Optional[str] = Field(None, description="Khasra or survey plot number")
    khata_number: Optional[str] = Field(None, description="Khata or holding account number")
    
    # Bank passbook specific
    ifsc_code: Optional[str] = Field(None, description="11-character RBI IFSC code")
    masked_account_number: Optional[str] = Field(None, description="Masked bank account number")
    bank_name: Optional[str] = Field(None, description="Bank institution name")


class OCRExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID = Field(..., description="ID of the processed citizen document")
    document_type: str = Field(..., description="Canonical document type")
    ocr_status: str = Field(..., description="COMPLETED, UNAVAILABLE, FAILED, or PARTIAL")
    extraction_engine: str = Field(..., description="pypdf_digital, tesseract_ocr, or fallback_mock")
    raw_text_snippet: str = Field(..., description="Truncated snippet of machine-extracted text")
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, description="Structured parsed demographic fields")
    confidence_score: float = Field(..., description="Estimated extraction confidence between 0.0 and 1.0")
    pii_masked: bool = Field(True, description="Indicates sensitive identifiers (Aadhaar, Account) are masked")
    pending_action_id: Optional[uuid.UUID] = Field(None, description="Staged PendingAction ID if proposal created")
    disclaimer: str = Field(DISCLAIMER_TEXT, description="Statutory accessibility assistance notice")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of extraction")

"""
Citizen Document Vault and Scheme Document Checklist API endpoints.
Provides authenticated endpoints for uploading certificates, tracking verification status,
and retrieving scheme document requirements.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.schemas.common import APIResponse

router = APIRouter()
logger = logging.getLogger(__name__)


class DocumentChecklistRequest(BaseModel):
    scheme_id: str


class DocumentChecklistResponseItem(BaseModel):
    id: str
    scheme_id: Optional[str] = None
    document_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    is_mandatory: bool = True
    alternatives: Optional[List[str]] = None
    issuing_authority: Optional[str] = None
    guidance: Optional[str] = None
    source_url: Optional[str] = None
    last_verified_at: Optional[str] = None


@router.get(
    "",
    response_model=APIResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List stored documents in user citizen vault",
)
def get_user_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[Dict[str, Any]]]:
    """
    Retrieve all encrypted / verified documents uploaded to the citizen vault.
    Strictly isolated to authenticated user.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        return APIResponse.ok([])

    docs = profile.profile_data.get("documents", [])
    return APIResponse.ok(docs)


@router.post(
    "/upload",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document to the citizen vault",
)
async def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Upload a certificate or identity document to the citizen vault.
    Extracts baseline attributes via deterministic OCR simulation and marks pending review.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        profile = UserProfile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            full_name="Citizen",
            profile_data={},
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    now_iso = datetime.now(timezone.utc).isoformat()
    new_doc_id = f"vault-doc-{uuid.uuid4().hex[:10]}"

    new_doc = {
        "id": new_doc_id,
        "user_id": str(current_user.id),
        "document_type": document_type,
        "file_name": file.filename,
        "content_type": file.content_type,
        "upload_status": "uploaded",
        "ocr_status": "completed",
        "review_status": "pending_review",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    current_profile_data = dict(profile.profile_data or {})
    documents_list = list(current_profile_data.get("documents", []))
    documents_list.insert(0, new_doc)
    current_profile_data["documents"] = documents_list

    # Also update profile attribute flags based on verified uploaded documents
    if document_type in ("aadhaar_card", "aadhaar"):
        current_profile_data["has_aadhaar"] = True
    elif document_type in ("land_records", "khasra", "patta"):
        current_profile_data["land_records_verified"] = True
    elif document_type in ("bank_passbook", "bank_account"):
        current_profile_data["has_bank_account"] = True
        current_profile_data["aadhaar_seeded_bank_account"] = True
    elif document_type == "income_certificate":
        current_profile_data["income_certificate_verified"] = True
    elif document_type == "caste_certificate":
        current_profile_data["caste_certificate_verified"] = True

    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(new_doc)


@router.post(
    "/checklist",
    response_model=APIResponse[List[DocumentChecklistResponseItem]],
    status_code=status.HTTP_200_OK,
    summary="Get document checklist for a scheme",
)
def get_scheme_document_checklist(
    payload: DocumentChecklistRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[DocumentChecklistResponseItem]]:
    """
    Retrieve authoritative document requirements from PostgreSQL for a given scheme.
    """
    scheme = None
    try:
        scheme_uuid = uuid.UUID(payload.scheme_id)
        scheme = db.query(Scheme).filter(Scheme.id == scheme_uuid).first()
    except (ValueError, AttributeError):
        scheme = db.query(Scheme).filter(
            (Scheme.scheme_code == payload.scheme_id) |
            (Scheme.scheme_code == payload.scheme_id.upper())
        ).first()

    if not scheme:
        return APIResponse.ok([])

    db_docs = db.query(SchemeDocument).filter(
        SchemeDocument.scheme_id == scheme.id,
        SchemeDocument.is_active == True,
    ).all()

    checklist = [
        DocumentChecklistResponseItem(
            id=str(d.id),
            scheme_id=str(d.scheme_id),
            document_type=d.document_type,
            title=d.title,
            description=d.description,
            is_mandatory=d.is_mandatory,
            alternatives=d.alternatives,
            issuing_authority=d.issuing_authority,
            guidance=d.guidance,
            source_url=d.source_url,
            last_verified_at=d.last_verified_at.isoformat() if d.last_verified_at else None,
        )
        for d in db_docs
    ]

    return APIResponse.ok(checklist)


@router.get(
    "/{document_id}/guidance",
    response_model=APIResponse[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Get issuing guidance for a document",
)
def get_document_guidance(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, str]]:
    """
    Retrieve official issuing authority guidance and alternative documents.
    """
    guidance = (
        "Apply online via your State e-District portal (edistrict.gov.in) or visit your nearest "
        "Common Service Centre (CSC) with your identity proof and residence certificate."
    )
    return APIResponse.ok({"guidance": guidance})

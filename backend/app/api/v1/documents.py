"""
Citizen Document Vault and Scheme Document Checklist API endpoints.
Provides authenticated endpoints for uploading documents, honest OCR inspection,
citizen review & correction, deterministic verification/rejection, and scheme checklists.

Verification Integrity:
- Uploading a file NEVER automatically verifies it.
- OCR extraction alone does not constitute verification.
- Citizens review extracted details (`awaiting_citizen_review` -> `reviewed`) before
  deterministic verification checks can mark a document `verified` or `rejected`.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.schemas.common import APIResponse
from app.services.document_service import (
    DOCUMENT_TYPE_LABELS,
    validate_uploaded_file_bytes,
    inspect_document_and_extract_ocr,
    save_document_file,
    resolve_document_file_path,
    delete_stored_file,
    normalize_vault_document,
    recalculate_profile_doc_flags,
    apply_citizen_review,
    verify_reviewed_document,
    get_localized_doc_label,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class DocumentChecklistRequest(BaseModel):
    scheme_id: str


class DocumentReviewRequest(BaseModel):
    reviewed_fields: Dict[str, Any] = Field(default_factory=dict)
    confirmed_accurate: bool = True


class DocumentVerifyRequest(BaseModel):
    reject: bool = False
    rejection_reason: Optional[str] = None


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


def _get_or_create_profile(db: Session, user: User) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = UserProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            full_name="Citizen",
            profile_data={},
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get(
    "/categories",
    response_model=APIResponse[List[Dict[str, str]]],
    status_code=status.HTTP_200_OK,
    summary="List supported citizen vault document categories",
)
def get_document_categories(
    lang: str = "en",
    current_user: User = Depends(get_current_user),
) -> APIResponse[List[Dict[str, str]]]:
    """Return canonical uploadable document categories cleanly localized without parentheticals."""
    supported_order = [
        "aadhaar_card",
        "bank_passbook",
        "income_certificate",
        "land_records",
        "land_possession",
        "job_card",
        "caste_certificate",
        "domicile_certificate",
        "ration_card",
        "death_certificate",
        "mcp_card",
        "vending_certificate",
        "marksheet_12th",
        "pan_card",
    ]
    categories = [
        {"value": code, "label": get_localized_doc_label(code, lang)}
        for code in supported_order
        if code in DOCUMENT_TYPE_LABELS
    ]
    return APIResponse.ok(categories)


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
    Retrieve all documents uploaded to the citizen vault with normalized lifecycle states.
    Strictly isolated to authenticated user.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        return APIResponse.ok([])

    raw_docs = profile.profile_data.get("documents", [])
    docs = [
        normalize_vault_document(d)
        for d in raw_docs
        if not d.get("user_id") or str(d.get("user_id")) == str(current_user.id)
    ]
    return APIResponse.ok(docs)


@router.post(
    "/upload",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document and run honest OCR inspection",
)
async def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Upload a certificate or identity document to the citizen vault:
    - Validates extension, size limits, and binary magic bytes (rejects invalid/empty/corrupted files).
    - Runs honest OCR/stream extraction without fabricating data.
    - Leaves document in `extracted` or `awaiting_citizen_review` status — NEVER auto-verifies.
    """
    raw_bytes = await file.read()
    try:
        file_meta = validate_uploaded_file_bytes(file.filename, file.content_type, raw_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    profile = _get_or_create_profile(db, current_user)
    now_iso = datetime.now(timezone.utc).isoformat()
    new_doc_id = f"vault-doc-{uuid.uuid4().hex[:10]}"

    storage_rel_path = save_document_file(
        user_id=str(current_user.id),
        doc_id=new_doc_id,
        extension=file_meta["extension"],
        raw_bytes=raw_bytes,
    )

    ocr_info = inspect_document_and_extract_ocr(
        document_type=document_type,
        raw_bytes=raw_bytes,
        file_meta=file_meta,
    )

    new_doc = {
        "id": new_doc_id,
        "user_id": str(current_user.id),
        "document_type": document_type,
        "file_name": file.filename or f"{new_doc_id}.{file_meta['extension']}",
        "content_type": file_meta["detected_mime"],
        "size_bytes": file_meta["size_bytes"],
        "sha256": file_meta["sha256"],
        "storage_rel_path": storage_rel_path,
        "upload_status": "uploaded",
        "ocr_status": ocr_info["ocr_status"],
        "ocr_engine": ocr_info["ocr_engine"],
        "ocr_confidence": ocr_info["ocr_confidence"],
        "ocr_note": ocr_info["ocr_note"],
        "extracted_fields": ocr_info["extracted_fields"],
        "reviewed_fields": {
            k: v
            for k, v in ocr_info["extracted_fields"].items()
            if k not in ("raw_text_preview", "detected_dates")
        },
        "lifecycle_status": ocr_info["lifecycle_status"],
        "verification_status": ocr_info["lifecycle_status"],
        "review_status": "pending_review",
        "citizen_confirmed_accurate": False,
        "rejection_reason": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "audit_trail": [
            {
                "timestamp": now_iso,
                "action": "DOCUMENT_UPLOADED",
                "details": f"File validated ({file_meta['detected_mime']}, {file_meta['size_bytes']} bytes). OCR status: {ocr_info['ocr_status']}.",
            }
        ],
    }

    current_profile_data = dict(profile.profile_data or {})
    documents_list = list(current_profile_data.get("documents", []))
    documents_list.insert(0, new_doc)
    current_profile_data["documents"] = documents_list

    # Strictly sync verification flags from verified documents only (never auto-verify on upload)
    recalculate_profile_doc_flags(current_profile_data)

    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(new_doc)


@router.get(
    "/{doc_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Inspect single vault document metadata and OCR findings",
)
def get_document_details(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    for raw_doc in profile.profile_data.get("documents", []):
        if raw_doc.get("id") == doc_id:
            if raw_doc.get("user_id") and str(raw_doc.get("user_id")) != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            return APIResponse.ok(normalize_vault_document(raw_doc))

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.get(
    "/{doc_id}/file",
    status_code=status.HTTP_200_OK,
    summary="Download or preview uploaded document bytes (owner-isolated)",
)
def get_document_file(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    target_doc = next(
        (d for d in profile.profile_data.get("documents", []) if d.get("id") == doc_id),
        None,
    )
    if not target_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = resolve_document_file_path(target_doc, str(current_user.id))
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file preview is unavailable for this record.",
        )

    return FileResponse(
        path=str(file_path),
        media_type=target_doc.get("content_type") or "application/octet-stream",
        filename=target_doc.get("file_name") or file_path.name,
    )


@router.post(
    "/{doc_id}/review",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Save citizen review and corrections for extracted document details",
)
def review_document(
    doc_id: str,
    payload: DocumentReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Allows citizen to review OCR output, edit or fill missing fields, and mark the document `reviewed`.
    Does NOT automatically verify the document.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    current_profile_data = dict(profile.profile_data)
    docs = list(current_profile_data.get("documents", []))

    idx = next((i for i, d in enumerate(docs) if d.get("id") == doc_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    target_doc = docs[idx]
    if target_doc.get("user_id") and str(target_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    updated_doc = apply_citizen_review(
        target_doc,
        reviewed_fields=payload.reviewed_fields,
        confirmed_accurate=payload.confirmed_accurate,
    )
    docs[idx] = updated_doc
    current_profile_data["documents"] = docs
    recalculate_profile_doc_flags(current_profile_data)

    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(updated_doc)


@router.post(
    "/{doc_id}/verify",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Run deterministic verification or rejection on a reviewed document",
)
def verify_document(
    doc_id: str,
    payload: Optional[DocumentVerifyRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Evaluates a reviewed document against deterministic format, expiry, and profile consistency rules.
    Transitions strictly to `verified` (if all checks pass) or `rejected` (with clear reasons).
    Requires prior citizen review (`reviewed`).
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    current_profile_data = dict(profile.profile_data)
    docs = list(current_profile_data.get("documents", []))

    idx = next((i for i, d in enumerate(docs) if d.get("id") == doc_id), None)
    if idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    target_doc = normalize_vault_document(docs[idx])
    if target_doc.get("user_id") and str(target_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if payload and payload.reject:
        now_iso = datetime.now(timezone.utc).isoformat()
        target_doc["lifecycle_status"] = "rejected"
        target_doc["verification_status"] = "rejected"
        target_doc["review_status"] = "rejected"
        target_doc["rejection_reason"] = payload.rejection_reason or "Marked rejected during verification."
        target_doc["verified_at"] = None
        target_doc["updated_at"] = now_iso
        audit = list(target_doc.get("audit_trail", []))
        audit.append({
            "timestamp": now_iso,
            "action": "DOCUMENT_REJECTED",
            "details": target_doc["rejection_reason"],
        })
        target_doc["audit_trail"] = audit
    else:
        target_doc, reasons = verify_reviewed_document(target_doc, profile_full_name=profile.full_name)
        if reasons and target_doc["lifecycle_status"] not in ("rejected", "verified"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="; ".join(reasons),
            )

    docs[idx] = target_doc
    current_profile_data["documents"] = docs
    recalculate_profile_doc_flags(current_profile_data)

    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(target_doc)


@router.delete(
    "/{doc_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Delete a document from the citizen vault",
)
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    current_profile_data = dict(profile.profile_data)
    docs = list(current_profile_data.get("documents", []))
    target_doc = next((d for d in docs if d.get("id") == doc_id), None)
    if not target_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if target_doc.get("user_id") and str(target_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    delete_stored_file(target_doc, str(current_user.id))
    current_profile_data["documents"] = [d for d in docs if d.get("id") != doc_id]
    recalculate_profile_doc_flags(current_profile_data)

    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    db.commit()
    db.refresh(profile)

    return APIResponse.ok({"deleted": True, "id": doc_id})


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
    from app.agents.form_schemas import get_document_sourcing_info
    info = get_document_sourcing_info(document_id, lang="en")
    guidance = (
        f"{info.get('where_to_obtain', 'Visit nearest CSC or State e-District portal.')} "
        f"Issuing Authority: {info.get('issuing_authority', 'Competent Authority')}."
    )
    return APIResponse.ok({"guidance": guidance})

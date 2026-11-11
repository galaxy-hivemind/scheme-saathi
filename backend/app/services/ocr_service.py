"""
OCR service orchestrating document text extraction, structured parsing,
database persistence, and human-in-the-loop pending action staging.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.citizen_document import CitizenDocument
from app.models.chat import PendingAction
from app.schemas.ocr import OCRExtractionResponse, DISCLAIMER_TEXT
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.services import document_service, chat_service
from app.ocr.engine import extract_text_from_file
from app.ocr.parsers import parse_document_text

logger = logging.getLogger(__name__)

ACTION_EXPIRY_MINUTES = 15

# Fields permitted to update citizen profile from OCR
ALLOWED_PROFILE_UPDATE_FIELDS = {
    "date_of_birth",
    "gender",
    "annual_family_income",
    "state",
    "district",
    "occupation",
    "residence_type",
}


def process_document_ocr(
    db: Session,
    current_user: User,
    document_id: uuid.UUID,
    stage_pending_action: bool = False,
) -> OCRExtractionResponse:
    """
    Extracts text and demographic fields from a citizen document,
    persists extracted metadata on the document record, and optionally
    stages a durable PendingAction for citizen review and confirmation.
    """
    # 1. Retrieve document and enforce ownership
    doc = db.query(CitizenDocument).filter(CitizenDocument.id == document_id).first()
    if not doc:
        raise NotFoundError(f"Document with ID '{document_id}' not found.")

    if doc.user_id != current_user.id:
        raise ForbiddenError("You do not have permission to access this document.")

    # 2. Get physical file path
    physical_path = document_service.get_document_physical_path(doc)

    # 3. Dispatch to OCR Engine
    raw_text, engine_name, ocr_status = extract_text_from_file(physical_path, doc.mime_type)

    # 4. Parse document-specific demographic fields
    extracted_fields, confidence = parse_document_text(doc.document_type, raw_text)

    # 5. Persist extracted metadata on document record
    now_utc = datetime.now(timezone.utc)
    snippet = raw_text[:500].strip() if raw_text else ""

    metadata = {
        "raw_text_snippet": snippet,
        "extracted_fields": extracted_fields,
        "ocr_status": ocr_status,
        "extraction_engine": engine_name,
        "confidence_score": confidence,
        "pii_masked": True,
        "extracted_at": now_utc.isoformat(),
    }

    doc.extracted_metadata = metadata
    db.commit()
    db.refresh(doc)

    # 6. Optionally stage a PendingAction proposal
    pending_action_id: Optional[uuid.UUID] = None

    if stage_pending_action and extracted_fields:
        # Filter fields to allowlisted profile update attributes
        filtered_payload = {
            k: v for k, v in extracted_fields.items() if k in ALLOWED_PROFILE_UPDATE_FIELDS and v is not None
        }

        if filtered_payload:
            # Resolve target conversation for pending action
            conv = chat_service.get_or_create_conversation(db, current_user)

            is_beneficiary = doc.beneficiary_id is not None
            action_type = "update_beneficiary" if is_beneficiary else "update_user_profile"

            # Create bilingual summary
            summary_en_items = [f"{k.replace('_', ' ').title()}: {v}" for k, v in filtered_payload.items()]
            summary_hi_items = [f"{k}: {v}" for k, v in filtered_payload.items()]

            target_label = "family beneficiary" if is_beneficiary else "your profile"
            summary_en = f"Update {target_label} with details extracted from {doc.document_type}: {', '.join(summary_en_items)}"
            summary_hi = f"{doc.document_type} से प्राप्त विवरण के साथ प्रोफ़ाइल अपडेट करें: {', '.join(summary_hi_items)}"

            action = PendingAction(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                user_id=current_user.id,
                beneficiary_id=doc.beneficiary_id,
                action_type=action_type,
                payload=filtered_payload,
                summary={
                    "en": summary_en,
                    "hi": summary_hi,
                },
                status="PENDING",
                expires_at=now_utc + timedelta(minutes=ACTION_EXPIRY_MINUTES),
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            pending_action_id = action.id

    return OCRExtractionResponse(
        document_id=doc.id,
        document_type=doc.document_type,
        ocr_status=ocr_status,
        extraction_engine=engine_name,
        raw_text_snippet=snippet,
        extracted_fields=extracted_fields,
        confidence_score=confidence,
        pii_masked=True,
        pending_action_id=pending_action_id,
        disclaimer=DISCLAIMER_TEXT,
        extracted_at=now_utc,
    )


def get_document_ocr(
    db: Session,
    current_user: User,
    document_id: uuid.UUID,
) -> OCRExtractionResponse:
    """
    Retrieves previously persisted OCR metadata from a citizen document
    without re-running the extraction pipeline.
    """
    doc = db.query(CitizenDocument).filter(CitizenDocument.id == document_id).first()
    if not doc:
        raise NotFoundError(f"Document with ID '{document_id}' not found.")

    if doc.user_id != current_user.id:
        raise ForbiddenError("You do not have permission to access this document.")

    meta = doc.extracted_metadata or {}
    snippet = meta.get("raw_text_snippet", "")
    extracted_fields = meta.get("extracted_fields", {})
    ocr_status = meta.get("ocr_status", "PENDING")
    engine = meta.get("extraction_engine", "none")
    confidence = meta.get("confidence_score", 0.0)

    extracted_at = datetime.now(timezone.utc)
    if "extracted_at" in meta:
        try:
            extracted_at = datetime.fromisoformat(meta["extracted_at"])
        except Exception:
            pass

    return OCRExtractionResponse(
        document_id=doc.id,
        document_type=doc.document_type,
        ocr_status=ocr_status,
        extraction_engine=engine,
        raw_text_snippet=snippet,
        extracted_fields=extracted_fields,
        confidence_score=confidence,
        pii_masked=True,
        pending_action_id=None,
        disclaimer=DISCLAIMER_TEXT,
        extracted_at=extracted_at,
    )

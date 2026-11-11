"""
Document Service for secure file validation, streaming upload, checksum verification,
storage management, and document checklist evaluation.
"""
from typing import Optional, List, Dict, Any, Tuple
import os
import re
import uuid
import hashlib
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError, PayloadTooLargeError, ForbiddenError
from app.models.user import User
from app.models.citizen_document import CitizenDocument
from app.models.scheme_document import SchemeDocument
from app.models.scheme import Scheme
from app.schemas.document import (
    CitizenDocumentResponse,
    DocumentListResponse,
    DocumentChecklistResponse,
    DocumentChecklistItem,
)
from app.services import beneficiary_service, scheme_service

logger = logging.getLogger(__name__)

CHUNK_SIZE = 65536  # 64 KB chunks
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 10 MB

# Magic byte signatures
MAGIC_BYTES = [
    (b"%PDF-", "application/pdf", [".pdf"]),
    (b"\xff\xd8\xff", "image/jpeg", [".jpg", ".jpeg"]),
    (b"\x89PNG\r\n\x1a\n", "image/png", [".png"]),
]


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename against path traversal, control characters, and unsafe extensions.
    Preserves valid basename and extension.
    """
    if not filename:
        return "document.pdf"

    # Strip directory components
    base_name = os.path.basename(filename).strip()

    # Remove null bytes, path traversal sequences
    base_name = base_name.replace("\x00", "").replace("..", "")
    # Remove leading dots and whitespace
    base_name = base_name.lstrip(". \t")

    # Match stem and extension
    p = Path(base_name)
    ext = p.suffix.lower()
    stem = p.stem

    # Sanitize stem: allow only alphanumeric, underscores, hyphens, and spaces
    safe_stem = re.sub(r"[^\w\s-]", "", stem).strip()
    safe_stem = re.sub(r"[-\s]+", "_", safe_stem)

    if not safe_stem:
        safe_stem = "document"

    # Truncate stem to at most 100 characters
    safe_stem = safe_stem[:100]

    return f"{safe_stem}{ext}"


def validate_file_signature(header_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Validate file magic bytes and verify compatibility with file extension.
    Returns (verified_mime_type, normalized_extension).
    Raises ValidationError if signature is invalid or mismatched.
    """
    if not header_bytes or len(header_bytes) < 4:
        raise ValidationError("File is empty or contains an invalid header.")

    detected_mime: Optional[str] = None
    allowed_exts: List[str] = []

    for signature, mime_type, exts in MAGIC_BYTES:
        if header_bytes.startswith(signature):
            detected_mime = mime_type
            allowed_exts = exts
            break

    if not detected_mime:
        raise ValidationError(
            "Unsupported file format. Only PDF, JPEG, and PNG documents are permitted."
        )

    # Check extension
    p = Path(filename)
    ext = p.suffix.lower()

    if ext not in allowed_exts:
        # Check if ext is any permitted extension but mismatched with content
        all_allowed_exts = [e for _, _, exts in MAGIC_BYTES for e in exts]
        if ext in all_allowed_exts:
            raise ValidationError(
                f"File content ({detected_mime}) does not match file extension '{ext}'."
            )
        raise ValidationError(
            f"File extension '{ext}' is not supported. Allowed extensions: {all_allowed_exts}."
        )

    return detected_mime, ext


def save_uploaded_document(
    db: Session,
    current_user: User,
    file: UploadFile,
    document_type: str,
    beneficiary_id: Optional[uuid.UUID] = None,
) -> CitizenDocument:
    """
    Stream and validate an uploaded document, compute SHA-256 digest,
    store to local protected storage, and persist CitizenDocument record.
    """
    doc_type = document_type.strip()
    if not doc_type:
        raise ValidationError("document_type cannot be empty.")
    if len(doc_type) > 50:
        raise ValidationError("document_type must be at most 50 characters.")

    # Validate beneficiary ownership if specified
    if beneficiary_id is not None:
        beneficiary_service.get_beneficiary_by_id(db, beneficiary_id, current_user.id)

    raw_filename = file.filename or "upload.pdf"
    safe_filename = sanitize_filename(raw_filename)

    doc_id = uuid.uuid4()
    user_storage_dir = os.path.join(settings.STORAGE_DIR, str(current_user.id))
    os.makedirs(user_storage_dir, mode=0o700, exist_ok=True)

    dest_filename = f"{doc_id}_{safe_filename}"
    dest_path = os.path.join(user_storage_dir, dest_filename)

    hasher = hashlib.sha256()
    total_bytes = 0
    header_checked = False
    verified_mime = ""

    try:
        with open(dest_path, "wb") as f_out:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break

                if not header_checked:
                    verified_mime, _ = validate_file_signature(chunk, safe_filename)
                    header_checked = True

                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise PayloadTooLargeError(
                        f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
                    )

                hasher.update(chunk)
                f_out.write(chunk)

        if not header_checked or total_bytes == 0:
            raise ValidationError("Uploaded file is empty.")

    except Exception:
        # Clean up partial file on failure
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        raise

    checksum = hasher.hexdigest()

    # Relative path stored in database
    relative_path = os.path.join(str(current_user.id), dest_filename)

    citizen_doc = CitizenDocument(
        id=doc_id,
        user_id=current_user.id,
        beneficiary_id=beneficiary_id,
        document_type=doc_type,
        file_name=safe_filename,
        file_path=relative_path,
        file_size_bytes=total_bytes,
        mime_type=verified_mime,
        checksum_sha256=checksum,
        extracted_metadata={},
        verification_status="PENDING",
    )
    db.add(citizen_doc)
    db.commit()
    db.refresh(citizen_doc)

    logger.info(
        f"Saved document {citizen_doc.id} ({doc_type}, {total_bytes} bytes) for user {current_user.id}"
    )
    return citizen_doc


def list_documents(
    db: Session,
    current_user: User,
    beneficiary_id: Optional[uuid.UUID] = None,
    document_type: Optional[str] = None,
) -> List[CitizenDocument]:
    """List documents for the current user, optionally filtered by beneficiary or type."""
    stmt = select(CitizenDocument).where(CitizenDocument.user_id == current_user.id)

    if beneficiary_id is not None:
        stmt = stmt.where(CitizenDocument.beneficiary_id == beneficiary_id)
    if document_type:
        stmt = stmt.where(CitizenDocument.document_type == document_type.strip())

    stmt = stmt.order_by(CitizenDocument.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_document_by_id(
    db: Session,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CitizenDocument:
    """Retrieve a document by ID with strict tenant isolation."""
    stmt = select(CitizenDocument).where(
        and_(CitizenDocument.id == document_id, CitizenDocument.user_id == user_id)
    )
    doc = db.execute(stmt).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found.")
    return doc


def get_document_physical_path(doc: CitizenDocument) -> str:
    """Get the verified absolute physical path of a document."""
    full_path = os.path.abspath(os.path.join(settings.STORAGE_DIR, doc.file_path))
    storage_root = os.path.abspath(settings.STORAGE_DIR)

    # Security check against traversal
    if not full_path.startswith(storage_root):
        raise ForbiddenError("Access to file path is denied.")
    if not os.path.exists(full_path):
        raise NotFoundError("Stored document file is missing on server.")

    return full_path


def delete_document(
    db: Session,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete a document record and remove its physical file."""
    doc = get_document_by_id(db, document_id, user_id)

    try:
        physical_path = get_document_physical_path(doc)
        if os.path.exists(physical_path):
            os.remove(physical_path)
    except (NotFoundError, ForbiddenError):
        # Even if physical file is missing, clean up DB record
        pass

    db.delete(doc)
    db.commit()
    logger.info(f"Deleted document {document_id} for user {user_id}")
    return True


def get_checklist(
    db: Session,
    current_user: User,
    scheme_id: uuid.UUID,
    beneficiary_id: Optional[uuid.UUID] = None,
) -> DocumentChecklistResponse:
    """
    Generate document readiness checklist for a scheme and applicant.
    Matches required scheme documents with uploaded citizen documents,
    supporting direct matches and alternative document types.
    """
    scheme = scheme_service.get_scheme_by_id(db, scheme_id)

    # Resolve applicant target name
    if beneficiary_id is not None:
        ben = beneficiary_service.get_beneficiary_by_id(db, beneficiary_id, current_user.id)
        target_name = ben.full_name
    else:
        target_name = (
            current_user.profile.full_name
            if current_user.profile and current_user.profile.full_name
            else "Self"
        )

    # Get active scheme document requirements
    scheme_docs_stmt = (
        select(SchemeDocument)
        .where(
            and_(
                SchemeDocument.scheme_id == scheme_id,
                SchemeDocument.is_active == True,
            )
        )
        .order_by(SchemeDocument.is_mandatory.desc(), SchemeDocument.document_type.asc())
    )
    scheme_docs = list(db.execute(scheme_docs_stmt).scalars().all())

    # Get citizen uploaded documents for this target applicant
    citizen_docs = list_documents(db, current_user, beneficiary_id=beneficiary_id)
    # Filter out rejected documents from fulfilling requirements
    valid_citizen_docs = [
        d for d in citizen_docs if d.verification_status != "REJECTED"
    ]

    mandatory_items: List[DocumentChecklistItem] = []
    optional_items: List[DocumentChecklistItem] = []

    total_mandatory = 0
    uploaded_mandatory = 0

    for s_doc in scheme_docs:
        # Match against citizen docs:
        # 1. Direct match: citizen_doc.document_type == s_doc.document_type
        # 2. Alternative match: citizen_doc.document_type in s_doc.alternatives
        matched_doc: Optional[CitizenDocument] = None

        for c_doc in valid_citizen_docs:
            if c_doc.document_type == s_doc.document_type:
                matched_doc = c_doc
                break

        if not matched_doc and s_doc.alternatives:
            alt_types = set(s_doc.alternatives)
            for c_doc in valid_citizen_docs:
                if c_doc.document_type in alt_types:
                    matched_doc = c_doc
                    break

        is_uploaded = matched_doc is not None
        status = "UPLOADED" if is_uploaded else "MISSING"

        if s_doc.is_mandatory:
            total_mandatory += 1
            if is_uploaded:
                uploaded_mandatory += 1

        item = DocumentChecklistItem(
            document_type=s_doc.document_type,
            title=s_doc.title,
            description=s_doc.description,
            is_mandatory=s_doc.is_mandatory,
            status=status,
            guidance=s_doc.guidance,
            issuing_authority=s_doc.issuing_authority,
            alternatives=s_doc.alternatives,
            attached_document_id=matched_doc.id if matched_doc else None,
            attached_file_name=matched_doc.file_name if matched_doc else None,
            attached_verification_status=matched_doc.verification_status if matched_doc else None,
        )

        if s_doc.is_mandatory:
            mandatory_items.append(item)
        else:
            optional_items.append(item)

    is_complete = total_mandatory == 0 or (uploaded_mandatory >= total_mandatory)
    pct = (
        100.0
        if total_mandatory == 0
        else round((uploaded_mandatory / total_mandatory) * 100.0, 1)
    )

    return DocumentChecklistResponse(
        scheme_id=scheme.id,
        scheme_code=scheme.scheme_code,
        scheme_name=scheme.name,
        beneficiary_id=beneficiary_id,
        target_name=target_name,
        total_mandatory=total_mandatory,
        uploaded_mandatory=uploaded_mandatory,
        is_complete=is_complete,
        completion_percentage=pct,
        mandatory_documents=mandatory_items,
        optional_documents=optional_items,
    )

"""
Citizen Document Vault Lifecycle, Integrity Validation & OCR Inspection Service.

Enforces strict verification integrity:
1. Uploading a file validates magic bytes, size, and image/PDF structure — NEVER auto-verifies.
2. Honest OCR inspection: extracts genuine embedded text (PDF text streams or Tesseract if available)
   and reports honest extraction limits without ever fabricating personal data.
3. Explicit citizen review (`awaiting_citizen_review` -> `reviewed`) allows inspection and correction
   of extracted fields.
4. Deterministic verification gate (`reviewed` -> `verified` or `rejected`) checks required metadata,
   valid document number formats, expiry dates, and name consistency with the citizen profile.
5. Canonical document equivalence mapping ensures `aadhaar_card` <-> `aadhaar`, `land_records` <->
   `land_possession`, etc., without confusing unrelated document types.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import io
import logging
import re
import shutil
import uuid
import zlib

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Secure storage root inside backend/data/vault_uploads (gitignored runtime data)
VAULT_STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "vault_uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

# Lifecycle states
DOC_STATE_UPLOADED = "uploaded"
DOC_STATE_OCR_PROCESSING = "ocr_processing"
DOC_STATE_EXTRACTED = "extracted"
DOC_STATE_AWAITING_REVIEW = "awaiting_citizen_review"
DOC_STATE_REVIEWED = "reviewed"
DOC_STATE_VERIFIED = "verified"
DOC_STATE_REJECTED = "rejected"

# Canonical document type groupings (bidirectional equivalence families)
DOCUMENT_EQUIVALENCE_GROUPS: Dict[str, Tuple[str, ...]] = {
    "aadhaar_card": ("aadhaar_card", "aadhaar", "aadhar", "aadhar_card", "uidai_card"),
    "aadhaar_guardian": ("aadhaar_guardian",),
    "income_certificate": ("income_certificate", "aay_praman_patra", "utpann_pramanpatra"),
    "land_records": ("land_records", "7_12_extract", "khasra", "khatauni", "patta", "ror"),
    "land_possession": (
        "land_possession",
        "homestead_land_title",
        "gram_panchayat_allotment",
        "land_records",
        "7_12_extract",
        "khasra",
        "patta",
    ),
    "bank_passbook": ("bank_passbook", "bank_account", "cancelled_cheque", "bank_statement"),
    "job_card": ("job_card", "mgnrega_job_card"),
    "caste_certificate": ("caste_certificate", "jati_praman_patra"),
    "domicile_certificate": ("domicile_certificate", "residence_certificate", "niwas_praman_patra"),
    "ration_card": ("ration_card",),
    "death_certificate": ("death_certificate", "husband_death_certificate"),
    "mcp_card": ("mcp_card", "mother_child_protection_card"),
    "vending_certificate": ("vending_certificate", "lor", "certificate_of_vending"),
    "marksheet_12th": ("marksheet_12th", "marksheet_12"),
    "marksheet_7th": ("marksheet_7th", "marksheet_7"),
    "bonafide_certificate": ("bonafide_certificate",),
    "pan_card": ("pan_card",),
    "pan_guardian": ("pan_guardian",),
    "passport_photo": ("passport_photo",),
    "birth_certificate": ("birth_certificate",),
    "delivery_certificate": ("delivery_certificate",),
    "shg_passbook": ("shg_passbook",),
    "sowing_certificate": ("sowing_certificate",),
    "trade_declaration": ("trade_declaration",),
    "fisheries_license": ("fisheries_license",),
    "project_report": ("project_report",),
    "education_certificate": ("education_certificate", "educational_certificate"),
    "business_proof": ("business_proof",),
}

# Uploadable vault document catalog with pure trilingual titles (no parenthetical mashups)
DOCUMENT_TYPE_LABELS: Dict[str, Dict[str, str]] = {
    "aadhaar_card": {
        "en": "Aadhaar Card",
        "hi": "आधार कार्ड",
        "mr": "आधार कार्ड",
    },
    "aadhaar": {
        "en": "Aadhaar Card",
        "hi": "आधार कार्ड",
        "mr": "आधार कार्ड",
    },
    "income_certificate": {
        "en": "Income Certificate",
        "hi": "आय प्रमाण पत्र",
        "mr": "उत्पन्न प्रमाणपत्र",
    },
    "bank_passbook": {
        "en": "Bank Passbook",
        "hi": "बैंक पासबुक",
        "mr": "बँक पासबुक",
    },
    "bank_account": {
        "en": "Bank Account Proof",
        "hi": "बैंक खाता विवरण",
        "mr": "बँक खाते पुरावा",
    },
    "land_records": {
        "en": "Land Ownership Records",
        "hi": "भूमि स्वामित्व रिकॉर्ड",
        "mr": "शेतजमिनीचा उतारा",
    },
    "land_possession": {
        "en": "Homestead Land / Allotment Proof",
        "hi": "आवासीय भूमि / पट्टा प्रमाण",
        "mr": "निवासी जागा / वाटप प्रमाणपत्र",
    },
    "job_card": {
        "en": "MGNREGA Job Card",
        "hi": "मनरेगा जॉब कार्ड",
        "mr": "मनरेगा जॉब कार्ड",
    },
    "caste_certificate": {
        "en": "Caste Certificate",
        "hi": "जाति प्रमाण पत्र",
        "mr": "जात प्रमाणपत्र",
    },
    "domicile_certificate": {
        "en": "Domicile Certificate",
        "hi": "निवास प्रमाण पत्र",
        "mr": "अधिवास प्रमाणपत्र",
    },
    "ration_card": {
        "en": "Ration Card",
        "hi": "राशन कार्ड",
        "mr": "रेशन कार्ड",
    },
    "death_certificate": {
        "en": "Husband's Death Certificate",
        "hi": "पति का मृत्यु प्रमाण पत्र",
        "mr": "पतीचे मृत्यू प्रमाणपत्र",
    },
    "mcp_card": {
        "en": "Mother & Child Protection Card",
        "hi": "मातृ एवं शिशु सुरक्षा कार्ड",
        "mr": "माता व बाल संरक्षण कार्ड",
    },
    "vending_certificate": {
        "en": "Certificate of Vending",
        "hi": "विक्रय प्रमाण पत्र",
        "mr": "विक्रेता प्रमाणपत्र",
    },
    "marksheet_12th": {
        "en": "Class 12 Marksheet",
        "hi": "कक्षा 12 अंकसूची",
        "mr": "इयत्ता १२ वी गुणपत्रक",
    },
    "marksheet_12": {
        "en": "Class 12 Marksheet",
        "hi": "कक्षा 12 अंकसूची",
        "mr": "इयत्ता १२ वी गुणपत्रक",
    },
    "pan_card": {
        "en": "PAN Card",
        "hi": "पैन कार्ड",
        "mr": "पॅन कार्ड",
    },
    "passport_photo": {
        "en": "Passport Photograph",
        "hi": "पासपोर्ट आकार का फोटो",
        "mr": "पासपोर्ट आकाराचे छायाचित्र",
    },
    "bonafide_certificate": {
        "en": "Bonafide Student Certificate",
        "hi": "बोनाफाइड छात्र प्रमाण पत्र",
        "mr": "बोनाफाईड विद्यार्थी प्रमाणपत्र",
    },
    "birth_certificate": {
        "en": "Birth Certificate",
        "hi": "जन्म प्रमाण पत्र",
        "mr": "जन्म दाखला",
    },
    "shg_passbook": {
        "en": "Self Help Group Passbook",
        "hi": "स्वयं सहायता समूह पासबुक",
        "mr": "बचत गट पासबुक",
    },
}

STATUS_LABELS: Dict[str, Dict[str, str]] = {
    DOC_STATE_UPLOADED: {
        "en": "Uploaded",
        "hi": "अपलोड किया गया",
        "mr": "अपलोड केलेले",
    },
    DOC_STATE_OCR_PROCESSING: {
        "en": "Processing OCR",
        "hi": "OCR प्रक्रियाधीन",
        "mr": "OCR प्रक्रिया सुरू",
    },
    DOC_STATE_EXTRACTED: {
        "en": "Awaiting Citizen Review",
        "hi": "नागरिक समीक्षा लंबित",
        "mr": "नागरिक तपासणी प्रलंबित",
    },
    DOC_STATE_AWAITING_REVIEW: {
        "en": "Awaiting Citizen Review",
        "hi": "नागरिक समीक्षा लंबित",
        "mr": "नागरिक तपासणी प्रलंबित",
    },
    DOC_STATE_REVIEWED: {
        "en": "Reviewed (Unverified)",
        "hi": "समीक्षित (सत्यापन शेष)",
        "mr": "तपासलेले (पडताळणी बाकी)",
    },
    DOC_STATE_VERIFIED: {
        "en": "Verified",
        "hi": "सत्यापित",
        "mr": "पडताळलेले",
    },
    DOC_STATE_REJECTED: {
        "en": "Rejected",
        "hi": "अस्वीकृत",
        "mr": "नाकारलेले",
    },
    "missing": {
        "en": "Missing",
        "hi": "अनुपलब्ध",
        "mr": "उपलब्ध नाही",
    },
    "waived": {
        "en": "Exempt (Conditional)",
        "hi": "सशर्त छूट प्राप्त",
        "mr": "अटीनुसार सूट",
    },
}


def get_localized_doc_label(doc_type: str, lang: str = "en") -> str:
    norm = (doc_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    entry = DOCUMENT_TYPE_LABELS.get(norm)
    if entry:
        return entry.get(lang) or entry["en"]
    return doc_type.replace("_", " ").title()


def get_localized_status_label(status_key: str, lang: str = "en") -> str:
    entry = STATUS_LABELS.get(status_key)
    if entry:
        return entry.get(lang) or entry["en"]
    return status_key.replace("_", " ").title()


def canonicalize_document_type(doc_type: str) -> str:
    """Normalize aliases like 'aadhaar' -> 'aadhaar_card', 'marksheet_12' -> 'marksheet_12th'."""
    norm = (doc_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if norm in ("aadhaar", "aadhar", "aadhar_card", "aadhaar_card"):
        return "aadhaar_card"
    if norm in ("marksheet_12", "marksheet_12th"):
        return "marksheet_12th"
    if norm in ("marksheet_7", "marksheet_7th"):
        return "marksheet_7th"
    if norm in ("educational_certificate", "education_certificate"):
        return "education_certificate"
    if norm in ("mgnrega_job_card", "job_card"):
        return "job_card"
    if norm in ("bank_account", "bank_passbook"):
        return "bank_passbook"
    return norm


def get_equivalent_doc_types(required_type: str) -> Tuple[str, ...]:
    """Return all vault document_type keys that legitimately satisfy `required_type`."""
    norm = (required_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if norm in DOCUMENT_EQUIVALENCE_GROUPS:
        return DOCUMENT_EQUIVALENCE_GROUPS[norm]
    canon = canonicalize_document_type(norm)
    if canon in DOCUMENT_EQUIVALENCE_GROUPS:
        return DOCUMENT_EQUIVALENCE_GROUPS[canon]
    return (norm, canon)


def doc_types_match(required_type: str, vault_doc_type: str) -> bool:
    """Checks if a document in citizen vault satisfies a scheme requirement."""
    req_norm = (required_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    vault_norm = (vault_doc_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not req_norm or not vault_norm:
        return False
    if req_norm == vault_norm:
        return True
    if canonicalize_document_type(req_norm) == canonicalize_document_type(vault_norm):
        return True
    return vault_norm in get_equivalent_doc_types(req_norm)


def normalize_vault_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes document schema fields and strictly prevents legacy/unverified uploads
    from masquerading as verified.
    """
    normalized = dict(doc)
    raw_lifecycle = normalized.get("lifecycle_status") or normalized.get("verification_status")
    raw_review = normalized.get("review_status")

    # Determine canonical lifecycle_status honestly
    if raw_lifecycle in (
        DOC_STATE_UPLOADED,
        DOC_STATE_OCR_PROCESSING,
        DOC_STATE_EXTRACTED,
        DOC_STATE_AWAITING_REVIEW,
        DOC_STATE_REVIEWED,
        DOC_STATE_VERIFIED,
        DOC_STATE_REJECTED,
    ):
        lifecycle = raw_lifecycle
    elif raw_review == "verified":
        lifecycle = DOC_STATE_VERIFIED
    elif raw_review in ("reviewed", "accepted"):
        lifecycle = DOC_STATE_REVIEWED
    elif raw_review == "rejected":
        lifecycle = DOC_STATE_REJECTED
    elif normalized.get("ocr_status") == "completed":
        lifecycle = DOC_STATE_AWAITING_REVIEW
    else:
        lifecycle = DOC_STATE_UPLOADED

    normalized["lifecycle_status"] = lifecycle
    normalized["verification_status"] = lifecycle

    # Sync backward-compatible review_status cleanly
    if lifecycle == DOC_STATE_VERIFIED:
        normalized["review_status"] = "verified"
    elif lifecycle == DOC_STATE_REVIEWED:
        normalized["review_status"] = "reviewed"
    elif lifecycle == DOC_STATE_REJECTED:
        normalized["review_status"] = "rejected"
    else:
        normalized["review_status"] = "pending_review"

    normalized.setdefault("ocr_status", "limited")
    normalized.setdefault("extracted_fields", {})
    normalized.setdefault("reviewed_fields", {})
    normalized.setdefault("audit_trail", [])
    return normalized


def validate_uploaded_file_bytes(
    filename: Optional[str],
    content_type: Optional[str],
    raw_bytes: bytes,
) -> Dict[str, Any]:
    """
    Validates uploaded file extension, size limits, and binary magic bytes / structure.
    Raises ValueError with clear reason if invalid or corrupted.
    """
    if not raw_bytes or len(raw_bytes) == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file exceeds maximum allowed size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    safe_name = (filename or "document").strip()
    ext = Path(safe_name).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension '.{ext}'. Allowed formats: PDF, PNG, JPG, JPEG.")

    # Verify magic bytes strictly so renamed text/executable files cannot pass
    if ext == "pdf":
        if not raw_bytes.lstrip().startswith(b"%PDF-"):
            raise ValueError("Invalid PDF file signature. The uploaded file does not contain a valid PDF header.")
        return {
            "extension": "pdf",
            "detected_mime": "application/pdf",
            "size_bytes": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }

    # Image verification with Pillow
    if ext == "png" and not raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG image signature. File may be corrupted or mislabeled.")
    if ext in ("jpg", "jpeg") and not raw_bytes.startswith(b"\xff\xd8\xff"):
        raise ValueError("Invalid JPEG image signature. File may be corrupted or mislabeled.")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(raw_bytes)) as img2:
            width, height = img2.size
            img_format = (img2.format or ext).upper()
            if width < 10 or height < 10:
                raise ValueError("Uploaded image dimensions are too small to be a readable document.")
    except ValueError:
        raise
    except (UnidentifiedImageError, Exception) as exc:
        raise ValueError(f"Uploaded image could not be decoded or is corrupted: {exc}")

    return {
        "extension": ext,
        "detected_mime": f"image/{'jpeg' if ext in ('jpg', 'jpeg') else 'png'}",
        "size_bytes": len(raw_bytes),
        "width": width,
        "height": height,
        "image_format": img_format,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }


def _extract_text_from_pdf_bytes(raw_bytes: bytes) -> str:
    """
    Lightweight stdlib PDF text extractor: reads uncompressed text operators and
    FlateDecode streams safely without crashing on binary content.
    """
    extracted_chunks: List[str] = []

    def _pull_tj_text(content_bytes: bytes) -> None:
        try:
            text_str = content_bytes.decode("latin-1", errors="ignore")
        except Exception:
            return
        # Match literal strings inside (...) Tj or TJ arrays
        for m in re.finditer(r"\(([^()\\]{2,200})\)\s*(?:Tj|'|\"|TJ)", text_str):
            candidate = m.group(1).strip()
            if candidate and any(ch.isalnum() for ch in candidate):
                extracted_chunks.append(candidate)

    # First scan top-level streams
    _pull_tj_text(raw_bytes)
    for m in re.finditer(b"stream\r?\n(.*?)\r?\nendstream", raw_bytes, re.DOTALL):
        stream_data = m.group(1)
        if not stream_data:
            continue
        _pull_tj_text(stream_data)
        try:
            decompressed = zlib.decompress(stream_data)
            _pull_tj_text(decompressed)
        except Exception:
            pass

    return " ".join(extracted_chunks).strip()


def _parse_genuine_fields_from_text(document_type: str, text: str) -> Dict[str, Any]:
    """
    Extracts structured attributes strictly from actual text present in the uploaded file.
    Never fabricates values that are not observed in `text`.
    """
    fields: Dict[str, Any] = {}
    if not text:
        return fields

    canon = canonicalize_document_type(document_type)

    # 1. Dates (DD/MM/YYYY or YYYY-MM-DD or DD-MM-YYYY)
    date_matches = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", text)
    if date_matches:
        fields["detected_dates"] = date_matches[:3]

    # 2. Aadhaar 12-digit number (spaced or contiguous)
    if canon == "aadhaar_card":
        aadhaar_match = re.search(r"\b([2-9]\d{3}\s?\d{4}\s?\d{4})\b", text)
        if aadhaar_match:
            fields["document_number"] = re.sub(r"\s+", "", aadhaar_match.group(1))

    # 3. PAN Card
    if canon == "pan_card":
        pan_match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text)
        if pan_match:
            fields["document_number"] = pan_match.group(1)

    # 4. IFSC Code & Bank Account
    if canon == "bank_passbook":
        ifsc_match = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text)
        if ifsc_match:
            fields["ifsc_code"] = ifsc_match.group(1)
        acct_match = re.search(r"(?:Account|A/c|Acc(?:ount)?\s*No\.?)[:\s-]*([0-9]{9,18})\b", text, re.IGNORECASE)
        if acct_match:
            fields["document_number"] = acct_match.group(1)

    # 5. Income Certificate annual amount
    if canon == "income_certificate":
        inc_match = re.search(r"(?:Rs\.?|INR|₹)\s*([0-9][0-9,]{2,9})", text, re.IGNORECASE)
        if inc_match:
            fields["declared_income"] = inc_match.group(1).replace(",", "")

    # 6. MGNREGA Job Card number
    if canon == "job_card":
        jc_match = re.search(r"\b([A-Z]{2}-\d{2}-\d{3}-\d{3}-\d{3}/\d{1,6})\b", text)
        if jc_match:
            fields["document_number"] = jc_match.group(1)

    # 7. Certificate / Registration Number generic pattern
    if "document_number" not in fields:
        cert_match = re.search(r"(?:Certificate|Cert|Reg|Reference|No\.?)[:\s#-]*([A-Z0-9/-]{6,24})", text, re.IGNORECASE)
        if cert_match:
            fields["document_number"] = cert_match.group(1)

    # 8. Name line if explicitly labeled
    name_match = re.search(r"(?:Name|Applicant|Holder)\s*[:\-]\s*([A-Za-z][A-Za-z\s]{2,50})", text, re.IGNORECASE)
    if name_match:
        fields["full_name_on_document"] = name_match.group(1).strip()

    return fields


def inspect_document_and_extract_ocr(
    document_type: str,
    raw_bytes: bytes,
    file_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Performs honest OCR / document structure inspection on uploaded bytes:
    - Extracts embedded text from text-based PDFs
    - Runs Tesseract OCR on images ONLY if tesseract binary is installed on the host
    - Otherwise honestly sets ocr_status='limited' with dimensions and metadata,
      requiring citizen review & entry without fabricating data.
    """
    ext = file_meta["extension"]
    raw_text = ""
    ocr_engine = "none"
    ocr_status = "limited"
    ocr_confidence = 0.0
    ocr_note = ""

    if ext == "pdf":
        raw_text = _extract_text_from_pdf_bytes(raw_bytes)
        ocr_engine = "pdf_stream_parser"
        if raw_text:
            ocr_status = "completed"
            ocr_confidence = 0.85
            ocr_note = "Embedded text extracted from PDF for citizen review."
        else:
            ocr_status = "limited"
            ocr_confidence = 0.0
            ocr_note = "Scanned or image-only PDF detected; automated OCR text unavailable. Please review and confirm details manually."
    else:
        tesseract_bin = shutil.which("tesseract")
        if tesseract_bin:
            try:
                import pytesseract

                with Image.open(io.BytesIO(raw_bytes)) as img:
                    raw_text = (pytesseract.image_to_string(img) or "").strip()
                ocr_engine = "tesseract"
                if raw_text:
                    ocr_status = "completed"
                    ocr_confidence = 0.78
                    ocr_note = "Text extracted via Tesseract OCR. Please verify accuracy."
                else:
                    ocr_status = "limited"
                    ocr_confidence = 0.1
                    ocr_note = "Image verified cleanly, but no legible text was detected by OCR. Please enter details manually."
            except Exception as exc:
                logger.warning("Tesseract execution failed: %s", exc)
                ocr_engine = "pillow_verified_only"
                ocr_status = "limited"
                ocr_note = "Image file integrity verified, automated OCR failed; manual citizen review required."
        else:
            # Check image info/comment metadata safely via Pillow
            meta_strings: List[str] = []
            try:
                with Image.open(io.BytesIO(raw_bytes)) as img:
                    for k, v in (img.info or {}).items():
                        if isinstance(v, str) and len(v) < 400:
                            meta_strings.append(f"{k}: {v}")
            except Exception:
                pass
            raw_text = " ".join(meta_strings).strip()
            ocr_engine = "pillow_structure_check"
            ocr_status = "limited"
            ocr_confidence = 0.0
            ocr_note = (
                f"Image format verified ({file_meta.get('width')}x{file_meta.get('height')} px). "
                "Local OCR binary not installed; citizen review and manual field confirmation required."
            )

    extracted_fields = _parse_genuine_fields_from_text(document_type, raw_text)
    if raw_text:
        extracted_fields["raw_text_preview"] = raw_text[:400]

    # Always transition to awaiting_citizen_review or extracted — NEVER verified!
    lifecycle_status = DOC_STATE_EXTRACTED if (ocr_status == "completed" and extracted_fields) else DOC_STATE_AWAITING_REVIEW

    return {
        "ocr_status": ocr_status,
        "ocr_engine": ocr_engine,
        "ocr_confidence": ocr_confidence,
        "ocr_note": ocr_note,
        "extracted_fields": extracted_fields,
        "lifecycle_status": lifecycle_status,
    }


def save_document_file(user_id: str, doc_id: str, extension: str, raw_bytes: bytes) -> str:
    """Persist uploaded document bytes safely under user-isolated vault directory."""
    safe_user_dir = VAULT_STORAGE_ROOT / str(user_id)
    safe_user_dir.mkdir(parents=True, exist_ok=True)
    file_path = safe_user_dir / f"{doc_id}.{extension}"
    file_path.write_bytes(raw_bytes)
    return str(file_path.relative_to(VAULT_STORAGE_ROOT))


def resolve_document_file_path(doc: Dict[str, Any], user_id: str) -> Optional[Path]:
    """Resolves absolute safe path only if owned by user and residing within VAULT_STORAGE_ROOT."""
    rel = doc.get("storage_rel_path")
    if not rel:
        return None
    candidate = (VAULT_STORAGE_ROOT / rel).resolve()
    root_resolved = VAULT_STORAGE_ROOT.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if str(doc.get("user_id")) != str(user_id):
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def delete_stored_file(doc: Dict[str, Any], user_id: str) -> None:
    path = resolve_document_file_path(doc, user_id)
    if path:
        try:
            path.unlink()
        except Exception as exc:
            logger.warning("Failed to delete vault file %s: %s", path, exc)


def recalculate_profile_doc_flags(profile_data: Dict[str, Any]) -> None:
    """
    Synchronizes profile_data boolean flags strictly from VERIFIED documents only.
    Never sets verification flags from uploaded, unreviewed, or rejected documents.
    """
    docs = [normalize_vault_document(d) for d in profile_data.get("documents", [])]
    verified_types = {
        canonicalize_document_type(d.get("document_type", ""))
        for d in docs
        if d.get("lifecycle_status") == DOC_STATE_VERIFIED
    }

    profile_data["has_aadhaar"] = "aadhaar_card" in verified_types
    profile_data["land_records_verified"] = any(
        t in verified_types for t in ("land_records", "land_possession")
    )
    profile_data["has_bank_account"] = "bank_passbook" in verified_types
    profile_data["aadhaar_seeded_bank_account"] = (
        "bank_passbook" in verified_types and "aadhaar_card" in verified_types
    )
    profile_data["income_certificate_verified"] = "income_certificate" in verified_types
    profile_data["caste_certificate_verified"] = "caste_certificate" in verified_types


def apply_citizen_review(
    doc: Dict[str, Any],
    reviewed_fields: Dict[str, Any],
    confirmed_accurate: bool,
) -> Dict[str, Any]:
    """
    Records citizen inspection and corrections to extracted document fields.
    Transitions document to `reviewed` (NEVER automatically to `verified`).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = normalize_vault_document(doc)

    cleaned_fields = {}
    for k, v in reviewed_fields.items():
        if v is None:
            cleaned_fields[k] = ""
        elif isinstance(v, str):
            val = v.strip()
            cleaned_fields[k] = "" if val.lower() in ("null", "undefined", "none") else val
        else:
            cleaned_fields[k] = v

    doc["reviewed_fields"] = cleaned_fields
    doc["citizen_confirmed_accurate"] = bool(confirmed_accurate)

    if confirmed_accurate:
        doc["lifecycle_status"] = DOC_STATE_REVIEWED
        doc["verification_status"] = DOC_STATE_REVIEWED
        doc["review_status"] = "reviewed"
        doc["rejection_reason"] = None
    else:
        doc["lifecycle_status"] = DOC_STATE_AWAITING_REVIEW
        doc["verification_status"] = DOC_STATE_AWAITING_REVIEW
        doc["review_status"] = "pending_review"

    doc["reviewed_at"] = now_iso
    doc["updated_at"] = now_iso

    audit = list(doc.get("audit_trail", []))
    audit.append({
        "timestamp": now_iso,
        "action": "CITIZEN_REVIEW_SAVED",
        "details": f"Citizen reviewed fields (confirmed_accurate={confirmed_accurate}). Status: {doc['lifecycle_status']}.",
    })
    doc["audit_trail"] = audit
    return doc


def _parse_iso_or_indian_date(raw_date: str) -> Optional[date]:
    s = (raw_date or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def verify_reviewed_document(
    doc: Dict[str, Any],
    profile_full_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Executes deterministic verification checks on a citizen-reviewed document.
    - Must already be in `reviewed` (or `verified`/`rejected` re-evaluation) — cannot verify unreviewed raw upload.
    - Checks mandatory fields for that document type, format patterns, expiry date, and citizen name match.
    - Transitions strictly to `verified` (if all checks pass) or `rejected` (with clear reasons).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = normalize_vault_document(doc)
    reasons: List[str] = []

    if doc["lifecycle_status"] in (DOC_STATE_UPLOADED, DOC_STATE_OCR_PROCESSING, DOC_STATE_EXTRACTED, DOC_STATE_AWAITING_REVIEW):
        reasons.append("Citizen review must be completed before verification can run.")
        return doc, reasons

    if doc.get("upload_status") != "uploaded":
        reasons.append("Valid uploaded file is required for verification.")

    fields = dict(doc.get("reviewed_fields") or {})
    canon = canonicalize_document_type(doc.get("document_type", ""))
    doc_num = str(fields.get("document_number") or "").strip()
    holder_name = str(fields.get("full_name_on_document") or "").strip()
    authority = str(fields.get("issuing_authority") or "").strip()
    issue_date_str = str(fields.get("issue_date") or "").strip()
    expiry_date_str = str(fields.get("expiry_date") or "").strip()

    # 1. Check expiry date if provided
    if expiry_date_str:
        exp_date = _parse_iso_or_indian_date(expiry_date_str)
        if not exp_date:
            reasons.append("Invalid expiry date format. Use YYYY-MM-DD or DD/MM/YYYY.")
        elif exp_date < date.today():
            reasons.append(f"Document expired on {exp_date.isoformat()}.")

    # 2. Check holder name & consistency with profile
    if not holder_name:
        reasons.append("Name as printed on the document is required during review.")
    elif profile_full_name and profile_full_name.strip().lower() not in ("citizen", ""):
        profile_tokens = {t.lower() for t in re.findall(r"[A-Za-z\u0900-\u097F]{2,}", profile_full_name)}
        doc_tokens = {t.lower() for t in re.findall(r"[A-Za-z\u0900-\u097F]{2,}", holder_name)}
        if profile_tokens and doc_tokens and profile_tokens.isdisjoint(doc_tokens):
            reasons.append(
                f"Name on document ('{holder_name}') does not match citizen profile name ('{profile_full_name}')."
            )

    # 3. Document-type specific deterministic rules
    if canon == "aadhaar_card":
        digits = re.sub(r"\s+", "", doc_num)
        if not re.match(r"^[2-9][0-9]{11}$", digits):
            reasons.append("Valid 12-digit Aadhaar number (starting with 2-9) is required.")
        elif len(set(digits)) == 1:
            reasons.append("Aadhaar number cannot consist of a single repeated digit.")
    elif canon == "bank_passbook":
        acct = re.sub(r"\s+", "", doc_num)
        ifsc = str(fields.get("ifsc_code") or "").strip().upper()
        if not re.match(r"^[0-9]{9,18}$", acct):
            reasons.append("Valid 9 to 18-digit bank account number is required.")
        if not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc):
            reasons.append("Valid 11-character bank IFSC code (e.g. SBIN0001234) is required.")
    elif canon == "pan_card":
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", doc_num.upper()):
            reasons.append("Valid 10-character PAN number is required.")
    elif canon == "income_certificate":
        if not doc_num or len(doc_num) < 4:
            reasons.append("Valid Income Certificate reference number is required.")
        if not authority:
            reasons.append("Issuing revenue authority (e.g. Tahsildar / SDM) is required.")
        if issue_date_str:
            iss = _parse_iso_or_indian_date(issue_date_str)
            if not iss:
                reasons.append("Invalid issue date format.")
            elif iss > date.today():
                reasons.append("Issue date cannot be in the future.")
    else:
        # Generic certificate verification rules
        if not doc_num or len(doc_num) < 3:
            reasons.append("Document / Certificate reference number is required for verification.")
        if canon in ("caste_certificate", "domicile_certificate", "land_records", "land_possession", "job_card", "death_certificate") and not authority:
            reasons.append("Issuing authority name is required.")

    audit = list(doc.get("audit_trail", []))
    if reasons:
        doc["lifecycle_status"] = DOC_STATE_REJECTED
        doc["verification_status"] = DOC_STATE_REJECTED
        doc["review_status"] = "rejected"
        doc["rejection_reason"] = "; ".join(reasons)
        doc["verified_at"] = None
        doc["updated_at"] = now_iso
        audit.append({
            "timestamp": now_iso,
            "action": "VERIFICATION_REJECTED",
            "details": doc["rejection_reason"],
        })
    else:
        doc["lifecycle_status"] = DOC_STATE_VERIFIED
        doc["verification_status"] = DOC_STATE_VERIFIED
        doc["review_status"] = "verified"
        doc["rejection_reason"] = None
        doc["verified_at"] = now_iso
        doc["updated_at"] = now_iso
        audit.append({
            "timestamp": now_iso,
            "action": "VERIFICATION_PASSED",
            "details": "Deterministic format, integrity, and profile consistency checks passed.",
        })

    doc["audit_trail"] = audit
    return doc, reasons

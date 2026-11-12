"""
Phase 7: Universal Application Review, Explicit Citizen Confirmation & Safe Submission Orchestration Service.

Guarantees:
1. Complete field-by-field application review with provenance (citizen-entered, profile, verified document),
   missing mandatory fields, and unresolved conflict blockers across all structured schemes.
2. Strict application lifecycle state machine:
   draft -> validated -> awaiting_confirmation -> confirmed -> submitting -> submitted | submission_failed
3. Cryptographic version/snapshot hashing so citizen confirmation binds strictly to the exact reviewed
   application version and is automatically invalidated if form data, profile data, or documents change.
4. Verified portal integration adapters ONLY where available and authorized; never simulates successful
   government submission or invents external transaction/reference IDs.
5. Idempotency keys, duplicate-submission prevention, timeout/failure handling, and strict blind-retry
   blocking when a previous submission outcome is uncertain.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.form_schemas import (
    SCHEME_CODE_ALIASES,
    get_form_schema_for_scheme,
    get_unavailable_schema_payload,
)
from app.models.application_record import ApplicationRecord
from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.portal_registry_service import (
    SUBMISSION_MODE_DIRECT_API,
    SUBMISSION_MODE_MANUAL,
    SUBMISSION_MODE_PORTAL_ASSISTED,
    get_portal_integration_entry,
)
from app.services.prefill_service import (
    SOURCE_CITIZEN_OVERRIDE,
    SOURCE_CONVERSATION,
    SOURCE_EXISTING_DRAFT,
    SOURCE_PRIOR_DRAFT,
    SOURCE_PROFILE,
    SOURCE_SYSTEM_DEFAULT,
    SOURCE_VERIFIED_DOC,
    clean_scalar,
    is_empty_value,
    run_universal_prefill,
)
from app.services.readiness_service import evaluate_application_readiness

logger = logging.getLogger(__name__)

# ── Part 5: Canonical Application States & Strict Transition Graph ────────────

STATE_DRAFT = "draft"
STATE_VALIDATED = "validated"
STATE_AWAITING_CONFIRMATION = "awaiting_confirmation"
STATE_CONFIRMED = "confirmed"
STATE_SUBMITTING = "submitting"
STATE_SUBMITTED = "submitted"
STATE_PORTAL_SUBMITTED = "portal_submitted"
STATE_SUBMISSION_FAILED = "submission_failed"
STATE_SUBMISSION_UNKNOWN = "submission_unknown"

# Legacy Phase 5 alias normalized smoothly without losing strict invariants
LEGACY_STATE_VALIDATION_FAILED = "validation_failed"

VALID_APPLICATION_STATES = {
    STATE_DRAFT,
    STATE_VALIDATED,
    STATE_AWAITING_CONFIRMATION,
    STATE_CONFIRMED,
    STATE_SUBMITTING,
    STATE_SUBMITTED,
    STATE_PORTAL_SUBMITTED,
    STATE_SUBMISSION_FAILED,
    STATE_SUBMISSION_UNKNOWN,
}

ALLOWED_STATE_TRANSITIONS: Dict[str, set[str]] = {
    STATE_DRAFT: {STATE_DRAFT, STATE_VALIDATED},
    LEGACY_STATE_VALIDATION_FAILED: {STATE_DRAFT, STATE_VALIDATED},
    STATE_VALIDATED: {STATE_DRAFT, STATE_VALIDATED, STATE_AWAITING_CONFIRMATION},
    STATE_AWAITING_CONFIRMATION: {STATE_DRAFT, STATE_VALIDATED, STATE_AWAITING_CONFIRMATION, STATE_CONFIRMED},
    STATE_CONFIRMED: {STATE_DRAFT, STATE_VALIDATED, STATE_CONFIRMED, STATE_SUBMITTING, STATE_PORTAL_SUBMITTED},
    STATE_SUBMITTING: {STATE_SUBMITTED, STATE_SUBMISSION_FAILED, STATE_SUBMISSION_UNKNOWN},
    STATE_SUBMITTED: set(),  # Terminal once verified external portal accepted submission
    STATE_PORTAL_SUBMITTED: {STATE_PORTAL_SUBMITTED},
    STATE_SUBMISSION_FAILED: {STATE_DRAFT, STATE_VALIDATED, STATE_AWAITING_CONFIRMATION, STATE_CONFIRMED, STATE_SUBMITTING, STATE_PORTAL_SUBMITTED},
    STATE_SUBMISSION_UNKNOWN: {STATE_SUBMITTED, STATE_CONFIRMED, STATE_SUBMISSION_FAILED},
}


def validate_state_transition(current_state: str, target_state: str) -> None:
    """Enforce strict application lifecycle state transitions cleanly."""
    cur = (current_state or STATE_DRAFT).strip().lower()
    tgt = (target_state or "").strip().lower()
    if tgt not in VALID_APPLICATION_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported lifecycle target state '{target_state}'.",
        )
    allowed = ALLOWED_STATE_TRANSITIONS.get(cur)
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown current lifecycle state '{current_state}'.",
        )
    if tgt not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid application state transition: '{cur}' -> '{tgt}'.",
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _localize(lang: str, en: str, hi: str, mr: str) -> str:
    if lang == "hi":
        return hi
    if lang == "mr":
        return mr
    return en


def is_verified_government_submission(app: Optional[Dict[str, Any]]) -> bool:
    """
    Return True ONLY when an application record carries authoritative proof of
    acceptance from an integrated official government portal (never legacy synthetic
    SAATHI/READY handoff packets or unverified records).
    """
    if not isinstance(app, dict):
        return False
    if (app.get("lifecycle_state") or "").strip().lower() != STATE_SUBMITTED:
        return False
    ext_ref = str(app.get("external_reference_id") or "").strip()
    source = str(app.get("submission_source") or "").strip().lower()
    if not ext_ref or source != "official_integration":
        return False
    if ext_ref.upper().startswith("SAATHI/"):
        return False
    return True


def sanitize_legacy_unverified_submission(
    target_app: Optional[Dict[str, Any]],
    readiness: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Quarantine historical/synthetic 'submitted' records that lack authoritative
    official_integration + external_reference_id proof (e.g. legacy Phase 5
    portal_handoff records carrying SAATHI/READY/... references).
    Preserves the underlying record cleanly while ensuring it can never surface
    as a genuine government submission. Returns True if quarantined/sanitized.
    """
    if not isinstance(target_app, dict):
        return False
    cur_state = (target_app.get("lifecycle_state") or "").strip().lower()
    if cur_state != STATE_SUBMITTED:
        # Ensure already-flagged legacy records never leak synthetic external refs
        if target_app.get("legacy_synthetic_submission"):
            target_app["is_verified_government_submission"] = False
            target_app["external_reference_id"] = None
            target_app["reference_number"] = None
        return False
    if is_verified_government_submission(target_app):
        target_app["is_verified_government_submission"] = True
        target_app["legacy_synthetic_submission"] = False
        return False

    legacy_ref = (
        target_app.get("legacy_reference_number")
        or target_app.get("reference_number")
    )
    if legacy_ref and str(legacy_ref).strip():
        target_app["legacy_reference_number"] = str(legacy_ref).strip()

    v_res = readiness if isinstance(readiness, dict) else target_app.get("validation_result")
    passed_validation = bool(isinstance(v_res, dict) and v_res.get("passed") is True)

    target_app["legacy_synthetic_submission"] = True
    target_app["is_verified_government_submission"] = False
    target_app["external_reference_id"] = None
    target_app["reference_number"] = None
    target_app["submission_source"] = "legacy_handoff_unverified"
    target_app["submission_outcome"] = "legacy_unverified"
    target_app["submission_status"] = "legacy_unverified"
    target_app["submitted_at"] = None
    target_app["lifecycle_state"] = STATE_VALIDATED if passed_validation else STATE_DRAFT
    target_app["status"] = "Legacy Packet (Unverified)" if passed_validation else "Incomplete"
    return True


# ── Portal Integration Contracts & Registry ───────────────────────────────────

@dataclass
class PortalSubmissionResult:
    """Structured external portal submission result returned ONLY by authorized adapters."""
    outcome: str  # "submitted" | "failed_retryable" | "failed_permanent" | "uncertain"
    external_reference_id: Optional[str] = None
    portal_status: Optional[str] = None
    message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=_now_iso)


@dataclass
class PortalReconciliationResult:
    """Result from checking an uncertain in-flight submission with an official portal."""
    resolved_outcome: str  # "submitted" | "not_received" | "still_uncertain"
    external_reference_id: Optional[str] = None
    portal_status: Optional[str] = None
    message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


class PortalIntegrationAdapter(Protocol):
    """Protocol implemented by verified external scheme submission integrations."""
    provider_name: str
    is_authorized: bool

    def submit(
        self,
        application: Dict[str, Any],
        idempotency_key: str,
        lang: str = "en",
    ) -> PortalSubmissionResult:
        ...

    def check_status(
        self,
        application_id: str,
        idempotency_key: str,
        attempt_id: str,
    ) -> PortalReconciliationResult:
        ...


# Global adapter registry: empty by default because NO unverified simulated integrations are allowed.
_PORTAL_ADAPTER_REGISTRY: Dict[str, PortalIntegrationAdapter] = {}


def register_portal_adapter(scheme_code: str, adapter: PortalIntegrationAdapter) -> None:
    """Register an authorized external submission adapter for a verified scheme code."""
    key = SCHEME_CODE_ALIASES.get((scheme_code or "").strip().upper(), (scheme_code or "").strip().upper())
    _PORTAL_ADAPTER_REGISTRY[key] = adapter


def unregister_portal_adapter(scheme_code: str) -> None:
    key = SCHEME_CODE_ALIASES.get((scheme_code or "").strip().upper(), (scheme_code or "").strip().upper())
    _PORTAL_ADAPTER_REGISTRY.pop(key, None)


def clear_registered_portal_adapters() -> None:
    _PORTAL_ADAPTER_REGISTRY.clear()


def get_portal_adapter(scheme_code: str) -> Optional[PortalIntegrationAdapter]:
    key = SCHEME_CODE_ALIASES.get((scheme_code or "").strip().upper(), (scheme_code or "").strip().upper())
    adapter = _PORTAL_ADAPTER_REGISTRY.get(key)
    if adapter is not None and getattr(adapter, "is_authorized", False):
        return adapter
    return None


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _is_valid_official_reference(ref_val: Optional[str], internal_app_id: str = "") -> bool:
    """Validate that an external/official portal reference is real and never synthetic/internal."""
    if not ref_val or not isinstance(ref_val, str):
        return False
    cleaned = ref_val.strip()
    if len(cleaned) < 3:
        return False
    upper = cleaned.upper()
    if upper.startswith("SAATHI/") or upper.startswith("APP-DRAFT-") or upper.startswith("APP-"):
        return False
    if internal_app_id and cleaned.lower() == str(internal_app_id).strip().lower():
        return False
    return True


def build_normalized_application_record(
    target_app: Dict[str, Any],
    citizen_id: Any,
    portal_entry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build canonical Step 5 Application Record shape strictly separating
    internal application_id from official_reference_number.
    """
    portal = portal_entry or get_portal_integration_entry(
        target_app.get("scheme_code") or target_app.get("scheme_id") or ""
    )
    app_id = str(target_app.get("id") or "")
    verified = is_verified_government_submission(target_app)
    raw_ref = target_app.get("official_reference_number") or target_app.get("external_reference_id")
    official_ref = (
        str(raw_ref).strip()
        if (verified or target_app.get("lifecycle_state") == STATE_PORTAL_SUBMITTED)
        and _is_valid_official_reference(str(raw_ref or ""), app_id)
        else None
    )
    submission_method = (
        target_app.get("submission_method")
        or portal.get("submission_method")
        or SUBMISSION_MODE_PORTAL_ASSISTED
    )
    return {
        "citizen_id": str(citizen_id or target_app.get("user_id") or ""),
        "scheme_id": target_app.get("scheme_id"),
        "scheme_code": portal.get("scheme_code") or target_app.get("scheme_code"),
        "scheme_name": target_app.get("scheme_name") or portal.get("scheme_name"),
        "application_id": app_id,
        "official_reference_number": official_ref,
        "reference_source": target_app.get("reference_source") or ("official_integration" if verified else None),
        "submission_date": target_app.get("submission_date") or target_app.get("submitted_at"),
        "portal_url": target_app.get("portal_url") or portal.get("official_application_url") or target_app.get("official_url"),
        "tracking_url": target_app.get("tracking_url") or portal.get("tracking_url"),
        "application_status": target_app.get("lifecycle_state") or STATE_DRAFT,
        "submission_method": submission_method,
    }


def sync_application_record_to_db(
    db: Optional[Session],
    target_app: Dict[str, Any],
    citizen_id: Any,
    portal_entry: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Upsert normalized Step 5 ApplicationRecord row into PostgreSQL/SQLite without
    affecting MockSession-based unit tests or raising FK errors for unseeded schemes.
    """
    if db is None or not isinstance(db, Session) or not target_app or not target_app.get("id"):
        return
    try:
        citizen_uuid = citizen_id if isinstance(citizen_id, uuid.UUID) else uuid.UUID(str(citizen_id))
    except Exception:
        return

    norm = build_normalized_application_record(target_app, citizen_uuid, portal_entry)

    scheme_uuid: Optional[uuid.UUID] = None
    raw_sid = target_app.get("scheme_id")
    if raw_sid:
        try:
            cand = uuid.UUID(str(raw_sid))
            if db.query(Scheme.id).filter(Scheme.id == cand).first() is not None:
                scheme_uuid = cand
        except Exception:
            scheme_uuid = None
    if scheme_uuid is None and norm.get("scheme_code"):
        try:
            row = db.query(Scheme.id).filter(Scheme.scheme_code == norm["scheme_code"]).first()
            if row is not None:
                scheme_uuid = row[0]
        except Exception:
            scheme_uuid = None

    try:
        with db.begin_nested():
            rec = (
                db.query(ApplicationRecord)
                .filter(
                    ApplicationRecord.application_id == norm["application_id"],
                    ApplicationRecord.citizen_id == citizen_uuid,
                )
                .first()
            )
            if rec is None:
                rec = ApplicationRecord(
                    application_id=norm["application_id"],
                    citizen_id=citizen_uuid,
                )
                db.add(rec)
            rec.scheme_id = scheme_uuid
            rec.scheme_code = str(norm["scheme_code"] or "UNKNOWN")[:100]
            rec.scheme_name = str(norm["scheme_name"] or norm["scheme_code"] or "Scheme")[:255]
            rec.official_reference_number = norm["official_reference_number"]
            rec.reference_source = norm["reference_source"]
            rec.submission_date = _parse_iso_dt(norm["submission_date"])
            rec.portal_url = str(norm["portal_url"] or "https://www.india.gov.in/")[:500]
            rec.tracking_url = str(norm["tracking_url"] or "")[:500] or None
            rec.application_status = str(norm["application_status"] or STATE_DRAFT)[:64]
            rec.submission_method = str(norm["submission_method"] or SUBMISSION_MODE_PORTAL_ASSISTED)[:64]
            rec.confirmation_version = target_app.get("confirmed_version")
            rec.confirmation_hash = target_app.get("confirmed_hash")
            rec.confirmed_at = _parse_iso_dt(target_app.get("confirmed_at"))
            rec.form_data = dict(target_app.get("form_data") or {})
            rec.metadata_json = {
                "version": target_app.get("version"),
                "data_hash": target_app.get("data_hash"),
                "portal_notes": target_app.get("portal_notes"),
                "last_audit": (target_app.get("audit_trail") or [])[-5:],
            }
            db.flush()
    except Exception as exc:
        logger.debug("Non-blocking ApplicationRecord DB sync skipped: %s", exc)


# ── Deterministic Snapshot Hashing & Confirmation Invalidation ───────────────

def _canonical_form_payload(form_data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for k in sorted((form_data or {}).keys()):
        v = clean_scalar((form_data or {}).get(k))
        if not is_empty_value(v):
            cleaned[k] = v
    return cleaned


def _verified_docs_fingerprint(profile: Optional[UserProfile]) -> List[Dict[str, str]]:
    if not profile or not profile.profile_data:
        return []
    docs = []
    for d in (profile.profile_data or {}).get("documents", []) or []:
        if not isinstance(d, dict):
            continue
        l_status = (d.get("lifecycle_status") or d.get("verification_status") or "").strip().lower()
        docs.append({
            "id": str(d.get("id") or ""),
            "type": str(d.get("document_type") or ""),
            "status": l_status,
            "sha256": str(d.get("sha256") or ""),
            "verified_at": str(d.get("verified_at") or ""),
        })
    docs.sort(key=lambda item: (item["type"], item["id"]))
    return docs


def compute_application_snapshot_hash(
    scheme_code: str,
    form_data: Dict[str, Any],
    resolved_conflicts: Optional[Dict[str, str]],
    profile: Optional[UserProfile],
) -> str:
    """
    Compute deterministic SHA-256 digest representing the exact reviewed application snapshot:
    - Canonical scheme code
    - Normalized form data values
    - Resolved conflict selections
    - Citizen profile core identity/income/location attributes
    - Vault document lifecycle states & SHA-256 checksums
    Any change to fields, profile, or Vault docs changes this hash and invalidates prior confirmation.
    """
    canon_scheme = SCHEME_CODE_ALIASES.get((scheme_code or "").strip().upper(), (scheme_code or "").strip().upper())
    profile_snapshot = {}
    if profile is not None:
        raw_income = getattr(profile, "annual_family_income", None)
        profile_snapshot = {
            "full_name": clean_scalar(getattr(profile, "full_name", "")),
            "age": getattr(profile, "age", None),
            "gender": clean_scalar(getattr(profile, "gender", "")),
            "state": clean_scalar(getattr(profile, "state", "")),
            "district": clean_scalar(getattr(profile, "district", "")),
            "residence_type": clean_scalar(getattr(profile, "residence_type", "")),
            "occupation": clean_scalar(getattr(profile, "occupation", "")),
            "annual_family_income": float(raw_income) if raw_income is not None else None,
        }

    payload = {
        "scheme_code": canon_scheme,
        "form_data": _canonical_form_payload(form_data),
        "resolved_conflicts": {str(k): str(v) for k, v in sorted((resolved_conflicts or {}).items())},
        "profile": profile_snapshot,
        "documents": _verified_docs_fingerprint(profile),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stamp_application_version_and_check_invalidation(
    target_app: Dict[str, Any],
    profile: Optional[UserProfile],
    increment_on_change: bool = True,
) -> Tuple[bool, str]:
    """
    Keep version & data_hash up to date. If prior citizen confirmation exists and the
    current application snapshot differs from confirmed_hash, immediately invalidate confirmation
    and revert lifecycle_state back to 'draft'.
    Returns (confirmation_was_invalidated, current_hash).
    """
    scheme_code = target_app.get("scheme_code") or target_app.get("scheme_id") or ""
    current_hash = compute_application_snapshot_hash(
        scheme_code=scheme_code,
        form_data=target_app.get("form_data") or {},
        resolved_conflicts=target_app.get("resolved_conflicts"),
        profile=profile,
    )
    prev_hash = target_app.get("data_hash")
    current_version = int(target_app.get("version") or 1)
    if prev_hash and prev_hash != current_hash and increment_on_change:
        current_version += 1

    target_app["version"] = current_version
    target_app["data_hash"] = current_hash

    invalidated = False
    confirmed_hash = target_app.get("confirmed_hash")
    if target_app.get("confirmed_at") and confirmed_hash and confirmed_hash != current_hash:
        now_iso = _now_iso()
        prev_confirmed_version = target_app.get("confirmed_version")
        target_app["confirmed_at"] = None
        target_app["confirmed_hash"] = None
        target_app["confirmed_version"] = None
        target_app["confirmation_invalidated_at"] = now_iso
        if isinstance(target_app.get("confirmation"), dict):
            target_app["confirmation"]["valid"] = False
            target_app["confirmation"]["invalidated_at"] = now_iso
            target_app["confirmation"]["invalidation_reason"] = (
                f"Application data or documents changed after confirmation of version v{prev_confirmed_version}."
            )
        if target_app.get("lifecycle_state") in (STATE_CONFIRMED, STATE_AWAITING_CONFIRMATION, STATE_VALIDATED):
            target_app["lifecycle_state"] = STATE_DRAFT
        audit = list(target_app.get("audit_trail") or [])
        audit.append({
            "timestamp": now_iso,
            "action": "CONFIRMATION_INVALIDATED",
            "actor": "system",
            "details": f"Invalidated confirmation for v{prev_confirmed_version} because snapshot hash changed.",
        })
        target_app["audit_trail"] = audit
        invalidated = True

    return invalidated, current_hash


# ── Ownership & Scheme Integrity Checks ──────────────────────────────────────

def assert_application_ownership_and_scheme(
    target_app: Optional[Dict[str, Any]],
    current_user: User,
    db: Optional[Session],
) -> Tuple[str, str]:
    """
    Strictly verify:
    1. Application exists and belongs to current_user (never cross-citizen leakage).
    2. Canonical scheme association matches verified schema registry.
    """
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    app_owner = target_app.get("user_id")
    if app_owner and str(app_owner) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    raw_scheme = str(target_app.get("scheme_code") or target_app.get("scheme_id") or "").strip()
    if not raw_scheme:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Application missing scheme association.")

    canon = SCHEME_CODE_ALIASES.get(raw_scheme.upper(), raw_scheme.upper())
    if db is not None and target_app.get("scheme_id"):
        try:
            s_uuid = uuid.UUID(str(target_app["scheme_id"]))
            scheme_obj = db.query(Scheme).filter(Scheme.id == s_uuid).first()
            if scheme_obj and scheme_obj.scheme_code:
                db_canon = SCHEME_CODE_ALIASES.get(scheme_obj.scheme_code.upper(), scheme_obj.scheme_code.upper())
                if canon and db_canon != canon:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Scheme association mismatch: '{canon}' vs '{db_canon}'.",
                    )
                canon = db_canon
        except ValueError:
            pass

    portal_url = target_app.get("official_url") or target_app.get("official_portal") or "https://india.gov.in"
    schema = get_form_schema_for_scheme(canon)
    if schema and schema.get("official_portal"):
        portal_url = schema["official_portal"]
    return canon, portal_url


# ── Part 1 & Part 2: Complete Review Payload Builder ─────────────────────────

def _source_category_label(source_tier: Optional[str], lang: str) -> Tuple[str, str]:
    """Map internal source_tier cleanly to (category_key, localized_badge)."""
    if source_tier == SOURCE_VERIFIED_DOC:
        return "verified_document", _localize(lang, "Verified Document", "सत्यापित दस्तावेज़", "पडताळलेला दस्तऐवज")
    if source_tier == SOURCE_PROFILE:
        return "profile_derived", _localize(lang, "Profile Derived", "प्रोफ़ाइल से प्राप्त", "प्रोफाईलवरून घेतलेले")
    if source_tier in (SOURCE_CITIZEN_OVERRIDE, SOURCE_EXISTING_DRAFT):
        return "citizen_entered", _localize(lang, "Citizen Entered", "नागरिक द्वारा दर्ज", "नागरिकाने भरलेले")
    if source_tier == SOURCE_CONVERSATION:
        return "citizen_entered", _localize(lang, "Citizen Session Answer", "सत्र उत्तर", "संभाषण उत्तर")
    if source_tier == SOURCE_PRIOR_DRAFT:
        return "citizen_entered", _localize(lang, "Saved Draft", "सहेजा गया ड्राफ्ट", "जतन केलेला मसुदा")
    if source_tier == SOURCE_SYSTEM_DEFAULT:
        return "system_default", _localize(lang, "System Standard", "सिस्टम मानक", "प्रणाली मानक")
    return "missing", _localize(lang, "Citizen Input Needed", "प्रविष्टि आवश्यक", "माहिती आवश्यक")


def build_application_review_summary(
    target_app: Dict[str, Any],
    profile: Optional[UserProfile],
    current_user: Optional[User],
    db: Optional[Session],
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Build the complete Part 1 + Part 2 + Part 3 + Part 4 review payload for an application.
    Never shows 'null'/'undefined' strings and surfaces all missing fields, provenance,
    conflicts, Vault verification state, version/hash, confirmation validity, and portal integration mode.
    """
    lang = lang if lang in ("en", "hi", "mr") else "en"
    sanitize_legacy_unverified_submission(target_app)
    scheme_code = target_app.get("scheme_code") or target_app.get("scheme_id") or ""
    canon_code = SCHEME_CODE_ALIASES.get(scheme_code.strip().upper(), scheme_code.strip().upper())

    stamp_application_version_and_check_invalidation(target_app, profile, increment_on_change=False)

    prefill = run_universal_prefill(
        scheme_code_or_name=canon_code,
        profile=profile,
        user=current_user,
        db=db,
        existing_draft=target_app,
        lang=lang,
    )

    schema_available = bool(prefill.get("schema_available", prefill.get("form_supported")))
    readiness = evaluate_application_readiness(
        scheme_code=canon_code,
        scheme_id=target_app.get("scheme_id"),
        form_data=target_app.get("form_data") or prefill.get("values") or {},
        profile=profile,
        db=db,
        lang=lang,
        resolved_conflicts=target_app.get("resolved_conflicts"),
    )
    sanitize_legacy_unverified_submission(target_app, readiness=readiness)

    portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
    portal_url = (
        portal_entry.get("official_application_url")
        or target_app.get("official_url")
        or prefill.get("official_portal")
        or "https://india.gov.in"
    )
    adapter = get_portal_adapter(canon_code)
    integration_supported = bool(adapter is not None and adapter.is_authorized)

    review_sections: List[Dict[str, Any]] = []
    if schema_available:
        for sec in prefill.get("sections") or []:
            sec_fields: List[Dict[str, Any]] = []
            for f in sec.get("fields") or []:
                tier = f.get("source_tier")
                cat_key, cat_label = _source_category_label(tier, lang)
                raw_val = f.get("value")
                clean_val_out = "" if is_empty_value(raw_val) else clean_scalar(raw_val)
                sec_fields.append({
                    "name": f.get("name"),
                    "label": f.get("label"),
                    "type": f.get("type", "text"),
                    "value": clean_val_out,
                    "required": bool(f.get("required")),
                    "is_missing": bool(f.get("required")) and is_empty_value(clean_val_out),
                    "source_tier": tier,
                    "source_category": cat_key,
                    "source_badge": f.get("source_label") or cat_label,
                    "conflict": f.get("conflict"),
                    "unverified_ocr_hint": f.get("unverified_ocr_hint"),
                    "options": f.get("options"),
                    "pattern": f.get("pattern"),
                })
            review_sections.append({
                "section_id": sec.get("section_id"),
                "title": sec.get("title"),
                "fields": sec_fields,
            })

    app_version = int(target_app.get("version") or 1)
    data_hash = target_app.get("data_hash") or ""
    confirmed_at = target_app.get("confirmed_at")
    confirmed_hash = target_app.get("confirmed_hash")
    confirmed_version = target_app.get("confirmed_version")
    cur_state = target_app.get("lifecycle_state") or STATE_DRAFT
    confirmation_valid = bool(
        confirmed_at
        and confirmed_hash == data_hash
        and confirmed_version == app_version
        and readiness.get("passed")
        and cur_state != STATE_SUBMISSION_UNKNOWN
        and not target_app.get("legacy_synthetic_submission")
    )

    last_attempt = (target_app.get("submission_attempts") or [None])[-1]
    blind_retry_blocked = bool(
        cur_state == STATE_SUBMISSION_UNKNOWN
        or target_app.get("blind_retry_blocked")
        or (
            isinstance(last_attempt, dict)
            and last_attempt.get("outcome_status") in ("uncertain", "submission_unknown")
        )
    )

    if not schema_available:
        unavail = get_unavailable_schema_payload(
            canon_code,
            target_app.get("scheme_name") or canon_code,
            portal_url,
            lang=lang,
        )
        return {
            "application_id": target_app.get("id"),
            "scheme_code": canon_code,
            "scheme_name": target_app.get("scheme_name") or canon_code,
            "schema_available": False,
            "form_supported": False,
            "message": unavail["message"],
            "lifecycle_state": target_app.get("lifecycle_state") or STATE_DRAFT,
            "version": app_version,
            "data_hash": data_hash,
            "sections": [],
            "missing_mandatory_fields": [],
            "conflicting_fields": [],
            "validation_result": readiness,
            "portal_integration": portal_entry,
            "application_record": build_normalized_application_record(
                target_app,
                current_user.id if current_user else target_app.get("user_id"),
                portal_entry,
            ),
            "confirmation": {
                "confirmed": bool(confirmed_at),
                "valid": False,
                "confirmed_at": confirmed_at,
                "confirmed_by_user_id": target_app.get("confirmed_by_user_id"),
                "confirmed_version": confirmed_version,
                "confirmed_hash": confirmed_hash,
                "invalidated_at": target_app.get("confirmation_invalidated_at"),
            },
            "submission": {
                "integration_supported": False,
                "integration_mode": "manual_portal_required",
                "submission_method": portal_entry.get("submission_method"),
                "integration_provider": None,
                "manual_submission_required": True,
                "official_portal_url": portal_url,
                "tracking_url": portal_entry.get("tracking_url"),
                "external_reference_id": None,
                "official_reference_number": (
                    target_app.get("official_reference_number")
                    if target_app.get("lifecycle_state") == STATE_PORTAL_SUBMITTED
                    else None
                ),
                "reference_source": target_app.get("reference_source"),
                "submission_date": target_app.get("submission_date"),
                "blind_retry_blocked": False,
                "last_attempt": None,
                "is_verified_government_submission": False,
            },
            "audit_trail": target_app.get("audit_trail") or [],
        }

    return {
        "application_id": target_app.get("id"),
        "scheme_code": canon_code,
        "scheme_name": target_app.get("scheme_name") or prefill.get("scheme_title") or canon_code,
        "schema_available": True,
        "form_supported": True,
        "lifecycle_state": target_app.get("lifecycle_state") or STATE_DRAFT,
        "version": app_version,
        "data_hash": data_hash,
        "sections": review_sections,
        "total_mandatory_fields": prefill.get("total_mandatory_fields", 0),
        "filled_mandatory_fields": prefill.get("filled_mandatory_fields", 0),
        "missing_mandatory_fields": readiness.get("breakdown", {}).get("form", {}).get("missing_fields", []),
        "conflicting_fields": prefill.get("conflicting_fields") or [],
        "invalid_fields": prefill.get("invalid_fields") or [],
        "documents": readiness.get("breakdown", {}).get("documents", {}),
        "validation_result": readiness,
        "portal_integration": portal_entry,
        "application_record": build_normalized_application_record(
            target_app,
            current_user.id if current_user else target_app.get("user_id"),
            portal_entry,
        ),
        "confirmation": {
            "confirmed": bool(confirmed_at),
            "valid": confirmation_valid,
            "confirmed_at": confirmed_at,
            "confirmed_by_user_id": target_app.get("confirmed_by_user_id"),
            "confirmed_version": confirmed_version,
            "confirmed_hash": confirmed_hash,
            "invalidated_at": target_app.get("confirmation_invalidated_at"),
        },
        "submission": {
            "integration_supported": integration_supported,
            "integration_mode": "official_integration" if integration_supported else "manual_portal_required",
            "submission_method": target_app.get("submission_method") or portal_entry.get("submission_method"),
            "integration_provider": adapter.provider_name if integration_supported and adapter else None,
            "manual_submission_required": not integration_supported,
            "official_portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "external_reference_id": target_app.get("external_reference_id"),
            "official_reference_number": (
                target_app.get("official_reference_number")
                or (target_app.get("external_reference_id") if is_verified_government_submission(target_app) else None)
            ),
            "reference_source": target_app.get("reference_source") or (
                "official_integration" if is_verified_government_submission(target_app) else None
            ),
            "submission_date": target_app.get("submission_date") or target_app.get("submitted_at"),
            "submitted_at": target_app.get("submitted_at"),
            "blind_retry_blocked": blind_retry_blocked,
            "last_attempt": last_attempt,
            "legacy_synthetic_submission": bool(target_app.get("legacy_synthetic_submission")),
            "is_verified_government_submission": is_verified_government_submission(target_app),
        },
        "legacy_synthetic_submission": bool(target_app.get("legacy_synthetic_submission")),
        "is_verified_government_submission": is_verified_government_submission(target_app),
        "audit_trail": target_app.get("audit_trail") or [],
    }


# ── Part 2 & Part 3: Validation + Explicit Citizen Confirmation ───────────────

def validate_and_advance_application(
    target_app: Dict[str, Any],
    profile: UserProfile,
    current_user: User,
    db: Optional[Session],
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Run strict multi-pillar & scheme-rule validation and transition states cleanly:
    draft -> validated -> awaiting_confirmation (or stays draft on failure).
    Never triggers confirmation or submission automatically.
    """
    canon_code, _ = assert_application_ownership_and_scheme(target_app, current_user, db)
    sanitize_legacy_unverified_submission(target_app)

    if target_app.get("lifecycle_state") == STATE_SUBMITTED and is_verified_government_submission(target_app):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Submitted application packets are finalized and cannot be re-validated.",
                "सबमिट किया गया आवेदन अंतिम हो चुका है और पुनः मान्य नहीं किया जा सकता।",
                "सादर झालेला अर्ज अंतिम केला गेला आहे.",
            ),
        )

    if target_app.get("lifecycle_state") == STATE_SUBMISSION_UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Submission outcome is currently unknown. Reconcile portal status before re-validating or editing.",
                "सबमिशन परिणाम वर्तमान में अनिश्चित है। पुनः जांच या संपादन से पहले पोर्टल स्थिति की पुष्टि करें।",
                "अर्ज सादरीकरणाची स्थिती अनिश्चित आहे. संपादन किंवा तपासणीपूर्वी पोर्टल स्थिती तपासा.",
            ),
        )

    invalidated, current_hash = stamp_application_version_and_check_invalidation(
        target_app, profile, increment_on_change=False
    )

    validation_result = evaluate_application_readiness(
        scheme_code=canon_code,
        scheme_id=target_app.get("scheme_id"),
        form_data=target_app.get("form_data") or {},
        profile=profile,
        db=db,
        lang=lang,
        resolved_conflicts=target_app.get("resolved_conflicts"),
    )
    target_app["validation_result"] = validation_result
    target_app["updated_at"] = _now_iso()

    cur_state = target_app.get("lifecycle_state") or STATE_DRAFT
    audit = list(target_app.get("audit_trail") or [])

    if validation_result.get("passed"):
        # Preserve already valid confirmation if hash/version remain identical
        if (
            cur_state == STATE_CONFIRMED
            and not invalidated
            and target_app.get("confirmed_hash") == current_hash
        ):
            target_app["lifecycle_state"] = STATE_CONFIRMED
        else:
            if cur_state not in (STATE_VALIDATED, STATE_AWAITING_CONFIRMATION):
                validate_state_transition(cur_state, STATE_VALIDATED)
                target_app["lifecycle_state"] = STATE_VALIDATED
                audit.append({
                    "timestamp": target_app["updated_at"],
                    "action": "APPLICATION_VALIDATED",
                    "actor": "system",
                    "details": f"Version v{target_app.get('version', 1)} passed all field, conflict, scheme-rule, and Vault checks.",
                })
            validate_state_transition(target_app["lifecycle_state"], STATE_AWAITING_CONFIRMATION)
            target_app["lifecycle_state"] = STATE_AWAITING_CONFIRMATION
            audit.append({
                "timestamp": target_app["updated_at"],
                "action": "AWAITING_CONFIRMATION",
                "actor": "system",
                "details": f"Version v{target_app.get('version', 1)} ready for explicit citizen review and confirmation.",
            })
    else:
        target_app["lifecycle_state"] = STATE_DRAFT
        if target_app.get("confirmed_at"):
            target_app["confirmed_at"] = None
            target_app["confirmed_hash"] = None
            target_app["confirmed_version"] = None

    target_app["audit_trail"] = audit
    return validation_result


def record_explicit_confirmation(
    target_app: Dict[str, Any],
    profile: UserProfile,
    current_user: User,
    db: Optional[Session],
    lang: str = "en",
    consent_acknowledged: bool = True,
    expected_version: Optional[int] = None,
    expected_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record explicit citizen confirmation bound strictly to the exact reviewed version & hash.
    Blocks confirmation if:
    - Citizen did not explicitly acknowledge consent
    - Draft data/version drifted since the citizen reviewed the summary
    - Live validation (mandatory fields, format/scheme rules, Vault docs, conflicts) fails
    """
    lang = lang if lang in ("en", "hi", "mr") else "en"
    canon_code, portal_url = assert_application_ownership_and_scheme(target_app, current_user, db)
    portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
    portal_url = portal_entry.get("official_application_url") or portal_url
    sanitize_legacy_unverified_submission(target_app)

    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_localize(
                lang,
                "Explicit citizen consent acknowledgment is required to confirm this application.",
                "इस आवेदन की पुष्टि के लिए स्पष्ट नागरिक सहमति आवश्यक है।",
                "हा अर्ज नक्की करण्यासाठी नागरिकाची स्पष्ट संमती आवश्यक आहे.",
            ),
        )

    if target_app.get("lifecycle_state") == STATE_SUBMITTED and is_verified_government_submission(target_app):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "This application has already been submitted.",
                "यह आवेदन पहले ही सबमिट किया जा चुका है।",
                "हा अर्ज आधीच सादर करण्यात आला आहे.",
            ),
        )

    if target_app.get("lifecycle_state") == STATE_SUBMISSION_UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Previous submission outcome is uncertain and requires portal reconciliation before re-confirming.",
                "पिछले सबमिशन की स्थिति अनिश्चित है; पुनः पुष्टि से पहले पोर्टल स्थिति की जांच आवश्यक है।",
                "मागील सादरीकरणाचा निकाल अनिश्चित आहे; पुन्हा पुष्टी करण्यापूर्वी पोर्टल स्थिती तपासणे आवश्यक आहे.",
            ),
        )

    # Refresh snapshot version/hash & check for stale review
    _, current_hash = stamp_application_version_and_check_invalidation(
        target_app, profile, increment_on_change=False
    )
    current_version = int(target_app.get("version") or 1)

    if expected_version is not None and int(expected_version) != current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                f"Application modified since review (reviewed v{expected_version}, current v{current_version}). Please review the updated application before confirming.",
                f"समीक्षा के बाद आवेदन बदला गया है (समीक्षित v{expected_version}, वर्तमान v{current_version})। कृपया पुष्टि से पहले अद्यतन विवरण देखें।",
                f"तपासणीनंतर अर्जात बदल झाला आहे (तपासलेले v{expected_version}, सध्याचे v{current_version}). कृपया पुष्टीपूर्वी अद्ययावत तपशील पहा.",
            ),
        )
    if expected_hash and expected_hash != current_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Application snapshot changed after review. Please re-review the latest details before confirming.",
                "समीक्षा के बाद आवेदन का डेटा बदल गया है। कृपया पुष्टि से पहले नवीनतम विवरण जांचें।",
                "तपासणीनंतर अर्जाची माहिती बदलली आहे. कृपया पुष्टीपूर्वी नवीनतम तपशील पहा.",
            ),
        )

    # Ensure state is validated -> awaiting_confirmation first if starting from draft
    validation_result = evaluate_application_readiness(
        scheme_code=canon_code,
        scheme_id=target_app.get("scheme_id"),
        form_data=target_app.get("form_data") or {},
        profile=profile,
        db=db,
        lang=lang,
        resolved_conflicts=target_app.get("resolved_conflicts"),
    )
    target_app["validation_result"] = validation_result
    if not validation_result.get("passed"):
        target_app["lifecycle_state"] = STATE_DRAFT
        target_app["confirmed_at"] = None
        target_app["confirmed_hash"] = None
        target_app["confirmed_version"] = None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(e["message"] for e in validation_result.get("errors", [])),
        )

    cur_state = target_app.get("lifecycle_state") or STATE_DRAFT
    if cur_state in (STATE_DRAFT, LEGACY_STATE_VALIDATION_FAILED):
        validate_state_transition(cur_state, STATE_VALIDATED)
        cur_state = STATE_VALIDATED
    if cur_state == STATE_VALIDATED:
        validate_state_transition(cur_state, STATE_AWAITING_CONFIRMATION)
        cur_state = STATE_AWAITING_CONFIRMATION
    if cur_state != STATE_CONFIRMED:
        validate_state_transition(cur_state, STATE_CONFIRMED)

    now_iso = _now_iso()
    portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
    eff_portal_url = portal_entry.get("official_application_url") or portal_url
    adapter = get_portal_adapter(canon_code)
    integration_mode = "official_integration" if adapter else "manual_portal_required"
    submission_method = portal_entry.get("submission_method") or (
        SUBMISSION_MODE_DIRECT_API if adapter else SUBMISSION_MODE_PORTAL_ASSISTED
    )

    confirmation_record = {
        "confirmed": True,
        "valid": True,
        "application_id": target_app.get("id"),
        "citizen_id": str(current_user.id),
        "scheme_code": canon_code,
        "confirmed_version": current_version,
        "confirmed_hash": current_hash,
        "confirmed_at": now_iso,
        "consent_acknowledged": True,
        "submission_mode": integration_mode,
        "submission_method": submission_method,
        "official_portal_url": eff_portal_url,
    }

    target_app["confirmed_at"] = now_iso
    target_app["confirmed_by_user_id"] = str(current_user.id)
    target_app["confirmed_version"] = current_version
    target_app["confirmed_hash"] = current_hash
    target_app["confirmation"] = confirmation_record
    target_app["confirmation_invalidated_at"] = None
    target_app["lifecycle_state"] = STATE_CONFIRMED
    target_app["submission_method"] = submission_method
    target_app["portal_url"] = eff_portal_url
    target_app["tracking_url"] = portal_entry.get("tracking_url")
    target_app["updated_at"] = now_iso

    audit = list(target_app.get("audit_trail") or [])
    audit.append({
        "timestamp": now_iso,
        "action": "CITIZEN_CONFIRMED",
        "actor": str(current_user.id),
        "details": f"Citizen confirmed v{current_version} (hash={current_hash[:12]}...) for {submission_method}.",
    })
    target_app["audit_trail"] = audit

    return {
        "confirmed": True,
        "confirmed_at": now_iso,
        "citizen_id": str(current_user.id),
        "application_id": target_app.get("id"),
        "confirmed_version": current_version,
        "confirmed_hash": current_hash,
        "lifecycle_state": STATE_CONFIRMED,
        "integration_supported": bool(adapter),
        "integration_provider": adapter.provider_name if adapter else None,
        "manual_submission_required": not bool(adapter),
        "submission_method": submission_method,
        "official_portal_url": eff_portal_url,
        "tracking_url": portal_entry.get("tracking_url"),
        "portal_integration": portal_entry,
        "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
        "message": _localize(
            lang,
            f"Confirmation recorded for version v{current_version}.",
            f"संस्करण v{current_version} के लिए नागरिक पुष्टि दर्ज की गई।",
            f"आवृत्ती v{current_version} साठी नागरिकाची संमती नोंदवली गेली.",
        ),
    }


# ── Part 4: Safe Submission Orchestration, Idempotency & Uncertainty Guard ────

def orchestrate_application_submission(
    target_app: Dict[str, Any],
    profile: UserProfile,
    current_user: User,
    db: Optional[Session],
    current_profile_data: Optional[Dict[str, Any]] = None,
    apps_list: Optional[List[Dict[str, Any]]] = None,
    lang: str = "en",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reusable submission orchestrator enforcing:
    - Pre-submission revalidation of ownership, scheme schema, readiness, and exact confirmed version/hash
    - Idempotency & duplicate-submission protection
    - Honest manual-portal disclosure when NO official API integration exists (never simulates success)
    - Authorized portal adapter dispatch with pre-send attempt logging & safe uncertainty/retry guards
    """
    lang = lang if lang in ("en", "hi", "mr") else "en"
    canon_code, portal_url = assert_application_ownership_and_scheme(target_app, current_user, db)
    portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
    portal_url = portal_entry.get("official_application_url") or portal_url
    sanitize_legacy_unverified_submission(target_app)

    invalidated, current_hash = stamp_application_version_and_check_invalidation(
        target_app, profile, increment_on_change=False
    )
    current_version = int(target_app.get("version") or 1)
    cur_state = target_app.get("lifecycle_state") or STATE_DRAFT

    attempts = list(target_app.get("submission_attempts") or [])
    effective_idem_key = (
        (idempotency_key or "").strip()
        or f"idem:{current_user.id}:{target_app.get('id')}:v{current_version}:{current_hash[:12]}"
    )

    # 1. Duplicate / Idempotency & Uncertain Outcome Guards
    if cur_state == STATE_SUBMITTED and is_verified_government_submission(target_app):
        prev_keys = {a.get("idempotency_key") for a in attempts if a.get("outcome_status") == "submitted"}
        if effective_idem_key in prev_keys or target_app.get("last_idempotency_key") == effective_idem_key:
            return {
                "success": True,
                "submitted": True,
                "idempotent_replay": True,
                "lifecycle_state": STATE_SUBMITTED,
                "submission_status": "submitted",
                "external_reference_id": target_app.get("external_reference_id"),
                "portal_url": portal_url,
                "integration_provider": target_app.get("integration_provider"),
                "submitted_at": target_app.get("submitted_at"),
                "message": _localize(
                    lang,
                    f"Application already submitted (Reference: {target_app.get('external_reference_id')}). Returning recorded receipt without duplicate submission.",
                    f"आवेदन पहले ही सबमिट हो चुका है (संदर्भ: {target_app.get('external_reference_id')})। डुप्लिकेट सबमिशन रोका गया।",
                    f"अर्ज आधीच सादर झाला आहे (संदर्भ: {target_app.get('external_reference_id')}). दुहेरी सादरीकरण रोखले गेले.",
                ),
            }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                f"Duplicate submission blocked: application already submitted with external reference {target_app.get('external_reference_id')}.",
                f"डुप्लिकेट सबमिशन अवरुद्ध: आवेदन पहले ही संदर्भ {target_app.get('external_reference_id')} के साथ जमा है।",
                f"दुहेरी सादरीकरण रोखले: हा अर्ज आधीच संदर्भ {target_app.get('external_reference_id')} सह सादर आहे.",
            ),
        )

    last_attempt = attempts[-1] if attempts else None
    if (
        cur_state in (STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
        or target_app.get("blind_retry_blocked")
        or (
            isinstance(last_attempt, dict)
            and last_attempt.get("outcome_status") in ("uncertain", "submission_unknown")
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Previous submission outcome is uncertain (submission_unknown). Blind retry is blocked to prevent duplicate submission; please reconcile submission status with the official portal first.",
                "पिछले सबमिशन की स्थिति अनिश्चित है। दोहरे आवेदन से बचने के लिए स्वतः पुनः प्रयास अवरुद्ध है; पहले पोर्टल स्थिति की पुष्टि करें।",
                "मागील सादरीकरणाचा निकाल अनिश्चित आहे. दुहेरी अर्ज टाळण्यासाठी थेट पुन्हा प्रयत्न बंद केला आहे; प्रथम पोर्टल स्थिती तपासा.",
            ),
        )

    # Idempotent replay if already portal-submitted by citizen
    if cur_state == STATE_PORTAL_SUBMITTED and target_app.get("official_reference_number"):
        return {
            "success": True,
            "submitted": False,
            "portal_submitted": True,
            "idempotent_replay": True,
            "manual_portal_required": True,
            "integration_supported": False,
            "submission_method": target_app.get("submission_method") or portal_entry.get("submission_method"),
            "lifecycle_state": STATE_PORTAL_SUBMITTED,
            "submission_status": STATE_PORTAL_SUBMITTED,
            "external_reference_id": None,
            "official_reference_number": target_app.get("official_reference_number"),
            "reference_source": target_app.get("reference_source") or "citizen_reported_portal_reference",
            "submission_date": target_app.get("submission_date"),
            "portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "portal_integration": portal_entry,
            "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
            "message": _localize(
                lang,
                f"Portal submission reference ({target_app.get('official_reference_number')}) is already recorded for tracking.",
                f"आधिकारिक पोर्टल संदर्भ संख्या ({target_app.get('official_reference_number')}) पहले ही ट्रैकिंग के लिए दर्ज है।",
                f"अधिकृत पोर्टल संदर्भ क्रमांक ({target_app.get('official_reference_number')}) आधीच ट्रॅकिंगसाठी नोंदवला आहे.",
            ),
        }

    # Idempotent replay if same idempotency_key already recorded manual handoff on this confirmed version
    if (
        cur_state == STATE_CONFIRMED
        and target_app.get("submission_outcome") == "manual_portal_required"
        and target_app.get("last_idempotency_key") == effective_idem_key
    ):
        submission_method = portal_entry.get("submission_method") or SUBMISSION_MODE_PORTAL_ASSISTED
        return {
            "success": True,
            "submitted": False,
            "idempotent_replay": True,
            "manual_portal_required": True,
            "integration_supported": False,
            "submission_method": submission_method,
            "can_record_portal_reference": True,
            "lifecycle_state": STATE_CONFIRMED,
            "submission_status": "manual_portal_required",
            "external_reference_id": None,
            "official_reference_number": None,
            "portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "portal_integration": portal_entry,
            "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
            "confirmed_version": current_version,
            "confirmed_hash": current_hash,
            "message": _localize(
                lang,
                f"Application version v{current_version} is confirmed. Follow the official portal steps at {portal_url} (complete OTP/CAPTCHA there directly), then return with your official application reference number.",
                f"आवेदन संस्करण v{current_version} की पुष्टि हो चुकी है। कृपया आधिकारिक पोर्टल ({portal_url}) पर चरणों का पालन कर आवेदन जमा करें (OTP/कैप्चा वहीं पूरा करें), और फिर आधिकारिक संदर्भ संख्या यहां दर्ज करें।",
                f"अर्ज आवृत्ती v{current_version} नक्की झाली आहे. कृपया अधिकृत पोर्टलवर ({portal_url}) टप्प्याटप्प्याने अर्ज भरा (OTP/कॅप्चा थेट पोर्टलवर पूर्ण करा), आणि नंतर अधिकृत संदर्भ क्रमांक येथे नोंदवा.",
            ),
        }

    # 2. Enforce Explicit Confirmation & Version Integrity
    if invalidated or not target_app.get("confirmed_at") or target_app.get("confirmed_hash") != current_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_localize(
                lang,
                "Valid explicit citizen confirmation for the current application version is required before submission.",
                "सबमिशन से पहले वर्तमान आवेदन संस्करण की मान्य नागरिक पुष्टि आवश्यक है।",
                "अर्ज सादर करण्यापूर्वी सध्याच्या आवृत्तीसाठी नागरिकाची वैध स्पष्ट संमती आवश्यक आहे.",
            ),
        )

    if cur_state not in (STATE_CONFIRMED, STATE_SUBMISSION_FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application must be in 'confirmed' state before submission (current: '{cur_state}').",
        )

    # 3. Immediate Pre-Submission Revalidation
    revalidation = evaluate_application_readiness(
        scheme_code=canon_code,
        scheme_id=target_app.get("scheme_id"),
        form_data=target_app.get("form_data") or {},
        profile=profile,
        db=db,
        lang=lang,
        resolved_conflicts=target_app.get("resolved_conflicts"),
    )
    target_app["validation_result"] = revalidation
    if not revalidation.get("passed"):
        target_app["confirmed_at"] = None
        target_app["confirmed_hash"] = None
        target_app["confirmed_version"] = None
        target_app["lifecycle_state"] = STATE_DRAFT
        if db is not None and profile is not None and current_profile_data is not None and apps_list is not None:
            current_profile_data["applications"] = apps_list
            profile.profile_data = current_profile_data
            flag_modified(profile, "profile_data")
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(e["message"] for e in revalidation.get("errors", [])),
        )

    # 4. Check Official Portal Integration Capability (NEVER simulate government submission!)
    adapter = get_portal_adapter(canon_code)
    if adapter is None:
        now_iso = _now_iso()
        submission_method = portal_entry.get("submission_method") or SUBMISSION_MODE_PORTAL_ASSISTED
        target_app["lifecycle_state"] = STATE_CONFIRMED
        target_app["submission_outcome"] = "manual_portal_required"
        target_app["submission_method"] = submission_method
        target_app["integration_supported"] = False
        target_app["external_reference_id"] = None
        target_app["portal_url"] = portal_url
        target_app["tracking_url"] = portal_entry.get("tracking_url")
        target_app["last_idempotency_key"] = effective_idem_key
        target_app["updated_at"] = now_iso

        audit = list(target_app.get("audit_trail") or [])
        audit.append({
            "timestamp": now_iso,
            "action": "MANUAL_PORTAL_REQUIRED",
            "actor": "submission_orchestrator",
            "details": f"No authorized portal API integration for {canon_code}. Prepared verified v{current_version} packet ({submission_method}) for official portal submission at {portal_url}.",
        })
        target_app["audit_trail"] = audit

        _commit_apps(db, profile, current_profile_data, apps_list, target_app=target_app, citizen_id=current_user.id, portal_entry=portal_entry)

        return {
            "success": True,
            "submitted": False,
            "manual_portal_required": True,
            "integration_supported": False,
            "submission_method": submission_method,
            "can_record_portal_reference": True,
            "lifecycle_state": STATE_CONFIRMED,
            "submission_status": "manual_portal_required",
            "external_reference_id": None,
            "official_reference_number": None,
            "portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "portal_integration": portal_entry,
            "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
            "confirmed_version": current_version,
            "confirmed_hash": current_hash,
            "message": _localize(
                lang,
                f"Application version v{current_version} is confirmed and ready. Follow the official portal steps at {portal_url} (complete OTP/CAPTCHA there directly), then return with your official application reference number.",
                f"आवेदन संस्करण v{current_version} की पुष्टि हो गई है। कृपया आधिकारिक पोर्टल ({portal_url}) पर चरणों का पालन कर आवेदन जमा करें (OTP/कैप्चा वहीं पूरा करें), और फिर आधिकारिक संदर्भ संख्या यहां दर्ज करें।",
                f"अर्ज आवृत्ती v{current_version} नक्की झाली आहे. कृपया अधिकृत पोर्टलवर ({portal_url}) टप्प्याटप्प्याने अर्ज भरा (OTP/कॅप्चा थेट पोर्टलवर पूर्ण करा), आणि नंतर अधिकृत संदर्भ क्रमांक येथे नोंदवा.",
            ),
        }

    # 5. Authorized External Portal Integration Dispatch
    now_iso = _now_iso()
    attempt_id = f"sub-{uuid.uuid4().hex[:10]}"
    validate_state_transition(cur_state, STATE_SUBMITTING)
    target_app["lifecycle_state"] = STATE_SUBMITTING
    target_app["last_idempotency_key"] = effective_idem_key
    target_app["updated_at"] = now_iso

    attempt_record: Dict[str, Any] = {
        "attempt_id": attempt_id,
        "idempotency_key": effective_idem_key,
        "provider": adapter.provider_name,
        "version": current_version,
        "snapshot_hash": current_hash,
        "started_at": now_iso,
        "completed_at": None,
        "outcome_status": "submitting",
        "external_reference_id": None,
        "error_message": None,
    }
    attempts.append(attempt_record)
    target_app["submission_attempts"] = attempts

    # Persist 'submitting' before external HTTP dispatch to guard against mid-flight crashes
    if db is not None and profile is not None and current_profile_data is not None and apps_list is not None:
        current_profile_data["applications"] = apps_list
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        db.commit()

    try:
        portal_res = adapter.submit(
            application=dict(target_app),
            idempotency_key=effective_idem_key,
            lang=lang,
        )
    except TimeoutError as exc:
        done_iso = _now_iso()
        validate_state_transition(STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
        attempt_record["completed_at"] = done_iso
        attempt_record["outcome_status"] = "uncertain"
        attempt_record["error_message"] = str(exc) or "Gateway timed out after request dispatch."
        target_app["lifecycle_state"] = STATE_SUBMISSION_UNKNOWN
        target_app["submission_outcome"] = STATE_SUBMISSION_UNKNOWN
        target_app["external_reference_id"] = None
        target_app["blind_retry_blocked"] = True
        target_app["updated_at"] = done_iso
        _append_attempt_audit(target_app, done_iso, "SUBMISSION_UNKNOWN", attempt_record["error_message"])
        _commit_apps(db, profile, current_profile_data, apps_list)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=_localize(
                lang,
                "Official portal request timed out after dispatch. Persisted as submission_unknown; blind retries are disabled until portal status is reconciled.",
                "आधिकारिक पोर्टल अनुरोध समय समाप्त हो गया। स्थिति 'submission_unknown' के रूप में सहेजी गई है; पोर्टल पुष्टि तक पुनः प्रयास अवरुद्ध है।",
                "अधिकृत पोर्टल विनंतीची वेळ संपली. स्थिती 'submission_unknown' म्हणून जतन केली आहे; तपासणीशिवाय पुन्हा प्रयत्न बंद आहे.",
            ),
        )
    except Exception as exc:
        done_iso = _now_iso()
        is_uncertain = bool(getattr(exc, "outcome_uncertain", False))
        target_state = STATE_SUBMISSION_UNKNOWN if is_uncertain else STATE_SUBMISSION_FAILED
        validate_state_transition(STATE_SUBMITTING, target_state)
        attempt_record["completed_at"] = done_iso
        attempt_record["outcome_status"] = "uncertain" if is_uncertain else "failed_retryable"
        attempt_record["error_message"] = str(exc) or "External portal submission failed."
        target_app["lifecycle_state"] = target_state
        target_app["submission_outcome"] = STATE_SUBMISSION_UNKNOWN if is_uncertain else "failed_retryable"
        target_app["external_reference_id"] = None
        target_app["blind_retry_blocked"] = is_uncertain
        target_app["updated_at"] = done_iso
        _append_attempt_audit(
            target_app,
            done_iso,
            "SUBMISSION_UNKNOWN" if is_uncertain else "SUBMISSION_FAILED",
            attempt_record["error_message"],
        )
        _commit_apps(db, profile, current_profile_data, apps_list)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=attempt_record["error_message"],
        )

    done_iso = portal_res.recorded_at or _now_iso()
    ext_ref_raw = str(portal_res.external_reference_id).strip() if portal_res.external_reference_id else ""
    if portal_res.outcome == "submitted" and ext_ref_raw and not ext_ref_raw.upper().startswith("SAATHI/"):
        ext_ref = ext_ref_raw
        validate_state_transition(STATE_SUBMITTING, STATE_SUBMITTED)
        attempt_record["completed_at"] = done_iso
        attempt_record["outcome_status"] = "submitted"
        attempt_record["external_reference_id"] = ext_ref
        attempt_record["raw_response"] = portal_res.raw_response

        target_app["lifecycle_state"] = STATE_SUBMITTED
        target_app["submission_outcome"] = "submitted"
        target_app["integration_supported"] = True
        target_app["integration_provider"] = adapter.provider_name
        target_app["submission_source"] = "official_integration"
        target_app["submission_method"] = SUBMISSION_MODE_DIRECT_API
        target_app["external_reference_id"] = ext_ref
        target_app["official_reference_number"] = ext_ref
        target_app["reference_source"] = "official_integration"
        target_app["reference_number"] = ext_ref
        target_app["submitted_at"] = done_iso
        target_app["submission_date"] = done_iso
        target_app["portal_url"] = portal_url
        target_app["tracking_url"] = portal_entry.get("tracking_url")
        target_app["blind_retry_blocked"] = False
        target_app["updated_at"] = done_iso
        _append_attempt_audit(target_app, done_iso, "SUBMISSION_SUCCEEDED", f"Submitted via {adapter.provider_name}; external_reference_id={ext_ref}.")
        _commit_apps(db, profile, current_profile_data, apps_list, target_app=target_app, citizen_id=current_user.id, portal_entry=portal_entry)
        return {
            "success": True,
            "submitted": True,
            "manual_portal_required": False,
            "integration_supported": True,
            "integration_provider": adapter.provider_name,
            "submission_method": SUBMISSION_MODE_DIRECT_API,
            "lifecycle_state": STATE_SUBMITTED,
            "submission_status": "submitted",
            "external_reference_id": ext_ref,
            "official_reference_number": ext_ref,
            "reference_number": ext_ref,
            "reference_source": "official_integration",
            "portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "submitted_at": done_iso,
            "submission_date": done_iso,
            "portal_integration": portal_entry,
            "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
            "message": portal_res.message
            or _localize(
                lang,
                f"Application submitted to {adapter.provider_name}. Official reference ID: {ext_ref}.",
                f"आवेदन {adapter.provider_name} पर सबमिट किया गया। आधिकारिक संदर्भ संख्या: {ext_ref}।",
                f"अर्ज {adapter.provider_name} वर सादर झाला आहे. अधिकृत संदर्भ क्रमांक: {ext_ref}.",
            ),
        }

    # If portal returned 'submitted' WITHOUT an authoritative non-synthetic external reference ID,
    # or returned 'uncertain', persist distinctly as submission_unknown — never submitted or submission_failed.
    if portal_res.outcome in ("submitted", "uncertain"):
        validate_state_transition(STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
        attempt_record["completed_at"] = done_iso
        attempt_record["outcome_status"] = "uncertain"
        attempt_record["error_message"] = (
            portal_res.message or "Portal response ambiguous or missing authoritative transaction reference ID."
        )
        attempt_record["raw_response"] = portal_res.raw_response
        target_app["lifecycle_state"] = STATE_SUBMISSION_UNKNOWN
        target_app["submission_outcome"] = STATE_SUBMISSION_UNKNOWN
        target_app["external_reference_id"] = None
        target_app["blind_retry_blocked"] = True
        target_app["updated_at"] = done_iso
        _append_attempt_audit(target_app, done_iso, "SUBMISSION_UNKNOWN", attempt_record["error_message"])
        _commit_apps(db, profile, current_profile_data, apps_list)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=attempt_record["error_message"],
        )

    # Definite failure (retryable or permanent rejection from portal)
    validate_state_transition(STATE_SUBMITTING, STATE_SUBMISSION_FAILED)
    attempt_record["completed_at"] = done_iso
    attempt_record["outcome_status"] = (
        "failed_permanent" if portal_res.outcome == "failed_permanent" else "failed_retryable"
    )
    attempt_record["error_message"] = portal_res.message or "Official portal rejected the submission request."
    attempt_record["raw_response"] = portal_res.raw_response
    target_app["lifecycle_state"] = STATE_SUBMISSION_FAILED
    target_app["submission_outcome"] = attempt_record["outcome_status"]
    target_app["blind_retry_blocked"] = portal_res.outcome == "failed_permanent"
    target_app["updated_at"] = done_iso
    _append_attempt_audit(target_app, done_iso, "SUBMISSION_FAILED", attempt_record["error_message"])
    _commit_apps(db, profile, current_profile_data, apps_list)
    return {
        "success": False,
        "submitted": False,
        "lifecycle_state": STATE_SUBMISSION_FAILED,
        "submission_status": attempt_record["outcome_status"],
        "retry_allowed": attempt_record["outcome_status"] == "failed_retryable",
        "blind_retry_blocked": bool(target_app["blind_retry_blocked"]),
        "error": attempt_record["error_message"],
        "portal_url": portal_url,
    }


def reconcile_application_submission(
    target_app: Dict[str, Any],
    profile: UserProfile,
    current_user: User,
    db: Optional[Session],
    current_profile_data: Optional[Dict[str, Any]] = None,
    apps_list: Optional[List[Dict[str, Any]]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Query authorized external portal integration to safely resolve an 'uncertain'
    submission attempt before permitting any retry or marking submitted.
    """
    canon_code, portal_url = assert_application_ownership_and_scheme(target_app, current_user, db)
    sanitize_legacy_unverified_submission(target_app)
    attempts = list(target_app.get("submission_attempts") or [])
    last_attempt = attempts[-1] if attempts else None
    if not last_attempt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No submission attempt to reconcile.")

    adapter = get_portal_adapter(canon_code)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorized external portal integration configured to reconcile remotely.",
        )

    cur_state = (target_app.get("lifecycle_state") or STATE_SUBMISSION_UNKNOWN).strip().lower()
    if cur_state not in (STATE_SUBMISSION_UNKNOWN, STATE_SUBMISSION_FAILED, STATE_SUBMITTING):
        cur_state = STATE_SUBMISSION_UNKNOWN

    rec = adapter.check_status(
        application_id=str(target_app.get("id") or ""),
        idempotency_key=str(last_attempt.get("idempotency_key") or ""),
        attempt_id=str(last_attempt.get("attempt_id") or ""),
    )
    now_iso = _now_iso()

    ext_ref_rec = str(rec.external_reference_id).strip() if rec.external_reference_id else ""
    if rec.resolved_outcome == "submitted" and ext_ref_rec and not ext_ref_rec.upper().startswith("SAATHI/"):
        ext_ref = ext_ref_rec
        portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
        portal_url = portal_entry.get("official_application_url") or portal_url
        validate_state_transition(cur_state, STATE_SUBMITTED)
        target_app["lifecycle_state"] = STATE_SUBMITTED
        target_app["submission_outcome"] = "submitted"
        target_app["submission_source"] = "official_integration"
        target_app["submission_method"] = SUBMISSION_MODE_DIRECT_API
        target_app["integration_supported"] = True
        target_app["integration_provider"] = adapter.provider_name
        target_app["external_reference_id"] = ext_ref
        target_app["official_reference_number"] = ext_ref
        target_app["reference_source"] = "official_integration"
        target_app["reference_number"] = ext_ref
        target_app["submitted_at"] = now_iso
        target_app["submission_date"] = now_iso
        target_app["portal_url"] = portal_url
        target_app["tracking_url"] = portal_entry.get("tracking_url")
        target_app["blind_retry_blocked"] = False
        last_attempt["outcome_status"] = "submitted"
        last_attempt["external_reference_id"] = ext_ref
        last_attempt["completed_at"] = now_iso
        target_app["updated_at"] = now_iso
        _append_attempt_audit(target_app, now_iso, "RECONCILED_SUBMITTED", f"Portal confirmed earlier receipt: {ext_ref}.")
        _commit_apps(db, profile, current_profile_data, apps_list, target_app=target_app, citizen_id=current_user.id, portal_entry=portal_entry)
        return {
            "resolved": True,
            "lifecycle_state": STATE_SUBMITTED,
            "external_reference_id": ext_ref,
            "official_reference_number": ext_ref,
            "portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "application_record": build_normalized_application_record(target_app, current_user.id, portal_entry),
            "message": _localize(
                lang,
                f"Reconciled: application was accepted by the portal (Reference: {ext_ref}).",
                f"सत्यापित: पोर्टल द्वारा आवेदन स्वीकार किया जा चुका है (संदर्भ: {ext_ref})।",
                f"तपासले: पोर्टलने अर्ज स्वीकारला आहे (संदर्भ: {ext_ref}).",
            ),
        }

    if rec.resolved_outcome == "not_received":
        validate_state_transition(cur_state, STATE_CONFIRMED)
        target_app["lifecycle_state"] = STATE_CONFIRMED
        target_app["submission_outcome"] = "failed_retryable"
        target_app["blind_retry_blocked"] = False
        last_attempt["outcome_status"] = "failed_retryable"
        last_attempt["completed_at"] = now_iso
        target_app["updated_at"] = now_iso
        _append_attempt_audit(target_app, now_iso, "RECONCILED_NOT_RECEIVED", "Portal confirmed request was not received; safe retry unlocked.")
        _commit_apps(db, profile, current_profile_data, apps_list)
        return {
            "resolved": True,
            "lifecycle_state": STATE_CONFIRMED,
            "retry_allowed": True,
            "blind_retry_blocked": False,
            "message": _localize(
                lang,
                "Portal confirmed the earlier request was not received. Safe retry is now unlocked.",
                "पोर्टल ने पुष्टि की कि पिछला अनुरोध प्राप्त नहीं हुआ था। अब सुरक्षित पुनः प्रयास सक्षम है।",
                "मागील विनंती पोर्टलपर्यंत पोहोचली नसल्याचे स्पष्ट झाले आहे. आता सुरक्षितरीत्या पुन्हा प्रयत्न करता येईल.",
            ),
        }

    if rec.resolved_outcome in ("failed", "failed_permanent", "rejected"):
        is_perm = rec.resolved_outcome == "failed_permanent"
        if cur_state != STATE_SUBMISSION_FAILED:
            validate_state_transition(cur_state, STATE_SUBMISSION_FAILED)
        target_app["lifecycle_state"] = STATE_SUBMISSION_FAILED
        target_app["submission_outcome"] = "failed_permanent" if is_perm else "failed_retryable"
        target_app["blind_retry_blocked"] = is_perm
        last_attempt["outcome_status"] = target_app["submission_outcome"]
        last_attempt["completed_at"] = now_iso
        target_app["updated_at"] = now_iso
        _append_attempt_audit(target_app, now_iso, "RECONCILED_FAILED", "Portal confirmed earlier submission attempt failed/rejected.")
        _commit_apps(db, profile, current_profile_data, apps_list)
        return {
            "resolved": True,
            "lifecycle_state": STATE_SUBMISSION_FAILED,
            "retry_allowed": not is_perm,
            "blind_retry_blocked": is_perm,
            "message": _localize(
                lang,
                "Reconciled: portal confirmed the submission failed.",
                "सत्यापित: पोर्टल ने पुष्टि की कि सबमिशन असफल रहा।",
                "तपासले: पोर्टलने सादरीकरण अयशस्वी झाल्याची पुष्टी केली.",
            ),
        }

    target_app["lifecycle_state"] = STATE_SUBMISSION_UNKNOWN
    target_app["submission_outcome"] = STATE_SUBMISSION_UNKNOWN
    target_app["blind_retry_blocked"] = True
    target_app["updated_at"] = now_iso
    _commit_apps(db, profile, current_profile_data, apps_list)
    return {
        "resolved": False,
        "lifecycle_state": STATE_SUBMISSION_UNKNOWN,
        "retry_allowed": False,
        "blind_retry_blocked": True,
        "message": _localize(
            lang,
            "Portal status remains submission_unknown. Blind retry remains blocked until reconciled.",
            "पोर्टल स्थिति अभी भी अनिश्चित (submission_unknown) है। पुनः प्रयास अवरुद्ध रहेगा।",
            "पोर्टलची स्थिती अद्याप अनिश्चित (submission_unknown) आहे. पुन्हा प्रयत्न बंद राहील.",
        ),
    }


def record_citizen_portal_reference(
    target_app: Dict[str, Any],
    profile: UserProfile,
    current_user: User,
    db: Optional[Session],
    official_reference_number: str,
    submission_date: Optional[str] = None,
    portal_notes: Optional[str] = None,
    confirmation_acknowledged: bool = True,
    current_profile_data: Optional[Dict[str, Any]] = None,
    apps_list: Optional[List[Dict[str, Any]]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Mode B (Portal-Assisted) & verified manual-portal return flow:
    Allows the citizen to return after submitting on the official government portal
    (where they complete login/OTP/CAPTCHA directly) and store the genuine official
    portal application reference number strictly distinct from internal application_id.
    """
    lang = lang if lang in ("en", "hi", "mr") else "en"
    canon_code, portal_url = assert_application_ownership_and_scheme(target_app, current_user, db)
    portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
    portal_url = portal_entry.get("official_application_url") or portal_url
    sanitize_legacy_unverified_submission(target_app)

    cur_state = (target_app.get("lifecycle_state") or STATE_DRAFT).strip().lower()
    if cur_state in (STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Submission status is uncertain/in-flight; reconcile portal status first.",
                "सबमिशन स्थिति अनिश्चित है; पहले पोर्टल स्थिति की पुष्टि करें।",
                "अर्ज सादरीकरण स्थिती अनिश्चित आहे; प्रथम पोर्टल स्थिती तपासा.",
            ),
        )
    if cur_state == STATE_SUBMITTED and is_verified_government_submission(target_app):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_localize(
                lang,
                "Application already has a verified official API submission reference.",
                "आवेदन पहले से सत्यापित आधिकारिक API संदर्भ के साथ सबमिट है।",
                "अर्जाचा अधिकृत API संदर्भ आधीच नोंदलेला आहे.",
            ),
        )

    cleaned_ref = str(official_reference_number or "").strip()
    app_id = str(target_app.get("id") or "")
    if not _is_valid_official_reference(cleaned_ref, app_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_localize(
                lang,
                "Please enter the valid official government portal application reference number (cannot be blank, internal draft ID, or synthetic SAATHI/... ID).",
                "कृपया आधिकारिक सरकारी पोर्टल से प्राप्त मान्य संदर्भ संख्या दर्ज करें (यह खाली या आंतरिक ड्राफ्ट आईडी नहीं हो सकती)।",
                "कृपया अधिकृत शासकीय पोर्टलवरून मिळालेला वैध अर्ज संदर्भ क्रमांक प्रविष्ट करा (रिकामा किंवा अंतर्गत मसुदा आयडी चालणार नाही).",
            ),
        )

    has_schema = get_form_schema_for_scheme(canon_code) is not None
    if has_schema:
        invalidated, current_hash = stamp_application_version_and_check_invalidation(
            target_app, profile, increment_on_change=False
        )
        if cur_state != STATE_PORTAL_SUBMITTED and (
            invalidated or not target_app.get("confirmed_at") or target_app.get("confirmed_hash") != current_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_localize(
                    lang,
                    "Explicit citizen confirmation of the current reviewed application version is required before recording an official portal reference.",
                    "आधिकारिक पोर्टल संदर्भ संख्या दर्ज करने से पहले वर्तमान आवेदन की स्पष्ट नागरिक पुष्टि आवश्यक है।",
                    "अधिकृत पोर्टल संदर्भ क्रमांक नोंदवण्यापूर्वी सध्याच्या अर्जाची स्पष्ट नागरिकाची पुष्टी आवश्यक आहे.",
                ),
            )
    elif not confirmation_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_localize(
                lang,
                "Explicit confirmation acknowledgment is required to record your portal submission.",
                "पोर्टल सबमिशन दर्ज करने के लिए स्पष्ट पुष्टि आवश्यक है।",
                "पोर्टल अर्ज नोंदवण्यासाठी तुमची स्पष्ट संमती आवश्यक आहे.",
            ),
        )

    if cur_state != STATE_PORTAL_SUBMITTED:
        if cur_state in (STATE_DRAFT, LEGACY_STATE_VALIDATION_FAILED, STATE_VALIDATED, STATE_AWAITING_CONFIRMATION) and not has_schema:
            target_app["confirmed_at"] = target_app.get("confirmed_at") or _now_iso()
            target_app["confirmed_by_user_id"] = str(current_user.id)
        else:
            validate_state_transition(cur_state, STATE_PORTAL_SUBMITTED)

    now_iso = _now_iso()
    eff_sub_date = submission_date.strip() if isinstance(submission_date, str) and submission_date.strip() else now_iso
    if _parse_iso_dt(eff_sub_date) is None:
        eff_sub_date = now_iso

    sub_method = portal_entry.get("submission_method") or SUBMISSION_MODE_PORTAL_ASSISTED
    if sub_method == SUBMISSION_MODE_DIRECT_API:
        sub_method = SUBMISSION_MODE_PORTAL_ASSISTED

    target_app["lifecycle_state"] = STATE_PORTAL_SUBMITTED
    target_app["submission_outcome"] = STATE_PORTAL_SUBMITTED
    target_app["submission_source"] = "portal_assisted"
    target_app["submission_method"] = sub_method
    target_app["official_reference_number"] = cleaned_ref
    target_app["reference_source"] = "citizen_reported_portal_reference"
    target_app["submission_date"] = eff_sub_date
    target_app["portal_url"] = portal_url
    target_app["tracking_url"] = portal_entry.get("tracking_url")
    target_app["is_verified_government_submission"] = False
    if portal_notes:
        target_app["portal_notes"] = portal_notes.strip()
    target_app["updated_at"] = now_iso

    _append_attempt_audit(
        target_app,
        now_iso,
        "PORTAL_REFERENCE_RECORDED",
        f"Citizen recorded official portal reference '{cleaned_ref}' for {portal_url} (method={sub_method}).",
    )
    _commit_apps(
        db,
        profile,
        current_profile_data,
        apps_list,
        target_app=target_app,
        citizen_id=current_user.id,
        portal_entry=portal_entry,
    )

    norm_record = build_normalized_application_record(target_app, current_user.id, portal_entry)
    return {
        "success": True,
        "recorded": True,
        "lifecycle_state": STATE_PORTAL_SUBMITTED,
        "application_status": STATE_PORTAL_SUBMITTED,
        "application_id": app_id,
        "official_reference_number": cleaned_ref,
        "reference_source": "citizen_reported_portal_reference",
        "submission_method": sub_method,
        "submission_date": eff_sub_date,
        "portal_url": portal_url,
        "tracking_url": portal_entry.get("tracking_url"),
        "portal_integration": portal_entry,
        "application_record": norm_record,
        "is_verified_government_submission": False,
        "message": _localize(
            lang,
            f"Saved official portal reference '{cleaned_ref}' against your application record ({app_id}). You can track status anytime at the official portal.",
            f"आधिकारिक पोर्टल संदर्भ संख्या '{cleaned_ref}' आपके आवेदन रिकॉर्ड ({app_id}) में सहेजी गई है। आप आधिकारिक पोर्टल पर स्थिति ट्रैक कर सकते हैं।",
            f"अधिकृत पोर्टल संदर्भ क्रमांक '{cleaned_ref}' तुमच्या अर्ज नोंदीमध्ये ({app_id}) जतन केला आहे. तुम्ही अधिकृत पोर्टलवर अर्जाची स्थिती तपासू शकता.",
        ),
    }


def _append_attempt_audit(target_app: Dict[str, Any], timestamp: str, action: str, details: str) -> None:
    audit = list(target_app.get("audit_trail") or [])
    audit.append({"timestamp": timestamp, "action": action, "actor": "submission_orchestrator", "details": details})
    target_app["audit_trail"] = audit


def _commit_apps(
    db: Optional[Session],
    profile: Optional[UserProfile],
    current_profile_data: Optional[Dict[str, Any]],
    apps_list: Optional[List[Dict[str, Any]]],
    target_app: Optional[Dict[str, Any]] = None,
    citizen_id: Any = None,
    portal_entry: Optional[Dict[str, Any]] = None,
) -> None:
    if db is not None and profile is not None and current_profile_data is not None and apps_list is not None:
        current_profile_data["applications"] = apps_list
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        if target_app is not None and citizen_id is not None:
            sync_application_record_to_db(db, target_app, citizen_id, portal_entry)
        db.commit()
        db.refresh(profile)

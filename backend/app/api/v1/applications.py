"""
Application Readiness and Official Portal Guidance API endpoints.
Provides authenticated endpoints for application drafting, deterministic readiness assessment,
duplicate draft consolidation, and explicit citizen confirmation before official portal handoff.
Scheme Saathi prepares application packets and never claims to submit government applications directly.
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.models.user_consent import UserConsent
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.schemas.common import APIResponse
from app.agents.form_schemas import (
    get_form_schema_for_scheme,
    get_unavailable_schema_payload,
    SCHEME_CODE_ALIASES,
)
from app.services.readiness_service import evaluate_application_readiness
from app.services.portal_registry_service import (
    get_portal_integration_entry,
    list_portal_registry,
)
from app.services.prefill_service import run_universal_prefill, clean_scalar, is_empty_value
from app.services.submission_service import (
    STATE_AWAITING_CONFIRMATION,
    STATE_CONFIRMED,
    STATE_DRAFT,
    STATE_PORTAL_SUBMITTED,
    STATE_SUBMISSION_FAILED,
    STATE_SUBMISSION_UNKNOWN,
    STATE_SUBMITTED,
    STATE_SUBMITTING,
    build_application_review_summary,
    build_normalized_application_record,
    is_verified_government_submission,
    orchestrate_application_submission,
    reconcile_application_submission,
    record_citizen_portal_reference,
    record_explicit_confirmation,
    sanitize_legacy_unverified_submission,
    stamp_application_version_and_check_invalidation,
    sync_application_record_to_db,
    validate_and_advance_application,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateDraftRequest(BaseModel):
    scheme_id: str
    form_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateDraftRequest(BaseModel):
    form_data: Dict[str, Any]


class ConfirmApplicationRequest(BaseModel):
    consent_acknowledged: bool = True
    expected_version: Optional[int] = None
    expected_hash: Optional[str] = None


class SubmitApplicationRequest(BaseModel):
    idempotency_key: Optional[str] = None


class RecordPortalReferenceRequest(BaseModel):
    official_reference_number: str
    submission_date: Optional[str] = None
    portal_notes: Optional[str] = None
    confirmation_acknowledged: bool = True


def clean_val(v: Any) -> Any:
    """Normalize missing values to empty string; never allow literal 'null' or 'undefined'."""
    if v is None:
        return ""
    if isinstance(v, str):
        trimmed = v.strip()
        if trimmed.lower() in ("null", "undefined", "none"):
            return ""
        return trimmed
    return v


def canonical_scheme_key(scheme_id_or_code: str, scheme_name: str = "") -> str:
    """Resolve canonical scheme key while strictly preserving PMAY-U vs PMAY-G distinction."""
    s_id = (scheme_id_or_code or "").strip().upper()
    s_name = (scheme_name or "").strip().upper()

    if s_id in SCHEME_CODE_ALIASES:
        return SCHEME_CODE_ALIASES[s_id]
    if "PM-KISAN" in s_id or "PM KISAN" in s_name or "KISAN SAMMAN" in s_name:
        return "PM-KISAN"
    if "AB-PMJAY" in s_id or "PMJAY" in s_id or "AYUSHMAN" in s_name:
        return "AB-PMJAY"
    if "MLBY" in s_id or "LADKI BAHIN" in s_name:
        return "MLBY-MH"
    if "PMAY-U" in s_id or "PMAY_U" in s_id or "PMAYU" in s_id or "URBAN" in s_name:
        return "PMAY-U"
    if "PMAY-G" in s_id or "PMAY_G" in s_id or "PMAYG" in s_id or "GRAMIN" in s_name:
        return "PMAY-G"
    if s_id == "APY" or "ATAL PENSION" in s_name or "ATAL PENSION" in s_id:
        return "APY"
    return s_id or s_name


def resolve_scheme_info(scheme_identifier: str, db: Session) -> Tuple[Optional[Scheme], str, str, str]:
    """Resolves scheme model, canonical code, human name, and official portal URL."""
    scheme = None
    try:
        scheme_uuid = uuid.UUID(scheme_identifier)
        scheme = db.query(Scheme).filter(Scheme.id == scheme_uuid).first()
    except (ValueError, AttributeError):
        scheme = db.query(Scheme).filter(
            (Scheme.scheme_code == scheme_identifier) |
            (Scheme.scheme_code == scheme_identifier.upper())
        ).first()

    code = scheme.scheme_code if scheme else canonical_scheme_key(scheme_identifier)
    name = scheme.name if scheme else (scheme_identifier if code == scheme_identifier else code)
    official_url = (scheme.application_url or scheme.official_url) if scheme else "https://india.gov.in"
    return scheme, code, name, official_url


def build_prefilled_form(
    scheme_code: str,
    profile: UserProfile,
    overrides: Optional[Dict[str, Any]] = None,
    existing_draft: Optional[Dict[str, Any]] = None,
    lang: str = "en",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Delegates draft form generation to the Universal Multi-Scheme Pre-Fill Engine.
    Returns (form_data_dict, full_prefill_result).
    """
    prefill = run_universal_prefill(
        scheme_code_or_name=scheme_code,
        profile=profile,
        existing_draft=existing_draft,
        form_overrides=overrides,
        lang=lang,
    )
    form_data: Dict[str, Any] = {}
    if prefill.get("form_supported"):
        for k, v in (prefill.get("values") or {}).items():
            form_data[k] = "" if is_empty_value(v) else clean_val(v)
    else:
        for k, v in (overrides or {}).items():
            if not is_empty_value(v):
                form_data[k] = clean_val(v)
    return form_data, prefill


def normalize_and_consolidate_apps(apps: List[Dict[str, Any]], db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Consolidates multiple unsubmitted drafts for the same canonical scheme without merging
    distinct schemes (such as PMAY-U vs PMAY-G) and without losing citizen-entered fields.
    Submitted applications are preserved cleanly.
    """
    consolidated: List[Dict[str, Any]] = []
    seen_scheme_drafts: Dict[str, Dict[str, Any]] = {}

    for raw_app in apps:
        app = dict(raw_app)
        state = app.get("lifecycle_state", "draft")
        s_id = app.get("scheme_code") or app.get("scheme_id") or ""
        s_name = app.get("scheme_name") or ""
        canonical_key = canonical_scheme_key(s_id, s_name)

        raw_form = app.get("form_data") or {}
        cleaned_form = {k: clean_val(v) for k, v in raw_form.items()}
        app["form_data"] = cleaned_form

        if not app.get("scheme_code") and canonical_key:
            app["scheme_code"] = canonical_key

        # Quarantine unverified/synthetic legacy 'submitted' packets without hiding real validation errors
        sanitize_legacy_unverified_submission(app)
        state = app.get("lifecycle_state", "draft")

        if (state == STATE_SUBMITTED and is_verified_government_submission(app)) or state in (STATE_PORTAL_SUBMITTED, STATE_SUBMISSION_UNKNOWN) or app.get("legacy_synthetic_submission"):
            consolidated.append(app)
        else:
            if canonical_key in seen_scheme_drafts:
                existing = seen_scheme_drafts[canonical_key]
                for k, v in cleaned_form.items():
                    if v not in ("", None) and existing["form_data"].get(k) in ("", None):
                        existing["form_data"][k] = v
                existing_filled = sum(1 for v in existing["form_data"].values() if v not in ("", None))
                this_filled = sum(1 for v in cleaned_form.values() if v not in ("", None))
                if this_filled > existing_filled:
                    for k, v in existing["form_data"].items():
                        if v not in ("", None) and cleaned_form.get(k) in ("", None):
                            cleaned_form[k] = v
                    existing["form_data"] = cleaned_form
                    existing["id"] = app["id"]
                    if app.get("scheme_name"):
                        existing["scheme_name"] = app["scheme_name"]
            else:
                seen_scheme_drafts[canonical_key] = app
                consolidated.append(app)

    return consolidated


def validate_draft_packet(
    target_app: Dict[str, Any],
    profile: UserProfile,
    db: Optional[Session],
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Delegates to the unified Application Readiness Engine computing profile completeness,
    form fields, scheme-specific conditional document applicability, and document verification states.
    """
    scheme_code = target_app.get("scheme_code") or canonical_scheme_key(
        target_app.get("scheme_id") or "", target_app.get("scheme_name") or ""
    )
    scheme_id = target_app.get("scheme_id")
    form_data = target_app.get("form_data") or {}

    return evaluate_application_readiness(
        scheme_code=scheme_code,
        scheme_id=scheme_id,
        form_data=form_data,
        profile=profile,
        db=db,
        lang=lang,
        resolved_conflicts=target_app.get("resolved_conflicts"),
    )


@router.get(
    "",
    response_model=APIResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List citizen application drafts and readiness packets",
)
def get_applications(
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[Dict[str, Any]]]:
    """
    Retrieve all application readiness packets for the authenticated user.
    Recomputes live readiness on unsubmitted drafts so document verification or profile
    updates immediately reflect accurately across the dashboard and applications view.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        return APIResponse.ok([])

    raw_apps = list(profile.profile_data.get("applications", []))
    # Enforce citizen isolation strictly
    own_apps = [
        a for a in raw_apps
        if not a.get("user_id") or str(a.get("user_id")) == str(current_user.id)
    ]
    consolidated = normalize_and_consolidate_apps(own_apps, db)

    # Refresh live readiness, snapshot version/hash & confirmation validity cleanly
    mutated_invalidation = False
    for app in consolidated:
        sanitize_legacy_unverified_submission(app)
        canon_code = app.get("scheme_code") or canonical_scheme_key(
            app.get("scheme_id") or "", app.get("scheme_name") or ""
        )
        portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
        app["portal_integration"] = portal_entry
        if app.get("legacy_synthetic_submission"):
            app["schema_available"] = bool(get_form_schema_for_scheme(app.get("scheme_code") or ""))
            app["application_record"] = build_normalized_application_record(app, current_user.id, portal_entry)
            continue
        cur_state_before = app.get("lifecycle_state") or STATE_DRAFT
        if not is_verified_government_submission(app) and cur_state_before not in (STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN):
            prev_confirmed_at = app.get("confirmed_at")
            review_meta = build_application_review_summary(
                target_app=app,
                profile=profile,
                current_user=current_user,
                db=db,
                lang=lang,
            )
            prefill_meta = run_universal_prefill(
                scheme_code_or_name=canon_code,
                profile=profile,
                user=current_user,
                db=db,
                existing_draft=app,
                lang=lang,
            )
            app["schema_available"] = bool(prefill_meta.get("schema_available", prefill_meta.get("form_supported")))
            app["prefill_summary"] = prefill_meta
            app["review_summary"] = review_meta
            app["validation_result"] = review_meta["validation_result"]
            app["portal_integration"] = review_meta.get("portal_integration") or portal_entry
            if prev_confirmed_at and not app.get("confirmed_at"):
                mutated_invalidation = True
            live_val = app["validation_result"]
            cur_st = app.get("lifecycle_state") or STATE_DRAFT
            if cur_st == STATE_SUBMISSION_UNKNOWN:
                app["lifecycle_state"] = STATE_SUBMISSION_UNKNOWN
            elif cur_st == STATE_PORTAL_SUBMITTED:
                app["lifecycle_state"] = STATE_PORTAL_SUBMITTED
            elif cur_st == STATE_CONFIRMED and review_meta["confirmation"]["valid"]:
                app["lifecycle_state"] = STATE_CONFIRMED
            elif cur_st == STATE_SUBMISSION_FAILED:
                app["lifecycle_state"] = STATE_SUBMISSION_FAILED
            elif live_val["passed"]:
                app["lifecycle_state"] = STATE_AWAITING_CONFIRMATION
            else:
                app["lifecycle_state"] = STATE_DRAFT
        app["application_record"] = build_normalized_application_record(app, current_user.id, portal_entry)

    if mutated_invalidation:
        current_profile_data = dict(profile.profile_data or {})
        current_profile_data["applications"] = consolidated
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        db.commit()

    return APIResponse.ok(consolidated)


@router.get(
    "/schema/{scheme_identifier}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get application form schema for a specific scheme",
)
def get_scheme_schema(
    scheme_identifier: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Retrieve the authoritative form schema and section fields for a welfare scheme.
    Never fabricates a generic fallback schema for unsupported schemes.
    """
    scheme, code, name, official_url = resolve_scheme_info(scheme_identifier, db)
    schema = get_form_schema_for_scheme(code)

    if not schema:
        return APIResponse.ok(get_unavailable_schema_payload(code, name, official_url, lang=lang))

    out_schema = dict(schema)
    out_schema["schema_available"] = True
    out_schema["portal_integration"] = get_portal_integration_entry(code, db=db, scheme=scheme, lang=lang)
    return APIResponse.ok(out_schema)


@router.get(
    "/portal-registry",
    response_model=APIResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List reusable official portal integration entries across all schemes",
)
def get_portal_registry(
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[Dict[str, Any]]]:
    return APIResponse.ok(list_portal_registry(db=db, lang=lang))


@router.get(
    "/portal-registry/{scheme_identifier}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get official portal integration metadata, instructions, documents, and mode for a scheme",
)
def get_scheme_portal_integration(
    scheme_identifier: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    scheme, code, _, _ = resolve_scheme_info(scheme_identifier, db)
    entry = get_portal_integration_entry(code, db=db, scheme=scheme, lang=lang)
    return APIResponse.ok(entry)


@router.get(
    "/{app_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get single application draft details",
)
def get_application_by_id(
    app_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    apps = profile.profile_data.get("applications", [])
    for raw_app in apps:
        if raw_app.get("id") == app_id:
            if raw_app.get("user_id") and str(raw_app.get("user_id")) != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
            app = dict(raw_app)
            app["form_data"] = {k: clean_val(v) for k, v in (app.get("form_data") or {}).items()}
            sanitize_legacy_unverified_submission(app)
            canon_code = app.get("scheme_code") or canonical_scheme_key(app.get("scheme_id") or "", app.get("scheme_name") or "")
            portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
            app["portal_integration"] = portal_entry
            if not is_verified_government_submission(app) and app.get("lifecycle_state") != STATE_SUBMITTING:
                review_meta = build_application_review_summary(dict(app), profile, current_user, db, lang=lang)
                app["review_summary"] = review_meta
                if not app.get("legacy_synthetic_submission") and app.get("lifecycle_state") != STATE_PORTAL_SUBMITTED:
                    app["validation_result"] = review_meta["validation_result"]
            app["application_record"] = build_normalized_application_record(app, current_user.id, portal_entry)
            return APIResponse.ok(app)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")


@router.get(
    "/{app_id}/review",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get complete field-by-field application review summary with provenance and confirmation state",
)
def get_application_review(
    app_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app or (target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    prev_confirmed = target_app.get("confirmed_at")
    review = build_application_review_summary(target_app, profile, current_user, db, lang=lang)
    if prev_confirmed and not target_app.get("confirmed_at"):
        current_profile_data["applications"] = apps
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        db.commit()
    return APIResponse.ok(review)


@router.get(
    "/{app_id}/status",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get honest application lifecycle & submission status",
)
def get_application_status(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    apps = profile.profile_data.get("applications", [])
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app or (target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    app_copy = dict(target_app)
    sanitize_legacy_unverified_submission(app_copy)
    state = app_copy.get("lifecycle_state") or STATE_DRAFT
    verified = is_verified_government_submission(app_copy)
    portal_sub = state == STATE_PORTAL_SUBMITTED and bool(app_copy.get("official_reference_number"))
    ext_ref = app_copy.get("external_reference_id") if verified else None
    off_ref = ext_ref if verified else (app_copy.get("official_reference_number") if portal_sub else None)
    canon_code = app_copy.get("scheme_code") or canonical_scheme_key(app_copy.get("scheme_id") or "", app_copy.get("scheme_name") or "")
    portal_entry = get_portal_integration_entry(canon_code, db=db)
    src_type = (
        "official_integration"
        if verified
        else (
            "citizen_reported_portal_reference"
            if portal_sub
            else ("legacy_unverified" if app_copy.get("legacy_synthetic_submission") else "manual_portal_required")
        )
    )
    return APIResponse.ok({
        "application_id": app_id,
        "status": state,
        "source_type": src_type,
        "source_reference": off_ref,
        "official_reference_number": off_ref,
        "submission_method": app_copy.get("submission_method") or portal_entry.get("submission_method"),
        "submission_date": app_copy.get("submission_date") or app_copy.get("submitted_at"),
        "portal_url": app_copy.get("portal_url") or portal_entry.get("official_application_url"),
        "tracking_url": portal_entry.get("tracking_url"),
        "is_verified_government_submission": verified,
        "legacy_synthetic_submission": bool(app_copy.get("legacy_synthetic_submission")),
        "blind_retry_blocked": bool(state == STATE_SUBMISSION_UNKNOWN or app_copy.get("blind_retry_blocked")),
        "notes": app_copy.get("submission_outcome") or state,
        "recorded_at": app_copy.get("submission_date") or app_copy.get("submitted_at") or app_copy.get("confirmed_at") or app_copy.get("updated_at"),
        "application_record": build_normalized_application_record(app_copy, current_user.id, portal_entry),
    })


@router.post(
    "/draft",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Create or reuse application readiness draft (prevents duplicates)",
)
def create_application_draft(
    payload: CreateDraftRequest,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
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

    scheme, code, scheme_name, official_url = resolve_scheme_info(payload.scheme_id, db)
    target_canon = canonical_scheme_key(code, scheme_name)
    now_iso = datetime.now(timezone.utc).isoformat()

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))

    # Strictly match same canonical scheme without colliding PMAY-U and PMAY-G,
    # and never reuse verified submitted packets, in-flight/unknown packets, or legacy unverified records.
    existing_draft = next(
        (
            a for a in apps
            if a.get("lifecycle_state") not in (STATE_SUBMITTED, STATE_PORTAL_SUBMITTED, STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
            and not a.get("legacy_synthetic_submission")
            and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
            and (
                canonical_scheme_key(a.get("scheme_code") or a.get("scheme_id") or "", a.get("scheme_name") or "") == target_canon
                or (scheme and a.get("scheme_id") == str(scheme.id))
            )
        ),
        None,
    )

    portal_entry = get_portal_integration_entry(target_canon, db=db, scheme=scheme, lang=lang)

    if existing_draft:
        merged_form, prefill_meta = build_prefilled_form(
            code, profile, overrides=payload.form_data, existing_draft=existing_draft, lang=lang
        )
        existing_draft["form_data"] = merged_form
        if prefill_meta.get("resolved_conflicts"):
            existing_draft["resolved_conflicts"] = prefill_meta["resolved_conflicts"]
        existing_draft["schema_available"] = bool(prefill_meta.get("schema_available", prefill_meta.get("form_supported")))
        existing_draft["prefill_summary"] = prefill_meta
        existing_draft["portal_integration"] = portal_entry
        existing_draft["submission_method"] = existing_draft.get("submission_method") or portal_entry.get("submission_method")
        existing_draft["portal_url"] = portal_entry.get("official_application_url") or official_url
        existing_draft["tracking_url"] = portal_entry.get("tracking_url")
        existing_draft["updated_at"] = now_iso
        stamp_application_version_and_check_invalidation(existing_draft, profile, increment_on_change=True)
        existing_draft["validation_result"] = validate_draft_packet(existing_draft, profile, db, lang=lang)
        existing_draft["application_record"] = build_normalized_application_record(existing_draft, current_user.id, portal_entry)
        current_profile_data["applications"] = apps
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        sync_application_record_to_db(db, existing_draft, current_user.id, portal_entry)
        db.commit()
        db.refresh(profile)
        return APIResponse.ok(existing_draft)

    prefilled_form, prefill_meta = build_prefilled_form(code, profile, overrides=payload.form_data, lang=lang)
    app_id = f"app-draft-{uuid.uuid4().hex[:8]}"
    eff_portal_url = portal_entry.get("official_application_url") or official_url

    draft: Dict[str, Any] = {
        "id": app_id,
        "user_id": str(current_user.id),
        "scheme_id": str(scheme.id) if scheme else payload.scheme_id,
        "scheme_code": code,
        "scheme_name": scheme_name,
        "official_url": eff_portal_url,
        "portal_url": eff_portal_url,
        "tracking_url": portal_entry.get("tracking_url"),
        "submission_method": portal_entry.get("submission_method"),
        "portal_integration": portal_entry,
        "schema_available": bool(prefill_meta.get("schema_available", prefill_meta.get("form_supported"))),
        "form_data": prefilled_form,
        "resolved_conflicts": prefill_meta.get("resolved_conflicts") or {},
        "prefill_summary": prefill_meta,
        "lifecycle_state": STATE_DRAFT,
        "version": 1,
        "created_at": now_iso,
        "updated_at": now_iso,
        "audit_trail": [
            {"timestamp": now_iso, "action": "DRAFT_CREATED", "actor": str(current_user.id), "details": f"Created {code} application draft v1."}
        ],
    }
    stamp_application_version_and_check_invalidation(draft, profile, increment_on_change=False)
    draft["validation_result"] = validate_draft_packet(draft, profile, db, lang=lang)
    if draft["validation_result"]["passed"]:
        draft["lifecycle_state"] = STATE_AWAITING_CONFIRMATION
    draft["application_record"] = build_normalized_application_record(draft, current_user.id, portal_entry)

    apps.insert(0, draft)
    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    sync_application_record_to_db(db, draft, current_user.id, portal_entry)
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(draft)


@router.put(
    "/{app_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update application draft form data, invalidate prior confirmation, and recalculate readiness",
)
def update_application_draft(
    app_id: str,
    payload: UpdateDraftRequest,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))

    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    sanitize_legacy_unverified_submission(target_app)
    if (
        (target_app.get("lifecycle_state") == STATE_SUBMITTED and is_verified_government_submission(target_app))
        or target_app.get("lifecycle_state") in (STATE_PORTAL_SUBMITTED, STATE_SUBMITTING, STATE_SUBMISSION_UNKNOWN)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submitted, portal-submitted, in-flight, or submission_unknown application packets cannot be edited.",
        )

    was_confirmed = bool(target_app.get("confirmed_at")) or target_app.get("lifecycle_state") == STATE_CONFIRMED
    old_form_data = dict(target_app.get("form_data") or {})
    clean_updates = {k: clean_val(v) for k, v in payload.form_data.items()}
    changed_overrides = {
        k: v for k, v in clean_updates.items()
        if str(clean_val(old_form_data.get(k))) != str(v) and v != ""
    }
    target_app["form_data"].update(clean_updates)
    canon_code = target_app.get("scheme_code") or canonical_scheme_key(
        target_app.get("scheme_id") or "", target_app.get("scheme_name") or ""
    )
    prefill_meta = run_universal_prefill(
        scheme_code_or_name=canon_code,
        profile=profile,
        user=current_user,
        db=db,
        existing_draft=target_app,
        form_overrides=changed_overrides,
        lang=lang,
    )
    if prefill_meta.get("resolved_conflicts"):
        target_app["resolved_conflicts"] = prefill_meta["resolved_conflicts"]
    if prefill_meta.get("field_sources"):
        target_app["field_sources"] = prefill_meta["field_sources"]
    target_app["prefill_summary"] = prefill_meta
    target_app["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Bump version/hash & strictly invalidate any prior confirmation on edit
    invalidated, _ = stamp_application_version_and_check_invalidation(
        target_app, profile, increment_on_change=True
    )
    if was_confirmed or invalidated:
        target_app["confirmed_at"] = None
        target_app["confirmed_hash"] = None
        target_app["confirmed_version"] = None
        target_app["submission_outcome"] = None
        target_app["lifecycle_state"] = STATE_DRAFT

    target_app["validation_result"] = validate_draft_packet(target_app, profile, db, lang=lang)
    target_app["lifecycle_state"] = (
        STATE_AWAITING_CONFIRMATION if target_app["validation_result"]["passed"] else STATE_DRAFT
    )
    review_summary = build_application_review_summary(
        target_app, profile, current_user, db, lang=lang
    )
    target_app["review_summary"] = review_summary
    target_app["portal_integration"] = review_summary.get("portal_integration")
    target_app["application_record"] = review_summary.get("application_record")

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    sync_application_record_to_db(db, target_app, current_user.id, review_summary.get("portal_integration"))
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(target_app)


@router.post(
    "/{app_id}/validate",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Validate draft details and advance lifecycle state safely",
)
def validate_application_draft(
    app_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    validation_result = validate_and_advance_application(
        target_app=target_app,
        profile=profile,
        current_user=current_user,
        db=db,
        lang=lang,
    )

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    sync_application_record_to_db(db, target_app, current_user.id)
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(validation_result)


@router.post(
    "/{app_id}/confirm",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Record explicit citizen confirmation bound strictly to reviewed application version and hash",
)
def confirm_application(
    app_id: str,
    payload: Optional[ConfirmApplicationRequest] = None,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    try:
        result = record_explicit_confirmation(
            target_app=target_app,
            profile=profile,
            current_user=current_user,
            db=db,
            lang=lang,
            consent_acknowledged=payload.consent_acknowledged if payload is not None else True,
            expected_version=payload.expected_version if payload is not None else None,
            expected_hash=payload.expected_hash if payload is not None else None,
        )
    except HTTPException:
        current_profile_data["applications"] = apps
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        db.commit()
        raise

    # Persist formal consent audit entry if DB session is active
    try:
        db.add(
            UserConsent(
                user_id=current_user.id,
                consent_type=f"app_confirm:{app_id}:v{result['confirmed_version']}"[:100],
                consent_status="given",
            )
        )
    except Exception:
        pass

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    flag_modified(profile, "profile_data")
    sync_application_record_to_db(db, target_app, current_user.id, result.get("portal_integration"))
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(result)


@router.post(
    "/{app_id}/submit",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Safely orchestrate application submission via verified portal integrations or honest manual-portal guidance",
)
def submit_application(
    app_id: str,
    payload: Optional[SubmitApplicationRequest] = None,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    raw_header_key = idempotency_key if isinstance(idempotency_key, str) else None
    eff_key = raw_header_key or (payload.idempotency_key if payload else None)
    res = orchestrate_application_submission(
        target_app=target_app,
        profile=profile,
        current_user=current_user,
        db=db,
        current_profile_data=current_profile_data,
        apps_list=apps,
        lang=lang,
        idempotency_key=eff_key,
    )
    return APIResponse.ok(res)


@router.post(
    "/{app_id}/portal-reference",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Mode B: Record citizen-reported official government portal application reference number",
)
def record_portal_reference_endpoint(
    app_id: str,
    payload: RecordPortalReferenceRequest,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    res = record_citizen_portal_reference(
        target_app=target_app,
        profile=profile,
        current_user=current_user,
        db=db,
        official_reference_number=payload.official_reference_number,
        submission_date=payload.submission_date,
        portal_notes=payload.portal_notes,
        confirmation_acknowledged=payload.confirmation_acknowledged,
        current_profile_data=current_profile_data,
        apps_list=apps,
        lang=lang,
    )
    return APIResponse.ok(res)


@router.post(
    "/{app_id}/reconcile",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Reconcile uncertain previous portal submission status before allowing retry",
)
def reconcile_submission(
    app_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if target_app.get("user_id") and str(target_app.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    res = reconcile_application_submission(
        target_app=target_app,
        profile=profile,
        current_user=current_user,
        db=db,
        current_profile_data=current_profile_data,
        apps_list=apps,
        lang=lang,
    )
    return APIResponse.ok(res)

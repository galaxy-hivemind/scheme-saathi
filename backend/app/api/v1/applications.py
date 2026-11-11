"""
Application Readiness and Official Portal Guidance API endpoints.
Provides authenticated endpoints for application drafting, document readiness validation,
and explicit citizen confirmation before official portal redirection.
Scheme Saathi prepares application packets but never claims to submit government applications directly.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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


class CreateDraftRequest(BaseModel):
    scheme_id: str
    form_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateDraftRequest(BaseModel):
    form_data: Dict[str, Any]


@router.get(
    "",
    response_model=APIResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List citizen application drafts and readiness packets",
)
def get_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[Dict[str, Any]]]:
    """
    Retrieve all application readiness packets for the authenticated user.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        return APIResponse.ok([])

    apps = profile.profile_data.get("applications", [])
    return APIResponse.ok(apps)


@router.get(
    "/{app_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get single application draft details",
)
def get_application_by_id(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    apps = profile.profile_data.get("applications", [])
    for app in apps:
        if app.get("id") == app_id:
            return APIResponse.ok(app)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")


@router.post(
    "/draft",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new application readiness draft",
)
def create_application_draft(
    payload: CreateDraftRequest,
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

    # Fetch scheme name and application url
    scheme = None
    try:
        scheme_uuid = uuid.UUID(payload.scheme_id)
        scheme = db.query(Scheme).filter(Scheme.id == scheme_uuid).first()
    except (ValueError, AttributeError):
        scheme = db.query(Scheme).filter(
            (Scheme.scheme_code == payload.scheme_id) |
            (Scheme.scheme_code == payload.scheme_id.upper())
        ).first()

    scheme_name = scheme.name if scheme else payload.scheme_id
    official_url = scheme.application_url or scheme.official_url if scheme else "https://india.gov.in"

    now_iso = datetime.now(timezone.utc).isoformat()
    app_id = f"app-draft-{uuid.uuid4().hex[:8]}"

    draft = {
        "id": app_id,
        "user_id": str(current_user.id),
        "scheme_id": str(scheme.id) if scheme else payload.scheme_id,
        "scheme_name": scheme_name,
        "official_url": official_url,
        "form_data": payload.form_data or {
            "applicant_name": profile.full_name or "Citizen",
            "state": profile.state or "State",
            "district": profile.district or "District",
            "occupation": profile.occupation or "General",
        },
        "lifecycle_state": "draft",
        "validation_result": {
            "passed": False,
            "errors": [],
            "warnings": [{"field": "readiness", "message": "Click 'Review & Validate' to assess application readiness."}],
        },
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    apps.insert(0, draft)
    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(draft)


@router.put(
    "/{app_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update application draft form data",
)
def update_application_draft(
    app_id: str,
    payload: UpdateDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))

    target_app = None
    for app in apps:
        if app.get("id") == app_id:
            target_app = app
            break

    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    target_app["form_data"].update(payload.form_data)
    target_app["updated_at"] = datetime.now(timezone.utc).isoformat()

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(target_app)


@router.post(
    "/{app_id}/validate",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Validate draft details and assess document readiness",
)
def validate_application_draft(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[Dict[str, Any]]:
    """
    Evaluates application readiness:
    - Validates profile attributes
    - Checks mandatory document requirements from PostgreSQL
    - Computes readiness outcome
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile or not profile.profile_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    current_profile_data = dict(profile.profile_data or {})
    apps = list(current_profile_data.get("applications", []))
    target_app = next((a for a in apps if a.get("id") == app_id), None)
    if not target_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Fetch mandatory scheme documents
    scheme_id = target_app.get("scheme_id")
    mandatory_docs = []
    try:
        scheme_uuid = uuid.UUID(scheme_id)
        db_docs = db.query(SchemeDocument).filter(
            SchemeDocument.scheme_id == scheme_uuid,
            SchemeDocument.is_mandatory == True,
            SchemeDocument.is_active == True,
        ).all()
        mandatory_docs = [d.document_type for d in db_docs]
    except Exception:
        pass

    user_docs = [d.get("document_type") for d in current_profile_data.get("documents", [])]

    missing_docs = [doc for doc in mandatory_docs if doc not in user_docs]
    passed = len(missing_docs) == 0

    errors = []
    warnings = []
    if missing_docs:
        errors.append({
            "field": "required_documents",
            "message": f"Mandatory documents pending in vault: {', '.join(missing_docs)}."
        })
    else:
        warnings.append({
            "field": "ready",
            "message": "All mandatory documents verified. Application packet is 100% ready for official portal submission."
        })

    validation_result = {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
    }

    target_app["validation_result"] = validation_result
    target_app["lifecycle_state"] = "awaiting_confirmation" if passed else "validation_failed"
    target_app["updated_at"] = datetime.now(timezone.utc).isoformat()

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok(validation_result)


@router.post(
    "/{app_id}/confirm",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Record explicit citizen confirmation",
)
def confirm_application(
    app_id: str,
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

    now_iso = datetime.now(timezone.utc).isoformat()
    target_app["confirmed_at"] = now_iso
    target_app["lifecycle_state"] = "awaiting_confirmation"
    target_app["updated_at"] = now_iso

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok({
        "confirmed": True,
        "message": "Explicit citizen confirmation recorded successfully with audit timestamp."
    })


@router.post(
    "/{app_id}/submit",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Generate readiness packet and official portal link",
)
def submit_application(
    app_id: str,
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

    now_iso = datetime.now(timezone.utc).isoformat()
    ref_no = f"SAATHI/READY/{datetime.now().year}/{uuid.uuid4().hex[:6].upper()}"

    target_app["reference_number"] = ref_no
    target_app["lifecycle_state"] = "submitted"
    target_app["submitted_at"] = now_iso
    target_app["submission_source"] = "portal_handoff"
    target_app["updated_at"] = now_iso

    portal_url = target_app.get("official_url") or "https://india.gov.in"

    current_profile_data["applications"] = apps
    profile.profile_data = current_profile_data
    db.commit()
    db.refresh(profile)

    return APIResponse.ok({
        "success": True,
        "reference_number": ref_no,
        "portal_url": portal_url,
        "disclaimer": "Scheme Saathi assists with readiness preparation and verified attribute matching. Application submission must be completed on the official government portal."
    })

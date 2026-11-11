"""
Application Draft service for preparing scheme application packages,
prefilling citizen demographic snapshots, linking verified documents,
resolving external portal links, and tracking external portal submissions.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.exceptions import NotFoundError, ValidationError, ConflictError
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.models.application_draft import ApplicationDraft
from app.models.application_status_history import ApplicationStatusHistory
from app.models.scheme import Scheme
from app.schemas.application import (
    ApplicationDraftCreate,
    ApplicationDraftUpdate,
    ApplicationDraftSubmitRequest,
    ApplicationDraftResponse,
)
from app.services import scheme_service, beneficiary_service, document_service, eligibility_service, notification_service

logger = logging.getLogger(__name__)


def _build_application_response(draft: ApplicationDraft, scheme: Scheme, target_name: str) -> ApplicationDraftResponse:
    """Helper to assemble ApplicationDraftResponse with denormalized scheme and applicant details."""
    now_utc = datetime.now(timezone.utc)
    return ApplicationDraftResponse(
        id=draft.id,
        user_id=draft.user_id,
        beneficiary_id=draft.beneficiary_id,
        scheme_id=draft.scheme_id,
        scheme_code=scheme.scheme_code,
        scheme_name=scheme.name,
        target_name=target_name,
        status=draft.status,
        prefilled_data=draft.prefilled_data,
        attached_documents=draft.attached_documents,
        official_portal_url=draft.official_portal_url,
        notes=draft.notes,
        external_reference_number=draft.external_reference_number,
        submitted_at=draft.submitted_at,
        created_at=draft.created_at or now_utc,
        updated_at=draft.updated_at or now_utc,
    )


def create_application_draft(
    db: Session,
    current_user: User,
    scheme_id: uuid.UUID,
    beneficiary_id: Optional[uuid.UUID] = None,
    notes: Optional[str] = None,
) -> ApplicationDraftResponse:
    """
    Prepare and persist an application draft package:
    1. Verify scheme and applicant ownership.
    2. Prefill demographic data snapshot (self or family beneficiary).
    3. Run deterministic eligibility check to capture rule evaluation snapshot.
    4. Link matching uploaded documents from checklist.
    5. Resolve official government portal URL.
    6. Set status (READY if all mandatory documents attached, else DRAFT).
    """
    scheme = scheme_service.get_scheme_by_id(db, scheme_id)

    # 1. Resolve target applicant and extract demographic snapshot
    if beneficiary_id is not None:
        ben = beneficiary_service.get_beneficiary(db, current_user, beneficiary_id)
        target_name = ben.full_name
        demographics: Dict[str, Any] = {
            "applicant_type": "beneficiary",
            "relationship": ben.relationship,
            "full_name": ben.full_name,
            "date_of_birth": ben.date_of_birth.isoformat() if ben.date_of_birth else None,
            "gender": ben.gender,
            "state": ben.state,
            "district": ben.district,
            "residence_type": ben.residence_type,
            "occupation": ben.occupation,
            "annual_family_income": float(ben.annual_family_income) if ben.annual_family_income is not None else None,
            "profile_data": ben.profile_data or {},
        }
    else:
        prof = current_user.profile
        target_name = prof.full_name if prof and prof.full_name else "Self"
        demographics = {
            "applicant_type": "self",
            "relationship": "self",
            "full_name": prof.full_name if prof else None,
            "date_of_birth": prof.date_of_birth.isoformat() if prof and prof.date_of_birth else None,
            "gender": prof.gender if prof else None,
            "state": prof.state if prof else None,
            "district": prof.district if prof else None,
            "residence_type": prof.residence_type if prof else None,
            "occupation": prof.occupation if prof else None,
            "annual_family_income": float(prof.annual_family_income) if prof and prof.annual_family_income is not None else None,
            "profile_data": prof.profile_data or {} if prof else {},
        }

    # 2. Capture eligibility evaluation snapshot
    try:
        elig_result = eligibility_service.evaluate_scheme_eligibility(
            db=db,
            current_user=current_user,
            scheme_id=scheme_id,
            beneficiary_id=beneficiary_id,
        )
        status_val = (
            elig_result.overall_status.value
            if hasattr(elig_result.overall_status, "value")
            else str(getattr(elig_result, "overall_status", "UNKNOWN"))
        )
        result_val = (
            elig_result.result.value
            if hasattr(elig_result.result, "value")
            else str(getattr(elig_result, "result", "insufficient_information"))
        )
        demographics["eligibility_snapshot"] = {
            "status": status_val,
            "result": result_val,
            "rule_version": getattr(elig_result, "rule_version", 1),
            "missing_fields": getattr(elig_result, "missing_fields", []),
            "reasons": getattr(elig_result, "reasons", []),
        }
    except Exception as e:
        logger.warning(f"Could not compute eligibility snapshot for draft: {e}")
        demographics["eligibility_snapshot"] = {
            "status": "UNKNOWN",
            "note": "Eligibility check could not be computed automatically.",
        }

    # 3. Match and link uploaded citizen documents
    checklist = document_service.get_checklist(
        db=db,
        current_user=current_user,
        scheme_id=scheme_id,
        beneficiary_id=beneficiary_id,
    )

    attached_docs: List[Dict[str, Any]] = []
    all_checklist_items = checklist.mandatory_documents + checklist.optional_documents
    for item in all_checklist_items:
        if item.status == "UPLOADED" and item.attached_document_id:
            attached_docs.append({
                "document_type": item.document_type,
                "title": item.title,
                "citizen_document_id": str(item.attached_document_id),
                "file_name": item.attached_file_name,
                "verification_status": item.attached_verification_status,
                "is_mandatory": item.is_mandatory,
            })

    # 4. Resolve portal link & determine initial status
    portal_url = scheme.application_url or scheme.official_url
    initial_status = "READY" if checklist.is_complete else "DRAFT"

    # 5. Create Draft record
    draft = ApplicationDraft(
        id=uuid.uuid4(),
        user_id=current_user.id,
        beneficiary_id=beneficiary_id,
        scheme_id=scheme_id,
        status=initial_status,
        prefilled_data=demographics,
        attached_documents=attached_docs,
        official_portal_url=portal_url,
        notes=notes.strip() if notes else None,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    logger.info(
        f"Created application draft {draft.id} ({initial_status}) for scheme {scheme.scheme_code}, user {current_user.id}"
    )
    return _build_application_response(draft, scheme, target_name)


def get_application_draft_by_id(
    db: Session,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ApplicationDraftResponse:
    """Retrieve an application draft by ID with strict tenant isolation."""
    stmt = (
        select(ApplicationDraft)
        .where(and_(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == user_id))
    )
    draft = db.execute(stmt).scalar_one_or_none()
    if not draft:
        raise NotFoundError("Application draft not found.")

    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    if draft.beneficiary_id is not None:
        ben = db.scalar(
            select(BeneficiaryProfile).where(
                BeneficiaryProfile.id == draft.beneficiary_id,
                BeneficiaryProfile.user_id == user_id,
            )
        )
        target_name = ben.full_name if ben else "Beneficiary"
    else:
        prof = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        target_name = prof.full_name if prof and prof.full_name else "Self"

    return _build_application_response(draft, scheme, target_name)


def list_application_drafts(
    db: Session,
    current_user: User,
    status: Optional[str] = None,
    scheme_id: Optional[uuid.UUID] = None,
) -> List[ApplicationDraftResponse]:
    """List application drafts belonging to current user."""
    stmt = select(ApplicationDraft).where(ApplicationDraft.user_id == current_user.id)

    if status:
        stmt = stmt.where(ApplicationDraft.status == status.strip().upper())
    if scheme_id:
        stmt = stmt.where(ApplicationDraft.scheme_id == scheme_id)

    stmt = stmt.order_by(ApplicationDraft.created_at.desc())
    drafts = list(db.execute(stmt).scalars().all())

    results: List[ApplicationDraftResponse] = []
    for draft in drafts:
        scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
        if draft.beneficiary_id is not None:
            ben = db.scalar(
                select(BeneficiaryProfile).where(
                    BeneficiaryProfile.id == draft.beneficiary_id,
                    BeneficiaryProfile.user_id == current_user.id,
                )
            )
            target_name = ben.full_name if ben else "Beneficiary"
        else:
            prof = current_user.profile
            target_name = prof.full_name if prof and prof.full_name else "Self"
        results.append(_build_application_response(draft, scheme, target_name))

    return results


def update_application_draft(
    db: Session,
    current_user: User,
    draft_id: uuid.UUID,
    update_data: ApplicationDraftUpdate,
) -> ApplicationDraftResponse:
    """Update citizen notes or form prefilled values in an application draft."""
    stmt = (
        select(ApplicationDraft)
        .where(and_(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == current_user.id))
    )
    draft = db.execute(stmt).scalar_one_or_none()
    if not draft:
        raise NotFoundError("Application draft not found.")

    if draft.status in ("SUBMITTED", "ARCHIVED"):
        raise ValidationError(f"Cannot update application draft in '{draft.status}' status.")

    if update_data.notes is not None:
        draft.notes = update_data.notes.strip() if update_data.notes.strip() else None

    if update_data.prefilled_data is not None:
        # Merge or update prefilled data
        updated_dict = dict(draft.prefilled_data)
        updated_dict.update(update_data.prefilled_data)
        draft.prefilled_data = updated_dict

    db.commit()
    db.refresh(draft)

    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    if draft.beneficiary_id is not None:
        ben = db.scalar(
            select(BeneficiaryProfile).where(
                BeneficiaryProfile.id == draft.beneficiary_id,
                BeneficiaryProfile.user_id == current_user.id,
            )
        )
        target_name = ben.full_name if ben else "Beneficiary"
    else:
        prof = current_user.profile
        target_name = prof.full_name if prof and prof.full_name else "Self"

    return _build_application_response(draft, scheme, target_name)


def submit_external_application(
    db: Session,
    current_user: User,
    draft_id: uuid.UUID,
    submit_data: ApplicationDraftSubmitRequest,
) -> ApplicationDraftResponse:
    """
    Record that the citizen has submitted the application on the external government portal,
    storing their portal reference number and transitioning draft status to SUBMITTED.
    """
    stmt = (
        select(ApplicationDraft)
        .where(and_(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == current_user.id))
    )
    draft = db.execute(stmt).scalar_one_or_none()
    if not draft:
        raise NotFoundError("Application draft not found.")

    ref_num = submit_data.external_reference_number.strip()
    if not ref_num:
        raise ValidationError("external_reference_number cannot be empty.")

    draft.external_reference_number = ref_num
    draft.status = "SUBMITTED"
    draft.submitted_at = datetime.now(timezone.utc)

    if submit_data.notes:
        draft.notes = submit_data.notes.strip()

    # Append initial immutable SUBMITTED status history event
    history_entry = ApplicationStatusHistory(
        application_id=draft.id,
        status="SUBMITTED",
        source_type="user_reported",
        source_reference=ref_num,
        notes=submit_data.notes.strip() if submit_data.notes else "Citizen recorded external portal submission.",
        created_at=draft.submitted_at,
    )
    db.add(history_entry)

    # Trigger submission notification
    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    scheme_name = getattr(scheme, "name", None) or getattr(scheme, "name_en", None) or "Scheme"
    notification_service.create_notification(
        db=db,
        user_id=current_user.id,
        title=f"Application Submitted: {scheme_name}",
        message=f"Application successfully submitted with reference number {ref_num}.",
        notification_type="status_update",
        priority="NORMAL",
        application_id=draft.id,
        channels=["in_app"],
        commit=False,
    )

    db.commit()
    db.refresh(draft)

    logger.info(
        f"Marked application draft {draft_id} as SUBMITTED with ref #{ref_num} for user {current_user.id}"
    )

    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    if draft.beneficiary_id is not None:
        ben = db.scalar(
            select(BeneficiaryProfile).where(
                BeneficiaryProfile.id == draft.beneficiary_id,
                BeneficiaryProfile.user_id == current_user.id,
            )
        )
        target_name = ben.full_name if ben else "Beneficiary"
    else:
        prof = current_user.profile
        target_name = prof.full_name if prof and prof.full_name else "Self"

    return _build_application_response(draft, scheme, target_name)


def delete_application_draft(
    db: Session,
    draft_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Delete an application draft."""
    stmt = (
        select(ApplicationDraft)
        .where(and_(ApplicationDraft.id == draft_id, ApplicationDraft.user_id == user_id))
    )
    draft = db.execute(stmt).scalar_one_or_none()
    if not draft:
        raise NotFoundError("Application draft not found.")

    db.delete(draft)
    db.commit()
    logger.info(f"Deleted application draft {draft_id} for user {user_id}")
    return True

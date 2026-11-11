"""
Tracking service managing immutable application status audit log, timeline retrieval,
external portal status synchronization, and notification triggers.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.application_draft import ApplicationDraft
from app.models.application_status_history import (
    ApplicationStatusHistory,
    VALID_APPLICATION_STATUSES,
    VALID_STATUS_SOURCES,
)
from app.models.beneficiary_profile import BeneficiaryProfile
from app.models.user_profile import UserProfile
from app.models.user import User
from app.schemas.tracking import (
    StatusTransitionCreate,
    StatusHistoryItemResponse,
    ApplicationTimelineResponse,
)
from app.services import scheme_service, notification_service
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError


def _build_timeline_response(
    db: Session,
    draft: ApplicationDraft,
    history_items: List[ApplicationStatusHistory],
) -> ApplicationTimelineResponse:
    """Build a complete ApplicationTimelineResponse from draft and its history."""
    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)

    if draft.beneficiary_id is not None:
        ben = db.scalar(
            select(BeneficiaryProfile).where(
                BeneficiaryProfile.id == draft.beneficiary_id,
                BeneficiaryProfile.user_id == draft.user_id,
            )
        )
        applicant_type = "beneficiary"
        target_name = ben.full_name if ben else "Beneficiary"
    else:
        prof = db.scalar(select(UserProfile).where(UserProfile.user_id == draft.user_id))
        applicant_type = "self"
        target_name = prof.full_name if prof and prof.full_name else "Self"

    history_responses = [
        StatusHistoryItemResponse.model_validate(h)
        for h in history_items
    ]

    scheme_name = getattr(scheme, "name", None) or getattr(scheme, "name_en", None) or "Unknown Scheme"
    scheme_code = getattr(scheme, "scheme_code", None) or getattr(scheme, "code", None)

    now = datetime.now(timezone.utc)
    return ApplicationTimelineResponse(
        application_id=draft.id,
        scheme_id=draft.scheme_id,
        scheme_name=scheme_name,
        scheme_code=scheme_code,
        applicant_type=applicant_type,
        target_name=target_name,
        current_status=draft.status,
        external_reference_number=draft.external_reference_number,
        official_portal_url=draft.official_portal_url,
        submitted_at=draft.submitted_at,
        history=history_responses,
        created_at=draft.created_at or now,
        updated_at=draft.updated_at or now,
    )


def record_status_transition(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    transition: StatusTransitionCreate,
) -> ApplicationTimelineResponse:
    """
    Record an application status transition, append immutable history record,
    and trigger citizen notification.
    """
    draft = db.scalar(
        select(ApplicationDraft).where(ApplicationDraft.id == application_id)
    )
    if not draft:
        raise NotFoundError("Application draft not found.")

    if draft.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this application draft.")

    status_clean = transition.status.strip().upper()
    if status_clean not in VALID_APPLICATION_STATUSES:
        raise ValidationError(
            f"Invalid status '{transition.status}'. Must be one of {VALID_APPLICATION_STATUSES}."
        )

    source_type_clean = (transition.source_type or "user_reported").strip().lower()
    if source_type_clean not in VALID_STATUS_SOURCES:
        raise ValidationError(
            f"Invalid source_type '{transition.source_type}'. Must be one of {VALID_STATUS_SOURCES}."
        )

    # Update draft status
    draft.status = status_clean
    if transition.source_reference:
        draft.external_reference_number = transition.source_reference.strip()

    now = datetime.now(timezone.utc)
    if status_clean == "SUBMITTED" and draft.submitted_at is None:
        draft.submitted_at = now
    draft.updated_at = now

    # Append immutable history
    history_entry = ApplicationStatusHistory(
        application_id=draft.id,
        status=status_clean,
        source_type=source_type_clean,
        source_reference=transition.source_reference.strip() if transition.source_reference else draft.external_reference_number,
        notes=transition.notes.strip() if transition.notes else None,
        created_at=now,
    )
    db.add(history_entry)

    # Automatic citizen notification
    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    scheme_name = getattr(scheme, "name", None) or getattr(scheme, "name_en", None) or "Scheme"
    priority = "HIGH" if status_clean in ("APPROVED", "REJECTED", "DISBURSED") else "NORMAL"
    notes_suffix = f" Details: {transition.notes.strip()}" if transition.notes else ""

    notification_service.create_notification(
        db=db,
        user_id=current_user.id,
        title=f"Application Update: {scheme_name}",
        message=f"Status changed to {status_clean}.{notes_suffix}",
        notification_type="status_update",
        priority=priority,
        application_id=draft.id,
        channels=["in_app"],
        commit=False,
    )

    db.commit()
    db.refresh(draft)

    # Fetch ordered history
    history_stmt = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == draft.id)
        .order_by(ApplicationStatusHistory.created_at.asc())
    )
    history_items = list(db.execute(history_stmt).scalars().all())

    return _build_timeline_response(db, draft, history_items)


def get_status_timeline(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
) -> ApplicationTimelineResponse:
    """Retrieve full chronological timeline and audit trail for an application draft."""
    draft = db.scalar(
        select(ApplicationDraft).where(ApplicationDraft.id == application_id)
    )
    if not draft:
        raise NotFoundError("Application draft not found.")

    if draft.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this application draft.")

    history_stmt = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == draft.id)
        .order_by(ApplicationStatusHistory.created_at.asc())
    )
    history_items = list(db.execute(history_stmt).scalars().all())

    return _build_timeline_response(db, draft, history_items)


def check_external_status_sync(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
) -> ApplicationTimelineResponse:
    """
    Simulated government portal synchronization hook.
    Checks external portal using reference number, records a portal_sync history record if updated.
    """
    draft = db.scalar(
        select(ApplicationDraft).where(ApplicationDraft.id == application_id)
    )
    if not draft:
        raise NotFoundError("Application draft not found.")

    if draft.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this application draft.")

    if not draft.external_reference_number:
        raise ValidationError("Application does not have an external reference number for portal synchronization.")

    # Portal sync logic: If currently SUBMITTED, department portal has picked it up -> IN_REVIEW
    if draft.status == "SUBMITTED":
        transition = StatusTransitionCreate(
            status="IN_REVIEW",
            source_type="portal_sync",
            source_reference=draft.external_reference_number,
            notes="Government department portal verified reference; application under departmental review.",
        )
        return record_status_transition(db, current_user, application_id, transition)

    # Otherwise return current timeline
    return get_status_timeline(db, current_user, application_id)


def get_application_status_summary(
    db: Session,
    current_user: User,
    application_id: Optional[uuid.UUID] = None,
    external_reference_number: Optional[str] = None,
    scheme_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """
    Helper for agent conversational tool:
    Retrieves latest application tracking summary with anti-IDOR isolation.
    """
    conditions = [ApplicationDraft.user_id == current_user.id]

    if application_id is not None:
        conditions.append(ApplicationDraft.id == application_id)
    if external_reference_number:
        conditions.append(
            ApplicationDraft.external_reference_number == external_reference_number.strip()
        )
    if scheme_id is not None:
        conditions.append(ApplicationDraft.scheme_id == scheme_id)

    stmt = (
        select(ApplicationDraft)
        .where(and_(*conditions))
        .order_by(ApplicationDraft.updated_at.desc())
    )
    draft = db.execute(stmt).scalars().first()

    if not draft:
        return {
            "found": False,
            "message": "No application found matching the specified criteria for this citizen.",
        }

    scheme = scheme_service.get_scheme_by_id(db, draft.scheme_id)
    scheme_name = getattr(scheme, "name", None) or getattr(scheme, "name_en", None) or "Unknown Scheme"
    scheme_code = getattr(scheme, "scheme_code", None) or getattr(scheme, "code", None)

    target_name = "Self"
    if draft.beneficiary_id:
        ben = db.scalar(
            select(BeneficiaryProfile).where(
                BeneficiaryProfile.id == draft.beneficiary_id,
                BeneficiaryProfile.user_id == current_user.id,
            )
        )
        if ben:
            target_name = ben.full_name

    history_stmt = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == draft.id)
        .order_by(ApplicationStatusHistory.created_at.desc())
    )
    latest_event = db.execute(history_stmt).scalars().first()

    return {
        "found": True,
        "application_id": str(draft.id),
        "scheme_name": scheme_name,
        "scheme_code": scheme_code,
        "applicant_name": target_name,
        "current_status": draft.status,
        "external_reference_number": draft.external_reference_number,
        "submitted_at": draft.submitted_at.isoformat() if draft.submitted_at else None,
        "official_portal_url": draft.official_portal_url,
        "latest_update": {
            "status": latest_event.status if latest_event else draft.status,
            "source_type": latest_event.source_type if latest_event else "initial",
            "notes": latest_event.notes if latest_event else None,
            "timestamp": latest_event.created_at.isoformat() if latest_event else None,
        } if latest_event else None,
    }

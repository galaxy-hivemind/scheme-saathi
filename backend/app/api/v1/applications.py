"""
Application Draft API endpoints:
- Create application draft packaging prefilled demographics, attached documents, and portal handoff.
- List citizen application drafts.
- Retrieve draft details and external portal handoff instructions.
- Update draft notes or prefilled form fields.
- Record external portal submission with government acknowledgement reference number.
- Delete or archive draft.
"""
from typing import Optional
import uuid
import logging
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.application import (
    ApplicationDraftCreate,
    ApplicationDraftUpdate,
    ApplicationDraftSubmitRequest,
    ApplicationDraftResponse,
    ApplicationDraftListResponse,
)
from app.services import application_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/draft",
    response_model=APIResponse[ApplicationDraftResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create application draft",
)
def create_application_draft(
    payload: ApplicationDraftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ApplicationDraftResponse]:
    """
    Prepare an application draft for a scheme:
    Prefills citizen/beneficiary demographic snapshot, links matching uploaded documents,
    evaluates rule engine eligibility snapshot, and provides official portal handoff link.
    """
    draft = application_service.create_application_draft(
        db=db,
        current_user=current_user,
        scheme_id=payload.scheme_id,
        beneficiary_id=payload.beneficiary_id,
        notes=payload.notes,
    )
    return APIResponse(
        success=True,
        data=draft,
        message="Application draft prepared successfully.",
    )


@router.get(
    "",
    response_model=APIResponse[ApplicationDraftListResponse],
    status_code=status.HTTP_200_OK,
    summary="List application drafts",
)
def list_application_drafts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (DRAFT, READY, SUBMITTED, ARCHIVED)"),
    scheme_id: Optional[uuid.UUID] = Query(None, description="Filter by scheme ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ApplicationDraftListResponse]:
    """List all application drafts belonging to the authenticated citizen."""
    drafts = application_service.list_application_drafts(
        db=db,
        current_user=current_user,
        status=status_filter,
        scheme_id=scheme_id,
    )
    return APIResponse(
        success=True,
        data=ApplicationDraftListResponse(items=drafts, total=len(drafts)),
    )


@router.get(
    "/{draft_id}",
    response_model=APIResponse[ApplicationDraftResponse],
    status_code=status.HTTP_200_OK,
    summary="Get application draft details",
)
def get_application_draft(
    draft_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ApplicationDraftResponse]:
    """Retrieve details of an application draft including prefilled form data and portal handoff info."""
    draft = application_service.get_application_draft_by_id(db, draft_id, current_user.id)
    return APIResponse(
        success=True,
        data=draft,
    )


@router.put(
    "/{draft_id}",
    response_model=APIResponse[ApplicationDraftResponse],
    status_code=status.HTTP_200_OK,
    summary="Update application draft",
)
def update_application_draft(
    draft_id: uuid.UUID,
    payload: ApplicationDraftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ApplicationDraftResponse]:
    """Update notes or demographic form fields in an unsubmitted draft."""
    updated = application_service.update_application_draft(
        db=db,
        current_user=current_user,
        draft_id=draft_id,
        update_data=payload,
    )
    return APIResponse(
        success=True,
        data=updated,
        message="Application draft updated successfully.",
    )


@router.post(
    "/{draft_id}/submit",
    response_model=APIResponse[ApplicationDraftResponse],
    status_code=status.HTTP_200_OK,
    summary="Record external portal submission",
)
def submit_external_application(
    draft_id: uuid.UUID,
    payload: ApplicationDraftSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ApplicationDraftResponse]:
    """
    Record that the citizen has submitted on the external government portal,
    storing their official application acknowledgement/reference number.
    """
    submitted = application_service.submit_external_application(
        db=db,
        current_user=current_user,
        draft_id=draft_id,
        submit_data=payload,
    )
    return APIResponse(
        success=True,
        data=submitted,
        message="External application submission recorded successfully.",
    )


@router.delete(
    "/{draft_id}",
    response_model=APIResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete application draft",
)
def delete_application_draft(
    draft_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """Delete an application draft."""
    application_service.delete_application_draft(db, draft_id, current_user.id)
    return APIResponse(
        success=True,
        data={"deleted": True, "draft_id": str(draft_id)},
        message="Application draft deleted successfully.",
    )

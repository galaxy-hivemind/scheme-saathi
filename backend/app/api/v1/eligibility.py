"""
Eligibility Evaluation API Endpoints.
Provides deterministic, authenticated endpoints for evaluating citizen eligibility against schemes.
"""
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.scheme import SchemeCategory
from app.schemas.eligibility import (
    EligibilityCheckRequest,
    EligibilityResult,
    BatchEligibilityCheckRequest,
    BatchEligibilityResponse,
)
from app.services import eligibility_service

router = APIRouter()


@router.post(
    "/check",
    response_model=APIResponse[EligibilityResult],
    status_code=status.HTTP_200_OK,
    summary="Evaluate eligibility for a single scheme",
)
def check_eligibility(
    payload: EligibilityCheckRequest,
    include_pending: bool = Query(False, description="Whether to permit evaluation of pending_verification schemes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[EligibilityResult]:
    """
    Evaluate eligibility for a single welfare scheme for the authenticated citizen.
    - Matches active rule version criteria AST against user profile.
    - Supports what-if evaluations via optional `profile_override` payload without mutating the database.
    - Requires Phase 1 native JWT authentication.
    """
    result = eligibility_service.evaluate_scheme_for_user(
        db=db,
        user=current_user,
        scheme_id=payload.scheme_id,
        profile_override=payload.profile_override,
        include_pending=include_pending,
    )
    return APIResponse.ok(result)


@router.post(
    "/evaluate/{scheme_id}",
    response_model=APIResponse[EligibilityResult],
    status_code=status.HTTP_200_OK,
    summary="Evaluate eligibility by scheme UUID in path",
)
def evaluate_scheme_by_id(
    scheme_id: uuid.UUID,
    payload: Optional[EligibilityCheckRequest] = None,
    include_pending: bool = Query(False, description="Whether to permit evaluation of pending_verification schemes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[EligibilityResult]:
    """
    RESTful path-based endpoint for evaluating a scheme.
    """
    profile_override = payload.profile_override if payload else None
    result = eligibility_service.evaluate_scheme_for_user(
        db=db,
        user=current_user,
        scheme_id=scheme_id,
        profile_override=profile_override,
        include_pending=include_pending,
    )
    return APIResponse.ok(result)


@router.post(
    "/evaluate-all",
    response_model=APIResponse[BatchEligibilityResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate citizen eligibility across all schemes",
)
def evaluate_all_schemes(
    payload: Optional[BatchEligibilityCheckRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[BatchEligibilityResponse]:
    """
    Batch evaluate authenticated citizen against all available schemes.
    Returns counts of eligible, ineligible, and unknown schemes along with per-scheme evaluations.
    """
    include_pending = payload.include_pending if payload else False
    category = payload.category if payload else None
    profile_override = payload.profile_override if payload else None

    # Validate category if provided
    if category is not None:
        try:
            SchemeCategory(category)
        except ValueError:
            valid_cats = [c.value for c in SchemeCategory]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid category '{category}'. Must be one of: {valid_cats}",
            )

    result = eligibility_service.evaluate_all_schemes_for_user(
        db=db,
        user=current_user,
        include_pending=include_pending,
        category=category,
        profile_override=profile_override,
    )
    return APIResponse.ok(result)

"""
Service layer for evaluating citizen eligibility against welfare schemes.
Orchestrates profile extraction, rule AST evaluation, and response generation.
"""
from typing import Optional, List, Dict, Any
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, selectinload

from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.eligibility.engine import evaluate_scheme_eligibility
from app.schemas.eligibility import (
    EligibilityResult,
    BatchEligibilityResponse,
    TriStateStatus,
)


def evaluate_scheme_for_user(
    db: Session,
    user: User,
    scheme_id: uuid.UUID,
    profile_override: Optional[Dict[str, Any]] = None,
    include_pending: bool = False,
) -> EligibilityResult:
    """
    Evaluate eligibility for a single scheme for the authenticated user.
    - Raises HTTP 404 if scheme does not exist, is inactive, or is pending without include_pending.
    - Evaluates against the active rule version using the deterministic AST engine.
    """
    query = (
        select(Scheme)
        .options(selectinload(Scheme.rule_versions))
        .where(Scheme.id == scheme_id)
    )
    scheme = db.scalar(query)

    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with ID '{scheme_id}' was not found.",
        )

    if scheme.scheme_status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme is inactive and not available for eligibility evaluation.",
        )

    if scheme.scheme_status == "pending_verification" and not include_pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme is pending verification. Include pending schemes to evaluate.",
        )

    # Retrieve citizen profile
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    return evaluate_scheme_eligibility(
        scheme=scheme,
        profile=profile,
        override_data=profile_override,
    )


def evaluate_all_schemes_for_user(
    db: Session,
    user: User,
    include_pending: bool = False,
    category: Optional[str] = None,
    profile_override: Optional[Dict[str, Any]] = None,
) -> BatchEligibilityResponse:
    """
    Evaluate citizen eligibility against all active schemes (or active + pending if specified).
    Returns summary statistics and per-scheme evaluation breakdowns.
    """
    filters = [Scheme.scheme_status != "inactive"]

    if not include_pending:
        filters.append(Scheme.scheme_status == "active")
    else:
        filters.append(Scheme.scheme_status.in_(["active", "pending_verification"]))

    if category:
        filters.append(Scheme.category == category)

    query = (
        select(Scheme)
        .options(selectinload(Scheme.rule_versions))
        .where(and_(*filters))
        .order_by(Scheme.name.asc(), Scheme.id.asc())
    )
    schemes = list(db.scalars(query).all())

    # Retrieve citizen profile once for batch evaluation
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    results: List[EligibilityResult] = [
        evaluate_scheme_eligibility(
            scheme=s,
            profile=profile,
            override_data=profile_override,
        )
        for s in schemes
    ]

    eligible_count = sum(1 for r in results if r.overall_status == TriStateStatus.PASS)
    ineligible_count = sum(1 for r in results if r.overall_status == TriStateStatus.FAIL)
    unknown_count = sum(1 for r in results if r.overall_status == TriStateStatus.UNKNOWN)

    return BatchEligibilityResponse(
        total_evaluated=len(results),
        eligible_count=eligible_count,
        ineligible_count=ineligible_count,
        unknown_count=unknown_count,
        results=results,
    )


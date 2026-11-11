"""
Service layer for evaluating citizen eligibility against welfare schemes.
Orchestrates profile extraction, rule AST evaluation, and response generation
for both primary account holders (self) and family beneficiaries.
"""
from typing import Optional, List, Dict, Any, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, selectinload

from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.eligibility.engine import evaluate_scheme_eligibility
from app.schemas.eligibility import (
    EligibilityResult,
    BatchEligibilityResponse,
    TriStateStatus,
)


def resolve_target_beneficiary(
    db: Session,
    user: User,
    beneficiary_id: Optional[uuid.UUID],
) -> Tuple[Any, Optional[uuid.UUID], Optional[str], str]:
    """
    Resolve the target beneficiary profile for evaluation.
    Returns (profile_model, beneficiary_id, full_name, relationship).
    - If beneficiary_id is None -> returns account holder UserProfile (relationship='self')
    - If beneficiary_id matches user_profile.id -> returns account holder UserProfile (relationship='self')
    - Otherwise queries BeneficiaryProfile scoped by user.id. Raises 404 if not found or unauthorized.
    """
    user_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    if beneficiary_id is None:
        if user_profile is None:
            return None, None, None, "self"
        return user_profile, user_profile.id, user_profile.full_name, "self"

    if user_profile is not None and user_profile.id == beneficiary_id:
        return user_profile, user_profile.id, user_profile.full_name, "self"

    stmt = select(BeneficiaryProfile).where(
        BeneficiaryProfile.id == beneficiary_id,
        BeneficiaryProfile.user_id == user.id,
    )
    b = db.scalar(stmt)
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Beneficiary with ID '{beneficiary_id}' not found.",
        )
    return b, b.id, b.full_name, b.relationship


def evaluate_scheme_for_user(
    db: Session,
    user: User,
    scheme_id: uuid.UUID,
    beneficiary_id: Optional[uuid.UUID] = None,
    profile_override: Optional[Dict[str, Any]] = None,
    include_pending: bool = False,
) -> EligibilityResult:
    """
    Evaluate eligibility for a single scheme for the authenticated user or selected beneficiary.
    - Raises HTTP 404 if scheme does not exist, is inactive, or is pending without include_pending.
    - Resolves beneficiary: self if omitted, or specific family member scoped to current user.
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

    # Resolve target beneficiary (self or family member)
    target_profile, b_id, b_name, b_rel = resolve_target_beneficiary(db, user, beneficiary_id)

    res = evaluate_scheme_eligibility(
        scheme=scheme,
        profile=target_profile,
        override_data=profile_override,
    )
    res.beneficiary_id = b_id
    res.beneficiary_name = b_name
    res.beneficiary_relationship = b_rel
    return res


def evaluate_all_schemes_for_user(
    db: Session,
    user: User,
    beneficiary_id: Optional[uuid.UUID] = None,
    include_pending: bool = False,
    category: Optional[str] = None,
    profile_override: Optional[Dict[str, Any]] = None,
) -> BatchEligibilityResponse:
    """
    Evaluate citizen eligibility against all active schemes (or active + pending if specified)
    for the authenticated account holder or specified family beneficiary.
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

    # Resolve target beneficiary once for batch evaluation
    target_profile, b_id, b_name, b_rel = resolve_target_beneficiary(db, user, beneficiary_id)

    results: List[EligibilityResult] = []
    for s in schemes:
        res = evaluate_scheme_eligibility(
            scheme=s,
            profile=target_profile,
            override_data=profile_override,
        )
        res.beneficiary_id = b_id
        res.beneficiary_name = b_name
        res.beneficiary_relationship = b_rel
        results.append(res)

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

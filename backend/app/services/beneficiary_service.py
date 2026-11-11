"""
Service layer for managing family beneficiaries under an authenticated account.
Handles CRUD operations, synthesizes the primary account holder as 'self',
and strictly enforces user ownership to prevent IDOR vulnerabilities.
"""
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.schemas.beneficiary import (
    BeneficiaryCreate,
    BeneficiaryUpdate,
    BeneficiaryResponse,
)


def _self_profile_to_response(profile: UserProfile) -> BeneficiaryResponse:
    """Format UserProfile (account holder) as a BeneficiaryResponse with relationship='self'."""
    return BeneficiaryResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name,
        relationship="self",
        date_of_birth=profile.date_of_birth,
        gender=profile.gender,
        state=profile.state,
        district=profile.district,
        residence_type=profile.residence_type,
        occupation=profile.occupation,
        annual_family_income=profile.annual_family_income,
        profile_data=profile.profile_data or {},
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_beneficiaries(db: Session, user: User) -> List[BeneficiaryResponse]:
    """
    List all beneficiaries for the authenticated user.
    Returns the primary account holder ('self') first, followed by all family beneficiaries.
    """
    results: List[BeneficiaryResponse] = []

    # 1. Retrieve account holder profile (self)
    user_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if user_profile is not None:
        results.append(_self_profile_to_response(user_profile))

    # 2. Retrieve family beneficiaries scoped by user_id
    stmt = (
        select(BeneficiaryProfile)
        .where(BeneficiaryProfile.user_id == user.id)
        .order_by(BeneficiaryProfile.created_at.asc())
    )
    family_beneficiaries = db.scalars(stmt).all()
    for b in family_beneficiaries:
        results.append(BeneficiaryResponse.model_validate(b))

    return results


def get_beneficiary(db: Session, user: User, beneficiary_id: uuid.UUID) -> BeneficiaryResponse:
    """
    Retrieve a beneficiary by UUID.
    Supports either the primary account holder (self) or a family member.
    Enforces strict IDOR protection: returns 404 if not found or owned by another user.
    """
    # 1. Check if ID matches account holder self profile
    user_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if user_profile is not None and user_profile.id == beneficiary_id:
        return _self_profile_to_response(user_profile)

    # 2. Query family beneficiary scoped by user_id
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

    return BeneficiaryResponse.model_validate(b)


def create_beneficiary(db: Session, user: User, data: BeneficiaryCreate) -> BeneficiaryResponse:
    """
    Create a new family beneficiary for the authenticated user.
    Never trusts client-supplied ownership; user_id is forced to current_user.id.
    """
    b = BeneficiaryProfile(
        user_id=user.id,
        full_name=data.full_name.strip(),
        relationship=data.relationship,
        date_of_birth=data.date_of_birth,
        gender=data.gender.strip() if data.gender else None,
        state=data.state.strip() if data.state else None,
        district=data.district.strip() if data.district else None,
        residence_type=data.residence_type,
        occupation=data.occupation.strip() if data.occupation else None,
        annual_family_income=data.annual_family_income,
        profile_data=data.profile_data or {},
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return BeneficiaryResponse.model_validate(b)


def update_beneficiary(
    db: Session,
    user: User,
    beneficiary_id: uuid.UUID,
    data: BeneficiaryUpdate,
) -> BeneficiaryResponse:
    """
    Update a beneficiary profile.
    If beneficiary_id matches the self profile, updates the UserProfile.
    Otherwise updates the BeneficiaryProfile scoped by user_id.
    Enforces strict IDOR protection: returns 404 if record is not owned by current user.
    """
    # 1. Check self profile
    user_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if user_profile is not None and user_profile.id == beneficiary_id:
        if data.full_name is not None:
            user_profile.full_name = data.full_name.strip()
        if data.date_of_birth is not None:
            user_profile.date_of_birth = data.date_of_birth
        if data.gender is not None:
            user_profile.gender = data.gender.strip() if data.gender else None
        if data.state is not None:
            user_profile.state = data.state.strip() if data.state else None
        if data.district is not None:
            user_profile.district = data.district.strip() if data.district else None
        if data.residence_type is not None:
            user_profile.residence_type = data.residence_type
        if data.occupation is not None:
            user_profile.occupation = data.occupation.strip() if data.occupation else None
        if data.annual_family_income is not None:
            user_profile.annual_family_income = data.annual_family_income
        if data.profile_data is not None:
            current_data = dict(user_profile.profile_data or {})
            current_data.update(data.profile_data)
            user_profile.profile_data = current_data
        user_profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user_profile)
        return _self_profile_to_response(user_profile)

    # 2. Query family beneficiary scoped by user_id
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

    if data.full_name is not None:
        b.full_name = data.full_name.strip()
    if data.relationship is not None:
        b.relationship = data.relationship
    if data.date_of_birth is not None:
        b.date_of_birth = data.date_of_birth
    if data.gender is not None:
        b.gender = data.gender.strip() if data.gender else None
    if data.state is not None:
        b.state = data.state.strip() if data.state else None
    if data.district is not None:
        b.district = data.district.strip() if data.district else None
    if data.residence_type is not None:
        b.residence_type = data.residence_type
    if data.occupation is not None:
        b.occupation = data.occupation.strip() if data.occupation else None
    if data.annual_family_income is not None:
        b.annual_family_income = data.annual_family_income
    if data.profile_data is not None:
        current_data = dict(b.profile_data or {})
        current_data.update(data.profile_data)
        b.profile_data = current_data

    b.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(b)
    return BeneficiaryResponse.model_validate(b)


def delete_beneficiary(db: Session, user: User, beneficiary_id: uuid.UUID) -> bool:
    """
    Delete a family beneficiary.
    Attempting to delete the primary account holder (self) profile is rejected with 400.
    Enforces strict IDOR protection: returns 404 if record is not owned by current user.
    """
    # 1. Reject deletion of self profile
    user_profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if user_profile is not None and user_profile.id == beneficiary_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete primary account holder self profile.",
        )

    # 2. Query family beneficiary scoped by user_id
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

    db.delete(b)
    db.commit()
    return True

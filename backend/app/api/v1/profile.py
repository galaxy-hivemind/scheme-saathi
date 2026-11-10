"""
Citizen profile endpoints for retrieving, completing profile details, and managing consents.
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
    UserConsentCreate,
    UserConsentRevokeRequest,
    UserConsentResponse,
)
from app.schemas.common import APIResponse
from app.services import profile_service

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current user's profile",
)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserProfileResponse]:
    """
    Retrieve the profile for the authenticated user.
    Enforces user-level authorization: users can only access their own profile.
    """
    profile = profile_service.get_user_profile(db, current_user.id)
    return APIResponse.ok(UserProfileResponse.model_validate(profile))


@router.post(
    "",
    response_model=APIResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="Create or complete profile",
)
def create_profile(
    data: UserProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserProfileResponse]:
    """
    Create or complete the citizen profile for the authenticated user.
    If the profile was already created during registration, safely updates it with any new details.
    """
    profile = profile_service.create_user_profile(db, current_user.id, data)
    return APIResponse.ok(UserProfileResponse.model_validate(profile))


@router.put(
    "",
    response_model=APIResponse[UserProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="Update current user's profile",
)
def update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserProfileResponse]:
    """
    Progressively update the profile fields for the authenticated user.
    """
    profile = profile_service.update_user_profile(db, current_user.id, data)
    return APIResponse.ok(UserProfileResponse.model_validate(profile))


@router.post(
    "/consent",
    response_model=APIResponse[UserConsentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record explicit user consent",
)
def record_consent(
    data: UserConsentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserConsentResponse]:
    """
    Record an explicit consent granted (or revoked) by the authenticated user.
    """
    consent = profile_service.record_user_consent(db, current_user.id, data)
    return APIResponse.ok(UserConsentResponse.model_validate(consent))


@router.post(
    "/consent/revoke",
    response_model=APIResponse[UserConsentResponse],
    status_code=status.HTTP_200_OK,
    summary="Explicitly revoke user consent",
)
def revoke_consent(
    data: UserConsentRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserConsentResponse]:
    """
    Revoke active consent for the specified type.
    Populates revoked_at and transitions status to 'revoked' while preserving audit history.
    """
    consent = profile_service.revoke_user_consent(db, current_user.id, data.consent_type)
    return APIResponse.ok(UserConsentResponse.model_validate(consent))


@router.get(
    "/consent",
    response_model=APIResponse[List[UserConsentResponse]],
    status_code=status.HTTP_200_OK,
    summary="List recorded consents for current user",
)
def get_consents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[List[UserConsentResponse]]:
    """
    Retrieve all recorded consent audit records for the authenticated user in chronological order.
    """
    consents = profile_service.get_user_consents(db, current_user.id)
    return APIResponse.ok([UserConsentResponse.model_validate(c) for c in consents])

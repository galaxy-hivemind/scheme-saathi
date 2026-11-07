"""
Citizen profile service managing profile lifecycle, progressive data completion, and consents.
"""
from datetime import datetime, timezone
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ConflictError
from app.models.user_profile import UserProfile
from app.models.user_consent import UserConsent
from app.schemas.profile import UserProfileCreate, UserProfileUpdate, UserConsentCreate


def get_user_profile(db: Session, user_id: uuid.UUID) -> UserProfile:
    """
    Retrieve the citizen profile for the specified user.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise NotFoundError("Profile not found for this user.")
    return profile


def create_user_profile(
    db: Session,
    user_id: uuid.UUID,
    data: UserProfileCreate,
) -> UserProfile:
    """
    Create a new citizen profile for the specified user.
    """
    existing = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if existing:
        raise ConflictError("Profile already exists for this user. Use update instead.")

    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        state=data.state,
        district=data.district,
        residence_type=data.residence_type,
        occupation=data.occupation,
        annual_family_income=data.annual_family_income,
        preferred_language=data.preferred_language,
        profile_data=data.profile_data or {},
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_user_profile(
    db: Session,
    user_id: uuid.UUID,
    data: UserProfileUpdate,
) -> UserProfile:
    """
    Progressively update an existing citizen profile.
    Only fields explicitly set in the request are updated.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        # If no profile exists yet, create one
        create_payload = UserProfileCreate(**data.model_dump(exclude_unset=True))
        return create_user_profile(db, user_id, create_payload)

    update_dict = data.model_dump(exclude_unset=True)

    # Handle nested profile_data merging
    if "profile_data" in update_dict and update_dict["profile_data"] is not None:
        merged_data = dict(profile.profile_data or {})
        merged_data.update(update_dict["profile_data"])
        profile.profile_data = merged_data
        del update_dict["profile_data"]

    for field, value in update_dict.items():
        setattr(profile, field, value)

    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile


def record_user_consent(
    db: Session,
    user_id: uuid.UUID,
    data: UserConsentCreate,
) -> UserConsent:
    """
    Record an explicit user consent event.
    """
    consent = UserConsent(
        id=uuid.uuid4(),
        user_id=user_id,
        consent_type=data.consent_type,
        consent_status=data.consent_status,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def get_user_consents(db: Session, user_id: uuid.UUID) -> List[UserConsent]:
    """
    Retrieve all recorded consents for a user.
    """
    return db.query(UserConsent).filter(UserConsent.user_id == user_id).all()

"""
Citizen profile service managing profile lifecycle, progressive data completion, and consent audit trail.
"""
from datetime import datetime, timezone
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ConflictError, ValidationError
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
    Safely creates or completes a citizen profile for the specified user.
    If a profile already exists, updates it with the provided non-empty fields,
    preventing 409 conflicts during onboarding/profile setup.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        update_data = UserProfileUpdate(**data.model_dump(exclude_unset=True))
        return update_user_profile(db, user_id, update_data)

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
        create_payload = UserProfileCreate(**data.model_dump(exclude_unset=True))
        return create_user_profile(db, user_id, create_payload)

    update_dict = data.model_dump(exclude_unset=True)

    # Handle nested profile_data merging
    if "profile_data" in update_dict and update_dict["profile_data"] is not None:
        from sqlalchemy.orm.attributes import flag_modified
        merged_data = dict(profile.profile_data or {})
        merged_data.update(update_dict["profile_data"])
        profile.profile_data = merged_data
        flag_modified(profile, "profile_data")
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
    If consent_status is 'revoked', routes to revocation logic.
    Otherwise, creates an active consent record with recorded_at set and revoked_at=None.
    """
    if data.consent_status == "revoked":
        return revoke_user_consent(db, user_id, data.consent_type)

    consent = UserConsent(
        id=uuid.uuid4(),
        user_id=user_id,
        consent_type=data.consent_type,
        consent_status="given",
        recorded_at=datetime.now(timezone.utc),
        revoked_at=None,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def revoke_user_consent(
    db: Session,
    user_id: uuid.UUID,
    consent_type: str,
) -> UserConsent:
    """
    Revoke active consent for the specified type.
    Populates revoked_at timestamp and transitions status to 'revoked'.
    Prevents invalid state transitions (cannot revoke already revoked or non-existent consent).
    """
    latest_consent = (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user_id, UserConsent.consent_type == consent_type)
        .order_by(UserConsent.recorded_at.desc())
        .first()
    )

    if not latest_consent:
        raise NotFoundError(f"No consent record found for type '{consent_type}' to revoke.")

    if latest_consent.consent_status == "revoked" or latest_consent.revoked_at is not None:
        raise ConflictError(f"Consent for type '{consent_type}' has already been revoked.")

    now = datetime.now(timezone.utc)
    latest_consent.consent_status = "revoked"
    latest_consent.revoked_at = now
    db.commit()
    db.refresh(latest_consent)
    return latest_consent


def get_user_consents(db: Session, user_id: uuid.UUID) -> List[UserConsent]:
    """
    Retrieve all recorded consents for a user in chronological audit order (newest first).
    Consent history is preserved and never deleted.
    """
    return (
        db.query(UserConsent)
        .filter(UserConsent.user_id == user_id)
        .order_by(UserConsent.recorded_at.desc())
        .all()
    )

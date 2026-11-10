"""
Integration tests for SQLAlchemy database models and relationships against PostgreSQL.
"""
from datetime import date
from decimal import Decimal
import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.user_consent import UserConsent
from app.core.security import hash_password


def test_create_user_and_profile_relationship(db_session):
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="farmer.ramesh@example.com",
        password_hash=hash_password("Pass1234!"),
        is_active=True,
    )
    db_session.add(user)

    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Ramesh Sharma",
        date_of_birth=date(1985, 6, 15),
        gender="male",
        state="Uttar Pradesh",
        district="Varanasi",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=Decimal("120000.00"),
        preferred_language="hi",
        profile_data={"land_holding_acres": 1.5},
    )
    db_session.add(profile)
    db_session.commit()

    # Query back
    fetched_user = db_session.query(User).filter(User.id == user_id).first()
    assert fetched_user is not None
    assert fetched_user.email == "farmer.ramesh@example.com"
    assert fetched_user.profile is not None
    assert fetched_user.profile.full_name == "Ramesh Sharma"
    assert fetched_user.profile.occupation == "farmer"
    assert fetched_user.profile.annual_family_income == Decimal("120000.00")
    assert fetched_user.profile.profile_data["land_holding_acres"] == 1.5


def test_duplicate_email_constraint(db_session):
    u1 = User(
        id=uuid.uuid4(),
        email="duplicate@example.com",
        password_hash=hash_password("Pass1234!"),
    )
    db_session.add(u1)
    db_session.commit()

    u2 = User(
        id=uuid.uuid4(),
        email="duplicate@example.com",
        password_hash=hash_password("Pass1234!"),
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_consent_recording(db_session):
    user = User(
        id=uuid.uuid4(),
        email="consent.user@example.com",
        password_hash=hash_password("Pass1234!"),
    )
    db_session.add(user)
    db_session.commit()

    consent = UserConsent(
        id=uuid.uuid4(),
        user_id=user.id,
        consent_type="data_processing",
        consent_status="given",
    )
    db_session.add(consent)
    db_session.commit()

    fetched_consents = db_session.query(UserConsent).filter(UserConsent.user_id == user.id).all()
    assert len(fetched_consents) == 1
    assert fetched_consents[0].consent_type == "data_processing"
    assert fetched_consents[0].consent_status == "given"
    assert fetched_consents[0].recorded_at is not None


def test_consent_retention_foreign_key_protection(db_session):
    """
    Verify that foreign key constraint prevents cascade deletion of user
    if consent audit records exist (RESTRICT behavior).
    """
    user = User(
        id=uuid.uuid4(),
        email="protected.audit@example.com",
        password_hash=hash_password("Pass1234!"),
    )
    db_session.add(user)
    db_session.commit()

    consent = UserConsent(
        id=uuid.uuid4(),
        user_id=user.id,
        consent_type="dpdp_compliance",
        consent_status="given",
    )
    db_session.add(consent)
    db_session.commit()

    # Attempt to delete user directly must be blocked by RESTRICT constraint
    db_session.delete(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

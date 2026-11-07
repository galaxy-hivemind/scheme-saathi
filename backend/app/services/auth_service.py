"""
Authentication service handling registration, credentials verification, and token issuance.
"""
from datetime import timedelta
import uuid
from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError, ForbiddenError
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse


def register_user(db: Session, req: RegisterRequest) -> Tuple[User, TokenResponse]:
    """
    Registers a new user account, creates their initial profile,
    and returns the User object along with a signed JWT.
    Catches IntegrityError on commit to handle concurrent registration attempts safely.
    """
    normalized_email = req.email.lower().strip()

    # Pre-check for existing email
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise ConflictError("An account with this email address already exists.")

    hashed_pw = hash_password(req.password)
    user_id = uuid.uuid4()

    new_user = User(
        id=user_id,
        email=normalized_email,
        password_hash=hashed_pw,
        is_active=True,
    )
    db.add(new_user)

    # Automatically create initial citizen profile with provided basic fields
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name=req.full_name,
        preferred_language=req.preferred_language,
        profile_data={},
    )
    db.add(profile)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Authoritative database uniqueness constraint violated (e.g. concurrent registration)
        raise ConflictError("An account with this email address already exists.")

    db.refresh(new_user)

    # Issue JWT token
    token = create_access_token(
        subject=str(new_user.id),
        claims={"email": new_user.email},
    )

    token_response = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=new_user.id,
        email=new_user.email,
    )
    return new_user, token_response


def authenticate_user(db: Session, req: LoginRequest) -> Tuple[User, TokenResponse]:
    """
    Authenticates user credentials and returns the User object with a signed JWT.
    Safely rejects invalid email or password without disclosing which was incorrect.
    """
    normalized_email = req.email.lower().strip()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise UnauthorizedError("Incorrect email or password.")

    if not user.is_active:
        raise ForbiddenError("This account has been deactivated. Please contact support.")

    token = create_access_token(
        subject=str(user.id),
        claims={"email": user.email},
    )

    token_response = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
    )
    return user, token_response

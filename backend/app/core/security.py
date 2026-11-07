"""
Security utilities — password hashing (bcrypt) and JWT access tokens.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.database.dependencies import get_db

# Bearer token scheme (auto_error=False so we can provide our standard error response)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JWT access token.
    'subject' is usually the user ID (UUID string).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        to_encode.update(claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises UnauthorizedError if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedError("Invalid token: missing subject.")
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid or expired token: {str(e)}")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency to authenticate requests using JWT Bearer token.
    Returns the authenticated User model.
    """
    from app.models.user import User

    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Authentication token is missing. Please log in.")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    try:
        import uuid
        uid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise UnauthorizedError("Invalid user identity in token.")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise UnauthorizedError("User account not found.")

    if not user.is_active:
        raise ForbiddenError("Account is inactive.")

    return user

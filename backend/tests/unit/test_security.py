"""
Unit tests for security utilities: password hashing and JWT token handling.
"""
from datetime import timedelta
import pytest

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.core.exceptions import UnauthorizedError


def test_password_hashing_and_verification():
    raw_password = "SecureCitizenPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    claims = {"email": "citizen@example.gov.in"}

    token = create_access_token(subject=user_id, claims=claims)
    decoded = decode_access_token(token)

    assert decoded["sub"] == user_id
    assert decoded["email"] == "citizen@example.gov.in"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_token_expiration_rejection():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    # Token that expired 5 minutes ago
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=-5),
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(expired_token)

    assert "expired" in str(exc_info.value.message).lower()


def test_invalid_jwt_token_rejection():
    with pytest.raises(UnauthorizedError):
        decode_access_token("completely.invalid.token-value")

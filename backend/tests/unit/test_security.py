"""
Unit tests for security utilities and production configuration safeguards.
"""
from datetime import timedelta
import pytest
from jose import jwt

from app.core.config import Settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.core.exceptions import UnauthorizedError, ValidationError


def test_password_hashing_and_verification():
    raw_password = "SecureCitizenPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_password_oversized_byte_length_rejected():
    # 73 bytes in ASCII
    oversized = "a" * 73
    with pytest.raises(ValidationError) as exc:
        hash_password(oversized)
    assert "72 bytes" in str(exc.value.message)

    # Multi-byte UTF-8 test (3-byte characters, 30 chars = 90 bytes)
    multibyte_oversized = "हिंदीयोजनासहायकपासवर्ड" * 3
    with pytest.raises(ValidationError):
        hash_password(multibyte_oversized)

    # verify_password safely returns False on oversized without crashing
    assert verify_password(oversized, "$2b$12$dummyhashplaceholder") is False


def test_jwt_token_creation_and_decoding():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    claims = {"email": "citizen@example.gov.in"}

    token = create_access_token(subject=user_id, claims=claims)
    decoded = decode_access_token(token)

    assert decoded["sub"] == user_id
    assert decoded["email"] == "citizen@example.gov.in"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_missing_subject_rejection():
    # Create a token without 'sub' claim
    token = jwt.encode({"email": "nosub@example.com", "exp": 9999999999}, "dev-scheme-saathi-jwt-secret-key-32-chars-long", algorithm="HS256")
    with pytest.raises(UnauthorizedError) as exc:
        decode_access_token(token)
    assert "missing subject" in str(exc.value.message).lower()


def test_jwt_invalid_signature_rejection():
    # Token signed with a different secret
    forged_token = jwt.encode({"sub": "user-123"}, "attacker-unauthorized-secret-key-32", algorithm="HS256")
    with pytest.raises(UnauthorizedError) as exc:
        decode_access_token(forged_token)
    assert "invalid" in str(exc.value.message).lower()


def test_jwt_token_expiration_rejection():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=-5),
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_access_token(expired_token)

    assert "expired" in str(exc_info.value.message).lower()


def test_invalid_jwt_format_rejection():
    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-jwt.token.format")


# ── Production configuration security tests ───────────────────────────────────

def test_production_rejects_missing_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET must be explicitly configured in production"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            JWT_SECRET="",
            SECRET_KEY="a" * 32,
        )


def test_production_rejects_weak_or_short_jwt_secret():
    with pytest.raises(ValueError, match="at least 32 characters long"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            JWT_SECRET="short-secret",
            SECRET_KEY="a" * 32,
        )


def test_production_rejects_placeholder_jwt_secret():
    with pytest.raises(ValueError, match="placeholder"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            JWT_SECRET="change-me-to-a-very-long-secret-key-string-for-prod",
            SECRET_KEY="a" * 32,
        )


def test_production_rejects_debug_enabled():
    with pytest.raises(ValueError, match="DEBUG mode must be disabled"):
        Settings(
            APP_ENV="production",
            DEBUG=True,
            JWT_SECRET="production-strong-random-jwt-secret-xyz-987654321",
            SECRET_KEY="production-strong-random-app-secret-xyz-987654321",
        )


def test_production_valid_configuration_passes():
    s = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET="production-strong-random-jwt-secret-xyz-987654321",
        SECRET_KEY="production-strong-random-app-secret-xyz-987654321",
    )
    assert s.APP_ENV == "production"
    assert s.DEBUG is False
    assert s.JWT_SECRET == "production-strong-random-jwt-secret-xyz-987654321"


def test_unsupported_jwt_algorithm_rejected():
    with pytest.raises(ValueError, match="Unsupported JWT_ALGORITHM"):
        Settings(
            JWT_ALGORITHM="none",
        )

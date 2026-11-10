"""
API tests for authentication endpoints: registration, login, token verification, and error handling.
"""
from unittest.mock import patch
import pytest
from sqlalchemy.exc import IntegrityError


def test_successful_registration(client):
    payload = {
        "email": "sunita.devi@example.com",
        "password": "SecurePassword123!",
        "full_name": "Sunita Devi",
        "preferred_language": "hi",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()

    assert body["success"] is True
    assert body["error"] is None
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["email"] == "sunita.devi@example.com"
    # Never return password hash
    assert "password" not in body["data"]
    assert "password_hash" not in body["data"]


def test_registration_duplicate_email_rejected(client):
    payload = {
        "email": "unique.citizen@example.com",
        "password": "SecurePassword123!",
        "full_name": "Aman Verma",
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"


def test_registration_concurrent_integrity_error_handled(client):
    """
    Simulate a concurrent registration race where another transaction inserts
    the same email between our application check and commit.
    """
    payload = {
        "email": "race.condition@example.com",
        "password": "SecurePassword123!",
    }

    # First registration succeeds
    client.post("/api/v1/auth/register", json=payload)

    # Patch db.commit to simulate database-level IntegrityError on duplicate
    with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("duplicate key", params=None, orig=Exception())):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "another.user@example.com", "password": "SecurePassword123!"},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "CONFLICT"


def test_registration_short_password_rejected(client):
    payload = {
        "email": "bad.pass@example.com",
        "password": "short",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_registration_oversized_password_rejected(client):
    payload = {
        "email": "oversized.pass@example.com",
        "password": "A" * 73,  # 73 bytes exceeds bcrypt limit
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "72 bytes" in str(body["error"]["details"]).lower()


def test_successful_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login.test@example.com",
            "password": "CorrectPassword123!",
            "full_name": "Login Test User",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login.test@example.com", "password": "CorrectPassword123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]


def test_login_incorrect_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong.pass@example.com",
            "password": "CorrectPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong.pass@example.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_email_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_login_inactive_account_rejected(client, db_session):
    from app.models.user import User

    client.post(
        "/api/v1/auth/register",
        json={"email": "deactivated@example.com", "password": "Password123!"},
    )

    # Deactivate the account in database
    user = db_session.query(User).filter(User.email == "deactivated@example.com").first()
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "deactivated@example.com", "password": "Password123!"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_get_current_user_me_authenticated(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "me.test@example.com",
            "password": "Password123!",
            "full_name": "Me Tester",
        },
    )
    token = reg.json()["data"]["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "me.test@example.com"
    assert body["data"]["is_active"] is True


def test_get_current_user_me_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"

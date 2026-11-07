"""
API tests for authentication endpoints: registration, login, and token verification.
"""
import pytest


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
    # First registration
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    # Second registration with same email
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    body = r2.json()
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


def test_successful_login(client):
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login.test@example.com",
            "password": "CorrectPassword123!",
            "full_name": "Login Test User",
        },
    )

    # Login
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

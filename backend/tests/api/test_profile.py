"""
API tests for citizen profile endpoints: retrieval, progressive updates, and user isolation.
"""
from decimal import Decimal
import pytest


def _register_and_get_token(client, email="citizen.test@example.com", name="Citizen Test"):
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": name,
            "preferred_language": "hi",
        },
    )
    return reg.json()["data"]["access_token"]


def test_get_own_profile(client):
    token = _register_and_get_token(client, "profile.fetch@example.com", "Rakesh Patel")
    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["full_name"] == "Rakesh Patel"
    assert body["data"]["preferred_language"] == "hi"


def test_update_profile_progressive(client):
    token = _register_and_get_token(client, "progressive@example.com", "Initial Name")

    # Step 1: Update demographics
    upd1 = client.put(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "date_of_birth": "1992-04-10",
            "gender": "female",
            "state": "Madhya Pradesh",
            "district": "Bhopal",
            "residence_type": "rural",
        },
    )
    assert upd1.status_code == 200
    b1 = upd1.json()["data"]
    assert b1["full_name"] == "Initial Name"  # preserved
    assert b1["state"] == "Madhya Pradesh"
    assert b1["district"] == "Bhopal"
    assert b1["residence_type"] == "rural"

    # Step 2: Update financial details
    upd2 = client.put(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "occupation": "artisan",
            "annual_family_income": 85000.0,
            "profile_data": {"has_bpl_card": True},
        },
    )
    assert upd2.status_code == 200
    b2 = upd2.json()["data"]
    assert b2["occupation"] == "artisan"
    assert float(b2["annual_family_income"]) == 85000.0
    assert b2["state"] == "Madhya Pradesh"  # previous fields still preserved!
    assert b2["profile_data"]["has_bpl_card"] is True


def test_user_data_isolation(client):
    """Verify that User A cannot see or mutate User B's profile."""
    token_a = _register_and_get_token(client, "user.a@example.com", "User Alpha")
    token_b = _register_and_get_token(client, "user.b@example.com", "User Beta")

    # Update User A's profile
    client.put(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"state": "Rajasthan", "district": "Jaipur"},
    )

    # Fetch User B's profile — must NOT contain User A's data
    resp_b = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()["data"]
    assert data_b["full_name"] == "User Beta"
    assert data_b["state"] is None


def test_record_and_get_consent(client):
    token = _register_and_get_token(client, "consent.api@example.com", "Consent User")

    # Record consent
    c_resp = client.post(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "data_processing", "consent_status": "given"},
    )
    assert c_resp.status_code == 201
    c_data = c_resp.json()["data"]
    assert c_data["consent_type"] == "data_processing"
    assert c_data["consent_status"] == "given"

    # List consents
    list_resp = client.get(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    records = list_resp.json()["data"]
    assert len(records) == 1
    assert records[0]["consent_type"] == "data_processing"


def test_unauthenticated_profile_access_rejected(client):
    response = client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

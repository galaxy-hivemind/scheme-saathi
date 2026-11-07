"""
API tests for citizen profile endpoints: retrieval, progressive updates, consent audit trail, and isolation.
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


def test_create_or_complete_profile_after_registration(client):
    """
    Fix 4: POST /profile safely completes an existing profile rather than
    failing with a 409 Conflict error.
    """
    token = _register_and_get_token(client, "post.profile@example.com", "Initial Name")

    # Call POST /profile to complete onboarding details
    response = client.post(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "state": "Bihar",
            "district": "Patna",
            "occupation": "small_business",
            "annual_family_income": 95000.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["full_name"] == "Initial Name"  # preserved
    assert body["data"]["state"] == "Bihar"
    assert body["data"]["occupation"] == "small_business"


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


def test_consent_lifecycle_and_audit_trail(client):
    """
    Fix 5: Test grant, revoke, revoked_at timestamp, repeated revocation rejection,
    and complete audit trail preservation.
    """
    token = _register_and_get_token(client, "consent.audit@example.com", "Consent Auditor")

    # 1. Grant consent
    grant_resp = client.post(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "data_processing", "consent_status": "given"},
    )
    assert grant_resp.status_code == 201
    g_data = grant_resp.json()["data"]
    assert g_data["consent_type"] == "data_processing"
    assert g_data["consent_status"] == "given"
    assert g_data["recorded_at"] is not None
    assert g_data["revoked_at"] is None

    # 2. Revoke consent explicitly
    revoke_resp = client.post(
        "/api/v1/profile/consent/revoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "data_processing"},
    )
    assert revoke_resp.status_code == 200
    r_data = revoke_resp.json()["data"]
    assert r_data["consent_type"] == "data_processing"
    assert r_data["consent_status"] == "revoked"
    assert r_data["revoked_at"] is not None

    # 3. Repeated revoke is rejected with 409 CONFLICT
    repeated_revoke = client.post(
        "/api/v1/profile/consent/revoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "data_processing"},
    )
    assert repeated_revoke.status_code == 409
    assert repeated_revoke.json()["error"]["code"] == "CONFLICT"

    # 4. Revoking a non-existent consent returns 404 NOT_FOUND
    nonexistent_revoke = client.post(
        "/api/v1/profile/consent/revoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "terms_never_granted"},
    )
    assert nonexistent_revoke.status_code == 404
    assert nonexistent_revoke.json()["error"]["code"] == "NOT_FOUND"

    # 5. Re-grant consent creates a new record and preserves both
    re_grant = client.post(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_type": "data_processing", "consent_status": "given"},
    )
    assert re_grant.status_code == 201

    # 6. Audit trail list shows both records
    history_resp = client.get(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_resp.status_code == 200
    records = history_resp.json()["data"]
    assert len(records) == 2
    # Newest record is active given
    assert records[0]["consent_status"] == "given"
    assert records[0]["revoked_at"] is None
    # Previous record is revoked with timestamp
    assert records[1]["consent_status"] == "revoked"
    assert records[1]["revoked_at"] is not None


def test_cross_user_consent_isolation(client):
    """Verify that User A cannot view User B's consent records."""
    token_a = _register_and_get_token(client, "consent.a@example.com", "User A")
    token_b = _register_and_get_token(client, "consent.b@example.com", "User B")

    # User A records consent
    client.post(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"consent_type": "special_scheme_consent", "consent_status": "given"},
    )

    # User B checks consents — must be empty
    resp_b = client.get(
        "/api/v1/profile/consent",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    assert len(resp_b.json()["data"]) == 0


def test_unauthenticated_profile_access_rejected(client):
    response = client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

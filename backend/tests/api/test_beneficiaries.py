"""
API tests for family beneficiary management:
- Create, list, retrieve, update, delete
- Relationship and residence type validation
- IDOR protection (cross-account 404)
- Self-profile synthesization and deletion prevention
- Zero privilege escalation via client-supplied user_id
"""
from decimal import Decimal
import uuid
import pytest


def _register_and_get_token(client, email: str, name: str = "Test User"):
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


def test_beneficiaries_unauthenticated_rejected(client):
    """Endpoints require valid JWT authentication."""
    res = client.get("/api/v1/beneficiaries")
    assert res.status_code == 401

    res = client.post("/api/v1/beneficiaries", json={"full_name": "Father", "relationship": "father"})
    assert res.status_code == 401


def test_beneficiaries_list_includes_self_first(client):
    """GET /beneficiaries returns self profile first, followed by family beneficiaries."""
    token = _register_and_get_token(client, "user.ben.list@example.com", "Ramesh Kumar")
    headers = {"Authorization": f"Bearer {token}"}

    # Before creating any family members, list returns the self profile
    res = client.get("/api/v1/beneficiaries", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert len(data) == 1
    assert data[0]["relationship"] == "self"
    assert data[0]["full_name"] == "Ramesh Kumar"

    # Create a father beneficiary
    create_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Dashrath Kumar",
            "relationship": "father",
            "date_of_birth": "1958-05-10",
            "gender": "male",
            "residence_type": "rural",
        },
    )
    assert create_res.status_code == 201

    # Now list returns self followed by father
    res2 = client.get("/api/v1/beneficiaries", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert len(data2) == 2
    assert data2[0]["relationship"] == "self"
    assert data2[1]["relationship"] == "father"
    assert data2[1]["full_name"] == "Dashrath Kumar"


def test_beneficiary_create_validation(client):
    """Verify input validation for creating a beneficiary."""
    token = _register_and_get_token(client, "user.ben.val@example.com", "Sunil")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid relationship (cannot be 'self' or random string)
    res_bad_rel = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={"full_name": "Self Clone", "relationship": "self"},
    )
    assert res_bad_rel.status_code == 422

    res_bad_rel2 = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={"full_name": "Friend", "relationship": "neighbor"},
    )
    assert res_bad_rel2.status_code == 422

    # 2. Invalid residence_type
    res_bad_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={"full_name": "Wife", "relationship": "spouse", "residence_type": "suburb"},
    )
    assert res_bad_res.status_code == 422

    # 3. Empty full_name
    res_empty_name = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={"full_name": "", "relationship": "mother"},
    )
    assert res_empty_name.status_code == 422


def test_beneficiary_crud_lifecycle(client):
    """Test full CRUD lifecycle: create, get, update, delete."""
    token = _register_and_get_token(client, "user.ben.crud@example.com", "Anita")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create mother
    create_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Kausalya Devi",
            "relationship": "mother",
            "date_of_birth": "1965-08-20",
            "gender": "female",
            "residence_type": "rural",
            "annual_family_income": 120000.00,
            "profile_data": {"has_lpg_connection": False},
        },
    )
    assert create_res.status_code == 201
    ben_id = create_res.json()["data"]["id"]

    # 2. Get mother
    get_res = client.post = client.get(f"/api/v1/beneficiaries/{ben_id}", headers=headers)
    assert get_res.status_code == 200
    b_data = get_res.json()["data"]
    assert b_data["id"] == ben_id
    assert b_data["full_name"] == "Kausalya Devi"
    assert b_data["relationship"] == "mother"
    assert b_data["profile_data"]["has_lpg_connection"] is False

    # 3. Update mother
    put_res = client.put(
        f"/api/v1/beneficiaries/{ben_id}",
        headers=headers,
        json={
            "occupation": "Homemaker",
            "profile_data": {"is_bpl_cardholder": True},
        },
    )
    assert put_res.status_code == 200
    updated_data = put_res.json()["data"]
    assert updated_data["occupation"] == "Homemaker"
    assert updated_data["profile_data"]["has_lpg_connection"] is False
    assert updated_data["profile_data"]["is_bpl_cardholder"] is True

    # 4. Delete mother
    del_res = client.delete(f"/api/v1/beneficiaries/{ben_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 5. Get after delete returns 404
    get_after_del = client.get(f"/api/v1/beneficiaries/{ben_id}", headers=headers)
    assert get_after_del.status_code == 404


def test_cannot_delete_self_profile(client):
    """Attempting to delete the primary account holder (self) profile is rejected with 400."""
    token = _register_and_get_token(client, "user.ben.selfdel@example.com", "Self Person")
    headers = {"Authorization": f"Bearer {token}"}

    list_res = client.get("/api/v1/beneficiaries", headers=headers)
    self_id = list_res.json()["data"][0]["id"]

    del_res = client.delete(f"/api/v1/beneficiaries/{self_id}", headers=headers)
    assert del_res.status_code == 400
    assert "Cannot delete primary account holder" in del_res.json()["detail"]


def test_idor_protection_cross_account_isolation(client):
    """
    IDOR Protection:
    User A's beneficiary cannot be retrieved, updated, or deleted by User B.
    Must return 404 Not Found (never 403, leaking existence).
    """
    token_a = _register_and_get_token(client, "user.a.idor@example.com", "User A")
    token_b = _register_and_get_token(client, "user.b.idor@example.com", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a son beneficiary
    create_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers_a,
        json={
            "full_name": "Son of A",
            "relationship": "son",
            "date_of_birth": "2010-01-01",
        },
    )
    son_id = create_res.json()["data"]["id"]

    # User B tries to GET User A's son
    res_get = client.get(f"/api/v1/beneficiaries/{son_id}", headers=headers_b)
    assert res_get.status_code == 404

    # User B tries to PUT User A's son
    res_put = client.put(
        f"/api/v1/beneficiaries/{son_id}",
        headers=headers_b,
        json={"full_name": "Hacked Son Name"},
    )
    assert res_put.status_code == 404

    # User B tries to DELETE User A's son
    res_del = client.delete(f"/api/v1/beneficiaries/{son_id}", headers=headers_b)
    assert res_del.status_code == 404

    # User A's son remains untouched
    get_res_a = client.get(f"/api/v1/beneficiaries/{son_id}", headers=headers_a)
    assert get_res_a.status_code == 200
    assert get_res_a.json()["data"]["full_name"] == "Son of A"


def test_client_cannot_assign_arbitrary_user_id(client):
    """Client-supplied user_id in payload is ignored; beneficiary always belongs to authenticated user."""
    token_a = _register_and_get_token(client, "user.a.owner@example.com", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    fake_user_id = str(uuid.uuid4())
    create_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers_a,
        json={
            "full_name": "Daughter of A",
            "relationship": "daughter",
            "user_id": fake_user_id,  # Injection attempt
        },
    )
    assert create_res.status_code == 201
    ben_data = create_res.json()["data"]
    # Ownership belongs to authenticated User A, not fake_user_id
    assert ben_data["user_id"] != fake_user_id

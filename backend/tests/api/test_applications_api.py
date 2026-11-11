"""
API tests for Application Draft preparation and submission tracking:
- POST /api/v1/applications/draft (create draft packaging prefilled data & portal handoff)
- GET /api/v1/applications (list drafts)
- GET /api/v1/applications/{id} (get draft with IDOR isolation)
- PUT /api/v1/applications/{id} (update notes/prefilled data)
- POST /api/v1/applications/{id}/submit (record external portal submission)
- DELETE /api/v1/applications/{id} (delete draft)
"""
from pathlib import Path
import uuid
import pytest
from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.scripts.seed_schemes import execute_seed_import


@pytest.fixture
def seeded_db(db_session):
    """Seed database with official curated schemes."""
    from sqlalchemy import text
    db_session.execute(text("DELETE FROM application_drafts;"))
    db_session.execute(text("DELETE FROM citizen_documents;"))
    db_session.execute(text("DELETE FROM scheme_documents;"))
    db_session.execute(text("DELETE FROM scheme_rule_versions;"))
    db_session.execute(text("DELETE FROM schemes;"))
    db_session.commit()
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
    execute_seed_import(data_dir=data_dir, dry_run=False, session=db_session)
    return db_session


def _register_and_get_token(client, email: str, name: str = "Test Citizen"):
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


def _get_active_scheme_id(client, token: str) -> str:
    """Helper to get an active scheme ID from catalogue."""
    res = client.get("/api/v1/schemes", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) > 0
    return items[0]["id"]


def test_applications_unauthenticated_rejected(client):
    """Unauthenticated requests must return 401."""
    res = client.get("/api/v1/applications")
    assert res.status_code == 401


def test_application_draft_lifecycle(client, seeded_db):
    """Test full draft lifecycle: create -> list -> detail -> update -> submit -> delete."""
    token = _register_and_get_token(client, "applicant.one@example.gov.in", "Dinesh Yadav")
    headers = {"Authorization": f"Bearer {token}"}
    scheme_id = _get_active_scheme_id(client, token)

    # 1. Create draft
    res_create = client.post(
        "/api/v1/applications/draft",
        headers=headers,
        json={"scheme_id": scheme_id, "notes": "Initial draft via API"},
    )
    assert res_create.status_code == 201
    draft_data = res_create.json()["data"]
    draft_id = draft_data["id"]
    assert draft_data["scheme_id"] == scheme_id
    assert draft_data["target_name"] == "Dinesh Yadav"
    assert draft_data["status"] in ("DRAFT", "READY")
    assert "official_portal_url" in draft_data
    assert draft_data["prefilled_data"]["full_name"] == "Dinesh Yadav"

    # 2. List drafts
    res_list = client.get("/api/v1/applications", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["data"]["total"] >= 1

    # 3. Get draft details
    res_get = client.get(f"/api/v1/applications/{draft_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["id"] == draft_id

    # 4. Update draft notes
    res_update = client.put(
        f"/api/v1/applications/{draft_id}",
        headers=headers,
        json={"notes": "Updated application remarks"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["data"]["notes"] == "Updated application remarks"

    # 5. Record external submission
    res_submit = client.post(
        f"/api/v1/applications/{draft_id}/submit",
        headers=headers,
        json={"external_reference_number": "GOV/2026/123456", "notes": "Submitted online"},
    )
    assert res_submit.status_code == 200
    submitted_data = res_submit.json()["data"]
    assert submitted_data["status"] == "SUBMITTED"
    assert submitted_data["external_reference_number"] == "GOV/2026/123456"
    assert submitted_data["submitted_at"] is not None

    # 6. Attempting to update after submission must be rejected
    res_bad_update = client.put(
        f"/api/v1/applications/{draft_id}",
        headers=headers,
        json={"notes": "Illegal edit after submit"},
    )
    assert res_bad_update.status_code == 422

    # 7. Delete draft
    res_del = client.delete(f"/api/v1/applications/{draft_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["data"]["deleted"] is True


def test_application_draft_cross_tenant_isolation(client, seeded_db):
    """User B cannot view or modify User A's application draft."""
    token_a = _register_and_get_token(client, "user.a.draft@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "user.b.draft@example.gov.in", "User B")
    scheme_id = _get_active_scheme_id(client, token_a)

    # User A creates a draft
    res_a = client.post(
        "/api/v1/applications/draft",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"scheme_id": scheme_id},
    )
    assert res_a.status_code == 201
    draft_a_id = res_a.json()["data"]["id"]

    # User B attempts to view User A's draft
    res_b_get = client.get(
        f"/api/v1/applications/{draft_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_get.status_code == 404

    # User B attempts to submit on User A's draft
    res_b_submit = client.post(
        f"/api/v1/applications/{draft_a_id}/submit",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"external_reference_number": "ATTACK/123"},
    )
    assert res_b_submit.status_code == 404

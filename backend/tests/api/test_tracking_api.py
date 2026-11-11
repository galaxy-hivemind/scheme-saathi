"""
API tests for Application Tracking, Timeline Audit Trail, and Portal Status Sync:
- GET /api/v1/tracking/{id}/timeline (chronological status audit log)
- POST /api/v1/tracking/{id}/status (status transitions)
- POST /api/v1/tracking/{id}/sync (external portal status sync)
- Anti-IDOR cross-tenant isolation enforcement
"""
from pathlib import Path
import uuid
import pytest
from app.scripts.seed_schemes import execute_seed_import


@pytest.fixture
def seeded_db(db_session):
    """Seed database with official curated schemes."""
    from sqlalchemy import text
    db_session.execute(text("DELETE FROM notifications;"))
    db_session.execute(text("DELETE FROM application_status_history;"))
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
    res = client.get("/api/v1/schemes", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) > 0
    return items[0]["id"]


def test_tracking_unauthenticated_rejected(client):
    """Unauthenticated requests must return 401."""
    res = client.get(f"/api/v1/tracking/{uuid.uuid4()}/timeline")
    assert res.status_code == 401


def test_tracking_timeline_lifecycle(client, seeded_db):
    """Test application timeline progression and status transitions."""
    token = _register_and_get_token(client, "tracking.citizen@example.gov.in", "Kavita Devi")
    headers = {"Authorization": f"Bearer {token}"}
    scheme_id = _get_active_scheme_id(client, token)

    # 1. Create draft
    res_create = client.post(
        "/api/v1/applications/draft",
        headers=headers,
        json={"scheme_id": scheme_id, "notes": "Tracking test draft"},
    )
    assert res_create.status_code == 201
    draft_id = res_create.json()["data"]["id"]

    # 2. Get initial timeline
    res_timeline_init = client.get(f"/api/v1/tracking/{draft_id}/timeline", headers=headers)
    assert res_timeline_init.status_code == 200
    timeline = res_timeline_init.json()
    assert timeline["application_id"] == draft_id
    assert timeline["current_status"] in ("DRAFT", "READY")
    assert timeline["applicant_type"] == "self"
    assert timeline["target_name"] == "Kavita Devi"

    # 3. Submit application
    res_submit = client.post(
        f"/api/v1/applications/{draft_id}/submit",
        headers=headers,
        json={"external_reference_number": "PMK/2026/778899", "notes": "Submitted via CSC"},
    )
    assert res_submit.status_code == 200

    # 4. Verify submission recorded in timeline
    res_timeline_sub = client.get(f"/api/v1/tracking/{draft_id}/timeline", headers=headers)
    assert res_timeline_sub.status_code == 200
    sub_timeline = res_timeline_sub.json()
    assert sub_timeline["current_status"] == "SUBMITTED"
    assert sub_timeline["external_reference_number"] == "PMK/2026/778899"
    assert len(sub_timeline["history"]) >= 1
    assert sub_timeline["history"][-1]["status"] == "SUBMITTED"

    # 5. Record status transition to IN_REVIEW
    res_status = client.post(
        f"/api/v1/tracking/{draft_id}/status",
        headers=headers,
        json={
            "status": "IN_REVIEW",
            "source_type": "official_integration",
            "source_reference": "PMK/2026/778899",
            "notes": "Under field verification by Tehsildar",
        },
    )
    assert res_status.status_code == 200
    review_timeline = res_status.json()
    assert review_timeline["current_status"] == "IN_REVIEW"
    assert len(review_timeline["history"]) >= 2
    assert review_timeline["history"][-1]["status"] == "IN_REVIEW"
    assert review_timeline["history"][-1]["source_type"] == "official_integration"

    # 6. Record status transition to APPROVED
    res_approved = client.post(
        f"/api/v1/tracking/{draft_id}/status",
        headers=headers,
        json={
            "status": "APPROVED",
            "source_type": "official_integration",
            "source_reference": "PMK/2026/778899",
            "notes": "Application approved for next disbursement cycle",
        },
    )
    assert res_approved.status_code == 200
    app_timeline = res_approved.json()
    assert app_timeline["current_status"] == "APPROVED"
    assert app_timeline["history"][-1]["status"] == "APPROVED"


def test_tracking_anti_idor_isolation(client, seeded_db):
    """User B cannot access or transition User A's application timeline."""
    token_a = _register_and_get_token(client, "user.a.track@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "user.b.track@example.gov.in", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    scheme_id = _get_active_scheme_id(client, token_a)

    # User A creates draft
    res_create = client.post(
        "/api/v1/applications/draft",
        headers=headers_a,
        json={"scheme_id": scheme_id},
    )
    assert res_create.status_code == 201
    draft_id = res_create.json()["data"]["id"]

    # User B attempts to get timeline -> 403 Forbidden
    res_timeline_b = client.get(f"/api/v1/tracking/{draft_id}/timeline", headers=headers_b)
    assert res_timeline_b.status_code == 403

    # User B attempts to update status -> 403 Forbidden
    res_update_b = client.post(
        f"/api/v1/tracking/{draft_id}/status",
        headers=headers_b,
        json={"status": "APPROVED"},
    )
    assert res_update_b.status_code == 403

    # User B attempts to sync status -> 403 Forbidden
    res_sync_b = client.post(f"/api/v1/tracking/{draft_id}/sync", headers=headers_b)
    assert res_sync_b.status_code == 403


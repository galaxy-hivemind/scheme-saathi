"""
API tests for Citizen Notifications, Alerts, and Unread Badge Counters:
- GET /api/v1/notifications (list citizen notifications)
- GET /api/v1/notifications/unread-count (unread count badge)
- PUT /api/v1/notifications/{id}/read (mark as read)
- PUT /api/v1/notifications/read-all (mark all as read)
- Automatic notifications on application submit and status transitions
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


def test_notifications_unauthenticated_rejected(client):
    """Unauthenticated requests must return 401."""
    res = client.get("/api/v1/notifications")
    assert res.status_code == 401

    res_badge = client.get("/api/v1/notifications/unread-count")
    assert res_badge.status_code == 401


def test_notifications_lifecycle(client, seeded_db):
    """Test full notifications lifecycle: automatic alert creation on submit -> badge count -> mark read -> read all."""
    token = _register_and_get_token(client, "notify.citizen@example.gov.in", "Pooja Sharma")
    headers = {"Authorization": f"Bearer {token}"}
    scheme_id = _get_active_scheme_id(client, token)

    # Initially unread count should be 0
    res_init_count = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res_init_count.status_code == 200
    assert res_init_count.json()["unread_count"] == 0

    # 1. Create and submit an application draft (triggers automatic notification)
    res_create = client.post(
        "/api/v1/applications/draft",
        headers=headers,
        json={"scheme_id": scheme_id},
    )
    assert res_create.status_code == 201
    draft_id = res_create.json()["data"]["id"]

    res_submit = client.post(
        f"/api/v1/applications/{draft_id}/submit",
        headers=headers,
        json={"external_reference_number": "ACK-2026-9999", "notes": "Submitted"},
    )
    assert res_submit.status_code == 200

    # 2. Check unread count - must now be 1
    res_count_1 = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res_count_1.status_code == 200
    assert res_count_1.json()["unread_count"] == 1

    # 3. List notifications
    res_list = client.get("/api/v1/notifications", headers=headers)
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == 1
    assert data["unread_count"] == 1
    notif = data["items"][0]
    notif_id = notif["id"]
    assert "ACK-2026-9999" in notif["message"]
    assert notif["is_read"] is False

    # 4. Trigger second notification by transitioning status
    res_status = client.post(
        f"/api/v1/tracking/{draft_id}/status",
        headers=headers,
        json={"status": "IN_REVIEW", "notes": "Officer assigned"},
    )
    assert res_status.status_code == 200

    # Verify unread count is now 2
    res_count_2 = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res_count_2.json()["unread_count"] == 2

    # 5. Mark first notification as read
    res_read = client.put(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True
    assert res_read.json()["read_at"] is not None

    # Unread count should now be 1
    res_count_3 = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res_count_3.json()["unread_count"] == 1

    # 6. Mark all as read
    res_read_all = client.put("/api/v1/notifications/read-all", headers=headers)
    assert res_read_all.status_code == 200
    assert res_read_all.json()["updated_count"] == 1

    # Unread count should now be 0
    res_count_4 = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res_count_4.json()["unread_count"] == 0


def test_notifications_anti_idor_isolation(client, seeded_db):
    """User B cannot mark or read User A's notifications."""
    token_a = _register_and_get_token(client, "user.a.notify@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "user.b.notify@example.gov.in", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    scheme_id = _get_active_scheme_id(client, token_a)

    # User A creates & submits draft
    res_create = client.post(
        "/api/v1/applications/draft",
        headers=headers_a,
        json={"scheme_id": scheme_id},
    )
    draft_id = res_create.json()["data"]["id"]
    client.post(
        f"/api/v1/applications/{draft_id}/submit",
        headers=headers_a,
        json={"external_reference_number": "USERA-REF-111"},
    )

    # User A gets their notification ID
    res_list_a = client.get("/api/v1/notifications", headers=headers_a)
    notif_id = res_list_a.json()["items"][0]["id"]

    # User B lists notifications -> empty
    res_list_b = client.get("/api/v1/notifications", headers=headers_b)
    assert res_list_b.json()["total"] == 0

    # User B attempts to mark User A's notification as read -> 403 Forbidden
    res_read_b = client.put(f"/api/v1/notifications/{notif_id}/read", headers=headers_b)
    assert res_read_b.status_code == 403


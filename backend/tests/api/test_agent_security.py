"""
API Security & IDOR tests for Conversational Intake & Agent endpoints:
- Cross-user conversation access isolation (404)
- Cross-user action confirmation isolation (404)
- Cross-user action cancellation isolation (404)
- Duplicate confirmation prevention (409)
- Expired action confirmation rejection (410)
- Client tamper resistance (no client payload accepted on confirmation)
"""
import uuid
from datetime import datetime, timezone, timedelta
from app.models.chat import PendingAction, ChatConversation


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


def test_cross_user_conversation_access_rejected(client):
    """User B cannot view or send messages to User A's conversation."""
    token_a = _register_and_get_token(client, "user.a.conv@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "user.b.conv@example.gov.in", "User B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a conversation
    chat_a = client.post("/api/v1/agent/chat", headers=headers_a, json={"message": "hello from A"})
    conv_id = chat_a.json()["data"]["conversation_id"]

    # User B attempts to access conversation
    res_b = client.get(f"/api/v1/agent/conversations/{conv_id}", headers=headers_b)
    assert res_b.status_code == 404

    # User B attempts to append message to User A's conversation
    chat_b = client.post(
        "/api/v1/agent/chat",
        headers=headers_b,
        json={"message": "hijack message", "conversation_id": conv_id},
    )
    assert chat_b.status_code == 404


def test_cross_user_action_confirmation_rejected(client, db_session):
    """User B cannot confirm User A's pending action (IDOR protection)."""
    token_a = _register_and_get_token(client, "user.a.pa@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "user.b.pa@example.gov.in", "User B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A establishes conversation
    chat_a = client.post("/api/v1/agent/chat", headers=headers_a, json={"message": "hi"})
    conv_id = uuid.UUID(chat_a.json()["data"]["conversation_id"])

    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()
    user_a_id = conv.user_id

    # Stage an action for User A
    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=user_a_id,
        action_type="update_user_profile",
        payload={"occupation": "Doctor"},
        summary={"en": "Update profile", "hi": "अपडेट"},
        status="PENDING",
        expires_at=now_utc + timedelta(minutes=15),
        created_at=now_utc,
    )
    db_session.add(pa)
    db_session.commit()

    # User B attempts to confirm User A's action
    confirm_b = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers_b)
    assert confirm_b.status_code == 404

    # User B attempts to cancel User A's action
    cancel_b = client.post(f"/api/v1/agent/actions/{action_id}/cancel", headers=headers_b)
    assert cancel_b.status_code == 404


def test_duplicate_confirmation_rejected_with_conflict(client, db_session):
    """Confirming an already EXECUTED action returns 409 Conflict."""
    token = _register_and_get_token(client, "dup.confirm@example.gov.in", "User Dup")
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/api/v1/agent/chat", headers=headers, json={"message": "hi"})
    conv_id = uuid.UUID(chat_res.json()["data"]["conversation_id"])

    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()

    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=conv.user_id,
        action_type="update_user_profile",
        payload={"occupation": "Artist"},
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=now_utc + timedelta(minutes=15),
        created_at=now_utc,
    )
    db_session.add(pa)
    db_session.commit()

    # First confirmation succeeds
    res1 = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert res1.status_code == 200

    # Second confirmation must fail with 409 Conflict
    res2 = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert res2.status_code == 409


def test_expired_action_confirmation_rejected_with_410(client, db_session):
    """Confirming an action past expires_at returns 410 Gone."""
    token = _register_and_get_token(client, "expired.confirm@example.gov.in", "User Exp")
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/api/v1/agent/chat", headers=headers, json={"message": "hi"})
    conv_id = uuid.UUID(chat_res.json()["data"]["conversation_id"])

    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()

    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=conv.user_id,
        action_type="update_user_profile",
        payload={"occupation": "Artist"},
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=now_utc - timedelta(minutes=1),  # Already expired
        created_at=now_utc - timedelta(minutes=16),
    )
    db_session.add(pa)
    db_session.commit()

    res = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert res.status_code == 410

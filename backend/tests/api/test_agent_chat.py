"""
API tests for Conversational Intake & Agent endpoints:
- POST /api/v1/agent/chat (multi-turn chat intake)
- POST /api/v1/agent/actions/{id}/confirm (explicit action confirmation)
- POST /api/v1/agent/actions/{id}/cancel (action cancellation)
- GET /api/v1/agent/conversations
- GET /api/v1/agent/conversations/{id}
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


def test_agent_chat_unauthenticated_rejected(client):
    """Unauthenticated requests must be rejected with 401."""
    res = client.post("/api/v1/agent/chat", json={"message": "hello"})
    assert res.status_code == 401


def test_agent_chat_flow(client):
    """Basic chat intake flow in fallback/direct mode."""
    token = _register_and_get_token(client, "chat.citizen@example.gov.in", "Rajesh Sharma")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "search schemes", "language": "en"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert "conversation_id" in data
    assert "message_id" in data
    assert data["role"] == "assistant"
    conv_id = data["conversation_id"]

    # Continue conversation
    res2 = client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "check my eligibility", "conversation_id": conv_id, "language": "en"},
    )
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["conversation_id"] == conv_id

    # Retrieve conversation history
    res_conv = client.get(f"/api/v1/agent/conversations/{conv_id}", headers=headers)
    assert res_conv.status_code == 200
    conv_data = res_conv.json()["data"]
    assert len(conv_data["messages"]) == 4  # user1, asst1, user2, asst2


def test_confirm_action_create_beneficiary_flow(client, db_session):
    """Confirming a staged create_beneficiary action executes cleanly and adds the family member."""
    token = _register_and_get_token(client, "confirm.ben@example.gov.in", "Amit Kumar")
    headers = {"Authorization": f"Bearer {token}"}

    # Start a chat to establish conversation
    chat_res = client.post("/api/v1/agent/chat", headers=headers, json={"message": "namaste"})
    conv_id = uuid.UUID(chat_res.json()["data"]["conversation_id"])

    # Query user to obtain ID
    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()
    user_id = conv.user_id

    # Stage a durable pending action in database
    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=user_id,
        beneficiary_id=None,
        action_type="create_beneficiary",
        payload={
            "full_name": "Kavita Devi",
            "relationship": "mother",
            "gender": "female",
            "residence_type": "rural",
            "profile_data": {"approximate_age": 58},
        },
        summary={"en": "Add Mother: Kavita Devi", "hi": "माताजी: कविता देवी"},
        status="PENDING",
        expires_at=now_utc + timedelta(minutes=15),
        created_at=now_utc,
    )
    db_session.add(pa)
    db_session.commit()

    # Explicit citizen confirmation
    confirm_res = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()["data"]
    assert confirm_data["status"] == "EXECUTED"
    assert confirm_data["action_type"] == "create_beneficiary"
    assert confirm_data["affected_entity_id"] is not None

    # Verify family member is now visible via beneficiary API
    ben_res = client.get("/api/v1/beneficiaries", headers=headers)
    assert ben_res.status_code == 200
    ben_items = ben_res.json()["data"]
    mother = next((b for b in ben_items if b["relationship"] == "mother"), None)
    assert mother is not None
    assert mother["full_name"] == "Kavita Devi"


def test_confirm_action_update_user_profile_flow(client, db_session):
    """Confirming a staged update_user_profile action updates the account profile."""
    token = _register_and_get_token(client, "confirm.prof@example.gov.in", "Suresh Patel")
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/api/v1/agent/chat", headers=headers, json={"message": "namaste"})
    conv_id = uuid.UUID(chat_res.json()["data"]["conversation_id"])

    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()
    user_id = conv.user_id

    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=user_id,
        beneficiary_id=None,
        action_type="update_user_profile",
        payload={
            "occupation": "Artisan",
            "residence_type": "urban",
        },
        summary={"en": "Update profile", "hi": "प्रोफ़ाइल अपडेट"},
        status="PENDING",
        expires_at=now_utc + timedelta(minutes=15),
        created_at=now_utc,
    )
    db_session.add(pa)
    db_session.commit()

    confirm_res = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert confirm_res.status_code == 200
    assert confirm_res.json()["data"]["status"] == "EXECUTED"

    # Verify profile API reflects update
    prof_res = client.get("/api/v1/profile", headers=headers)
    assert prof_res.status_code == 200
    prof_data = prof_res.json()["data"]
    assert prof_data["occupation"] == "Artisan"
    assert prof_data["residence_type"] == "urban"


def test_cancel_action_flow(client, db_session):
    """Cancelling a pending action marks it CANCELLED; subsequent confirmation is rejected."""
    token = _register_and_get_token(client, "cancel.action@example.gov.in", "Vikas Singh")
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/api/v1/agent/chat", headers=headers, json={"message": "namaste"})
    conv_id = uuid.UUID(chat_res.json()["data"]["conversation_id"])

    conv = db_session.query(ChatConversation).filter(ChatConversation.id == conv_id).first()
    user_id = conv.user_id

    action_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    pa = PendingAction(
        id=action_id,
        conversation_id=conv_id,
        user_id=user_id,
        beneficiary_id=None,
        action_type="update_user_profile",
        payload={"occupation": "Teacher"},
        summary={"en": "Update profile", "hi": "अपडेट"},
        status="PENDING",
        expires_at=now_utc + timedelta(minutes=15),
        created_at=now_utc,
    )
    db_session.add(pa)
    db_session.commit()

    cancel_res = client.post(f"/api/v1/agent/actions/{action_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "CANCELLED"

    # Re-confirming cancelled action must fail with 409 Conflict
    reconfirm_res = client.post(f"/api/v1/agent/actions/{action_id}/confirm", headers=headers)
    assert reconfirm_res.status_code == 409


def test_list_conversations(client):
    """GET /api/v1/agent/conversations returns paginated summaries."""
    token = _register_and_get_token(client, "list.convs@example.gov.in", "Deepak Verma")
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/agent/chat", headers=headers, json={"message": "yojana batao"})

    res = client.get("/api/v1/agent/conversations", headers=headers)
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) >= 1
    assert "title" in items[0]
    assert "updated_at" in items[0]

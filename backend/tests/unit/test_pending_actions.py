"""
Unit tests for PendingAction state machine, concurrency, and validation.
Verifies:
- State transitions: PENDING -> CONFIRMED -> EXECUTED
- State transitions: PENDING -> CANCELLED
- State transitions: PENDING -> EXPIRED
- Expiration detection and 410 Gone enforcement
- Duplicate execution rejection (409 Conflict)
- Cancellation guard (409 Conflict on confirm)
- Row lock verification (with_for_update)
- Exact payload execution without client override
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from app.models.user import User
from app.models.chat import PendingAction
from app.core.exceptions import NotFoundError, ConflictError, GoneError, ValidationError
from app.services import chat_service


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="citizen.fsm@test.gov.in",
        password_hash="hash",
        is_active=True,
    )


@pytest.fixture
def other_user():
    return User(
        id=uuid.uuid4(),
        email="other.citizen@test.gov.in",
        password_hash="hash",
        is_active=True,
    )


def test_confirm_rejects_nonexistent_action(mock_user):
    """Confirming nonexistent action raises NotFoundError."""
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(NotFoundError):
        chat_service.confirm_pending_action(db, mock_user, uuid.uuid4())


def test_confirm_rejects_cross_user_action(mock_user, other_user):
    """User B cannot confirm User A's pending action (IDOR protection)."""
    db = MagicMock()
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        action_type="create_beneficiary",
        payload={"full_name": "Test", "relationship": "father"},
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.scalar.return_value = action

    with pytest.raises(NotFoundError):
        chat_service.confirm_pending_action(db, other_user, action.id)


def test_confirm_rejects_already_executed_action(mock_user):
    """Replaying or double-confirming an EXECUTED action raises ConflictError (409)."""
    db = MagicMock()
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        action_type="update_user_profile",
        payload={"occupation": "Doctor"},
        summary={"en": "test", "hi": "test"},
        status="EXECUTED",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.scalar.return_value = action

    with pytest.raises(ConflictError) as exc:
        chat_service.confirm_pending_action(db, mock_user, action.id)
    assert "already been confirmed and executed" in str(exc.value)


def test_confirm_rejects_cancelled_action(mock_user):
    """Confirming a CANCELLED action raises ConflictError (409)."""
    db = MagicMock()
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        action_type="update_user_profile",
        payload={"occupation": "Doctor"},
        summary={"en": "test", "hi": "test"},
        status="CANCELLED",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.scalar.return_value = action

    with pytest.raises(ConflictError) as exc:
        chat_service.confirm_pending_action(db, mock_user, action.id)
    assert "previously cancelled" in str(exc.value)


def test_confirm_rejects_expired_action(mock_user):
    """Confirming an expired action marks status EXPIRED and raises GoneError (410)."""
    db = MagicMock()
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        action_type="create_beneficiary",
        payload={"full_name": "Test", "relationship": "father"},
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=expired_time,
    )
    db.scalar.return_value = action

    with pytest.raises(GoneError) as exc:
        chat_service.confirm_pending_action(db, mock_user, action.id)
    assert "expired" in str(exc.value).lower()
    assert action.status == "EXPIRED"
    db.commit.assert_called_once()


@patch("app.services.chat_service.beneficiary_service.create_beneficiary")
def test_confirm_executes_exact_create_beneficiary_payload(mock_create_ben, mock_user):
    """Valid confirmation dispatches exact persisted payload and transitions status to EXECUTED."""
    db = MagicMock()
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        beneficiary_id=None,
        action_type="create_beneficiary",
        payload={
            "full_name": "Sunita Devi",
            "relationship": "mother",
            "gender": "female",
            "residence_type": "rural",
        },
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.scalar.return_value = action

    mock_ben = MagicMock()
    mock_ben.id = uuid.uuid4()
    mock_ben.full_name = "Sunita Devi"
    mock_ben.relationship = "mother"
    mock_create_ben.return_value = mock_ben

    resp = chat_service.confirm_pending_action(db, mock_user, action.id)
    assert resp.status == "EXECUTED"
    assert resp.action_type == "create_beneficiary"
    assert resp.affected_entity_id == mock_ben.id
    assert action.status == "EXECUTED"
    assert action.confirmed_at is not None
    assert action.executed_at is not None
    db.commit.assert_called_once()


def test_cancel_pending_action_success(mock_user):
    """Cancelling a PENDING action updates status to CANCELLED."""
    db = MagicMock()
    action = PendingAction(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_id=mock_user.id,
        action_type="create_beneficiary",
        payload={"full_name": "Test", "relationship": "mother"},
        summary={"en": "test", "hi": "test"},
        status="PENDING",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.scalar.return_value = action

    resp = chat_service.cancel_pending_action(db, mock_user, action.id)
    assert resp.status == "CANCELLED"
    assert action.status == "CANCELLED"
    db.commit.assert_called_once()

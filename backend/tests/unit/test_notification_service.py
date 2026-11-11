"""
Unit tests for notification service:
- Notification creation with validation of type and priority
- Filtering by is_read and notification_type
- Pagination and unread count
- Mark as read with timestamp update
- Anti-IDOR tenant isolation
- Mark all as read
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import MagicMock

from app.models.notification import Notification
from app.models.user import User
from app.services import notification_service
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError


@pytest.fixture
def sample_user():
    return User(id=uuid.uuid4(), email="user@example.com", password_hash="hash", is_active=True)


@pytest.fixture
def other_user():
    return User(id=uuid.uuid4(), email="other@example.com", password_hash="hash", is_active=True)


def test_create_notification_success(sample_user):
    """Test creating a valid notification persists record with defaults."""
    mock_db = MagicMock()

    notif = notification_service.create_notification(
        db=mock_db,
        user_id=sample_user.id,
        title="Application Status Update",
        message="Your application is now IN_REVIEW",
        notification_type="status_update",
        priority="NORMAL",
        commit=True,
    )

    assert notif.user_id == sample_user.id
    assert notif.title == "Application Status Update"
    assert notif.notification_type == "status_update"
    assert notif.priority == "NORMAL"
    assert notif.channels == ["in_app"]
    assert notif.is_read is False

    mock_db.add.assert_called_once_with(notif)
    mock_db.commit.assert_called_once()


def test_create_notification_invalid_type_raises(sample_user):
    """Test creating a notification with invalid type raises ValidationError."""
    mock_db = MagicMock()

    with pytest.raises(ValidationError, match="Invalid notification_type"):
        notification_service.create_notification(
            db=mock_db,
            user_id=sample_user.id,
            title="Alert",
            message="Test message",
            notification_type="unsupported_type",
        )


def test_create_notification_invalid_priority_raises(sample_user):
    """Test creating a notification with invalid priority raises ValidationError."""
    mock_db = MagicMock()

    with pytest.raises(ValidationError, match="Invalid priority"):
        notification_service.create_notification(
            db=mock_db,
            user_id=sample_user.id,
            title="Alert",
            message="Test message",
            notification_type="status_update",
            priority="CRITICAL",
        )


def test_list_notifications_filtering_and_pagination(sample_user):
    """Test list_notifications returns formatted items with total and unread count."""
    mock_db = MagicMock()
    mock_db.scalar.side_effect = [
        3,  # total count
        2,  # unread count
    ]

    n1 = Notification(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        title="Alert 1",
        message="Message 1",
        notification_type="status_update",
        priority="NORMAL",
        channels=["in_app"],
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    mock_db.execute.return_value.scalars.return_value.all.return_value = [n1]

    res = notification_service.list_notifications(
        mock_db, sample_user, is_read=False, limit=10, offset=0
    )

    assert res.total == 3
    assert res.unread_count == 2
    assert len(res.items) == 1
    assert res.items[0].title == "Alert 1"


def test_get_unread_count(sample_user):
    """Test get_unread_count queries unread notifications."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = 5

    count = notification_service.get_unread_count(mock_db, sample_user)
    assert count == 5


def test_mark_as_read_success(sample_user):
    """Test marking an unread notification as read sets is_read and read_at."""
    notif = Notification(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        title="Alert",
        message="Message",
        notification_type="status_update",
        priority="NORMAL",
        channels=["in_app"],
        is_read=False,
        read_at=None,
        created_at=datetime.now(timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = notif

    res = notification_service.mark_as_read(mock_db, sample_user, notif.id)

    assert res.is_read is True
    assert res.read_at is not None
    assert notif.is_read is True
    assert notif.read_at is not None
    mock_db.commit.assert_called_once()


def test_mark_as_read_cross_user_forbidden(other_user, sample_user):
    """Test that User B cannot mark User A's notification as read."""
    notif = Notification(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        title="Alert",
        message="Message",
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = notif

    with pytest.raises(ForbiddenError, match="do not have access"):
        notification_service.mark_as_read(mock_db, other_user, notif.id)


def test_mark_as_read_nonexistent_raises(sample_user):
    """Test marking non-existent notification raises NotFoundError."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = None

    with pytest.raises(NotFoundError, match="Notification not found"):
        notification_service.mark_as_read(mock_db, sample_user, uuid.uuid4())


def test_mark_all_as_read(sample_user):
    """Test marking all notifications as read executes update."""
    mock_db = MagicMock()
    mock_db.execute.return_value.rowcount = 4

    count = notification_service.mark_all_as_read(mock_db, sample_user)
    assert count == 4
    mock_db.commit.assert_called_once()

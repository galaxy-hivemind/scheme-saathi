"""
Unit tests for tracking service:
- Status transition recording and immutable history append
- Validation of status and source type
- Anti-IDOR tenant isolation
- Chronological timeline retrieval
- External portal status synchronization
- Summary helper for agent tool
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.models.application_draft import ApplicationDraft
from app.models.application_status_history import ApplicationStatusHistory
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.schemas.tracking import StatusTransitionCreate
from app.services import tracking_service
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError


@pytest.fixture
def mock_user():
    user = User(id=uuid.uuid4(), email="aarav@example.com", password_hash="hash", is_active=True)
    profile = UserProfile(id=uuid.uuid4(), user_id=user.id, full_name="Aarav Sharma")
    user.profile = profile
    return user


@pytest.fixture
def other_user():
    user = User(id=uuid.uuid4(), email="other@example.com", password_hash="hash", is_active=True)
    profile = UserProfile(id=uuid.uuid4(), user_id=user.id, full_name="Other User")
    user.profile = profile
    return user


@pytest.fixture
def mock_scheme():
    return Scheme(
        id=uuid.uuid4(),
        scheme_code="PM-KISAN",
        name="PM Kisan Samman Nidhi",
        description="Income support scheme for farmers",
        ministry="Ministry of Agriculture",
    )


@pytest.fixture
def sample_draft(mock_user, mock_scheme):
    return ApplicationDraft(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        scheme_id=mock_scheme.id,
        beneficiary_id=None,
        status="DRAFT",
        prefilled_data={"full_name": "Aarav Sharma"},
        attached_documents=[],
        official_portal_url="https://pmkisan.gov.in",
        notes="Initial draft",
        external_reference_number=None,
        submitted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@patch("app.services.scheme_service.get_scheme_by_id")
@patch("app.services.notification_service.create_notification")
def test_record_status_transition_success(mock_notify, mock_get_scheme, mock_user, mock_scheme, sample_draft):
    """Test recording a valid status transition updates draft, appends history, and triggers notification."""
    mock_get_scheme.return_value = mock_scheme

    mock_db = MagicMock()
    mock_db.scalar.side_effect = [
        sample_draft,  # select ApplicationDraft
        mock_user.profile,  # select UserProfile
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = [
        ApplicationStatusHistory(
            id=uuid.uuid4(),
            application_id=sample_draft.id,
            status="SUBMITTED",
            source_type="user_reported",
            source_reference="PMK-12345",
            notes="Submitted online",
            created_at=datetime.now(timezone.utc),
        )
    ]

    transition = StatusTransitionCreate(
        status="SUBMITTED",
        source_type="user_reported",
        source_reference="PMK-12345",
        notes="Submitted online",
    )

    res = tracking_service.record_status_transition(mock_db, mock_user, sample_draft.id, transition)

    assert res.current_status == "SUBMITTED"
    assert res.external_reference_number == "PMK-12345"
    assert res.applicant_type == "self"
    assert res.target_name == "Aarav Sharma"
    assert len(res.history) == 1
    assert res.history[0].status == "SUBMITTED"

    mock_db.add.assert_called_once()
    mock_notify.assert_called_once()
    mock_db.commit.assert_called_once()


def test_record_status_transition_invalid_status_raises(mock_user, sample_draft):
    """Test that invalid status is rejected with ValidationError."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = sample_draft

    transition = StatusTransitionCreate(
        status="INVALID_STATUS_VALUE",
        source_type="user_reported",
    )

    with pytest.raises(ValidationError, match="Invalid status"):
        tracking_service.record_status_transition(mock_db, mock_user, sample_draft.id, transition)


def test_record_status_transition_invalid_source_raises(mock_user, sample_draft):
    """Test that invalid source type is rejected with ValidationError."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = sample_draft

    transition = StatusTransitionCreate(
        status="APPROVED",
        source_type="unauthorized_source",
    )

    with pytest.raises(ValidationError, match="Invalid source_type"):
        tracking_service.record_status_transition(mock_db, mock_user, sample_draft.id, transition)


def test_record_status_transition_cross_user_forbidden(other_user, sample_draft):
    """Test that User B cannot record a transition on User A's application draft."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = sample_draft

    transition = StatusTransitionCreate(status="SUBMITTED")

    with pytest.raises(ForbiddenError, match="do not have access"):
        tracking_service.record_status_transition(mock_db, other_user, sample_draft.id, transition)


@patch("app.services.scheme_service.get_scheme_by_id")
def test_get_status_timeline_order_and_enrichment(mock_get_scheme, mock_user, mock_scheme, sample_draft):
    """Test retrieving full status timeline with chronological history."""
    mock_get_scheme.return_value = mock_scheme

    h1 = ApplicationStatusHistory(
        id=uuid.uuid4(),
        application_id=sample_draft.id,
        status="READY",
        source_type="user_reported",
        created_at=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
    )
    h2 = ApplicationStatusHistory(
        id=uuid.uuid4(),
        application_id=sample_draft.id,
        status="SUBMITTED",
        source_type="user_reported",
        source_reference="REF-999",
        created_at=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.scalar.side_effect = [
        sample_draft,
        mock_user.profile,
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = [h1, h2]

    res = tracking_service.get_status_timeline(mock_db, mock_user, sample_draft.id)

    assert res.application_id == sample_draft.id
    assert res.scheme_name == "PM Kisan Samman Nidhi"
    assert len(res.history) == 2
    assert res.history[0].status == "READY"
    assert res.history[1].status == "SUBMITTED"


def test_get_status_timeline_cross_user_forbidden(other_user, sample_draft):
    """Test anti-IDOR: other user cannot view application timeline."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = sample_draft

    with pytest.raises(ForbiddenError, match="do not have access"):
        tracking_service.get_status_timeline(mock_db, other_user, sample_draft.id)


@patch("app.services.scheme_service.get_scheme_by_id")
@patch("app.services.notification_service.create_notification")
def test_check_external_status_sync_submitted_transitions_to_in_review(
    mock_notify, mock_get_scheme, mock_user, mock_scheme, sample_draft
):
    """Test simulated portal synchronization on SUBMITTED draft transitions it to IN_REVIEW."""
    mock_get_scheme.return_value = mock_scheme
    sample_draft.status = "SUBMITTED"
    sample_draft.external_reference_number = "PMKISAN/2026/001"

    mock_db = MagicMock()
    mock_db.scalar.side_effect = [
        sample_draft,  # select ApplicationDraft in check_external_status_sync
        sample_draft,  # select ApplicationDraft in record_status_transition
        mock_user.profile,  # select UserProfile
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = [
        ApplicationStatusHistory(
            id=uuid.uuid4(),
            application_id=sample_draft.id,
            status="IN_REVIEW",
            source_type="portal_sync",
            source_reference="PMKISAN/2026/001",
            notes="Government department portal verified reference; application under departmental review.",
            created_at=datetime.now(timezone.utc),
        )
    ]

    res = tracking_service.check_external_status_sync(mock_db, mock_user, sample_draft.id)

    assert res.current_status == "IN_REVIEW"
    assert res.history[0].source_type == "portal_sync"


@patch("app.services.scheme_service.get_scheme_by_id")
def test_get_application_status_summary_for_agent(mock_get_scheme, mock_user, mock_scheme, sample_draft):
    """Test get_application_status_summary tool helper returns structured summary."""
    mock_get_scheme.return_value = mock_scheme
    sample_draft.status = "SUBMITTED"
    sample_draft.external_reference_number = "PMKISAN-2026-9812"

    h = ApplicationStatusHistory(
        id=uuid.uuid4(),
        application_id=sample_draft.id,
        status="SUBMITTED",
        source_type="user_reported",
        notes="Citizen submitted on portal",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.first.side_effect = [
        sample_draft,
        h,
    ]

    summary = tracking_service.get_application_status_summary(
        mock_db, mock_user, application_id=sample_draft.id
    )

    assert summary["found"] is True
    assert summary["scheme_name"] == "PM Kisan Samman Nidhi"
    assert summary["current_status"] == "SUBMITTED"
    assert summary["external_reference_number"] == "PMKISAN-2026-9812"
    assert summary["latest_update"]["status"] == "SUBMITTED"

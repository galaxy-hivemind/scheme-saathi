"""
Unit tests for the allowlisted Tool Registry and security enforcement.
Verifies that:
- Read-only tools validate inputs and return expected data.
- Proposal tools stage pending actions in PostgreSQL and NEVER write directly to profiles.
- Model confirmation tools and unauthorized tools are strictly rejected.
- Gemini function declarations match allowlisted tools.
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from app.models.user import User
from app.models.chat import ChatConversation, PendingAction
from app.schemas.beneficiary import BeneficiaryResponse
from app.schemas.eligibility import EligibilityResult, TriStateStatus, EligibilityResultStatus
from app.tools.registry import (
    ALLOWLISTED_TOOLS,
    PROHIBITED_CONFIRMATION_TOOLS,
    execute_tool,
    get_gemini_tools_declarations,
)


@pytest.fixture
def mock_user():
    user = User(
        id=uuid.uuid4(),
        email="citizen@example.gov.in",
        password_hash="mockhash",
        is_active=True,
    )
    return user


@pytest.fixture
def mock_db():
    session = MagicMock()
    return session


def test_tool_allowlist_structure():
    """Verify registry strictly contains expected tools and no write tools."""
    assert "confirm_beneficiary_creation" not in ALLOWLISTED_TOOLS
    assert "confirm_profile_update" not in ALLOWLISTED_TOOLS
    assert "confirm_action" not in ALLOWLISTED_TOOLS

    assert {
        "search_schemes",
        "get_scheme_details",
        "list_beneficiaries",
        "get_beneficiary",
        "evaluate_eligibility",
        "evaluate_all_schemes",
        "get_document_checklist",
        "generate_application_draft",
        "propose_create_beneficiary",
        "propose_update_beneficiary",
        "propose_update_user_profile",
    }.issubset(ALLOWLISTED_TOOLS)


def test_prohibited_confirmation_tool_rejection(mock_db, mock_user):
    """Model attempting to invoke a confirmation tool must be strictly blocked."""
    conv_id = uuid.uuid4()
    for tool in PROHIBITED_CONFIRMATION_TOOLS:
        result = execute_tool(mock_db, mock_user, conv_id, tool, {"action_id": str(uuid.uuid4())})
        assert result.success is False
        assert "Security violation" in result.error
        assert "cannot be executed by AI" in result.error


def test_unknown_tool_rejection(mock_db, mock_user):
    """Unknown or arbitrary tools must be rejected."""
    conv_id = uuid.uuid4()
    result = execute_tool(mock_db, mock_user, conv_id, "execute_shell_command", {"cmd": "ls"})
    assert result.success is False
    assert "Unknown or unauthorized tool" in result.error


@patch("app.tools.registry.scheme_service.get_schemes")
def test_search_schemes_tool(mock_get_schemes, mock_db, mock_user):
    """Search schemes returns serialized list."""
    conv_id = uuid.uuid4()
    scheme_mock = MagicMock()
    scheme_mock.id = uuid.uuid4()
    scheme_mock.scheme_code = "PM-KISAN"
    scheme_mock.name = "PM Kisan Samman Nidhi"
    scheme_mock.short_title = "PM-Kisan"
    scheme_mock.ministry = "Ministry of Agriculture"
    scheme_mock.category = "agriculture"
    scheme_mock.geographic_scope = "central"

    mock_get_schemes.return_value = ([scheme_mock], 1)

    result = execute_tool(mock_db, mock_user, conv_id, "search_schemes", {"q": "kisan", "limit": 5})
    assert result.success is True
    assert result.data["total"] == 1
    assert result.data["items"][0]["scheme_code"] == "PM-KISAN"
    mock_get_schemes.assert_called_once_with(mock_db, q="kisan", category=None, page=1, limit=5, include_pending=False)


@patch("app.tools.registry.beneficiary_service.list_beneficiaries")
def test_list_beneficiaries_tool(mock_list_ben, mock_db, mock_user):
    """List beneficiaries forwards user context."""
    conv_id = uuid.uuid4()
    b_id = uuid.uuid4()
    mock_list_ben.return_value = [
        BeneficiaryResponse(
            id=b_id,
            user_id=mock_user.id,
            full_name="Rajesh Sharma",
            relationship="self",
            gender="male",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    result = execute_tool(mock_db, mock_user, conv_id, "list_beneficiaries", {})
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0]["relationship"] == "self"
    mock_list_ben.assert_called_once_with(mock_db, user=mock_user)


@patch("app.tools.registry.beneficiary_service.get_beneficiary")
def test_get_beneficiary_tool(mock_get_ben, mock_db, mock_user):
    """Get beneficiary validates UUID and returns details."""
    conv_id = uuid.uuid4()
    b_id = uuid.uuid4()
    mock_get_ben.return_value = BeneficiaryResponse(
        id=b_id,
        user_id=mock_user.id,
        full_name="Sunita Devi",
        relationship="mother",
        gender="female",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    result = execute_tool(mock_db, mock_user, conv_id, "get_beneficiary", {"beneficiary_id": str(b_id)})
    assert result.success is True
    assert result.data["full_name"] == "Sunita Devi"
    assert result.data["relationship"] == "mother"


@patch("app.tools.registry.eligibility_service.evaluate_scheme_for_user")
def test_evaluate_eligibility_tool(mock_eval, mock_db, mock_user):
    """Deterministic eligibility evaluator forwarding."""
    conv_id = uuid.uuid4()
    scheme_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    mock_eval.return_value = EligibilityResult(
        scheme_id=scheme_id,
        scheme_code="IGNOAPS",
        scheme_name="Indira Gandhi National Old Age Pension Scheme",
        overall_status=TriStateStatus.UNKNOWN,
        result=EligibilityResultStatus.INSUFFICIENT_INFORMATION,
        explanation="Missing statutory age verification.",
        evaluated_at=now_utc,
    )

    result = execute_tool(
        mock_db,
        mock_user,
        conv_id,
        "evaluate_eligibility",
        {"scheme_id": str(scheme_id)},
    )
    assert result.success is True
    assert result.data["overall_status"] == "UNKNOWN"
    assert result.data["result"] == "insufficient_information"


def test_propose_create_beneficiary_tool(mock_db, mock_user):
    """Proposal tool stages pending action in DB and does not update profiles."""
    conv_id = uuid.uuid4()
    args = {
        "full_name": "Sunita Devi",
        "relationship": "mother",
        "gender": "female",
        "residence_type": "rural",
        "profile_data": {"approximate_age": 62},
    }

    result = execute_tool(mock_db, mock_user, conv_id, "propose_create_beneficiary", args)
    assert result.success is True
    assert result.data["status"] == "pending_confirmation"
    assert result.data["action_type"] == "create_beneficiary"
    assert "Sunita Devi" in result.data["summary_en"]
    assert "62" in result.data["summary_en"]

    # Verify PendingAction was added to DB session
    mock_db.add.assert_called_once()
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, PendingAction)
    assert added_obj.status == "PENDING"
    assert added_obj.action_type == "create_beneficiary"
    assert added_obj.payload["full_name"] == "Sunita Devi"
    assert added_obj.payload["relationship"] == "mother"
    assert added_obj.user_id == mock_user.id
    assert added_obj.conversation_id == conv_id
    mock_db.commit.assert_called_once()


@patch("app.tools.registry.beneficiary_service.get_beneficiary")
def test_propose_update_beneficiary_rejects_self(mock_get_ben, mock_db, mock_user):
    """propose_update_beneficiary must reject attempting to update 'self'."""
    conv_id = uuid.uuid4()
    self_id = uuid.uuid4()
    mock_get_ben.return_value = BeneficiaryResponse(
        id=self_id,
        user_id=mock_user.id,
        relationship="self",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    result = execute_tool(
        mock_db,
        mock_user,
        conv_id,
        "propose_update_beneficiary",
        {"beneficiary_id": str(self_id), "occupation": "farmer"},
    )
    assert result.success is False
    assert "Cannot update account-holder (self) via beneficiary update" in result.error


def test_propose_update_user_profile_tool(mock_db, mock_user):
    """propose_update_user_profile stages an update for account holder."""
    conv_id = uuid.uuid4()
    args = {
        "full_name": "Rajesh Kumar Sharma",
        "occupation": "Artisan",
        "residence_type": "urban",
    }

    result = execute_tool(mock_db, mock_user, conv_id, "propose_update_user_profile", args)
    assert result.success is True
    assert result.data["status"] == "pending_confirmation"
    assert result.data["action_type"] == "update_user_profile"

    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, PendingAction)
    assert added_obj.action_type == "update_user_profile"
    assert added_obj.payload["full_name"] == "Rajesh Kumar Sharma"
    assert added_obj.beneficiary_id is None


@patch("app.services.document_service.get_checklist")
def test_get_document_checklist_tool(mock_get_checklist, mock_db, mock_user):
    """get_document_checklist invokes document service and returns structured checklist."""
    scheme_id = uuid.uuid4()
    mock_checklist = MagicMock()
    mock_checklist.model_dump.return_value = {
        "scheme_id": str(scheme_id),
        "scheme_code": "PM-KISAN",
        "scheme_name": "PM Kisan Samman Nidhi",
        "is_complete": False,
        "completion_percentage": 50.0,
        "mandatory_documents": [],
        "optional_documents": [],
    }
    mock_get_checklist.return_value = mock_checklist

    conv_id = uuid.uuid4()
    args = {"scheme_id": str(scheme_id)}
    result = execute_tool(mock_db, mock_user, conv_id, "get_document_checklist", args)

    assert result.success is True
    assert result.data["scheme_code"] == "PM-KISAN"
    assert result.data["completion_percentage"] == 50.0
    mock_get_checklist.assert_called_once_with(
        db=mock_db,
        current_user=mock_user,
        scheme_id=scheme_id,
        beneficiary_id=None,
    )


@patch("app.services.application_service.create_application_draft")
def test_generate_application_draft_tool(mock_create_draft, mock_db, mock_user):
    """generate_application_draft invokes application draft builder."""
    scheme_id = uuid.uuid4()
    draft_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.model_dump.return_value = {
        "id": str(draft_id),
        "scheme_id": str(scheme_id),
        "status": "READY",
        "official_portal_url": "https://pmkisan.gov.in",
    }
    mock_create_draft.return_value = mock_draft

    conv_id = uuid.uuid4()
    args = {"scheme_id": str(scheme_id), "notes": "Prepared via chat"}
    result = execute_tool(mock_db, mock_user, conv_id, "generate_application_draft", args)

    assert result.success is True
    assert result.data["status"] == "READY"
    assert result.data["official_portal_url"] == "https://pmkisan.gov.in"
    mock_create_draft.assert_called_once_with(
        db=mock_db,
        current_user=mock_user,
        scheme_id=scheme_id,
        beneficiary_id=None,
        notes="Prepared via chat",
    )


def test_gemini_tools_declarations_validity():
    """Verify Gemini function declarations match allowlisted tools."""
    decls = get_gemini_tools_declarations()
    decl_names = {d["name"] for d in decls}
    assert decl_names == ALLOWLISTED_TOOLS
    assert "confirm_beneficiary_creation" not in decl_names
    assert "confirm_profile_update" not in decl_names

    for d in decls:
        assert "name" in d
        assert "description" in d
        assert "parameters" in d
        assert d["parameters"]["type"] == "OBJECT"

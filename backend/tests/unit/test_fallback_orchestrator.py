"""
Unit tests for DeterministicFallbackOrchestrator.
Verifies that rule-based offline fallback handles:
- Scheme search in Hindi, English, and Hinglish.
- Eligibility check queries.
- Family beneficiary lookups.
- Clarification / help prompts.
- Zero exceptions / HTTP 500 errors.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.models.user import User
from app.schemas.beneficiary import BeneficiaryResponse
from app.schemas.eligibility import BatchEligibilityResponse, EligibilityResult, TriStateStatus, EligibilityResultStatus
from app.agents.fallback import DeterministicFallbackOrchestrator


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="citizen@test.gov.in",
        password_hash="hash",
        is_active=True,
    )


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def fallback():
    return DeterministicFallbackOrchestrator()


@patch("app.agents.fallback.scheme_service.get_schemes")
def test_fallback_scheme_search_hindi(mock_get_schemes, mock_db, mock_user, fallback):
    """Fallback handles Hindi scheme search keyword."""
    scheme = MagicMock()
    scheme.id = uuid.uuid4()
    scheme.scheme_code = "PM-KISAN"
    scheme.name = "PM Kisan"
    scheme.ministry = "Agri"
    scheme.category = "agriculture"
    scheme.geographic_scope = "central"

    mock_get_schemes.return_value = ([scheme], 1)

    result = fallback.process_message(mock_db, mock_user, "मुझे किसान योजना बताओ", language="hi")
    assert result["response_type"] == "scheme_cards"
    assert "PM-KISAN" in result["structured_data"]["items"][0]["scheme_code"]
    assert "सक्रिय योजनाएं" in result["content"]


@patch("app.agents.fallback.scheme_service.get_schemes")
def test_fallback_scheme_search_english(mock_get_schemes, mock_db, mock_user, fallback):
    """Fallback handles English scheme search."""
    mock_get_schemes.return_value = ([], 0)

    result = fallback.process_message(mock_db, mock_user, "search pension schemes", language="en")
    assert result["response_type"] == "text"
    assert "no active welfare schemes matched" in result["content"].lower()


@patch("app.agents.fallback.eligibility_service.evaluate_all_schemes_for_user")
def test_fallback_eligibility_query(mock_eval_all, mock_db, mock_user, fallback):
    """Fallback evaluates eligibility when asked."""
    scheme_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    res = EligibilityResult(
        scheme_id=scheme_id,
        scheme_code="PM-KISAN",
        scheme_name="PM Kisan",
        overall_status=TriStateStatus.PASS,
        result=EligibilityResultStatus.ELIGIBLE,
        explanation="Eligible.",
        evaluated_at=now_utc,
    )
    mock_eval_all.return_value = BatchEligibilityResponse(
        total_evaluated=1,
        eligible_count=1,
        ineligible_count=0,
        unknown_count=0,
        results=[res],
    )

    result = fallback.process_message(mock_db, mock_user, "kya main eligible hoon?", language="hi")
    assert result["response_type"] == "eligibility_result"
    assert "पात्र योजनाएं: 1" in result["content"]


@patch("app.agents.fallback.beneficiary_service.list_beneficiaries")
def test_fallback_beneficiary_query(mock_list_ben, mock_db, mock_user, fallback):
    """Fallback lists family members when asked."""
    mock_list_ben.return_value = [
        BeneficiaryResponse(
            id=uuid.uuid4(),
            user_id=mock_user.id,
            full_name="Rajesh",
            relationship="self",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    result = fallback.process_message(mock_db, mock_user, "mere parivar ke sadasya", language="hi")
    assert result["response_type"] == "text"
    assert len(result["structured_data"]["beneficiaries"]) == 1
    assert "1 सदस्य" in result["content"]


def test_fallback_default_clarification(mock_db, mock_user, fallback):
    """Fallback returns structured help options for general greetings or unknown queries."""
    result = fallback.process_message(mock_db, mock_user, "namaste", language="hi")
    assert result["response_type"] == "question"
    assert "suggested_actions" in result["structured_data"]
    assert len(result["structured_data"]["suggested_actions"]) == 3

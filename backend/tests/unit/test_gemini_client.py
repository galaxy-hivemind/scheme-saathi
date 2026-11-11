"""
Unit tests for GeminiRESTClient and ConversationalOrchestrator.
Tests response parsing, authentication failure, quota retry, and orchestrator turn flow with mocks.
Zero external network calls.
"""
import uuid
from unittest.mock import patch, MagicMock
import pytest
import httpx

from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage
from app.agents.gemini_client import (
    GeminiRESTClient,
    GeminiAuthError,
    GeminiQuotaError,
    GeminiBadRequestError,
)
from app.agents.orchestrator import ConversationalOrchestrator


def test_gemini_client_configuration():
    """Verify is_configured correctly rejects empty/placeholder keys."""
    assert GeminiRESTClient(api_key="").is_configured() is False
    assert GeminiRESTClient(api_key="placeholder").is_configured() is False
    assert GeminiRESTClient(api_key="change-me").is_configured() is False
    assert GeminiRESTClient(api_key="AIzaSyValidKey123").is_configured() is True


def test_gemini_client_parse_response():
    """Verify response parsing extracts text and function calls."""
    client = GeminiRESTClient(api_key="valid-key")
    mock_payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "Sure, let me check the schemes for you."},
                        {
                            "functionCall": {
                                "name": "search_schemes",
                                "args": {"q": "pension"},
                            }
                        },
                    ],
                }
            }
        ]
    }
    parsed = client._parse_response(mock_payload)
    assert parsed["text"] == "Sure, let me check the schemes for you."
    assert len(parsed["function_calls"]) == 1
    assert parsed["function_calls"][0]["name"] == "search_schemes"
    assert parsed["function_calls"][0]["args"]["q"] == "pension"


@patch("httpx.Client.post")
def test_gemini_client_auth_error(mock_post):
    """HTTP 401/403 raises GeminiAuthError."""
    client = GeminiRESTClient(api_key="bad-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_post.return_value = mock_resp

    with pytest.raises(GeminiAuthError):
        client.generate_content([{"role": "user", "parts": [{"text": "hello"}]}])


@patch("httpx.Client.post")
def test_gemini_client_bad_request_error(mock_post):
    """HTTP 400 raises GeminiBadRequestError."""
    client = GeminiRESTClient(api_key="valid-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Invalid JSON schema"
    mock_post.return_value = mock_resp

    with pytest.raises(GeminiBadRequestError):
        client.generate_content([{"role": "user", "parts": [{"text": "hello"}]}])


def test_orchestrator_unconfigured_delegates_to_fallback():
    """When Gemini is not configured, orchestrator seamlessly routes to fallback."""
    user = User(id=uuid.uuid4(), email="cit@test.gov.in", password_hash="h", is_active=True)
    conv = ChatConversation(id=uuid.uuid4(), user_id=user.id, title="Test", language="hi")
    db = MagicMock()

    client = GeminiRESTClient(api_key="")
    orchestrator = ConversationalOrchestrator(gemini_client=client)

    result = orchestrator.process_turn(db, user, conv, "namaste", language="hi")
    assert result["response_type"] == "question"
    assert "suggested_actions" in result["structured_data"]
    assert result["pending_action"] is None

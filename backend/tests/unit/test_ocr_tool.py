"""
Unit tests for extract_document_text tool execution and schema validation.
"""
from typing import Dict, Any
from unittest.mock import MagicMock, patch
import uuid
import pytest

from app.models.user import User
from app.models.chat import ChatConversation
from app.tools.registry import execute_tool, ALLOWLISTED_TOOLS, READ_ONLY_TOOLS
from app.schemas.ocr import OCRExtractionResponse


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), email="user@example.com", is_active=True)


def test_tool_registry_includes_extract_document_text():
    """Verify extract_document_text is in ALLOWLISTED_TOOLS and READ_ONLY_TOOLS."""
    assert "extract_document_text" in ALLOWLISTED_TOOLS
    assert "extract_document_text" in READ_ONLY_TOOLS


def test_execute_extract_document_text_tool_success(mock_user):
    """Verify tool executes successfully with valid document_id."""
    db = MagicMock()
    doc_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    mock_resp = OCRExtractionResponse(
        document_id=doc_id,
        document_type="income_certificate",
        ocr_status="COMPLETED",
        extraction_engine="pypdf_digital",
        raw_text_snippet="Income snippet",
        extracted_fields={"annual_family_income": 75000},
        confidence_score=0.90,
        pii_masked=True,
        pending_action_id=None,
        disclaimer="Notice disclaimer",
    )

    with patch("app.services.ocr_service.process_document_ocr", return_value=mock_resp):
        res = execute_tool(
            db=db,
            current_user=mock_user,
            conversation_id=conv_id,
            tool_name="extract_document_text",
            arguments={"document_id": str(doc_id)},
        )

        assert res.success is True
        assert res.data["document_id"] == str(doc_id)
        assert res.data["ocr_status"] == "COMPLETED"
        assert res.data["extracted_fields"]["annual_family_income"] == 75000


def test_execute_extract_document_text_tool_invalid_uuid(mock_user):
    """Verify tool returns error when document_id is not a valid UUID."""
    db = MagicMock()
    conv_id = uuid.uuid4()

    res = execute_tool(
        db=db,
        current_user=mock_user,
        conversation_id=conv_id,
        tool_name="extract_document_text",
        arguments={"document_id": "not-a-valid-uuid"},
    )

    assert res.success is False
    assert "Invalid UUID" in res.error

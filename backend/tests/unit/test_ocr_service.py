"""
Unit tests for OCR service layer: tenant isolation, pending action generation,
disclaimer assertion, and zero-direct-write safety.
"""
from typing import Dict, Any
from unittest.mock import MagicMock, patch
import uuid
import pytest
from datetime import datetime, timezone

from app.models.user import User
from app.models.citizen_document import CitizenDocument
from app.models.chat import ChatConversation, PendingAction
from app.core.exceptions import NotFoundError, ForbiddenError
from app.services import ocr_service
from app.schemas.ocr import DISCLAIMER_TEXT


@pytest.fixture
def mock_user():
    user = User(
        id=uuid.uuid4(),
        email="citizen@example.com",
        password_hash="hashed_pw",
        is_active=True,
    )
    return user


@pytest.fixture
def mock_document(mock_user):
    doc = CitizenDocument(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        beneficiary_id=None,
        document_type="income_certificate",
        file_name="income_cert.pdf",
        file_path="uploads/income_cert.pdf",
        file_size_bytes=10240,
        mime_type="application/pdf",
        checksum_sha256="abc123sha",
        verification_status="PENDING",
        extracted_metadata={},
    )
    return doc


def test_process_document_ocr_not_found(mock_user):
    """Verify 404 is raised when document does not exist."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(NotFoundError):
        ocr_service.process_document_ocr(
            db=db,
            current_user=mock_user,
            document_id=uuid.uuid4(),
        )


def test_process_document_ocr_tenant_isolation(mock_user, mock_document):
    """Verify ForbiddenError is raised when trying to OCR another user's document."""
    db = MagicMock()
    other_user = User(id=uuid.uuid4(), email="other@example.com", is_active=True)
    db.query.return_value.filter.return_value.first.return_value = mock_document

    with pytest.raises(ForbiddenError):
        ocr_service.process_document_ocr(
            db=db,
            current_user=other_user,
            document_id=mock_document.id,
        )


def test_process_document_ocr_success(mock_user, mock_document):
    """Verify document OCR extracts fields, persists metadata, and returns disclaimer."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_document

    sample_ocr_text = """
    OFFICE OF THE TEHSILDAR
    INCOME CERTIFICATE: INC/2026/99123
    Total Annual Income: Rs. 85,000/-
    Date: 01/01/2026
    """

    with patch("app.services.document_service.get_document_physical_path", return_value="/tmp/test.pdf"), \
         patch("app.services.ocr_service.extract_text_from_file", return_value=(sample_ocr_text, "pypdf_digital", "COMPLETED")):

        response = ocr_service.process_document_ocr(
            db=db,
            current_user=mock_user,
            document_id=mock_document.id,
            stage_pending_action=False,
        )

        assert response.document_id == mock_document.id
        assert response.ocr_status == "COMPLETED"
        assert response.extraction_engine == "pypdf_digital"
        assert response.extracted_fields.get("annual_family_income") == 85000
        assert response.extracted_fields.get("certificate_number") == "INC/2026/99123"
        assert response.disclaimer == DISCLAIMER_TEXT
        assert response.pii_masked is True
        assert response.pending_action_id is None
        assert db.commit.called


def test_process_document_ocr_stages_pending_action(mock_user, mock_document):
    """
    Verify that when stage_pending_action=True, a durable PendingAction is staged
    in PostgreSQL, and the user profile is NOT directly modified.
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_document

    sample_ocr_text = """
    OFFICE OF THE TEHSILDAR
    Annual Income: Rs. 1,40,000/-
    Date of Birth: 12/04/1988
    """

    mock_conv = ChatConversation(id=uuid.uuid4(), user_id=mock_user.id)

    with patch("app.services.document_service.get_document_physical_path", return_value="/tmp/test.pdf"), \
         patch("app.services.ocr_service.extract_text_from_file", return_value=(sample_ocr_text, "pypdf_digital", "COMPLETED")), \
         patch("app.services.chat_service.get_or_create_conversation", return_value=mock_conv):

        response = ocr_service.process_document_ocr(
            db=db,
            current_user=mock_user,
            document_id=mock_document.id,
            stage_pending_action=True,
        )

        assert response.pending_action_id is not None
        # Verify db.add was called with a PendingAction
        assert db.add.called
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, PendingAction)
        assert added_obj.action_type == "update_user_profile"
        assert added_obj.payload.get("annual_family_income") == 140000
        assert added_obj.payload.get("date_of_birth") == "1988-04-12"
        assert added_obj.status == "PENDING"


def test_get_document_ocr_cached(mock_user, mock_document):
    """Verify get_document_ocr returns existing metadata without running OCR."""
    db = MagicMock()
    mock_document.extracted_metadata = {
        "raw_text_snippet": "Previously extracted snippet",
        "extracted_fields": {"annual_family_income": 95000},
        "ocr_status": "COMPLETED",
        "extraction_engine": "cached_engine",
        "confidence_score": 0.88,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    db.query.return_value.filter.return_value.first.return_value = mock_document

    response = ocr_service.get_document_ocr(
        db=db,
        current_user=mock_user,
        document_id=mock_document.id,
    )

    assert response.ocr_status == "COMPLETED"
    assert response.extracted_fields.get("annual_family_income") == 95000
    assert response.confidence_score == 0.88

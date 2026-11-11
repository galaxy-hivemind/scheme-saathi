"""
Unit tests for Document Service:
- Filename sanitization against path traversal, control chars, null bytes, long names.
- Magic byte validation for PDF, JPEG, PNG.
- Rejection of spoofed/disguised files and mismatched extensions.
- 10MB size ceiling enforcement (PayloadTooLargeError).
- Cryptographic SHA-256 calculation.
"""
import io
import os
import uuid
import hashlib
import tempfile
from unittest.mock import MagicMock
import pytest
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationError, PayloadTooLargeError, NotFoundError
from app.models.user import User
from app.models.citizen_document import CitizenDocument
from app.services.document_service import (
    sanitize_filename,
    validate_file_signature,
    save_uploaded_document,
    MAGIC_BYTES,
)


def test_sanitize_filename_path_traversal():
    """Verify path traversal sequences and dangerous characters are stripped."""
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\windows\\system32\\calc.png") == "calc.png"
    assert sanitize_filename("my\x00file.jpg") == "myfile.jpg"
    assert sanitize_filename("   ...doc.pdf   ") == "doc.pdf"
    assert sanitize_filename("a" * 150 + ".pdf").endswith(".pdf")
    assert len(sanitize_filename("a" * 150 + ".pdf")) <= 105  # 100 stem + 4 ext


def test_sanitize_filename_empty_fallback():
    """Empty or whitespace-only filename falls back to safe default."""
    assert sanitize_filename("") == "document.pdf"
    assert sanitize_filename("   ") == "document.pdf"


def test_validate_file_signature_pdf():
    """Valid PDF header is accepted."""
    pdf_bytes = b"%PDF-1.4\n%test content\n"
    mime, ext = validate_file_signature(pdf_bytes, "ration_card.pdf")
    assert mime == "application/pdf"
    assert ext == ".pdf"


def test_validate_file_signature_jpeg():
    """Valid JPEG header is accepted for .jpg and .jpeg."""
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    mime, ext = validate_file_signature(jpg_bytes, "photo.jpg")
    assert mime == "image/jpeg"
    assert ext == ".jpg"

    mime2, ext2 = validate_file_signature(jpg_bytes, "photo.jpeg")
    assert mime2 == "image/jpeg"
    assert ext2 == ".jpeg"


def test_validate_file_signature_png():
    """Valid PNG header is accepted."""
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    mime, ext = validate_file_signature(png_bytes, "income.png")
    assert mime == "image/png"
    assert ext == ".png"


def test_validate_file_signature_disguised_text_file():
    """Text file renamed to .pdf is rejected."""
    text_bytes = b"Hello world! This is plain text, not a PDF."
    with pytest.raises(ValidationError) as exc:
        validate_file_signature(text_bytes, "fake.pdf")
    assert "Unsupported file format" in str(exc.value.message)


def test_validate_file_signature_mismatched_extension():
    """PNG bytes named with .pdf extension are rejected."""
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    with pytest.raises(ValidationError) as exc:
        validate_file_signature(png_bytes, "mismatched.pdf")
    assert "does not match file extension" in str(exc.value.message)


def test_validate_file_signature_empty_or_too_short():
    """Empty or truncated header is rejected."""
    with pytest.raises(ValidationError):
        validate_file_signature(b"", "empty.pdf")
    with pytest.raises(ValidationError):
        validate_file_signature(b"%P", "short.pdf")


def test_save_uploaded_document_size_limit(monkeypatch, tmp_path):
    """File exceeding MAX_UPLOAD_SIZE_MB raises PayloadTooLargeError."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)  # 1 MB for testing

    mock_user = User(id=uuid.uuid4(), email="cit@gov.in", password_hash="h")
    mock_db = MagicMock()

    # Generate 1MB + 10KB of PDF content
    large_pdf = io.BytesIO(b"%PDF-1.4\n" + b"A" * (1024 * 1024 + 10240))
    upload_file = UploadFile(file=large_pdf, filename="large.pdf")

    with pytest.raises(PayloadTooLargeError):
        save_uploaded_document(
            db=mock_db,
            current_user=mock_user,
            file=upload_file,
            document_type="aadhaar",
        )


def test_save_uploaded_document_success(monkeypatch, tmp_path):
    """Valid document upload calculates checksum and creates CitizenDocument record."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    mock_user = User(id=uuid.uuid4(), email="cit@gov.in", password_hash="h")
    mock_db = MagicMock()

    content = b"%PDF-1.4\nSample Aadhaar Document Content\n%%EOF"
    expected_sha256 = hashlib.sha256(content).hexdigest()

    file_obj = io.BytesIO(content)
    upload_file = UploadFile(file=file_obj, filename="my_aadhaar.pdf")

    doc = save_uploaded_document(
        db=mock_db,
        current_user=mock_user,
        file=upload_file,
        document_type="aadhaar",
    )

    assert doc.user_id == mock_user.id
    assert doc.beneficiary_id is None
    assert doc.document_type == "aadhaar"
    assert doc.file_name == "my_aadhaar.pdf"
    assert doc.mime_type == "application/pdf"
    assert doc.file_size_bytes == len(content)
    assert doc.checksum_sha256 == expected_sha256
    assert doc.verification_status == "PENDING"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

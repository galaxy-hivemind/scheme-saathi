"""
API tests for Document Management endpoints:
- POST /api/v1/documents/upload (secure file upload with magic byte verification)
- GET /api/v1/documents (listing with beneficiary and type filtering)
- GET /api/v1/documents/{id} (metadata retrieval with IDOR isolation)
- GET /api/v1/documents/{id}/download (secure streaming file download)
- DELETE /api/v1/documents/{id} (file removal)
- GET /api/v1/documents/checklist/{scheme_id} (readiness checklist)
"""
import io
import uuid
import pytest
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument


def _register_and_get_token(client, email: str, name: str = "Test Citizen"):
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


def test_documents_unauthenticated_rejected(client):
    """Unauthenticated requests must return 401."""
    res = client.get("/api/v1/documents")
    assert res.status_code == 401


def test_upload_valid_pdf_document(client, tmp_path, monkeypatch):
    """Uploading a valid PDF creates a CitizenDocument record and stores file."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    token = _register_and_get_token(client, "doc.uploader@example.gov.in", "Sunil Verma")
    headers = {"Authorization": f"Bearer {token}"}

    pdf_content = b"%PDF-1.4\nTest Aadhaar content\n%%EOF"
    files = {"file": ("aadhaar.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"document_type": "aadhaar"}

    res = client.post("/api/v1/documents/upload", headers=headers, files=files, data=data)
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    doc_data = body["data"]
    assert doc_data["document_type"] == "aadhaar"
    assert doc_data["file_name"] == "aadhaar.pdf"
    assert doc_data["mime_type"] == "application/pdf"
    assert doc_data["file_size_bytes"] == len(pdf_content)
    assert doc_data["verification_status"] == "PENDING"
    assert "checksum_sha256" in doc_data

    doc_id = doc_data["id"]

    # Verify retrieval
    res_get = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["id"] == doc_id

    # Verify download
    res_down = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert res_down.status_code == 200
    assert res_down.content == pdf_content

    # Delete
    res_del = client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["data"]["deleted"] is True


def test_upload_disguised_file_rejected(client, tmp_path, monkeypatch):
    """Uploading a text file renamed to .pdf fails signature validation with 422."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    token = _register_and_get_token(client, "fake.uploader@example.gov.in", "Fake Uploader")
    headers = {"Authorization": f"Bearer {token}"}

    fake_pdf = b"Plain text payload pretending to be a PDF"
    files = {"file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    data = {"document_type": "aadhaar"}

    res = client.post("/api/v1/documents/upload", headers=headers, files=files, data=data)
    assert res.status_code == 422
    assert "Unsupported file format" in res.json()["error"]["message"]


def test_document_cross_tenant_isolation(client, tmp_path, monkeypatch):
    """User B cannot view or download User A's document."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    token_a = _register_and_get_token(client, "tenant.a@example.gov.in", "User A")
    token_b = _register_and_get_token(client, "tenant.b@example.gov.in", "User B")

    pdf_content = b"%PDF-1.4\nSecret User A Document\n%%EOF"
    files = {"file": ("secret.pdf", io.BytesIO(pdf_content), "application/pdf")}
    res_a = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files=files,
        data={"document_type": "pan"},
    )
    assert res_a.status_code == 201
    doc_id = res_a.json()["data"]["id"]

    # User B attempts to access User A's document
    res_b_get = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_get.status_code == 404

    # User B attempts to download User A's document
    res_b_down = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_down.status_code == 404


def test_upload_for_beneficiary_anti_idor(client, tmp_path, monkeypatch):
    """Citizen cannot upload a document for a beneficiary belonging to another user."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    token_a = _register_and_get_token(client, "family.a@example.gov.in", "Family A")
    token_b = _register_and_get_token(client, "family.b@example.gov.in", "Family B")

    # User A creates a beneficiary
    res_ben = client.post(
        "/api/v1/beneficiaries",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "Father A", "relationship": "father"},
    )
    assert res_ben.status_code == 201
    ben_a_id = res_ben.json()["data"]["id"]

    # User B attempts to upload document tagging User A's beneficiary
    pdf_content = b"%PDF-1.4\nDocument\n%%EOF"
    files = {"file": ("doc.pdf", io.BytesIO(pdf_content), "application/pdf")}
    res_attack = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token_b}"},
        files=files,
        data={"document_type": "aadhaar", "beneficiary_id": ben_a_id},
    )
    assert res_attack.status_code == 404

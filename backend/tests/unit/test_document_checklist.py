"""
Unit tests for Scheme Document Checklist matching engine:
- Direct document type matching.
- Alternative document types matching (e.g., voter_id for identity_proof).
- Exclusion of rejected documents from satisfying requirements.
- Completion metrics (total_mandatory, uploaded_mandatory, completion_percentage, is_complete).
- Family beneficiary isolation.
"""
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.models.citizen_document import CitizenDocument
from app.models.scheme_document import SchemeDocument
from app.models.scheme import Scheme
from app.services.document_service import get_checklist


@pytest.fixture
def sample_user():
    user = User(id=uuid.uuid4(), email="ramesh@gov.in", password_hash="h")
    user.profile = UserProfile(id=uuid.uuid4(), user_id=user.id, full_name="Ramesh Kumar")
    return user


@pytest.fixture
def sample_scheme():
    scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="PM-KISAN",
        name="PM Kisan Samman Nidhi",
        description="Farmer support",
        ministry="Ministry of Agriculture",
        category="agriculture",
        benefits="6000 per year",
        target_beneficiaries=["farmers"],
        official_url="https://pmkisan.gov.in",
        application_url="https://pmkisan.gov.in/registration",
        source_url="https://pmkisan.gov.in",
    )
    return scheme


@patch("app.services.scheme_service.get_scheme_by_id")
def test_checklist_direct_match(mock_get_scheme, sample_user, sample_scheme):
    """Direct matching of mandatory document type."""
    mock_get_scheme.return_value = sample_scheme

    scheme_doc = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=sample_scheme.id,
        document_type="aadhaar",
        title="Aadhaar Card",
        is_mandatory=True,
        is_active=True,
        alternatives=None,
    )

    citizen_doc = CitizenDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        beneficiary_id=None,
        document_type="aadhaar",
        file_name="aadhaar.pdf",
        file_path="sample.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        checksum_sha256="abc",
        verification_status="PENDING",
    )

    mock_db = MagicMock()
    # Mocking scheme_docs query and citizen_docs query
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [scheme_doc],      # scheme_documents query
        [citizen_doc],     # citizen_documents query
    ]

    res = get_checklist(mock_db, sample_user, sample_scheme.id, beneficiary_id=None)

    assert res.scheme_code == "PM-KISAN"
    assert res.target_name == "Ramesh Kumar"
    assert res.total_mandatory == 1
    assert res.uploaded_mandatory == 1
    assert res.is_complete is True
    assert res.completion_percentage == 100.0
    assert len(res.mandatory_documents) == 1
    assert res.mandatory_documents[0].status == "UPLOADED"
    assert res.mandatory_documents[0].attached_document_id == citizen_doc.id


@patch("app.services.scheme_service.get_scheme_by_id")
def test_checklist_alternative_match(mock_get_scheme, sample_user, sample_scheme):
    """Citizen document matching one of scheme document's alternatives fulfills requirement."""
    mock_get_scheme.return_value = sample_scheme

    scheme_doc = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=sample_scheme.id,
        document_type="identity_proof",
        title="Identity Proof",
        is_mandatory=True,
        is_active=True,
        alternatives=["aadhaar", "voter_id", "passport"],
    )

    citizen_doc = CitizenDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        beneficiary_id=None,
        document_type="voter_id",  # Matched via alternatives
        file_name="voter.jpg",
        file_path="sample.jpg",
        file_size_bytes=2000,
        mime_type="image/jpeg",
        checksum_sha256="def",
        verification_status="VERIFIED",
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [scheme_doc],
        [citizen_doc],
    ]

    res = get_checklist(mock_db, sample_user, sample_scheme.id, beneficiary_id=None)
    assert res.is_complete is True
    assert res.mandatory_documents[0].status == "UPLOADED"
    assert res.mandatory_documents[0].attached_document_id == citizen_doc.id


@patch("app.services.scheme_service.get_scheme_by_id")
def test_checklist_rejected_document_does_not_fulfill(mock_get_scheme, sample_user, sample_scheme):
    """Rejected citizen document does not satisfy mandatory requirement."""
    mock_get_scheme.return_value = sample_scheme

    scheme_doc = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=sample_scheme.id,
        document_type="land_records",
        title="Land Ownership Record",
        is_mandatory=True,
        is_active=True,
    )

    citizen_doc = CitizenDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        beneficiary_id=None,
        document_type="land_records",
        file_name="land.pdf",
        file_path="sample.pdf",
        file_size_bytes=3000,
        mime_type="application/pdf",
        checksum_sha256="ghi",
        verification_status="REJECTED",  # REJECTED
        rejection_reason="Unclear land parcel survey number",
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [scheme_doc],
        [citizen_doc],
    ]

    res = get_checklist(mock_db, sample_user, sample_scheme.id, beneficiary_id=None)
    assert res.is_complete is False
    assert res.uploaded_mandatory == 0
    assert res.completion_percentage == 0.0
    assert res.mandatory_documents[0].status == "MISSING"


@patch("app.services.beneficiary_service.get_beneficiary")
@patch("app.services.scheme_service.get_scheme_by_id")
def test_checklist_family_beneficiary_isolation(
    mock_get_scheme, mock_get_beneficiary, sample_user, sample_scheme
):
    """Checklist for family beneficiary only considers documents tagged for that beneficiary."""
    mock_get_scheme.return_value = sample_scheme

    ben_id = uuid.uuid4()
    mock_ben = BeneficiaryProfile(
        id=ben_id,
        user_id=sample_user.id,
        full_name="Sita Devi",
        relationship="mother",
    )
    mock_get_beneficiary.return_value = mock_ben

    scheme_doc = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=sample_scheme.id,
        document_type="aadhaar",
        title="Aadhaar Card",
        is_mandatory=True,
        is_active=True,
    )

    mock_db = MagicMock()
    # No documents uploaded for mother yet
    mock_db.execute.return_value.scalars.return_value.all.side_effect = [
        [scheme_doc],
        [],
    ]

    res = get_checklist(mock_db, sample_user, sample_scheme.id, beneficiary_id=ben_id)
    assert res.target_name == "Sita Devi"
    assert res.beneficiary_id == ben_id
    assert res.is_complete is False
    assert res.uploaded_mandatory == 0
    assert res.mandatory_documents[0].status == "MISSING"

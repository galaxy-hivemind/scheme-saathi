"""
Unit tests for Application Draft Service:
- Prefilling demographics from UserProfile (self) and BeneficiaryProfile (family member).
- Deterministic eligibility check snapshot.
- Automatic linkage of uploaded documents from checklist.
- Status assignment (READY vs DRAFT).
- Portal URL resolution.
- External submission recording and reference number storage.
- Preventing edits to already submitted drafts.
"""
from datetime import date
from decimal import Decimal
import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.core.exceptions import ValidationError, NotFoundError
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.models.scheme import Scheme
from app.models.application_draft import ApplicationDraft
from app.schemas.application import ApplicationDraftUpdate, ApplicationDraftSubmitRequest
from app.schemas.document import DocumentChecklistResponse, DocumentChecklistItem
from app.schemas.eligibility import EligibilityResult, TriStateStatus, EligibilityResultStatus
from app.services.application_service import (
    create_application_draft,
    update_application_draft,
    submit_external_application,
)


@pytest.fixture
def sample_user():
    user = User(id=uuid.uuid4(), email="citizen@gov.in", password_hash="h")
    user.profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name="Anil Kumar",
        date_of_birth=date(1985, 5, 20),
        gender="male",
        state="Bihar",
        district="Patna",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=Decimal("80000.00"),
        profile_data={"caste": "OBC", "bpl_card": True},
    )
    return user


@pytest.fixture
def sample_scheme():
    return Scheme(
        id=uuid.uuid4(),
        scheme_code="PM-KISAN",
        name="PM Kisan Samman Nidhi",
        description="Farmer support",
        ministry="Ministry of Agriculture",
        category="agriculture",
        benefits="6000 per year",
        target_beneficiaries=["farmers"],
        official_url="https://pmkisan.gov.in",
        application_url="https://pmkisan.gov.in/apply",
        source_url="https://pmkisan.gov.in",
    )


@patch("app.services.eligibility_service.evaluate_scheme_eligibility")
@patch("app.services.document_service.get_checklist")
@patch("app.services.scheme_service.get_scheme_by_id")
def test_create_application_draft_self(
    mock_get_scheme, mock_get_checklist, mock_eval_elig, sample_user, sample_scheme
):
    """Creating draft for self prefills UserProfile demographics and resolves official portal URL."""
    mock_get_scheme.return_value = sample_scheme

    doc_id = uuid.uuid4()
    mock_get_checklist.return_value = DocumentChecklistResponse(
        scheme_id=sample_scheme.id,
        scheme_code="PM-KISAN",
        scheme_name=sample_scheme.name,
        target_name="Anil Kumar",
        total_mandatory=1,
        uploaded_mandatory=1,
        is_complete=True,
        completion_percentage=100.0,
        mandatory_documents=[
            DocumentChecklistItem(
                document_type="aadhaar",
                title="Aadhaar",
                is_mandatory=True,
                status="UPLOADED",
                attached_document_id=doc_id,
                attached_file_name="aadhaar.pdf",
                attached_verification_status="PENDING",
            )
        ],
        optional_documents=[],
    )

    mock_elig = MagicMock()
    mock_elig.overall_status.value = "PASS"
    mock_elig.result.value = "eligible"
    mock_elig.rule_version = 1
    mock_elig.missing_fields = []
    mock_elig.reasons = ["All conditions met"]
    mock_eval_elig.return_value = mock_elig

    mock_db = MagicMock()
    res = create_application_draft(
        db=mock_db,
        current_user=sample_user,
        scheme_id=sample_scheme.id,
        beneficiary_id=None,
        notes="First time applying",
    )

    assert res.scheme_code == "PM-KISAN"
    assert res.target_name == "Anil Kumar"
    assert res.status == "READY"
    assert res.official_portal_url == "https://pmkisan.gov.in/apply"
    assert res.notes == "First time applying"

    # Verify demographic prefilling
    assert res.prefilled_data["full_name"] == "Anil Kumar"
    assert res.prefilled_data["state"] == "Bihar"
    assert res.prefilled_data["occupation"] == "farmer"
    assert res.prefilled_data["annual_family_income"] == 80000.0

    # Verify attached documents
    assert len(res.attached_documents) == 1
    assert res.attached_documents[0]["document_type"] == "aadhaar"
    assert res.attached_documents[0]["citizen_document_id"] == str(doc_id)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@patch("app.services.eligibility_service.evaluate_scheme_eligibility")
@patch("app.services.document_service.get_checklist")
@patch("app.services.beneficiary_service.get_beneficiary")
@patch("app.services.scheme_service.get_scheme_by_id")
def test_create_application_draft_family_beneficiary(
    mock_get_scheme, mock_get_beneficiary, mock_get_checklist, mock_eval_elig, sample_user, sample_scheme
):
    """Creating draft for family beneficiary prefills beneficiary attributes."""
    mock_get_scheme.return_value = sample_scheme

    ben_id = uuid.uuid4()
    mock_ben = BeneficiaryProfile(
        id=ben_id,
        user_id=sample_user.id,
        full_name="Kavita Kumar",
        relationship="spouse",
        date_of_birth=date(1988, 3, 15),
        gender="female",
        state="Bihar",
        district="Patna",
        residence_type="rural",
        occupation="homemaker",
        annual_family_income=Decimal("80000.00"),
        profile_data={},
    )
    mock_get_beneficiary.return_value = mock_ben

    # Checklist has missing documents -> status DRAFT
    mock_get_checklist.return_value = DocumentChecklistResponse(
        scheme_id=sample_scheme.id,
        scheme_code="PM-KISAN",
        scheme_name=sample_scheme.name,
        target_name="Kavita Kumar",
        total_mandatory=1,
        uploaded_mandatory=0,
        is_complete=False,
        completion_percentage=0.0,
        mandatory_documents=[
            DocumentChecklistItem(
                document_type="aadhaar",
                title="Aadhaar",
                is_mandatory=True,
                status="MISSING",
            )
        ],
        optional_documents=[],
    )

    mock_elig = MagicMock()
    mock_elig.overall_status.value = "UNKNOWN"
    mock_elig.result.value = "insufficient_information"
    mock_elig.rule_version = 1
    mock_elig.missing_fields = ["land_ownership"]
    mock_elig.reasons = []
    mock_eval_elig.return_value = mock_elig

    mock_db = MagicMock()
    res = create_application_draft(
        db=mock_db,
        current_user=sample_user,
        scheme_id=sample_scheme.id,
        beneficiary_id=ben_id,
    )

    assert res.target_name == "Kavita Kumar"
    assert res.beneficiary_id == ben_id
    assert res.status == "DRAFT"
    assert res.prefilled_data["relationship"] == "spouse"
    assert res.prefilled_data["gender"] == "female"


@patch("app.services.scheme_service.get_scheme_by_id")
def test_submit_external_application(mock_get_scheme, sample_user, sample_scheme):
    """Recording external portal submission sets reference number and status SUBMITTED."""
    mock_get_scheme.return_value = sample_scheme

    draft_id = uuid.uuid4()
    draft = ApplicationDraft(
        id=draft_id,
        user_id=sample_user.id,
        scheme_id=sample_scheme.id,
        status="READY",
        prefilled_data={"full_name": "Anil Kumar"},
        attached_documents=[],
        official_portal_url="https://pmkisan.gov.in",
    )
    draft.user = sample_user

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = draft

    req = ApplicationDraftSubmitRequest(
        external_reference_number="PMKISAN/2026/987654",
        notes="Submitted at CSC Kendra",
    )
    res = submit_external_application(mock_db, sample_user, draft_id, req)

    assert res.status == "SUBMITTED"
    assert res.external_reference_number == "PMKISAN/2026/987654"
    assert res.submitted_at is not None
    assert res.notes == "Submitted at CSC Kendra"
    mock_db.commit.assert_called_once()


def test_update_submitted_draft_raises_error(sample_user, sample_scheme):
    """Cannot edit an already submitted application draft."""
    draft_id = uuid.uuid4()
    draft = ApplicationDraft(
        id=draft_id,
        user_id=sample_user.id,
        scheme_id=sample_scheme.id,
        status="SUBMITTED",
        prefilled_data={},
        attached_documents=[],
        official_portal_url="https://pmkisan.gov.in",
    )

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = draft

    update_req = ApplicationDraftUpdate(notes="Trying to edit after submission")
    with pytest.raises(ValidationError) as exc:
        update_application_draft(mock_db, sample_user, draft_id, update_req)
    assert "Cannot update application draft in 'SUBMITTED' status" in str(exc.value.message)

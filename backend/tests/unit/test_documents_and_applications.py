"""
Unit tests for Document Vault and Application Readiness endpoints.
"""
import uuid
from datetime import datetime, timezone
import pytest
from app.models.user import User
from app.models.user_profile import UserProfile
from app.api.v1.documents import get_user_documents, get_scheme_document_checklist, DocumentChecklistRequest
from app.api.v1.applications import (
    get_applications,
    create_application_draft,
    CreateDraftRequest,
    update_application_draft,
    UpdateDraftRequest,
    validate_application_draft,
    confirm_application,
    submit_application,
    get_scheme_schema,
    clean_val,
)


class MockSession:
    def __init__(self, profile=None, scheme=None, scheme_docs=None):
        self.profile = profile
        self.scheme = scheme
        self.scheme_docs = scheme_docs or []
        self.added = []
        self.committed = False
        self.refreshed = False

    def query(self, model):
        session_self = self
        class QueryMock:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                if model == UserProfile:
                    return session_self.profile
                elif model.__name__ == "Scheme":
                    return session_self.scheme
                return None

            def all(self):
                if model.__name__ == "SchemeDocument":
                    return session_self.scheme_docs
                return []
        return QueryMock()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = True


def test_get_user_documents_empty():
    user = User(id=uuid.uuid4(), email="test@example.com")
    db = MockSession(profile=None)
    res = get_user_documents(current_user=user, db=db)
    assert res.success is True
    assert res.data == []


def test_get_user_documents_with_docs():
    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Citizen",
        profile_data={
            "documents": [
                {"id": "doc-1", "document_type": "aadhaar", "upload_status": "uploaded"}
            ]
        }
    )
    db = MockSession(profile=profile)
    res = get_user_documents(current_user=user, db=db)
    assert res.success is True
    assert len(res.data) == 1
    assert res.data[0]["document_type"] == "aadhaar"


def test_create_and_validate_application_draft():
    from fastapi import HTTPException

    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@example.com")
    # Initial incomplete profile & unverified uploaded document
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Test Farmer",
        profile_data={
            "documents": [
                {"id": "doc-land-1", "document_type": "land_records", "upload_status": "uploaded", "review_status": "pending_review"}
            ]
        }
    )
    db = MockSession(profile=profile)

    # 1. Create incomplete draft
    req = CreateDraftRequest(scheme_id="PM-KISAN", form_data={"state": "Maharashtra"})
    res_draft = create_application_draft(payload=req, current_user=user, db=db)
    assert res_draft.success is True
    app_id = res_draft.data["id"]
    assert res_draft.data["lifecycle_state"] == "draft"

    # 2. Validation detects missing profile, form fields, and unverified documents
    res_val = validate_application_draft(app_id=app_id, current_user=user, db=db)
    assert res_val.success is True
    assert res_val.data["passed"] is False

    # 3. Attempting to confirm or submit unready draft must be blocked cleanly (never silent submit)
    with pytest.raises(HTTPException) as exc_conf:
        confirm_application(app_id=app_id, current_user=user, db=db)
    assert exc_conf.value.status_code == 422

    with pytest.raises(HTTPException) as exc_sub:
        submit_application(app_id=app_id, current_user=user, db=db)
    assert exc_sub.value.status_code == 400

    # 4. Complete profile, verify mandatory documents (aadhaar_card, land_records, bank_passbook), and fill required fields
    profile.gender = "male"
    profile.state = "Maharashtra"
    profile.district = "Pune"
    profile.residence_type = "rural"
    profile.occupation = "farmer"
    profile.annual_family_income = 95000
    profile.age = 42
    profile.profile_data["documents"] = [
        {"id": "doc-1", "document_type": "aadhaar_card", "upload_status": "uploaded", "lifecycle_status": "verified"},
        {"id": "doc-2", "document_type": "land_records", "upload_status": "uploaded", "lifecycle_status": "verified"},
        {"id": "doc-3", "document_type": "bank_passbook", "upload_status": "uploaded", "lifecycle_status": "verified"},
    ]

    update_application_draft(
        app_id=app_id,
        payload=UpdateDraftRequest(form_data={
            "applicant_name": "Test Farmer",
            "gender": "MALE",
            "category": "OBC",
            "aadhaar_number": "234567890123",
            "mobile_number": "9876543210",
            "state": "Maharashtra",
            "district": "Pune",
            "sub_district_block": "Haveli",
            "village": "Shivpur",
            "land_ownership_type": "Single",
            "khasra_khatauni_no": "104/2",
            "land_area_acres": "2.0",
            "bank_account_number": "123456789012",
            "ifsc_code": "SBIN0001234",
        }),
        current_user=user,
        db=db,
    )

    res_val_ready = validate_application_draft(app_id=app_id, current_user=user, db=db)
    assert res_val_ready.data["passed"] is True

    # 5. Confirm draft after readiness passes
    res_conf = confirm_application(app_id=app_id, current_user=user, db=db)
    assert res_conf.success is True
    assert res_conf.data["confirmed"] is True

    # 6. Submission orchestrator honors manual portal submission when no government API integration exists
    res_sub = submit_application(app_id=app_id, current_user=user, db=db)
    assert res_sub.success is True
    assert res_sub.data["manual_portal_required"] is True
    assert res_sub.data["submitted"] is False
    assert res_sub.data["external_reference_id"] is None
    assert res_sub.data["lifecycle_state"] == "confirmed"
    assert "pmkisan.gov.in" in res_sub.data["portal_url"]


def test_get_scheme_application_schema():
    user = User(id=uuid.uuid4(), email="test@example.com")
    db = MockSession()
    
    # PM-KISAN schema
    res_kisan = get_scheme_schema("PM-KISAN", current_user=user, db=db)
    assert res_kisan.success is True
    assert res_kisan.data["scheme_code"] == "PM-KISAN"
    field_names_kisan = [f["name"] for sec in res_kisan.data["sections"] for f in sec["fields"]]
    assert "aadhaar_number" in field_names_kisan
    assert "khasra_khatauni_no" in field_names_kisan
    assert "bank_account_number" in field_names_kisan
    assert "ifsc_code" in field_names_kisan

    # PMAY-G schema
    res_pmay = get_scheme_schema("PMAY-G", current_user=user, db=db)
    assert res_pmay.success is True
    assert "PMAY" in res_pmay.data["scheme_code"]
    field_names_pmay = [f["name"] for sec in res_pmay.data["sections"] for f in sec["fields"]]
    assert "current_house_type" in field_names_pmay
    assert "ownership_of_pucca_house" in field_names_pmay

    # AB-PMJAY schema
    res_pmjay = get_scheme_schema("AB-PMJAY", current_user=user, db=db)
    assert res_pmjay.success is True
    field_names_pmjay = [f["name"] for sec in res_pmjay.data["sections"] for f in sec["fields"]]
    assert "existing_ayushman_card" in field_names_pmjay
    assert "coverage_category" in field_names_pmjay


def test_update_application_draft_persistence_and_cleanup():
    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Ramesh Kumar",
        profile_data={"applications": []}
    )
    db = MockSession(profile=profile)

    # 1. Create draft
    req = CreateDraftRequest(scheme_id="PM-KISAN", form_data={"state": "Maharashtra", "district": "Pune"})
    res_draft = create_application_draft(payload=req, current_user=user, db=db)
    app_id = res_draft.data["id"]

    # 2. Update with null values and empty strings to test clean_val
    update_req = UpdateDraftRequest(form_data={
        "state": "Maharashtra",
        "district": "Pune",
        "khasra_number": "null",
        "village": "Shivpur",
        "mobile_number": "9876543210",
        "aadhaar_number": "123456789012"
    })
    res_update = update_application_draft(app_id=app_id, payload=update_req, current_user=user, db=db)
    assert res_update.success is True
    updated_form = res_update.data["form_data"]
    assert updated_form["khasra_number"] == ""  # literal "null" was converted to clean empty string
    assert updated_form["village"] == "Shivpur"
    assert updated_form["mobile_number"] == "9876543210"


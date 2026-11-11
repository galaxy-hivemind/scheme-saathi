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
    validate_application_draft,
    confirm_application,
    submit_application,
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
    user_id = uuid.uuid4()
    user = User(id=user_id, email="test@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        full_name="Test Farmer",
        profile_data={
            "documents": [
                {"document_type": "land_records", "upload_status": "uploaded"}
            ]
        }
    )
    db = MockSession(profile=profile)

    # 1. Create draft
    req = CreateDraftRequest(scheme_id="PM-KISAN", form_data={"state": "Maharashtra"})
    res_draft = create_application_draft(payload=req, current_user=user, db=db)
    assert res_draft.success is True
    app_id = res_draft.data["id"]
    assert res_draft.data["lifecycle_state"] == "draft"

    # 2. Validate draft
    res_val = validate_application_draft(app_id=app_id, current_user=user, db=db)
    assert res_val.success is True

    # 3. Confirm draft
    res_conf = confirm_application(app_id=app_id, current_user=user, db=db)
    assert res_conf.success is True
    assert res_conf.data["confirmed"] is True

    # 4. Submit / Portal handoff
    res_sub = submit_application(app_id=app_id, current_user=user, db=db)
    assert res_sub.success is True
    assert "SAATHI/READY" in res_sub.data["reference_number"]

"""
Comprehensive End-to-End Application Workflow Tests (Steps 1-5):
  Step 1: Conversational application preparation ("Apply for this scheme" / "Apply for PM-KISAN")
          across en/hi/mr with profile recovery, Vault readiness, missing fields & missing mandatory docs.
  Step 2: Editable application draft -> save -> resume across fresh DB session -> complete -> validate.
  Step 3: Official Portal Integration Registry across Mode A (direct_api), Mode B (portal_assisted),
          and Mode C (manual), including unmodeled / pending schemes.
  Step 4: Explicit confirmation gate, OTP/CAPTCHA non-bypass security controls, rejection of
          synthetic SAATHI/... or internal app IDs, and Mode B citizen-reported reference via REST & Chat.
  Step 5: Normalized `ApplicationRecord` persistence in SQLite/ORM cleanly separating internal
          `application_id` from optional `official_reference_number`, plus strict citizen isolation.
"""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON as SA_JSON, MetaData, create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import get_current_user
from app.database.base import Base
from app.database.dependencies import get_db
import app.models  # noqa: F401
from app.models.application_record import ApplicationRecord
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.user import User
from app.models.user_profile import UserProfile
from app.main import app
from app.schemas.agent import AgentChatRequest, ChatResponseType
from app.services import agent_service
from app.services.portal_registry_service import (
    SUBMISSION_MODE_DIRECT_API,
    SUBMISSION_MODE_MANUAL,
    SUBMISSION_MODE_PORTAL_ASSISTED,
    get_portal_integration_entry,
)
from app.services.submission_service import (
    PortalSubmissionResult,
    STATE_AWAITING_CONFIRMATION,
    STATE_CONFIRMED,
    STATE_PORTAL_SUBMITTED,
    STATE_SUBMITTED,
    clear_registered_portal_adapters,
    register_portal_adapter,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


_orig_array_bind = ARRAY.bind_processor
_orig_array_res = ARRAY.result_processor


def _sqlite_array_bind(self, dialect):
    if dialect.name == "sqlite":
        return SA_JSON().bind_processor(dialect)
    return _orig_array_bind(self, dialect)


def _sqlite_array_res(self, dialect, coltype):
    if dialect.name == "sqlite":
        return SA_JSON().result_processor(dialect, coltype)
    return _orig_array_res(self, dialect, coltype)


ARRAY.bind_processor = _sqlite_array_bind
ARRAY.result_processor = _sqlite_array_res


SCHEME_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
SEED_FILES = [
    "pm-kisan.json",
    "kcc.json",
    "ab-pmjay.json",
    "pmay-g.json",
    "apy.json",
    "nsp-csss.json",
]


def _seed_schemes(db: Session, filenames: List[str] = None) -> Dict[str, Scheme]:
    seeded: Dict[str, Scheme] = {}
    now = datetime.now(timezone.utc)
    for fname in (filenames or SEED_FILES):
        raw = json.loads((SCHEME_DIR / fname).read_text(encoding="utf-8"))
        scheme = Scheme(
            id=uuid.uuid4(),
            scheme_code=raw["scheme_code"],
            name=raw["name"],
            short_title=raw.get("short_title"),
            description=raw["description"],
            ministry=raw["ministry"],
            department=raw.get("department"),
            category=raw["category"],
            geographic_scope=raw.get("geographic_scope", "central"),
            target_beneficiaries=raw.get("target_beneficiaries", []),
            benefits=raw["benefits"],
            official_url=raw.get("official_url"),
            application_url=raw.get("application_url"),
            source_url=raw["source_url"],
            source_evidence=raw.get("source_evidence", []),
            scheme_status=raw.get("scheme_status", "active"),
            last_retrieved_at=now,
            last_verified_at=now,
        )
        db.add(scheme)
        db.flush()

        db.add(
            SchemeRuleVersion(
                id=uuid.uuid4(),
                scheme_id=scheme.id,
                version=1,
                is_active=True,
                eligibility_criteria=raw.get("eligibility_criteria", {}),
                source_url=raw["source_url"],
            )
        )

        for doc in raw.get("required_documents", []):
            db.add(
                SchemeDocument(
                    id=uuid.uuid4(),
                    scheme_id=scheme.id,
                    document_type=doc["document_type"],
                    title=doc["title"],
                    description=doc.get("description"),
                    is_mandatory=doc.get("is_mandatory", True),
                    is_active=True,
                    alternatives=doc.get("alternatives") or [],
                    issuing_authority=doc.get("issuing_authority"),
                    guidance=doc.get("guidance"),
                    source_url=doc.get("source_url"),
                )
            )
        seeded[scheme.scheme_code] = scheme

    db.commit()
    return seeded


@pytest.fixture
def file_sqlite_env(tmp_path, monkeypatch):
    """Real SQLite file DB supporting fresh sessions across simulated restarts + TestClient."""
    agent_service._CONVERSATION_SESSIONS.clear()
    clear_registered_portal_adapters()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    db_file = tmp_path / "e2e_workflow.db"
    test_meta = MetaData()
    for tbl in Base.metadata.sorted_tables:
        cloned = tbl.to_metadata(test_meta)
        cloned.indexes = {
            idx
            for idx in cloned.indexes
            if "fts" not in (idx.name or "") and "trgm" not in str(idx.dialect_options)
        }
        cloned.constraints = {
            c for c in cloned.constraints if "char_length" not in str(getattr(c, "sqltext", ""))
        }

    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    test_meta.create_all(engine)
    SessionFactory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    setup_db = SessionFactory()
    _seed_schemes(setup_db)
    setup_db.close()

    yield SessionFactory

    app.dependency_overrides.clear()
    clear_registered_portal_adapters()
    agent_service._CONVERSATION_SESSIONS.clear()
    engine.dispose()


def _create_farmer_with_partial_vault(db: Session, *, email: str = "farmer.e2e@example.gov.in"):
    uid = uuid.uuid4()
    user = User(id=uid, email=email, password_hash="hashed", is_active=True)
    db.add(user)
    db.flush()
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Suresh Patil",
        age=44,
        gender="male",
        state="Maharashtra",
        district="Nashik",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=Decimal("90000.00"),
        profile_data={
            "caste_category": "OBC",
            "phone_number": "9822011223",
            "is_landholding_farmer": True,
            "land_holding_acres": 2.5,
            "documents": [
                {
                    "id": "doc-aadhaar",
                    "user_id": str(uid),
                    "document_type": "aadhaar_card",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "sha256": "aaa111",
                    "verified_at": "2026-11-11T09:00:00Z",
                    "reviewed_fields": {
                        "holder_name": "Suresh Patil",
                        "document_number": "345678901234",
                    },
                },
                {
                    "id": "doc-bank",
                    "user_id": str(uid),
                    "document_type": "bank_passbook",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "sha256": "bbb222",
                    "verified_at": "2026-11-11T09:05:00Z",
                    "reviewed_fields": {
                        "document_number": "556677889900",
                        "ifsc_code": "SBIN0004321",
                    },
                },
            ],
        },
    )
    db.add(profile)
    db.commit()
    return user, profile


def test_step1_trilingual_apply_for_scheme_preparation_and_persistence(file_sqlite_env):
    """
    Step 1 across en/hi/mr:
    'Tell me more about PM-KISAN' -> 'Apply for this scheme' (en) / 'इस योजना के लिए आवेदन करें' (hi) /
    'या योजनेसाठी अर्ज करा' (mr) prepares draft, exposes missing fields & missing mandatory docs,
    attaches Step 3 portal registry metadata, and persists Step 5 ApplicationRecord in DB.
    """
    SessionFactory = file_sqlite_env
    db = SessionFactory()
    user, _ = _create_farmer_with_partial_vault(db)

    try:
        # English active scheme -> "Apply for this scheme"
        conv_en = "conv-e2e-apply-en"
        r_info = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_en, message="Tell me more about PM-KISAN.", language="en"),
            current_user=user,
        )
        assert r_info.active_scheme and r_info.active_scheme["scheme_code"] == "PM-KISAN"

        r_apply = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_en, message="Apply for this scheme", language="en"),
            current_user=user,
        )
        assert r_apply.detected_language == "en"
        assert r_apply.response_type == ChatResponseType.FORM_DRAFT
        assert r_apply.form_draft_data is not None
        draft_id = r_apply.form_draft_data["application_id"]
        assert draft_id.startswith("app-")
        assert r_apply.form_draft_data["portal_integration"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED
        assert "pmkisan.gov.in" in r_apply.form_draft_data["portal_integration"]["official_application_url"]
        assert len(r_apply.form_draft_data["missing_fields"]) >= 1
        assert any(
            "land" in str(m).lower() or "khasra" in str(m).lower() or "record" in str(m).lower()
            for m in r_apply.form_draft_data["missing_mandatory_documents"]
        )
        assert "Draft ID:" in r_apply.message or draft_id in r_apply.message

        # Hindi trigger on the same pattern
        conv_hi = "conv-e2e-apply-hi"
        agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_hi, message="PM-KISAN के बारे में बताएं", language="hi"),
            current_user=user,
        )
        r_hi = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_hi, message="इस योजना के लिए आवेदन करें", language="hi"),
            current_user=user,
        )
        assert r_hi.detected_language == "hi"
        assert r_hi.response_type == ChatResponseType.FORM_DRAFT
        assert "ड्राफ्ट ID" in r_hi.message or "आवेदन" in r_hi.message

        # Marathi direct explicit trigger
        conv_mr = "conv-e2e-apply-mr"
        r_mr = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_mr, message="PM-KISAN साठी अर्ज करा", language="mr"),
            current_user=user,
        )
        assert r_mr.detected_language == "mr"
        assert r_mr.response_type == ChatResponseType.FORM_DRAFT
        assert "मसुदा ID" in r_mr.message or "अर्ज" in r_mr.message

        # Verify Step 5 normalized ApplicationRecord row persisted in DB
        fresh_db = SessionFactory()
        try:
            rec = fresh_db.execute(
                select(ApplicationRecord).where(ApplicationRecord.application_id == draft_id)
            ).scalar_one_or_none()
            assert rec is not None
            assert rec.citizen_id == user.id
            assert rec.scheme_code == "PM-KISAN"
            assert rec.official_reference_number is None
            assert rec.submission_method == SUBMISSION_MODE_PORTAL_ASSISTED
            assert "pmkisan.gov.in" in rec.portal_url
            assert rec.tracking_url and "BeneficiaryStatus" in rec.tracking_url
        finally:
            fresh_db.close()
    finally:
        db.close()


def test_steps_2_3_4_5_full_rest_and_chat_workflow_including_mode_b_return_reference(file_sqlite_env):
    """
    Full REST + Chat E2E workflow across distinct DB sessions:
    Prepare -> Edit/Save -> Resume in new session -> Upload/verify missing doc -> Complete fields ->
    Validate -> Portal Registry check -> Confirm -> Reject synthetic/internal refs ->
    Mode B official reference return (REST + Chat) -> Verify ApplicationRecord & citizen isolation.
    """
    SessionFactory = file_sqlite_env
    seed_db = SessionFactory()
    user, _ = _create_farmer_with_partial_vault(seed_db, email="e2e.farmer@example.gov.in")
    other_user, _ = _create_farmer_with_partial_vault(seed_db, email="intruder.farmer@example.gov.in")
    seed_db.close()

    active_user_holder = {"user": user}

    def override_get_db():
        s = SessionFactory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: active_user_holder["user"]

    client = TestClient(app)

    # Step 3: Portal Registry endpoints work across seeded & structured schemes
    reg_res = client.get("/api/v1/applications/portal-registry?lang=en")
    assert reg_res.status_code == 200
    reg_body = reg_res.json()["data"]
    assert isinstance(reg_body, list) and len(reg_body) >= 6
    by_code = {e["scheme_code"]: e for e in reg_body}
    assert by_code["PM-KISAN"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED
    assert by_code["PM-KISAN"]["supported_api_integration"] is False
    assert "BeneficiaryStatus" in by_code["PM-KISAN"]["tracking_url"]
    assert by_code["APY"]["submission_method"] == SUBMISSION_MODE_MANUAL
    assert by_code["APY"]["structured_form_supported"] is False

    single_hi = client.get("/api/v1/applications/portal-registry/PM-KISAN?lang=hi")
    assert single_hi.status_code == 200
    assert single_hi.json()["data"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED
    assert "OTP" in single_hi.json()["data"]["security_controls_notice"]

    # Step 1 & 2: Create draft -> edit partial fields -> save
    create_res = client.post(
        "/api/v1/applications/draft?lang=en",
        json={"scheme_id": "PM-KISAN", "form_data": {"village": "Ozar"}},
    )
    assert create_res.status_code in (200, 201)
    draft = create_res.json()["data"]
    app_id = draft["id"]
    assert draft["lifecycle_state"] == "draft"
    assert draft["portal_integration"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED
    assert draft["application_record"]["application_id"] == app_id
    assert draft["application_record"]["official_reference_number"] is None

    # Save partial edit and resume across a fresh request/session
    edit_res = client.put(
        f"/api/v1/applications/{app_id}?lang=en",
        json={"form_data": {"sub_district_block": "Niphad", "village": "Ozar Budruk", "land_ownership_type": "Single"}},
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["data"]["form_data"]["village"] == "Ozar Budruk"

    list_res = client.get("/api/v1/applications/?lang=en")
    assert list_res.status_code == 200
    resumed = next(item for item in list_res.json()["data"] if item["id"] == app_id)
    assert resumed["form_data"]["village"] == "Ozar Budruk"
    assert resumed["form_data"]["sub_district_block"] == "Niphad"

    # Cross-citizen isolation check (404 for another user)
    active_user_holder["user"] = other_user
    assert client.get(f"/api/v1/applications/{app_id}?lang=en").status_code == 404
    assert client.put(f"/api/v1/applications/{app_id}?lang=en", json={"form_data": {"village": "Hack"}}).status_code == 404
    active_user_holder["user"] = user

    # Attempt validation before land_records doc is verified & remaining fields entered -> blocked cleanly
    val_fail = client.post(f"/api/v1/applications/{app_id}/validate?lang=en")
    assert val_fail.status_code == 200
    assert val_fail.json()["data"]["passed"] is False

    # Verify land_records doc in DB & fill remaining mandatory fields
    doc_db = SessionFactory()
    try:
        prof = doc_db.execute(select(UserProfile).where(UserProfile.user_id == user.id)).scalar_one()
        pdata = dict(prof.profile_data or {})
        docs = list(pdata.get("documents", []))
        docs.append(
            {
                "id": "doc-land-1",
                "user_id": str(user.id),
                "document_type": "land_records",
                "lifecycle_status": "verified",
                "verification_status": "verified",
                "sha256": "ccc333",
                "verified_at": "2026-11-11T10:00:00Z",
                "reviewed_fields": {"khasra_number": "88/2A", "area": "1.01"},
            }
        )
        pdata["documents"] = docs
        prof.profile_data = pdata
        doc_db.commit()
    finally:
        doc_db.close()

    complete_res = client.put(
        f"/api/v1/applications/{app_id}?lang=en",
        json={
            "form_data": {
                "sub_district_block": "Niphad",
                "village": "Ozar Budruk",
                "land_ownership_type": "Single",
                "land_area_acres": 2.5,
                "khasra_khatauni_no": "88/2A",
            }
        },
    )
    assert complete_res.status_code == 200

    # Validate -> awaiting_confirmation
    val_ok = client.post(f"/api/v1/applications/{app_id}/validate?lang=en")
    assert val_ok.status_code == 200
    assert val_ok.json()["data"]["passed"] is True

    # Confirm gate: Mode B portal-reference MUST fail before explicit confirmation
    pre_ref = client.post(
        f"/api/v1/applications/{app_id}/portal-reference?lang=en",
        json={"official_reference_number": "PMK-MH-2026-884421", "confirmation_acknowledged": True},
    )
    assert pre_ref.status_code in (400, 409)

    rev = client.get(f"/api/v1/applications/{app_id}/review?lang=en").json()["data"]
    assert rev["lifecycle_state"] == STATE_AWAITING_CONFIRMATION
    assert rev["portal_integration"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED

    # Explicit confirmation
    conf_res = client.post(
        f"/api/v1/applications/{app_id}/confirm?lang=en",
        json={
            "consent_acknowledged": True,
            "expected_version": rev["version"],
            "expected_hash": rev["data_hash"],
        },
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["data"]["lifecycle_state"] == STATE_CONFIRMED

    # Step 4: Portal handoff does NOT fake government submission
    handoff_res = client.post(
        f"/api/v1/applications/{app_id}/submit?lang=en",
        json={"idempotency_key": f"e2e:{app_id}:v{rev['version']}"},
    )
    assert handoff_res.status_code == 200
    handoff_data = handoff_res.json()["data"]
    assert handoff_data["submitted"] is False
    assert handoff_data["manual_portal_required"] is True
    assert handoff_data["external_reference_id"] is None
    assert handoff_data["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED

    # Reject synthetic / internal draft IDs if passed as official_reference_number
    for bad_ref in ["", "SAATHI/READY/2026/0001", app_id, "app-draft-1234"]:
        bad_res = client.post(
            f"/api/v1/applications/{app_id}/portal-reference?lang=en",
            json={"official_reference_number": bad_ref, "confirmation_acknowledged": True},
        )
        assert bad_res.status_code in (400, 422), f"Expected rejection for {bad_ref!r}, got {bad_res.status_code}"

    # Mode B citizen returns with genuine official government portal reference number
    save_ref_res = client.post(
        f"/api/v1/applications/{app_id}/portal-reference?lang=en",
        json={
            "official_reference_number": "PMK-MH-2026-884421",
            "submission_date": "2026-11-12",
            "portal_notes": "Submitted after Aadhaar OTP on pmkisan.gov.in",
            "confirmation_acknowledged": True,
        },
    )
    assert save_ref_res.status_code == 200
    saved = save_ref_res.json()["data"]
    assert saved["lifecycle_state"] == STATE_PORTAL_SUBMITTED
    assert saved["official_reference_number"] == "PMK-MH-2026-884421"
    assert saved["application_id"] == app_id
    assert saved["application_id"] != saved["official_reference_number"]
    assert saved["reference_source"] == "citizen_reported_portal_reference"
    assert saved["application_record"]["submission_method"] == SUBMISSION_MODE_PORTAL_ASSISTED
    assert saved["application_record"]["reference_source"] == "citizen_reported_portal_reference"
    assert saved["application_record"]["application_status"] == STATE_PORTAL_SUBMITTED

    # Confirm persisted GET /applications/{app_id} exposes full Step 5 fields & non-fake flag
    reloaded = client.get(f"/api/v1/applications/{app_id}?lang=en").json()["data"]
    assert reloaded["id"] == app_id
    assert reloaded["lifecycle_state"] == STATE_PORTAL_SUBMITTED
    assert reloaded["submission_source"] == "portal_assisted"
    assert reloaded["is_verified_government_submission"] is False
    assert reloaded["official_reference_number"] == "PMK-MH-2026-884421"

    # Also verify chat planner form_action='record_portal_reference' persists in chat path
    chat_db = SessionFactory()
    try:
        db_user = chat_db.execute(select(User).where(User.id == user.id)).scalar_one()
        r_chat_ref = agent_service.process_chat_message(
            db=chat_db,
            request=AgentChatRequest(
                conversation_id="conv-e2e-return-ref",
                message="Record official portal reference number: PMK-MH-2026-884422",
                language="en",
                scheme_id="PM-KISAN",
                workflow_step="SUBMIT",
                form_action="record_portal_reference",
                official_reference_number="PMK-MH-2026-884422",
                form_data={"application_id": app_id, "official_reference_number": "PMK-MH-2026-884422"},
            ),
            current_user=db_user,
        )
        assert r_chat_ref.response_type == ChatResponseType.CONFIRMATION_RESULT
        assert r_chat_ref.confirmation_data["lifecycle_state"] == STATE_PORTAL_SUBMITTED
        assert r_chat_ref.confirmation_data["official_reference_number"] == "PMK-MH-2026-884422"
    finally:
        chat_db.close()

    # Step 5: Inspect normalized ApplicationRecord in fresh session
    verify_db = SessionFactory()
    try:
        rec = verify_db.execute(
            select(ApplicationRecord).where(ApplicationRecord.application_id == app_id)
        ).scalar_one()
        assert rec.citizen_id == user.id
        assert rec.scheme_code == "PM-KISAN"
        assert rec.application_id == app_id
        assert rec.official_reference_number == "PMK-MH-2026-884422"
        assert rec.reference_source == "citizen_reported_portal_reference"
        assert rec.application_status == STATE_PORTAL_SUBMITTED
        assert rec.submission_method == SUBMISSION_MODE_PORTAL_ASSISTED
        assert rec.submission_date is not None
        assert "pmkisan.gov.in" in rec.portal_url
        assert "BeneficiaryStatus" in (rec.tracking_url or "")
    finally:
        verify_db.close()


def test_mode_a_direct_api_adapter_updates_registry_and_application_record(file_sqlite_env):
    """Mode A direct_api works cleanly ONLY when an authorized official adapter is registered."""
    class FakeOfficialGateway:
        provider_name = "MAHA-DIRECT-API"
        is_authorized = True

        def submit(self, application, idempotency_key, lang="en"):
            return PortalSubmissionResult(
                outcome="submitted",
                external_reference_id="GOV-MH-2026-DIRECT-01",
                portal_status="ACCEPTED",
                raw_response={"tx": "GOV-MH-2026-DIRECT-01"},
            )

    SessionFactory = file_sqlite_env
    db = SessionFactory()
    user, profile = _create_farmer_with_partial_vault(db, email="modea.farmer@example.gov.in")
    pdata = dict(profile.profile_data)
    pdata["documents"].append(
        {
            "id": "doc-land-a",
            "user_id": str(user.id),
            "document_type": "land_records",
            "lifecycle_status": "verified",
            "verification_status": "verified",
            "sha256": "ddd444",
            "verified_at": "2026-11-11T10:15:00Z",
            "reviewed_fields": {"khasra_number": "12/1"},
        }
    )
    profile.profile_data = pdata
    db.commit()

    register_portal_adapter("PM-KISAN", FakeOfficialGateway())
    try:
        reg_entry = get_portal_integration_entry("PM-KISAN", db=db, lang="en")
        assert reg_entry["submission_method"] == SUBMISSION_MODE_DIRECT_API
        assert reg_entry["supported_api_integration"] is True

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        client = TestClient(app)

        draft_res = client.post(
            "/api/v1/applications/draft?lang=en",
            json={
                "scheme_id": "PM-KISAN",
                "form_data": {
                    "sub_district_block": "Sinnar",
                    "village": "Musalgaon",
                    "land_ownership_type": "Single",
                    "land_area_acres": 2.5,
                    "khasra_khatauni_no": "12/1",
                },
            },
        )
        assert draft_res.status_code in (200, 201), draft_res.text
        draft = draft_res.json()["data"]
        app_id = draft["id"]
        conf_res = client.post(f"/api/v1/applications/{app_id}/confirm?lang=en", json={"consent_acknowledged": True})
        assert conf_res.status_code == 200, conf_res.text
        sub_res = client.post(
            f"/api/v1/applications/{app_id}/submit?lang=en",
            json={"idempotency_key": f"modea:{app_id}:v1"},
        )
        assert sub_res.status_code == 200, sub_res.text
        sub = sub_res.json()["data"]
        assert sub["submitted"] is True
        assert sub["lifecycle_state"] == STATE_SUBMITTED
        assert sub["external_reference_id"] == "GOV-MH-2026-DIRECT-01"
        assert sub["submission_method"] == SUBMISSION_MODE_DIRECT_API

        rec = db.execute(
            select(ApplicationRecord).where(ApplicationRecord.application_id == app_id)
        ).scalar_one()
        assert rec.application_status == STATE_SUBMITTED
        assert rec.submission_method == SUBMISSION_MODE_DIRECT_API
        assert rec.official_reference_number == "GOV-MH-2026-DIRECT-01"
    finally:
        app.dependency_overrides.clear()
        clear_registered_portal_adapters()
        db.close()

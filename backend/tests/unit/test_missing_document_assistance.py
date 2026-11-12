"""
Missing-Document Preparation Assistance & Conversational Integration Tests.

Verifies:
1. All 10 required assistance elements on "I don't have my land possession certificate."
   (document identification, active scheme, why required, where to obtain, authority, portal,
   preparation process, estimated processing time, fees, fallback options).
2. Strict epistemic honesty separating Verified information, Estimated information, and
   Information unavailable — including zero fabricated fees/SLAs/URLs for unknown documents.
3. Scheme-specific document resolution (`PM-KISAN` -> `land_records` vs `PMAY-G` -> `land_possession`).
4. Multi-turn follow-up continuity (`last_discussed_document`) across restart:
   - "I don't have my land possession certificate."
   - "How do I get this document?"
   - "How much will it cost?"
   - "Where do I apply?"
   - "What if I can't obtain it?"
5. Pure trilingual (en / hi / mr) responses with zero cross-script leakage and strict citizen isolation.
6. End-to-end Phase 5 Document Vault integrity via FastAPI endpoints (`upload` -> OCR ->
   `awaiting_citizen_review` -> `reviewed` -> `verified`) and chat readiness recheck.
7. Real Gemini Function Calling compatibility for missing-document & focused guidance calls.
"""
from __future__ import annotations

import io
import json
import shutil
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import JSON as SA_JSON, MetaData, create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.form_schemas import get_document_sourcing_info
from app.core.config import settings
from app.core.security import get_current_user
from app.database.base import Base
from app.database.dependencies import get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401
from app.models.conversation_session import ConversationSession
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.agent import AgentChatRequest, ChatResponseType
from app.services import agent_service
from app.services.document_guidance_service import identify_document_key
from app.services.document_service import (
    DOC_STATE_AWAITING_REVIEW,
    DOC_STATE_REVIEWED,
    DOC_STATE_VERIFIED,
    VAULT_STORAGE_ROOT,
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


def _sqlite_safe_array_bind(self, dialect):
    if dialect.name == "sqlite":
        return SA_JSON().bind_processor(dialect)
    return _orig_array_bind(self, dialect)


def _sqlite_safe_array_res(self, dialect, coltype):
    if dialect.name == "sqlite":
        return SA_JSON().result_processor(dialect, coltype)
    return _orig_array_res(self, dialect, coltype)


ARRAY.bind_processor = _sqlite_safe_array_bind
ARRAY.result_processor = _sqlite_safe_array_res

SCHEME_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
SEED_FILES = [
    "pm-kisan.json",
    "pmay-g.json",
    "kcc.json",
    "mlby-mh.json",
    "pm-svanidhi.json",
    "nsp-csss.json",
    "pmmvy.json",
]


def _build_test_db():
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
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    test_meta.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, SessionFactory


def _seed_schemes(db: Session) -> Dict[str, Scheme]:
    seeded: Dict[str, Scheme] = {}
    now = datetime.now(timezone.utc)
    for fname in SEED_FILES:
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


@pytest.fixture()
def doc_db(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    agent_service._CONVERSATION_SESSIONS.clear()
    engine, SessionFactory = _build_test_db()
    db = SessionFactory()
    _seed_schemes(db)
    try:
        yield db, SessionFactory
    finally:
        db.close()
        engine.dispose()
        agent_service._CONVERSATION_SESSIONS.clear()


def _make_farmer(db: Session, *, email: str = "ramesh.doc@example.gov.in") -> tuple[User, UserProfile]:
    uid = uuid.uuid4()
    user = User(id=uid, email=email, password_hash="hashed", is_active=True)
    db.add(user)
    db.flush()
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kulkarni",
        age=42,
        gender="male",
        state="Maharashtra",
        district="Pune",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=110000,
        profile_data={
            "caste_category": "OBC",
            "land_holding_acres": 2.5,
            "is_landholding_farmer": True,
            "documents": [
                {
                    "id": "doc-aadhaar-1",
                    "document_type": "aadhaar_card",
                    "upload_status": "uploaded",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "citizen_confirmed_accurate": True,
                    "reviewed_fields": {"full_name_on_document": "Ramesh Kulkarni", "document_number": "234567891234"},
                },
                {
                    "id": "doc-bank-1",
                    "document_type": "bank_passbook",
                    "upload_status": "uploaded",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "citizen_confirmed_accurate": True,
                    "reviewed_fields": {"full_name_on_document": "Ramesh Kulkarni", "document_number": "123456789012", "ifsc_code": "SBIN0001234"},
                },
            ],
            "applications": [],
        },
    )
    db.add(profile)
    db.commit()
    return user, profile


def _make_valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(240, 240, 240)).save(buf, format="PNG")
    return buf.getvalue()


def test_missing_land_possession_10_elements_and_scheme_mapping(doc_db):
    """
    Verifies both PMAY-G (`land_possession`) and PM-KISAN (`land_records`) resolve
    'I don't have my land possession certificate.' accurately with all 10 required points
    and strict separation of Verified, Estimated, and Unavailable information.
    """
    db, _ = doc_db
    user, _ = _make_farmer(db)

    # Scenario A: Active scheme PMAY-G -> maps to `land_possession`
    conv_pmay = "conv-pmay-land-doc"
    agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_pmay, message="What documents are required for PMAY-G?", language="en"),
        current_user=user,
    )
    r_pmay = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_pmay, message="I don't have my land possession certificate.", language="en"),
        current_user=user,
    )

    msg = r_pmay.message
    assert r_pmay.detected_language == "en"
    assert not any("\u0900" <= ch <= "\u097F" for ch in msg)
    assert r_pmay.active_scheme["scheme_code"] == "PMAY-G"
    assert "identify_missing_documents" in r_pmay.tool_calls_used
    # All 10 required elements + 3 epistemic buckets
    assert "Verified Information" in msg
    assert "Estimated Information" in msg
    assert "Information Unavailable" in msg
    assert "Homestead Land Title" in msg
    assert "PMAY-G" in msg
    assert "Mandatory" in msg
    assert "Revenue Department" in msg or "Gram Panchayat" in msg
    assert "pmayg.nic.in" in msg
    assert "How to Prepare & Obtain" in msg
    assert "7–15 working days" in msg
    assert "₹15–₹30" in msg
    assert "If You Cannot Obtain It" in msg
    assert "Gram Panchayat Allotment Certificate" in msg
    assert "Exact local office street address" in msg

    # Scenario B: Active scheme PM-KISAN -> same citizen wording maps to `land_records`!
    conv_kisan = "conv-pmkisan-land-doc"
    agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_kisan, message="What documents are required for PM-KISAN?", language="en"),
        current_user=user,
    )
    r_kisan = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_kisan, message="I don't have my land possession certificate.", language="en"),
        current_user=user,
    )
    assert r_kisan.active_scheme["scheme_code"] == "PM-KISAN"
    assert "Land Ownership Records" in r_kisan.message or "7/12" in r_kisan.message
    assert "pmkisan.gov.in" in r_kisan.message
    assert "Record of Rights (RoR)" in r_kisan.message
    assert "Verified Information" in r_kisan.message
    assert "Estimated Information" in r_kisan.message
    assert "Information Unavailable" in r_kisan.message


def test_unknown_document_never_fabricates_fees_portals_or_timelines(doc_db):
    """
    Ensures unrecognized/unverified documents explicitly report 'Information unavailable'
    and NEVER return synthetic fee, SLA, or generic portal defaults.
    """
    db, _ = doc_db
    user, _ = _make_farmer(db, email="honest.doc@example.gov.in")

    raw_sourcing = get_document_sourcing_info("quantum_drone_clearance_certificate", lang="en")
    assert raw_sourcing["info_unavailable"] is True
    assert raw_sourcing["verified_fee"] is None
    assert raw_sourcing["expected_processing_days"] is None
    assert raw_sourcing["official_url"] is None
    assert raw_sourcing["issuing_authority"] is None

    assert identify_document_key("quantum drone clearance certificate") is None

    conv_id = "conv-unknown-doc-1"
    resp = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(
            conversation_id=conv_id,
            message="I don't have my quantum drone clearance certificate.",
            language="en",
        ),
        current_user=user,
    )
    assert resp.detected_language == "en"
    assert "Information Unavailable" in resp.message
    assert "unavailable" in resp.message.lower()
    assert "7 to 15 working days" not in resp.message
    assert "Nominal statutory fee" not in resp.message
    assert "services.india.gov.in" not in resp.message


def test_continuous_document_followup_chain_across_restart_and_trilingual(doc_db):
    """
    Verifies full follow-up continuity keyed on persisted `last_discussed_document`:
    Turn 1: "I don't have my land possession certificate." (cold query -> identifies schemes & saves doc memory)
    Simulated server restart (`_CONVERSATION_SESSIONS.clear()` + new DB Session)
    Turn 2: "How do I get this document?"
    Turn 3: "How much will it cost?"
    Turn 4: "Where do I apply?"
    Turn 5: "What if I can't obtain it?"
    Also verifies Hindi & Marathi conversations without cross-language mixing.
    """
    db1, SessionFactory = doc_db
    user, _ = _make_farmer(db1, email="continuity.doc@example.gov.in")
    conv_id = "conv-doc-followups-1"

    r1 = agent_service.process_chat_message(
        db=db1,
        request=AgentChatRequest(
            conversation_id=conv_id,
            message="I don't have my land possession certificate.",
            language="en",
        ),
        current_user=user,
    )
    assert "identify_missing_documents" in r1.tool_calls_used
    assert "PMAY-G" in r1.message
    assert "Verified Information" in r1.message

    row = db1.scalar(
        select(ConversationSession).where(
            ConversationSession.user_id == user.id,
            ConversationSession.conversation_id == conv_id,
        )
    )
    assert row is not None
    assert row.state_data.get("last_discussed_document", {}).get("document_type") == "land_possession"

    # Simulate backend restart: clear RAM and use fresh DB Session
    agent_service._CONVERSATION_SESSIONS.clear()
    db2 = SessionFactory()
    try:
        fresh_user = db2.scalar(select(User).where(User.id == user.id))

        # Turn 2: Process
        r2 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=conv_id, message="How do I get this document?", language="en"),
            current_user=fresh_user,
        )
        assert "get_document_preparation_guidance" in r2.tool_calls_used
        assert "Step-by-Step Preparation Process" in r2.message
        assert "1." in r2.message and "Document Vault" in r2.message
        assert "Estimated Information" in r2.message

        # Turn 3: Cost
        r3 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=conv_id, message="How much will it cost?", language="en"),
            current_user=fresh_user,
        )
        assert "get_document_preparation_guidance" in r3.tool_calls_used
        assert "Cost & Fee Breakdown" in r3.message
        assert "Verified Information" in r3.message
        assert "Estimated Information" in r3.message
        assert "Information Unavailable" in r3.message

        # Turn 4: Where to apply
        r4 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=conv_id, message="Where do I apply?", language="en"),
            current_user=fresh_user,
        )
        assert "Where to Apply" in r4.message
        assert "Tehsil" in r4.message or "Gram Panchayat" in r4.message
        assert "https://pmayg.nic.in" in r4.message
        assert "Information Unavailable" in r4.message

        # Turn 5: Fallback
        r5 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=conv_id, message="What if I can't obtain it?", language="en"),
            current_user=fresh_user,
        )
        assert "What If You Cannot Obtain" in r5.message
        assert "Gram Panchayat Allotment Certificate" in r5.message
        assert "landless rural household" in r5.message
        assert not any("\u0900" <= ch <= "\u097F" for ch in r5.message)
        assert not any("\u0900" <= ch <= "\u097F" for ch in r5.spoken_text)

        # Trilingual checks: Hindi & Marathi
        conv_hi = "conv-doc-hi-1"
        rh1 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(
                conversation_id=conv_hi,
                message="मेरे पास आवासीय भूमि कब्ज़ा प्रमाण पत्र नहीं है।",
                language="hi",
            ),
            current_user=fresh_user,
        )
        assert rh1.detected_language == "hi"
        assert "सत्यापित जानकारी" in rh1.message
        assert "अनुमानित जानकारी" in rh1.message
        assert "उपलब्ध न होने वाली जानकारी" in rh1.message

        rh2 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=conv_hi, message="इसमें कितना शुल्क लगेगा?", language="hi"),
            current_user=fresh_user,
        )
        assert rh2.detected_language == "hi"
        assert "शुल्क विवरण" in rh2.message
        assert "Verified Information" not in rh2.message

        conv_mr = "conv-doc-mr-1"
        rm1 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(
                conversation_id=conv_mr,
                message="माझ्याकडे जमीन ताबा प्रमाणपत्र नाही.",
                language="mr",
            ),
            current_user=fresh_user,
        )
        assert rm1.detected_language == "mr"
        assert "पडताळलेली माहिती" in rm1.message
        assert "अंदाजे माहिती" in rm1.message
        assert "उपलब्ध नसलेली माहिती" in rm1.message
        assert "Verified Information" not in rm1.message
    finally:
        db2.close()


def test_cross_citizen_isolation_for_document_memory(doc_db):
    """
    Ensures Citizen B using the exact same conversation_id as Citizen A does not
    inherit Citizen A's `last_discussed_document` or missing-document context.
    """
    db, _ = doc_db
    citizen_a, _ = _make_farmer(db, email="doc_a@example.gov.in")
    citizen_b = User(id=uuid.uuid4(), email="doc_b@example.gov.in", password_hash="x", is_active=True)
    db.add(citizen_b)
    db.add(
        UserProfile(
            id=uuid.uuid4(),
            user_id=citizen_b.id,
            full_name="Meera Joshi",
            age=25,
            gender="female",
            state="Maharashtra",
            district="Nagpur",
            occupation="student",
            profile_data={"documents": [], "applications": []},
        )
    )
    db.commit()

    shared_conv = "shared-doc-conv-99"
    r_a = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(
            conversation_id=shared_conv,
            message="I don't have my land possession certificate.",
            language="en",
        ),
        current_user=citizen_a,
    )
    assert "Land Title" in r_a.message

    r_b = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(
            conversation_id=shared_conv,
            message="How much will it cost?",
            language="en",
        ),
        current_user=citizen_b,
    )
    assert "Land Title" not in r_b.message
    assert "Homestead" not in r_b.message
    assert "Ramesh" not in r_b.message


def test_document_vault_upload_review_verify_updates_chat_readiness(doc_db):
    """
    Tests genuine Document Vault integration end-to-end:
    - PM-KISAN farmer missing `land_records` gets missing-doc assistance.
    - Uploading a real PNG via POST /api/v1/documents/upload leaves status = `awaiting_citizen_review`
      (NEVER `verified`), and readiness stays False.
    - POST /api/v1/documents/{id}/review sets `reviewed`, readiness STILL False.
    - POST /api/v1/documents/{id}/verify checks fields -> `verified`, and chat readiness becomes True!
    """
    db, _ = doc_db
    user, profile = _make_farmer(db, email="vault.e2e@example.gov.in")
    conv_id = "conv-vault-e2e-1"

    def _override_db():
        yield db

    def _override_user():
        return user

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_current_user] = _override_user

    try:
        # 1. Start PM-KISAN checklist and disclose missing doc
        agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_id, message="What documents are required for PM-KISAN?", language="en"),
            current_user=user,
        )
        r_missing = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_id, message="I don't have my land possession certificate.", language="en"),
            current_user=user,
        )
        assert r_missing.checklist_data["is_ready_for_application"] is False

        # 2. Citizen uploads real PNG to Vault
        client = TestClient(fastapi_app)
        up_res = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "land_records"},
            files={"file": ("7_12_extract.png", _make_valid_png_bytes(), "image/png")},
        )
        assert up_res.status_code == 201, up_res.text
        uploaded_doc = up_res.json()["data"]
        doc_id = uploaded_doc["id"]
        assert uploaded_doc["lifecycle_status"] == DOC_STATE_AWAITING_REVIEW

        # Attempting to verify BEFORE citizen review must fail
        premature_ver = client.post(f"/api/v1/documents/{doc_id}/verify")
        assert premature_ver.status_code == 422

        # Chat readiness recheck must report NOT verified yet!
        r_after_upload = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_id, message="Now I have all the documents.", language="en"),
            current_user=user,
        )
        assert "awaiting" in r_after_upload.message.lower() or "review" in r_after_upload.message.lower()
        assert "great news" not in r_after_upload.message.lower()

        # 3. Citizen completes review
        rev_res = client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={
                "confirmed_accurate": True,
                "reviewed_fields": {
                    "full_name_on_document": "Ramesh Kulkarni",
                    "document_number": "712-HVL-142B",
                    "issuing_authority": "Tahsildar Haveli, Pune",
                    "issue_date": "2026-02-15",
                },
            },
        )
        assert rev_res.status_code == 200, rev_res.text
        assert rev_res.json()["data"]["lifecycle_status"] == DOC_STATE_REVIEWED

        # 4. Deterministic verification transitions to verified
        ver_res = client.post(f"/api/v1/documents/{doc_id}/verify")
        assert ver_res.status_code == 200, ver_res.text
        assert ver_res.json()["data"]["lifecycle_status"] == DOC_STATE_VERIFIED

        # 5. Chat readiness recheck now confirms 3/3 mandatory verified!
        db.expire_all()
        user_refreshed = db.scalar(select(User).where(User.id == user.id))
        r_verified = agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_id, message="Now I have all the documents.", language="en"),
            current_user=user_refreshed,
        )
        assert r_verified.checklist_data["is_ready_for_application"] is True
        assert "3/3" in r_verified.message
    finally:
        fastapi_app.dependency_overrides.clear()
        user_dir = VAULT_STORAGE_ROOT / str(user.id)
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)


def test_gemini_function_calling_for_missing_doc_and_followup(doc_db, monkeypatch):
    """
    Verifies Gemini FunctionCall execution for `get_document_preparation_guidance`
    resolving `last_discussed_document` with explicit `focus='cost'`.
    """
    import google.generativeai as genai

    db, _ = doc_db
    user, _ = _make_farmer(db, email="gemini.doc@example.gov.in")
    conv_id = "conv-gemini-doc-1"

    # Establish last_discussed_document via missing doc disclosure
    agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="I don't have my land possession certificate.", language="en"),
        current_user=user,
    )

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaSy-test-valid-key-987654")
    monkeypatch.setattr(genai, "configure", lambda api_key=None: None)

    class FakeResponse:
        def __init__(self, parts):
            self.candidates = [types.SimpleNamespace(content=types.SimpleNamespace(parts=parts))]

    class FakeGeminiModel:
        def __init__(self, model_name=None, tools=None, system_instruction=None):
            assert "last_discussed_document" in system_instruction
            assert "Verified information" in system_instruction

        def generate_content(self, contents):
            last_fr = getattr(contents[-1].parts[0], "function_response", None)
            if not last_fr or not getattr(last_fr, "name", ""):
                return FakeResponse([
                    types.SimpleNamespace(
                        function_call=types.SimpleNamespace(
                            name="get_document_preparation_guidance",
                            args={"document_name_or_ordinal": "this document", "focus": "cost"},
                        ),
                        text="",
                    )
                ])
            assert last_fr.name == "get_document_preparation_guidance"
            return FakeResponse([
                types.SimpleNamespace(
                    function_call=None,
                    text=(
                        "**Verified information:** Viewing computerized land records online is free.\n"
                        "**Estimated information:** Typically INR 15-30 for a digitally signed extract via CSC.\n"
                        "**Information unavailable:** Exact district stamp/survey fee and local office street address."
                    ),
                )
            ])

    monkeypatch.setattr(genai, "GenerativeModel", FakeGeminiModel)

    resp = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="How much will it cost?", language="en"),
        current_user=user,
    )
    assert resp.engine_mode == "gemini_grounded"
    assert "get_document_preparation_guidance" in resp.tool_calls_used
    assert isinstance(resp.data, dict)
    assert resp.data.get("document_type") == "land_possession"
    assert "Verified information" in resp.message
    assert "Estimated information" in resp.message
    assert "Information unavailable" in resp.message

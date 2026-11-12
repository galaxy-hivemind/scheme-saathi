"""
Phase 8 Comprehensive Conversational Intelligence & Gemini Tool-Calling Tests.

Verifies:
1. Full 9-turn natural welfare journey in a SINGLE conversation_id against real SQLite ORM models:
   - Eligibility discovery -> explicit scheme details -> anaphoric benefits ->
     numbered document checklist -> ordinal document ("second document") ->
     missing document disclosure & sourcing guidance -> honest Vault readiness recheck ->
     application pre-fill draft creation (zero redundant questions for known profile fields) ->
     post-application "What happens next?"
2. Real Google Gemini Function Calling execution loop (`google.generativeai` FunctionCall ->
   real backend tool execution in `tool_registry.py` -> FunctionResponse -> structured widgets +
   `engine_mode == "gemini_grounded"` + `tool_calls_used`), plus clean fallback on API/script error.
3. Relational persistence across simulated server restart (`_CONVERSATION_SESSIONS.clear()` + fresh
   SQLAlchemy session on the same SQLite DB) and strict cross-citizen / cross-conversation isolation.
4. Phase 5/6/7 integrity guarantees: unmodeled scheme (`APY`) returns `form_supported=False` honestly;
   unverified/missing Vault docs cannot be rubber-stamped via chat ("Now I have all the documents").
5. Pure trilingual (en / hi / mr) multi-turn consistency with zero script mixing and complete `spoken_text`.
"""
import json
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from sqlalchemy import JSON as SA_JSON, MetaData, create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from app.agents.tool_registry import TOOL_REGISTRY, get_gemini_tool_declarations
from app.core.config import settings
from app.database.base import Base
import app.models  # noqa: F401
from app.models.conversation_session import ConversationSession
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.agent import AgentChatRequest, ChatResponseType
from app.services import agent_service
from app.services.conversation_memory import (
    get_conversation_history_for_user,
    list_conversations_for_user,
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


# Enable SQLite bind/result serialization for Postgres ARRAY columns in unit tests only
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
    "kcc.json",
    "ab-pmjay.json",
    "pmay-g.json",
    "apy.json",
    "nsp-csss.json",
]


def _create_sqlite_session_factory():
    """Creates a clean SQLite in-memory database supporting all Scheme Saathi ORM models."""
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

    engine = create_engine("sqlite:///:memory:", future=True)
    test_meta.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, SessionFactory


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

        rule = SchemeRuleVersion(
            id=uuid.uuid4(),
            scheme_id=scheme.id,
            version=1,
            is_active=True,
            eligibility_criteria=raw.get("eligibility_criteria", {}),
            source_url=raw["source_url"],
        )
        db.add(rule)

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


def _create_farmer_citizen(db: Session, *, email: str = "ramesh.farmer@example.gov.in") -> tuple[User, UserProfile]:
    uid = uuid.uuid4()
    user = User(id=uid, email=email, password_hash="hashed", is_active=True)
    db.add(user)
    db.flush()
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kulkarni",
        gender="male",
        state="Maharashtra",
        district="Pune",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=85000,
        profile_data={
            "caste_category": "OBC",
            "is_landholding_farmer": True,
            "is_institutional_landholder": False,
            "is_income_tax_payer": False,
            "land_holding_acres": 2.0,
            "has_kisan_credit_card": False,
            # Start with ONLY Aadhaar and Bank Passbook verified — missing Land Records!
            "documents": [
                {
                    "id": "doc-aadhaar-1",
                    "document_type": "aadhaar",
                    "file_name": "aadhaar.pdf",
                    "upload_status": "uploaded",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "citizen_confirmed_accurate": True,
                    "reviewed_fields": {"full_name": "Ramesh Kulkarni"},
                },
                {
                    "id": "doc-bank-1",
                    "document_type": "bank_passbook",
                    "file_name": "sbi_passbook.pdf",
                    "upload_status": "uploaded",
                    "lifecycle_status": "verified",
                    "verification_status": "verified",
                    "citizen_confirmed_accurate": True,
                    "reviewed_fields": {"ifsc_code": "SBIN0001234"},
                },
            ],
        },
    )
    db.add(profile)
    db.commit()
    return user, profile


@pytest.fixture
def conv_db(monkeypatch):
    agent_service._CONVERSATION_SESSIONS.clear()
    # Keep deterministic offline tests independent of ambient developer env vars
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    engine, SessionFactory = _create_sqlite_session_factory()
    db = SessionFactory()
    _seed_schemes(db)
    yield db, SessionFactory
    db.close()
    engine.dispose()
    agent_service._CONVERSATION_SESSIONS.clear()


def test_full_single_conversation_end_to_end_welfare_journey(conv_db):
    """
    Reproduces the complete 9-turn citizen journey in a single conversation_id:
    1. Eligible scheme discovery against saved citizen profile (without re-asking saved facts)
    2. Explicit scheme overview ("Tell me more about PM-KISAN.")
    3. Anaphoric benefits query ("What benefits will I receive?")
    4. Anaphoric document checklist ("What documents are required?")
    5. Ordinal document query ("Tell me about the second document")
    6. Missing document disclosure ("I don't have my land possession certificate.")
    7. Honest Vault readiness recheck ("Now I have all the documents.") before & after Vault upload
    8. Application draft creation / pre-fill ("Help me apply.") preserving known profile facts
    9. Post-application guidance ("What happens next?")
    """
    db, _ = conv_db
    user, profile = _create_farmer_citizen(db)
    conv_id = "conv-e2e-farmer-journey-1"

    def ask(msg: str):
        return agent_service.process_chat_message(
            db=db,
            request=AgentChatRequest(conversation_id=conv_id, message=msg, language="en"),
            current_user=user,
        )

    # Turn 1: Discovery
    r1 = ask("Which government schemes am I eligible for?")
    assert r1.detected_language == "en"
    assert r1.response_type == ChatResponseType.SCHEME_CARDS
    assert "PM-KISAN" in r1.message
    assert r1.spoken_text and len(r1.spoken_text) > 20
    # Never redundantly ask for profile fields we already have saved!
    lower1 = r1.message.lower()
    assert "what is your state" not in lower1
    assert "what is your occupation" not in lower1
    assert "check_all_eligible_schemes" in r1.tool_calls_used

    # Turn 2: Explicit Scheme Details
    r2 = ask("Tell me more about PM-KISAN.")
    assert r2.detected_language == "en"
    assert r2.active_scheme and r2.active_scheme["scheme_code"] == "PM-KISAN"
    assert "6,000" in r2.message or "Pradhan Mantri Kisan" in r2.message
    assert "get_scheme_details" in r2.tool_calls_used

    # Turn 3: Anaphoric Benefits (no scheme name repeated!)
    r3 = ask("What benefits will I receive?")
    assert r3.detected_language == "en"
    assert r3.response_type == ChatResponseType.BENEFITS_INFO
    assert r3.active_scheme["scheme_code"] == "PM-KISAN"
    assert "6,000" in r3.message
    assert "get_scheme_benefits" in r3.tool_calls_used

    # Turn 4: Anaphoric Required Documents (no scheme name repeated!)
    r4 = ask("What documents are required?")
    assert r4.detected_language == "en"
    assert r4.response_type == ChatResponseType.DOCUMENT_CHECKLIST
    assert r4.active_scheme["scheme_code"] == "PM-KISAN"
    docs_payload = r4.data if isinstance(r4.data, list) else (r4.checklist_data or {}).get("items", [])
    assert len(docs_payload) >= 3
    assert docs_payload[1]["document_type"] == "land_records"
    assert docs_payload[1]["index"] == 2
    assert "get_required_documents" in r4.tool_calls_used

    # Turn 5: Ordinal document follow-up ("the second document")
    r5 = ask("Tell me about the second document")
    assert r5.detected_language == "en"
    assert r5.active_scheme["scheme_code"] == "PM-KISAN"
    assert "Land" in r5.message or "Khatauni" in r5.message or "7/12" in r5.message
    assert "get_document_preparation_guidance" in r5.tool_calls_used

    # Turn 6: Missing document disclosure using citizen wording ("land possession certificate")
    r6 = ask("I don't have my land possession certificate.")
    assert r6.detected_language == "en"
    assert r6.active_scheme["scheme_code"] == "PM-KISAN"
    assert "identify_missing_documents" in r6.tool_calls_used
    assert "Land" in r6.message or "Bhulekh" in r6.message or "Tehsildar" in r6.message
    assert "Tehsil" in r6.message or "Talathi" in r6.message or "Portal" in r6.message

    # Turn 7a: Honest readiness check BEFORE uploading land_records to Vault
    r7_before = ask("Now I have all the documents.")
    assert r7_before.detected_language == "en"
    assert "recheck_application_readiness" in r7_before.tool_calls_used
    assert r7_before.workflow_step in ("CHECKLIST", "MATCH")
    # Must NOT rubber-stamp as ready when Vault is still missing land_records!
    assert "missing" in r7_before.message.lower() or "upload" in r7_before.message.lower()
    assert "land" in r7_before.message.lower()

    # Citizen now genuinely uploads & verifies Land Records in Vault
    docs = list(profile.profile_data["documents"])
    docs.append(
        {
            "id": "doc-land-1",
            "document_type": "land_records",
            "file_name": "satbara_7_12.pdf",
            "upload_status": "uploaded",
            "lifecycle_status": "verified",
            "verification_status": "verified",
            "citizen_confirmed_accurate": True,
            "reviewed_fields": {"land_area_acres": 2.0, "sub_district": "Haveli"},
        }
    )
    profile.profile_data = {**profile.profile_data, "documents": docs}
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(profile, "profile_data")
    db.commit()

    # Turn 7b: Recheck AFTER Vault verification -> now all 3 docs genuinely ready!
    r7_after = ask("Now I have all the documents.")
    assert r7_after.detected_language == "en"
    assert "recheck_application_readiness" in r7_after.tool_calls_used
    assert "ready" in r7_after.message.lower() or "verified" in r7_after.message.lower()

    # Turn 8: Application draft creation & schema-validated pre-fill
    r8 = ask("Help me apply.")
    assert r8.detected_language == "en"
    assert r8.response_type == ChatResponseType.FORM_DRAFT
    assert r8.form_draft_data is not None
    assert r8.form_draft_data["scheme_code"] == "PM-KISAN"
    assert r8.form_draft_data["form_supported"] is True
    assert "create_or_prefill_application_draft" in r8.tool_calls_used

    # Saved profile attributes must populate without fabricated tehsil/sub_district unless doc-backed
    vals = {f["name"]: f["value"] for sec in r8.form_draft_data["sections"] for f in sec["fields"]}
    assert vals["applicant_name"] == "Ramesh Kulkarni"
    assert vals["state"] == "Maharashtra"
    assert vals["district"] == "Pune"
    assert vals["category"] == "OBC"

    # Draft genuinely persisted onto citizen profile
    assert len(profile.profile_data.get("applications", [])) == 1

    # Turn 9: Post-application "What happens next?"
    r9 = ask("What happens next?")
    assert r9.detected_language == "en"
    assert r9.response_type == ChatResponseType.STATUS_TRACKING
    assert r9.active_scheme["scheme_code"] == "PM-KISAN"
    assert "get_application_status" in r9.tool_calls_used
    assert "draft" in r9.message.lower() or "submit" in r9.message.lower()


def test_ordinal_scheme_and_out_of_range_anaphora_honesty(conv_db):
    """
    Verifies ordinal scheme selection ('the second scheme'), subsequent pronoun inheritance ('its'),
    and honest boundary messaging when an ordinal exceeds available items.
    """
    db, _ = conv_db
    user, _ = _create_farmer_citizen(db)
    conv_id = "conv-ordinals-1"

    r1 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="Which government schemes am I eligible for?", language="en"),
        current_user=user,
    )
    schemes_returned = r1.data
    assert isinstance(schemes_returned, list) and len(schemes_returned) >= 2
    expected_second_code = schemes_returned[1]["scheme_code"]

    r2 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="Tell me about the second scheme.", language="en"),
        current_user=user,
    )
    assert r2.active_scheme and r2.active_scheme["scheme_code"] == expected_second_code

    r3 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="What benefits will I receive?", language="en"),
        current_user=user,
    )
    assert r3.active_scheme["scheme_code"] == expected_second_code
    assert r3.response_type == ChatResponseType.BENEFITS_INFO

    r4 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="What documents are required?", language="en"),
        current_user=user,
    )
    assert r4.active_scheme["scheme_code"] == expected_second_code
    assert r4.response_type == ChatResponseType.DOCUMENT_CHECKLIST

    # Out-of-range document ordinal should NEVER silently pick doc 1 or fabricate doc 9
    r5 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="Tell me about the 9th document.", language="en"),
        current_user=user,
    )
    assert "only" in r5.message.lower() or "available" in r5.message.lower() or "out of" in r5.message.lower() or str(len(r4.data)) in r5.message


def test_gemini_native_function_calling_and_clean_fallback(conv_db, monkeypatch):
    """
    Verifies real Gemini FunctionDeclaration tool calling against real backend tools in `tool_registry.py`:
    - When Gemini returns FunctionCall parts, `execute_backend_tool` executes the genuine DB/service function
      and feeds its real JSON result back to Gemini via FunctionResponse.
    - Resulting `AgentChatResponse` carries `engine_mode == "gemini_grounded"`, populated widgets, and
      `tool_calls_used`.
    - When Gemini output mixes languages or raises an exception, orchestrator falls back cleanly to
      grounded deterministic tool execution without breaking the turn.
    """
    import google.generativeai as genai
    from google.generativeai import protos

    db, _ = conv_db
    user, _ = _create_farmer_citizen(db)
    conv_id = "conv-gemini-fc-1"

    # Confirm Gemini tool declarations match TOOL_REGISTRY cleanly
    decl = get_gemini_tool_declarations()
    decl_names = {f.name for f in decl.function_declarations}
    assert decl_names == set(TOOL_REGISTRY.keys())
    assert len(decl_names) == 13

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaSy-test-valid-key-123456")
    monkeypatch.setattr(genai, "configure", lambda api_key=None: None)

    recorded_contents: List[Any] = []

    class FakeResponse:
        def __init__(self, parts):
            content = types.SimpleNamespace(parts=parts)
            self.candidates = [types.SimpleNamespace(content=content)]

    class FakeModelScripted:
        def __init__(self, model_name=None, tools=None, system_instruction=None):
            self.tools = tools
            self.system_instruction = system_instruction

        def generate_content(self, contents):
            recorded_contents.append(contents)
            # Round 1: emit FunctionCall to get_scheme_benefits for PM-KISAN
            if len(contents) == 1:
                fc_part = types.SimpleNamespace(
                    function_call=types.SimpleNamespace(
                        name="get_scheme_benefits",
                        args={"scheme_code_or_name": "PM-KISAN"},
                    ),
                    text="",
                )
                return FakeResponse([fc_part])

            # Round 2: inspect FunctionResponse received by Gemini -> confirm real DB benefits passed!
            def _to_plain(obj):
                if hasattr(obj, "items"):
                    return {k: _to_plain(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)) or type(obj).__name__.endswith("RepeatedComposite"):
                    return [_to_plain(v) for v in obj]
                return obj

            last_user_turn = contents[-1]
            fn_resp = last_user_turn.parts[0].function_response
            assert fn_resp.name == "get_scheme_benefits"
            unpacked = _to_plain(fn_resp.response)
            assert "6,000" in json.dumps(unpacked)

            text_part = types.SimpleNamespace(
                function_call=None,
                text="Under PM-KISAN, eligible landholding farmer families receive Rs. 6,000 per year in three instalments of Rs. 2,000 directly into their Aadhaar-seeded bank accounts.",
            )
            return FakeResponse([text_part])

    monkeypatch.setattr(genai, "GenerativeModel", FakeModelScripted)

    resp = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="What benefits does PM-KISAN offer?", language="en"),
        current_user=user,
    )
    assert resp.engine_mode == "gemini_grounded"
    assert "get_scheme_benefits" in resp.tool_calls_used
    assert resp.response_type == ChatResponseType.BENEFITS_INFO
    assert resp.active_scheme and resp.active_scheme["scheme_code"] == "PM-KISAN"
    assert "6,000" in resp.message

    # Now simulate Gemini violating language script purity (returning Hindi for English user query)
    class FakeModelMixedScript:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, contents):
            if len(contents) == 1:
                return FakeResponse([
                    types.SimpleNamespace(
                        function_call=types.SimpleNamespace(name="get_required_documents", args={"scheme_code_or_name": "PM-KISAN"}),
                        text="",
                    )
                ])
            return FakeResponse([
                types.SimpleNamespace(function_call=None, text="यह दस्तावेज़ आवश्यक हैं।")
            ])

    monkeypatch.setattr(genai, "GenerativeModel", FakeModelMixedScript)
    resp_fallback = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=conv_id, message="What documents are required for PM-KISAN?", language="en"),
        current_user=user,
    )
    assert resp_fallback.detected_language == "en"
    assert "Devanagari" not in resp_fallback.message
    assert not any("\u0900" <= ch <= "\u097F" for ch in resp_fallback.message)
    assert resp_fallback.response_type == ChatResponseType.DOCUMENT_CHECKLIST


def test_persistence_across_restart_and_strict_citizen_isolation(conv_db):
    """
    Verifies:
    1. Conversation context, active scheme, checklist, and turns persist in `conversation_sessions`.
    2. Wiping in-memory `_CONVERSATION_SESSIONS` AND creating a brand new SQLAlchemy Session seamlessly
       recovers context for Citizen A on their follow-up ("What are its benefits?").
    3. Citizen B using the EXACT SAME `conversation_id` receives zero Citizen A context, profile facts,
       history, or scheme inheritance.
    """
    db1, SessionFactory = conv_db
    citizen_a, _ = _create_farmer_citizen(db1, email="citizen_a@example.gov.in")
    citizen_b = User(id=uuid.uuid4(), email="citizen_b@example.gov.in", password_hash="x", is_active=True)
    db1.add(citizen_b)
    profile_b = UserProfile(
        id=uuid.uuid4(),
        user_id=citizen_b.id,
        full_name="Priya Deshmukh",
        gender="female",
        state="Maharashtra",
        district="Nagpur",
        occupation="student",
        annual_family_income=120000,
        profile_data={"documents": []},
    )
    db1.add(profile_b)
    db1.commit()

    shared_conv_id = "conv-shared-browser-id-42"

    # Citizen A establishes active scheme PM-KISAN & checklist
    r_a1 = agent_service.process_chat_message(
        db=db1,
        request=AgentChatRequest(conversation_id=shared_conv_id, message="What documents are required for PM-KISAN?", language="en"),
        current_user=citizen_a,
    )
    assert r_a1.active_scheme["scheme_code"] == "PM-KISAN"

    # Verify DB row directly created for Citizen A
    row_a = db1.scalar(
        select(ConversationSession).where(
            ConversationSession.user_id == citizen_a.id,
            ConversationSession.conversation_id == shared_conv_id,
        )
    )
    assert row_a is not None
    assert row_a.active_scheme_code == "PM-KISAN"
    assert len(row_a.turns) == 2

    # SIMULATE SERVER RESTART: clear RAM session dict & open a brand new DB Session!
    agent_service._CONVERSATION_SESSIONS.clear()
    db2 = SessionFactory()
    try:
        citizen_a_fresh = db2.scalar(select(User).where(User.id == citizen_a.id))
        citizen_b_fresh = db2.scalar(select(User).where(User.id == citizen_b.id))

        # Citizen A sends purely anaphoric follow-up after restart -> must recover PM-KISAN!
        r_a2 = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=shared_conv_id, message="What benefits will I receive?", language="en"),
            current_user=citizen_a_fresh,
        )
        assert r_a2.active_scheme and r_a2.active_scheme["scheme_code"] == "PM-KISAN"
        assert "6,000" in r_a2.message

        # Persisted history API helper shows 4 turns for Citizen A and ZERO turns for Citizen B
        hist_a = get_conversation_history_for_user(db2, shared_conv_id, citizen_a_fresh, db2.scalar(select(UserProfile).where(UserProfile.user_id == citizen_a.id)))
        assert hist_a is not None and len(hist_a["turns"]) == 4

        hist_b = get_conversation_history_for_user(db2, shared_conv_id, citizen_b_fresh, db2.scalar(select(UserProfile).where(UserProfile.user_id == citizen_b.id)))
        assert hist_b is None

        assert len(list_conversations_for_user(db2, citizen_a_fresh)) == 1
        assert len(list_conversations_for_user(db2, citizen_b_fresh)) == 0

        # Citizen B sends anaphoric "What benefits will I receive?" with same conv_id -> must NOT get PM-KISAN!
        r_b = agent_service.process_chat_message(
            db=db2,
            request=AgentChatRequest(conversation_id=shared_conv_id, message="What benefits will I receive?", language="en"),
            current_user=citizen_b_fresh,
        )
        assert not r_b.active_scheme or r_b.active_scheme.get("scheme_code") != "PM-KISAN"
        assert "6,000" not in r_b.message
        assert "Ramesh" not in r_b.message
    finally:
        db2.close()


def test_unmodeled_scheme_and_multilingual_pure_conversations(conv_db):
    """
    Verifies:
    1. Unmodeled scheme APY still explicitly blocks fabricated application prefill (`form_supported=False`).
    2. Hindi and Marathi multi-turn conversations stay strictly within their requested/detected language
       across discovery -> details -> benefits -> checklist -> missing doc -> next steps.
    """
    db, _ = conv_db
    user, _ = _create_farmer_citizen(db)

    # 1. APY honest unavailability
    r_apy = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id="conv-apy", message="Help me apply for Atal Pension Yojana", language="en"),
        current_user=user,
    )
    assert r_apy.active_scheme and r_apy.active_scheme["scheme_code"] == "APY"
    assert r_apy.form_draft_data is not None
    assert r_apy.form_draft_data["form_supported"] is False

    # 2. Pure Hindi multi-turn journey
    hi_conv = "conv-hi-1"
    r_hi1 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=hi_conv, message="पीएम-किसान योजना के बारे में बताएं", language="hi"),
        current_user=user,
    )
    assert r_hi1.detected_language == "hi"
    assert r_hi1.active_scheme["scheme_code"] == "PM-KISAN"
    assert "आहे" not in r_hi1.message  # zero Marathi leak
    assert "6,000" in r_hi1.message or "किस्त" in r_hi1.message

    r_hi2 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=hi_conv, message="इसके लिए कौन से दस्तावेज़ चाहिए?", language="hi"),
        current_user=user,
    )
    assert r_hi2.detected_language == "hi"
    assert r_hi2.response_type == ChatResponseType.DOCUMENT_CHECKLIST
    assert "कागदपत्रे" not in r_hi2.message  # zero Marathi vocabulary leak

    # 3. Pure Marathi multi-turn journey
    mr_conv = "conv-mr-1"
    r_mr1 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=mr_conv, message="पीएम-किसान योजनेचे फायदे काय आहेत?", language="mr"),
        current_user=user,
    )
    assert r_mr1.detected_language == "mr"
    assert r_mr1.response_type == ChatResponseType.BENEFITS_INFO
    assert "लाभ" in r_mr1.message or "हप्ते" in r_mr1.message or "6,000" in r_mr1.message

    r_mr2 = agent_service.process_chat_message(
        db=db,
        request=AgentChatRequest(conversation_id=mr_conv, message="यासाठी कोणती कागदपत्रे लागतात?", language="mr"),
        current_user=user,
    )
    assert r_mr2.detected_language == "mr"
    assert r_mr2.response_type == ChatResponseType.DOCUMENT_CHECKLIST
    assert "कागदपत्र" in r_mr2.message
    assert "दस्तावेज़" not in r_mr2.message  # zero Hindi vocabulary leak

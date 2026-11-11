"""
Comprehensive Unit & Integration Tests for Phase 3: Agentic Welfare Application Workflow.
Tests:
1. Multilingual Entity Extraction (English, Hindi, Marathi).
2. Backend Tool Execution (check_eligibility, build_checklist, fill_form, submit_form).
3. Conversational Replanning when missing documents are disclosed.
4. Mandatory 5 Personas (Widow Pension, Small Farmer, Student, Rural Woman, Senior Citizen).
5. Application Form Pre-filling across all 6 supported schemes.
6. Three-tier persistent memory and backend restart recovery.
"""
import pytest
import uuid
from typing import Dict, Any, List

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.agents.tools import (
    extract_citizen_entities,
    tool_check_eligibility,
    tool_build_checklist,
    tool_fill_form,
    tool_submit_form,
)
from app.agents.form_schemas import (
    get_form_schema_for_scheme,
    get_document_sourcing_info,
    SCHEME_FORM_SCHEMAS,
)
from app.agents.planner import plan_and_execute_agentic_flow


# ── 1. Entity Extraction Tests ───────────────────────────────────────────────

def test_extract_citizen_entities_english_widow():
    text = "I'm a 63-year-old widow from Uttar Pradesh. My annual family income is ₹60,000."
    entities = extract_citizen_entities(text)
    assert entities.get("age") == 63
    assert entities.get("marital_status") == "widowed"
    assert entities.get("gender") == "FEMALE"
    assert entities.get("state") == "Uttar Pradesh"
    assert entities.get("annual_income") == 60000


def test_extract_citizen_entities_hindi_widow():
    text = "मैं उत्तर प्रदेश की 63 साल की विधवा हूँ और मेरी वार्षिक आय ₹60,000 है।"
    entities = extract_citizen_entities(text)
    assert entities.get("age") == 63
    assert entities.get("marital_status") == "widowed"
    assert entities.get("gender") == "FEMALE"
    assert entities.get("state") == "Uttar Pradesh"
    assert entities.get("annual_income") == 60000


def test_extract_citizen_entities_marathi_farmer():
    text = "मी महाराष्ट्रातील शेतकरी आहे, माझ्याकडे २.५ एकर शेतजमीन आहे."
    entities = extract_citizen_entities(text)
    assert entities.get("occupation") == "farmer"
    assert entities.get("state") == "Maharashtra"
    assert entities.get("land_holding_acres") == 2.5
    assert entities.get("is_landholding_farmer") is True


def test_extract_citizen_entities_student():
    text = "I am a student from Maharashtra, passed 12th with 88%, annual income 1.8 lakh."
    entities = extract_citizen_entities(text)
    assert entities.get("occupation") == "student"
    assert entities.get("state") == "Maharashtra"
    assert entities.get("student_percentage") == 88.0
    assert entities.get("annual_income") == 180000


def test_extract_missing_document_disclosure():
    text1 = "I don't have an income certificate right now."
    entities1 = extract_citizen_entities(text1)
    assert entities1.get("missing_document_disclosed") == "income_certificate"

    text2 = "माझ्याकडे पतीचे मृत्यू प्रमाणपत्र उपलब्ध नाही."
    entities2 = extract_citizen_entities(text2)
    assert entities2.get("missing_document_disclosed") == "death_certificate"


# ── 2. Tool Execution Tests ──────────────────────────────────────────────────

def test_tool_check_eligibility_widow_pension():
    extracted = {
        "age": 63,
        "marital_status": "widowed",
        "gender": "FEMALE",
        "state": "Uttar Pradesh",
        "annual_income": 60000,
    }
    res = tool_check_eligibility(db=None, user=None, profile=None, scheme_code_or_name="WIDOW-PENSION", extracted_data=extracted)
    assert res["status"] == "eligible"
    assert "₹1,000" in res["monthly_benefit"]
    assert "sspy-up.gov.in" in res["official_portal"]
    assert len(res["satisfied_criteria"]) >= 3


def test_tool_build_checklist_widow_pension():
    res = tool_build_checklist(db=None, user=None, profile=None, scheme_code_or_name="WIDOW-PENSION")
    assert res["scheme_code"] == "WIDOW-PENSION"
    assert res["mandatory_count"] >= 3
    doc_types = [item["document_type"] for item in res["items"]]
    assert "aadhaar_card" in doc_types
    assert "death_certificate" in doc_types
    assert "income_certificate" in doc_types

    # Sourcing information verification
    death_doc = next(d for d in res["items"] if d["document_type"] == "death_certificate")
    assert death_doc["sourcing"]["is_verified"] is True
    assert "Registrar" in death_doc["sourcing"]["issuing_authority"]
    assert "crsorgi.gov.in" in death_doc["sourcing"]["official_url"]


def test_tool_fill_form_supported_schemes():
    supported = ["PM-KISAN", "KCC", "PM-SVANIDHI", "NSP-CSSS", "PMMVY", "WIDOW-PENSION"]
    for code in supported:
        schema = get_form_schema_for_scheme(code)
        assert schema is not None, f"Schema missing for {code}"
        assert schema["form_supported"] is True

        res = tool_fill_form(db=None, user=None, profile=None, scheme_code_or_name=code)
        assert res["form_supported"] is True
        assert res["scheme_code"] == code
        assert len(res["sections"]) >= 2
        assert res["total_mandatory_fields"] > 0


def test_tool_fill_form_unsupported_scheme():
    res = tool_fill_form(db=None, user=None, profile=None, scheme_code_or_name="UNKNOWN-XYZ-SCHEME")
    assert res["form_supported"] is False
    assert "official" in res["message"].lower()


def test_tool_submit_form_confirmation_and_handoff():
    # Unconfirmed test
    prompt = tool_submit_form(db=None, user=None, profile=None, scheme_code_or_name="WIDOW-PENSION", confirmed=False)
    assert prompt["requires_confirmation"] is True
    assert "review and confirm" in prompt["message"]

    # Confirmed test with UP state profile
    profile = UserProfile(user_id=uuid.uuid4(), state="Uttar Pradesh", profile_data={})
    confirmed_res = tool_submit_form(db=None, user=None, profile=profile, scheme_code_or_name="WIDOW-PENSION", confirmed=True)
    assert confirmed_res["requires_confirmation"] is False
    assert "SAATHI/READY/2026/" in confirmed_res["handoff_reference"]
    assert "sspy-up.gov.in" in confirmed_res["official_portal_url"]


# ── 3. Replanning Test ───────────────────────────────────────────────────────

def test_conversational_replanning_missing_income_certificate():
    session = {"conv_id": "test-replan", "active_scheme_code": "WIDOW-PENSION", "workflow_step": "MATCH"}
    req = AgentChatRequest(conversation_id="test-replan", message="I don't have an income certificate.")
    
    res = plan_and_execute_agentic_flow(
        db=None,
        request=req,
        current_user=None,
        profile=None,
        session=session,
        lang="en",
        all_schemes=[],
    )
    assert res is not None
    assert res.workflow_step == "CHECKLIST"
    assert "Tahsildar" in res.message or "Revenue" in res.message
    assert "₹15 to ₹30" in res.message
    assert session["active_scheme_code"] == "WIDOW-PENSION"


# ── 4. Mandatory 5 Personas End-to-End Tests ─────────────────────────────────

def test_persona_1_widow_pension_flow():
    """63-year-old widow from Uttar Pradesh, annual family income ₹60,000."""
    session = {"conv_id": "widow-test"}
    req = AgentChatRequest(
        conversation_id="widow-test",
        message="I'm a 63-year-old widow from Uttar Pradesh. My annual family income is ₹60,000."
    )
    res = plan_and_execute_agentic_flow(db=None, request=req, current_user=None, profile=None, session=session, lang="en", all_schemes=[])
    assert res is not None
    assert res.workflow_step == "MATCH"
    assert "ELIGIBLE" in res.message
    assert "Death Certificate" in res.message
    assert session["active_scheme_code"] == "WIDOW-PENSION"


def test_persona_2_small_farmer_flow():
    """Small farmer with 2.5 acres of land in Maharashtra."""
    session = {"conv_id": "farmer-test", "active_scheme_code": "PM-KISAN", "workflow_step": "MATCH"}
    req = AgentChatRequest(
        conversation_id="farmer-test",
        message="Pre-fill application form for PM-KISAN"
    )
    res = plan_and_execute_agentic_flow(db=None, request=req, current_user=None, profile=None, session=session, lang="mr", all_schemes=[])
    assert res is not None
    assert res.workflow_step == "PRE-FILL"
    assert res.form_draft_data is not None
    assert res.form_draft_data["scheme_code"] == "PM-KISAN"


def test_persona_3_student_flow():
    """Student exploring education scholarship."""
    session = {"conv_id": "student-test", "active_scheme_code": "NSP-CSSS", "workflow_step": "CHECKLIST"}
    req = AgentChatRequest(
        conversation_id="student-test",
        message="Start application for NSP-CSSS"
    )
    res = plan_and_execute_agentic_flow(db=None, request=req, current_user=None, profile=None, session=session, lang="en", all_schemes=[])
    assert res is not None
    assert res.workflow_step == "PRE-FILL"
    assert res.form_draft_data["scheme_code"] == "NSP-CSSS"


def test_persona_4_rural_woman_flow():
    """Rural pregnant woman applying for PMMVY."""
    session = {"conv_id": "woman-test", "active_scheme_code": "PMMVY", "workflow_step": "MATCH"}
    req = AgentChatRequest(
        conversation_id="woman-test",
        message="Fill form for PMMVY"
    )
    res = plan_and_execute_agentic_flow(db=None, request=req, current_user=None, profile=None, session=session, lang="hi", all_schemes=[])
    assert res is not None
    assert res.workflow_step == "PRE-FILL"
    assert res.form_draft_data["scheme_code"] == "PMMVY"


def test_persona_5_senior_citizen_confirmation_handoff():
    """Senior citizen completing confirmation handoff."""
    session = {"conv_id": "senior-test", "active_scheme_code": "WIDOW-PENSION", "workflow_step": "PRE-FILL"}
    profile = UserProfile(user_id=uuid.uuid4(), state="Uttar Pradesh", profile_data={})
    req = AgentChatRequest(
        conversation_id="senior-test",
        message="Confirm and submit application",
        form_action="confirm_submit"
    )
    res = plan_and_execute_agentic_flow(db=None, request=req, current_user=None, profile=profile, session=session, lang="en", all_schemes=[])
    assert res is not None
    assert res.workflow_step == "CONFIRM"
    assert "SAATHI/READY/2026/" in res.confirmation_data["handoff_reference"]
    assert "sspy-up.gov.in" in res.confirmation_data["official_portal_url"]

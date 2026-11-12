"""
Phase 6 Comprehensive Tests: Universal Multi-Scheme Application Pre-Fill Engine.

Verifies:
1. PM-KISAN complete 15-field (14 mandatory) audit: partial profile (6/14), verified docs + conversation
   enrichment (13/14), no district->sub_district fabrication, no unsafe 'Single' default.
2. All 10 structured schemas via unified prefill_service (REST & Agent parity).
3. Strict Schema Integrity across all 22 unavailable seeded schemes (including APY):
   - form_supported=False, schema_available=False, sections=[], official portal preserved.
   - Zero fake 5-field or 1-field fallback in /applications/schema or readiness evaluation.
   - Eligibility & document checklists stay distinct from application form readiness.
4. Data Integrity & Provenance:
   - Unverified extracted OCR NEVER auto-populates form fields or self-verifies documents.
   - Citizen-confirmed ('reviewed') documents retain unverified document status cleanly.
   - Unsafe defaults removed from PM-KISAN, KCC, PM-SVANIDHI, NSP-CSSS, PMMVY.
   - Select option casing ('male'->'MALE', 'obc'->'OBC'), date/number normalization, format validation.
5. Conflict Detection: cross-source mismatches flagged in en/hi/mr and never silently overwritten;
   explicit citizen resolution clears conflict cleanly.
6. Citizen Isolation: cross-user access rejected and foreign user_id records excluded.
7. Chat planner confirmation gate preserves Phase 5 readiness checks cleanly.
"""
import json
import uuid
from pathlib import Path
import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.agents.form_schemas import SCHEME_FORM_SCHEMAS, get_form_schema_for_scheme
from app.agents.tools import extract_citizen_entities, tool_fill_form
from app.agents.planner import plan_and_execute_agentic_flow
from app.schemas.agent import AgentChatRequest, ChatResponseType
from app.services.prefill_service import (
    SOURCE_CONVERSATION,
    SOURCE_PROFILE,
    SOURCE_SYSTEM_DEFAULT,
    SOURCE_VERIFIED_DOC,
    run_universal_prefill,
)
from app.services.readiness_service import evaluate_application_readiness
from app.api.v1.applications import (
    get_scheme_schema,
    create_application_draft,
    update_application_draft,
    validate_application_draft,
    confirm_application,
    CreateDraftRequest,
    UpdateDraftRequest,
)
from tests.unit.test_documents_and_applications import MockSession


SCHEME_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"


def test_pm_kisan_14_mandatory_fields_partial_vs_verified_sources():
    """
    Reproduces why PM-KISAN previously populated only 6/14 fields and verifies the
    universal engine fills 6/14 cleanly from partial profile, then 13/14 cleanly once
    verified documents and conversation entities are supplied—without ever inventing
    sub_district or land_ownership_type.
    """
    uid = uuid.uuid4()
    user = User(id=uid, email="farmer@example.com")
    partial_profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kumar",
        gender="male",  # lowercase must normalize cleanly to 'MALE'
        state="Uttar Pradesh",
        district="Varanasi",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=85000,
        profile_data={
            "caste_category": "obc",  # lowercase must normalize cleanly to 'OBC'
            "land_holding_acres": 1.5,
        },
    )

    # Phase A: Baseline profile only (NO district->sub_district fabrication, NO unsafe 'Single' default)
    res_partial = run_universal_prefill("PM-KISAN", partial_profile, user=user, lang="en")
    assert res_partial["form_supported"] is True
    assert res_partial["total_fields"] == 15
    assert res_partial["total_mandatory_fields"] == 14
    assert res_partial["filled_mandatory_fields"] == 6
    assert res_partial["values"]["applicant_name"] == "Ramesh Kumar"
    assert res_partial["values"]["gender"] == "MALE"
    assert res_partial["values"]["category"] == "OBC"
    assert res_partial["values"]["state"] == "Uttar Pradesh"
    assert res_partial["values"]["district"] == "Varanasi"
    assert res_partial["values"]["land_area_acres"] == 1.5
    # Strict non-fabrication assertions
    assert res_partial["values"]["sub_district_block"] is None
    assert res_partial["values"]["land_ownership_type"] is None
    assert res_partial["values"]["village"] is None

    # Phase B: Enrich with Verified Vault Documents + Conversation Entities -> 13/14 auto-filled
    partial_profile.profile_data["documents"] = [
        {
            "id": "v-aadhaar",
            "user_id": str(uid),
            "document_type": "aadhaar_card",
            "lifecycle_status": "verified",
            "reviewed_fields": {
                "holder_name": "Ramesh Kumar",
                "document_number": "234567890123",
            },
        },
        {
            "id": "v-bank",
            "user_id": str(uid),
            "document_type": "bank_passbook",
            "lifecycle_status": "verified",
            "reviewed_fields": {
                "holder_name": "Ramesh Kumar",
                "document_number": "123456789012",
                "ifsc_code": "SBIN0001234",
            },
        },
        {
            "id": "v-land",
            "user_id": str(uid),
            "document_type": "land_records",
            "lifecycle_status": "verified",
            "reviewed_fields": {
                "khasra_number": "104/2",
                "registration_date": "15/06/2020",
            },
        },
    ]

    conv_text = "My mobile number is 9876543210, tehsil Pindra, village Shivpur."
    conv_entities = extract_citizen_entities(conv_text)
    assert conv_entities["phone_number"] == "9876543210"
    assert conv_entities["sub_district"] == "Pindra"
    assert conv_entities["village"] == "Shivpur"

    res_enriched = run_universal_prefill(
        "PM-KISAN",
        partial_profile,
        user=user,
        conversation_entities=conv_entities,
        lang="en",
    )
    assert res_enriched["filled_mandatory_fields"] == 13
    assert res_enriched["auto_populated_fields"] == 14  # 13 mandatory + 1 optional land_transfer_date
    assert res_enriched["prefill_percentage"] == 92.9
    assert res_enriched["values"]["aadhaar_number"] == "234567890123"
    assert res_enriched["values"]["bank_account_number"] == "123456789012"
    assert res_enriched["values"]["ifsc_code"] == "SBIN0001234"
    assert res_enriched["values"]["khasra_khatauni_no"] == "104/2"
    assert res_enriched["values"]["land_transfer_date"] == "2020-06-15"  # Normalized DD/MM/YYYY -> YYYY-MM-DD
    assert res_enriched["values"]["sub_district_block"] == "Pindra"
    assert res_enriched["values"]["village"] == "Shivpur"
    assert res_enriched["values"]["mobile_number"] == "9876543210"
    assert res_enriched["values"]["land_ownership_type"] is None  # Still requires citizen input!

    # Check source provenance labels cleanly
    all_fields = {f["name"]: f for s in res_enriched["sections"] for f in s["fields"]}
    assert all_fields["aadhaar_number"]["source_tier"] == SOURCE_VERIFIED_DOC
    assert all_fields["applicant_name"]["source_tier"] == SOURCE_VERIFIED_DOC  # Verified doc outweighs profile when agreeing
    assert all_fields["gender"]["source_tier"] == SOURCE_PROFILE
    assert all_fields["sub_district_block"]["source_tier"] == SOURCE_CONVERSATION
    assert all_fields["land_ownership_type"]["requires_input"] is True


def test_all_10_structured_schemes_universal_engine():
    """Verify every modeled scheme produces valid counts, no fabricated sub_district/defaults, and respects conditionals."""
    uid = uuid.uuid4()
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Sunita Devi",
        gender="female",
        state="Maharashtra",
        district="Pune",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=110000,
        profile_data={
            "phone_number": "9822334455",
            "aadhaar_number": "345678901234",
            "bank_account_number": "998877665544",
            "bank_ifsc": "MAHB0001234",
            "caste_category": "sc",
            "marital_status": "widowed",
            "sub_district": "Baramati",
            "village": "Malegaon",
            "land_holding_acres": 2.0,
            "khasra_number": "88/1",
            "student_percentage": 89.2,
        },
    )
    profile.age = 35

    for scheme_code in SCHEME_FORM_SCHEMAS:
        res = run_universal_prefill(scheme_code, profile, lang="en")
        assert res["form_supported"] is True
        assert res["schema_available"] is True
        assert res["total_fields"] >= res["total_mandatory_fields"] > 0
        assert 0.0 <= res["prefill_percentage"] <= 100.0
        if scheme_code == "PMAY-G":
            assert "mgnrega_job_card_number" in res["conditional_fields"]
            all_f = {f["name"]: f for s in res["sections"] for f in s["fields"]}
            assert all_f["ifsc_code"]["value"] == "MAHB0001234"  # alias bank_ifsc <-> ifsc_code
        if scheme_code == "AB-PMJAY":
            all_f = {f["name"]: f for s in res["sections"] for f in s["fields"]}
            assert all_f["ekyc_mode"]["source_tier"] == SOURCE_SYSTEM_DEFAULT
            assert "ration_card_number" in res["conditional_fields"]


def test_unsafe_personal_defaults_removed_across_older_schemas():
    """Ensure personal facts are never silently defaulted in PM-KISAN, KCC, PM-SVANIDHI, NSP-CSSS, or PMMVY."""
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), full_name="Test Citizen Name", profile_data={})

    kisan = run_universal_prefill("PM-KISAN", profile)
    assert kisan["values"]["land_ownership_type"] is None

    kcc = run_universal_prefill("KCC", profile)
    assert kcc["values"]["farming_type"] is None
    assert kcc["values"]["existing_outstanding_debt"] is None

    svanidhi = run_universal_prefill("PM-SVANIDHI", profile)
    assert svanidhi["values"]["loan_tranche"] is None
    assert svanidhi["values"]["requested_amount"] is None

    nsp = run_universal_prefill("NSP-CSSS", profile)
    assert nsp["values"]["class_12_passing_year"] is None

    pmmvy = run_universal_prefill("PMMVY", profile)
    assert pmmvy["values"]["child_order"] is None


def test_all_22_unavailable_schemes_including_apy_remain_explicitly_blocked():
    """
    Option A Strict Schema Integrity:
    Every seeded scheme lacking a verified application schema (all 22 including APY) must
    explicitly return form_supported=False, schema_available=False, sections=[], never generate
    a fake 5-field generic form, and never pass readiness checks as 100% complete.
    """
    uid = uuid.uuid4()
    user = User(id=uid, email="citizen@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Asha Kulkarni",
        age=28,
        gender="female",
        state="Maharashtra",
        district="Pune",
        residence_type="urban",
        occupation="self_employed",
        annual_family_income=120000,
        profile_data={},
    )

    unavailable_codes = []
    for fp in sorted(SCHEME_DIR.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        code = data["scheme_code"]
        if code not in SCHEME_FORM_SCHEMAS:
            unavailable_codes.append(code)

    assert "APY" in unavailable_codes
    assert len(unavailable_codes) == 22

    for code in unavailable_codes:
        assert get_form_schema_for_scheme(code) is None, f"Unexpected schema matched for {code}"

        # 1. Universal prefill + tool_fill_form
        pf = tool_fill_form(db=None, user=user, profile=profile, scheme_code_or_name=code, lang="en")
        assert pf["form_supported"] is False
        assert pf["schema_available"] is False
        assert pf["sections"] == []
        if code == "APY":
            assert "pfrda" in pf["official_portal"].lower() or "enps" in pf["official_portal"].lower()

        # 2. REST /applications/schema/{code}
        apy_scheme = Scheme(
            id=uuid.uuid4(),
            scheme_code=code,
            name=f"{code} Test Name",
            description="desc",
            category="social_security",
            geographic_scope="central",
            official_url="https://www.pfrda.org.in/",
        )
        db = MockSession(profile=profile, scheme=apy_scheme)
        schema_res = get_scheme_schema(code, lang="hi", current_user=user, db=db)
        assert schema_res.data["form_supported"] is False
        assert schema_res.data["schema_available"] is False
        assert schema_res.data["sections"] == []

        # 3. Readiness gate never pretends 100% for unmodeled schemes
        readiness = evaluate_application_readiness(
            scheme_code=code,
            scheme_id=code,
            form_data={"applicant_name": "Asha Kulkarni"},
            profile=profile,
            db=None,
            lang="mr",
        )
        assert readiness["passed"] is False
        assert readiness["breakdown"]["form"]["schema_available"] is False
        assert readiness["breakdown"]["form"]["percentage"] == 0.0


def test_unverified_ocr_never_auto_populates_and_never_self_verifies():
    """Uploading an unreviewed document with OCR extracted fields must not auto-fill or self-verify."""
    uid = uuid.uuid4()
    doc = {
        "id": "doc-ocr-1",
        "user_id": str(uid),
        "document_type": "aadhaar_card",
        "upload_status": "uploaded",
        "ocr_status": "completed",
        "lifecycle_status": "extracted",
        "review_status": "pending_review",
        "citizen_confirmed_accurate": False,
        "extracted_fields": {"document_number": "234567890123", "holder_name": "Ramesh Kumar"},
    }
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kumar",
        profile_data={"documents": [doc]},
    )

    res = run_universal_prefill("PM-KISAN", profile, lang="en")
    assert res["values"]["aadhaar_number"] is None  # NEVER auto-populated from unverified OCR
    assert doc["lifecycle_status"] == "extracted"   # Document remains unverified
    all_f = {f["name"]: f for s in res["sections"] for f in s["fields"]}
    assert all_f["aadhaar_number"]["unverified_ocr_hint"]["suggested_value"] == "234567890123"


def test_conflict_detection_blocks_silent_overwrite_and_allows_explicit_resolution():
    """
    When profile data and verified document disagree (e.g. different Aadhaar numbers),
    universal engine flags conflict visibly, blocks readiness confirmation, and honors explicit choice.
    """
    uid = uuid.uuid4()
    user = User(id=uid, email="conflict@example.com")
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uid,
        full_name="Ramesh Kumar",
        age=42,
        gender="male",
        state="Uttar Pradesh",
        district="Varanasi",
        residence_type="rural",
        occupation="farmer",
        annual_family_income=90000,
        profile_data={
            "aadhaar_number": "726726378736",
            "phone_number": "9876543210",
            "caste_category": "OBC",
            "sub_district": "Pindra",
            "village": "Shivpur",
            "khasra_number": "104/2",
            "land_holding_acres": 1.5,
            "bank_account_number": "123456789012",
            "bank_ifsc": "SBIN0001234",
            "land_ownership_type": "Single",
            "documents": [
                {
                    "id": "doc-a1",
                    "user_id": str(uid),
                    "document_type": "aadhaar_card",
                    "lifecycle_status": "verified",
                    "reviewed_fields": {"holder_name": "Ramesh Kumar", "document_number": "234567890123"},
                },
                {
                    "id": "doc-l1",
                    "user_id": str(uid),
                    "document_type": "land_records",
                    "lifecycle_status": "verified",
                },
                {
                    "id": "doc-b1",
                    "user_id": str(uid),
                    "document_type": "bank_passbook",
                    "lifecycle_status": "verified",
                },
            ],
        },
    )

    # 1. Conflict detected in en, hi, mr — value NOT silently guessed
    for lang_code in ("en", "hi", "mr"):
        pf = run_universal_prefill("PM-KISAN", profile, user=user, lang=lang_code)
        assert len(pf["conflicting_fields"]) == 1
        assert pf["conflicting_fields"][0]["field"] == "aadhaar_number"
        cand_vals = {c["value"] for c in pf["conflicting_fields"][0]["candidates"]}
        assert cand_vals == {"726726378736", "234567890123"}
        assert pf["values"]["aadhaar_number"] == ""
        assert pf["can_confirm"] is False

    # 2. Conflict blocks readiness & REST confirmation
    db = MockSession(profile=profile)
    draft_res = create_application_draft(CreateDraftRequest(scheme_id="PM-KISAN"), current_user=user, db=db)
    app_id = draft_res.data["id"]
    val_blocked = validate_application_draft(app_id, current_user=user, db=db).data
    assert val_blocked["passed"] is False
    assert len(val_blocked["breakdown"]["form"]["conflicting_fields"]) == 1

    with pytest.raises(HTTPException) as exc_conf:
        confirm_application(app_id, current_user=user, db=db)
    assert exc_conf.value.status_code == 422

    # 3. Citizen explicitly resolves conflict via UpdateDraftRequest -> readiness passes!
    upd = update_application_draft(
        app_id,
        UpdateDraftRequest(form_data={"aadhaar_number": "234567890123"}),
        current_user=user,
        db=db,
    )
    assert upd.data["form_data"]["aadhaar_number"] == "234567890123"
    assert upd.data["prefill_summary"]["conflicting_fields"] == []
    val_ok = validate_application_draft(app_id, current_user=user, db=db).data
    assert val_ok["passed"] is True


def test_cross_citizen_isolation_and_invalid_format_rejection():
    """Cross-citizen User/UserProfile mismatch fails closed, foreign documents ignored, invalid formats blocked."""
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()
    user_a = User(id=uid_a, email="a@example.com")
    profile_b = UserProfile(id=uuid.uuid4(), user_id=uid_b, full_name="Other Citizen", profile_data={"aadhaar_number": "999988887777"})

    with pytest.raises(PermissionError):
        run_universal_prefill("PM-KISAN", profile_b, user=user_a)

    # Foreign user_id doc or app inside profile_data must be excluded
    profile_a = UserProfile(
        id=uuid.uuid4(),
        user_id=uid_a,
        full_name="Citizen A",
        profile_data={
            "documents": [
                {
                    "id": "foreign-doc",
                    "user_id": str(uid_b),
                    "document_type": "aadhaar_card",
                    "lifecycle_status": "verified",
                    "reviewed_fields": {"document_number": "999988887777"},
                }
            ]
        },
    )
    pf = run_universal_prefill(
        "PM-KISAN",
        profile_a,
        user=user_a,
        form_overrides={"ifsc_code": "INVALID_IFSC"},
    )
    assert pf["values"]["aadhaar_number"] is None
    assert any(err["field"] == "ifsc_code" for err in pf["invalid_fields"])
    assert pf["can_confirm"] is False


def test_planner_blocks_incomplete_request_confirmation_and_handles_apy():
    """Planner request_confirmation rejects incomplete form_data; APY returns unavailable schema cleanly."""
    session_kisan = {"conv_id": "c-p6-1", "active_scheme_code": "PM-KISAN"}
    req_incomplete = AgentChatRequest(
        conversation_id="c-p6-1",
        message="Proceed to confirmation for PM-KISAN",
        form_action="request_confirmation",
        form_data={"applicant_name": "Ramesh Kumar"},
    )
    res = plan_and_execute_agentic_flow(
        db=None,
        request=req_incomplete,
        current_user=None,
        profile=None,
        session=session_kisan,
        lang="en",
        all_schemes=[],
    )
    assert res is not None
    assert res.workflow_step == "PRE-FILL"
    assert res.response_type == ChatResponseType.FORM_DRAFT
    assert res.form_draft_data["can_confirm"] is False

    # APY via planner
    session_apy = {"conv_id": "c-p6-2"}
    req_apy = AgentChatRequest(
        conversation_id="c-p6-2",
        message="Pre-fill application form for Atal Pension Yojana",
    )
    res_apy = plan_and_execute_agentic_flow(
        db=None,
        request=req_apy,
        current_user=None,
        profile=None,
        session=session_apy,
        lang="hi",
        all_schemes=[],
    )
    assert res_apy is not None
    assert res_apy.form_draft_data is not None
    assert res_apy.form_draft_data["form_supported"] is False
    assert res_apy.form_draft_data["schema_available"] is False
    assert "आधिकारिक" in res_apy.message

    # Switching schemes via Hindi text when an existing session/request carries a prior scheme_id
    session_switch = {"conv_id": "c-p6-3", "active_scheme_code": "KCC"}
    req_switch = AgentChatRequest(
        conversation_id="c-p6-3",
        message="अटल पेंशन योजना का आवेदन फॉर्म भरें",
        scheme_id="KCC",
    )
    res_switch = plan_and_execute_agentic_flow(
        db=None,
        request=req_switch,
        current_user=None,
        profile=None,
        session=session_switch,
        lang="hi",
        all_schemes=[],
    )
    assert res_switch is not None
    assert res_switch.active_scheme["scheme_code"] == "APY"
    assert res_switch.form_draft_data["schema_available"] is False

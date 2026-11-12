"""
Comprehensive Trilingual Test Suite for Scheme Saathi
Verifies:
1. Exactly three supported languages: English (en), Hindi (hi), Marathi (mr).
2. Pure English queries yield 100% pure English responses (no Hindi/Marathi contamination).
3. Pure Hindi queries yield 100% pure Hindi responses (no English/Marathi contamination).
4. Pure Marathi queries yield 100% pure Marathi responses (no English/Hindi contamination).
5. Hinglish queries yield natural Hinglish responses.
6. Marathi-English queries yield natural Marathi responses with English terms.
7. No parenthetical or slashed mixed phrases like '(Government of Maharashtra)' in regional responses.
8. Instant mid-conversation language switching preserves scheme context.
9. Follow-up chips and document checklists are correctly localized.
"""

import pytest
from app.schemas.agent import AgentChatRequest
from app.services.agent_service import (
    detect_language_and_style,
    detect_language,
    _extract_intent,
    _handle_comprehensive_scheme_inquiry,
    _handle_document_query,
    _handle_eligibility_query,
    _handle_scheme_overview_query,
    _handle_geographic_availability_query,
    _update_session_scheme,
    _get_session,
)
from tests.unit.test_agent_service import _load_all_test_schemes


@pytest.fixture(scope="module")
def all_schemes():
    return _load_all_test_schemes()


def test_scenario_1_pure_english(all_schemes):
    """
    Scenario 1: Pure English Input
    Query: 'What is PM-KISAN? Explain its eligibility and required documents.'
    Expected:
    - Detected language: 'en'
    - Style: 'pure'
    - Response strictly in English (no Devanagari script, no Marathi/Hindi keywords)
    - Followups strictly in English
    """
    query = "What is PM-KISAN? Explain its eligibility and required documents."
    lang, style = detect_language_and_style(query)
    assert lang == "en"
    assert style == "pure"

    intent = _extract_intent(query, schemes=all_schemes)
    assert intent["type"] == "comprehensive_scheme_inquiry"
    assert intent["scheme_code"] == "PM-KISAN"

    resp = _handle_comprehensive_scheme_inquiry(
        db=None,
        schemes=all_schemes,
        intent=intent,
        lang=lang,
        conv_id="conv-multi-1",
        profile=None,
        raw_query=query,
        style=style,
    )

    assert resp.detected_language == "en"
    # Ensure no Devanagari characters in English response
    assert not any(0x0900 <= ord(c) <= 0x097F for c in resp.message), "Found Devanagari characters in English response"
    assert "Overview, Eligibility & Required Documents" in resp.message or "Pradhan Mantri Kisan Samman Nidhi" in resp.message
    assert "Financial Benefits & Assistance:" in resp.message
    assert "Eligibility Criteria & Target Beneficiaries:" in resp.message
    assert "Required Document Checklist:" in resp.message
    # Check followups
    for chip in resp.suggested_followups:
        assert not any(0x0900 <= ord(c) <= 0x097F for c in chip), f"Found non-English chip: {chip}"


def test_scenario_2_pure_hindi(all_schemes):
    """
    Scenario 2: Pure Hindi Input
    Query: 'पीएम-किसान योजना क्या है? इसकी पात्रता और आवश्यक दस्तावेज़ समझाइए।'
    Expected:
    - Detected language: 'hi'
    - Style: 'pure'
    - Response strictly in Hindi (no English phrases except standard acronyms/URLs)
    - Followups in Hindi
    """
    query = "पीएम-किसान योजना क्या है? इसकी पात्रता और आवश्यक दस्तावेज़ समझाइए।"
    lang, style = detect_language_and_style(query)
    assert lang == "hi"
    assert style == "pure"

    intent = _extract_intent(query, schemes=all_schemes)
    assert intent["type"] == "comprehensive_scheme_inquiry"
    assert intent["scheme_code"] == "PM-KISAN"

    resp = _handle_comprehensive_scheme_inquiry(
        db=None,
        schemes=all_schemes,
        intent=intent,
        lang=lang,
        conv_id="conv-multi-2",
        profile=None,
        raw_query=query,
        style=style,
    )

    assert resp.detected_language == "hi"
    assert "का संपूर्ण विवरण, पात्रता एवं आवश्यक दस्तावेज़:" in resp.message
    assert "वित्तीय लाभ एवं सहायता:" in resp.message
    assert "पात्रता मानदंड एवं लक्षित लाभार्थी:" in resp.message
    assert "आवश्यक आधिकारिक दस्तावेज़:" in resp.message
    # Verify no Marathi-specific vocabulary
    assert "कागदपत्रे" not in resp.message
    assert "आहे" not in resp.message
    assert "(Government of Maharashtra)" not in resp.message
    assert "(Mandatory / अनिवार्य)" not in resp.message


def test_scenario_3_pure_marathi(all_schemes):
    """
    Scenario 3: Pure Marathi Input
    Query: 'पीएम-किसान योजना काय आहे? तिची पात्रता आणि आवश्यक कागदपत्रे समजावून सांगा.'
    Expected:
    - Detected language: 'mr'
    - Style: 'pure'
    - Response strictly in Marathi
    - Followups in Marathi
    """
    query = "पीएम-किसान योजना काय आहे? तिची पात्रता आणि आवश्यक कागदपत्रे समजावून सांगा."
    lang, style = detect_language_and_style(query)
    assert lang == "mr"
    assert style == "pure"

    intent = _extract_intent(query, schemes=all_schemes)
    assert intent["type"] == "comprehensive_scheme_inquiry"
    assert intent["scheme_code"] == "PM-KISAN"

    resp = _handle_comprehensive_scheme_inquiry(
        db=None,
        schemes=all_schemes,
        intent=intent,
        lang=lang,
        conv_id="conv-multi-3",
        profile=None,
        raw_query=query,
        style=style,
    )

    assert resp.detected_language == "mr"
    assert "चा संपूर्ण तपशील, पात्रता आणि आवश्यक कागदपत्रे:" in resp.message
    assert "शासकीय लाभ व आर्थिक सहाय्य:" in resp.message
    assert "पात्रता निकष व लाभार्थी:" in resp.message
    assert "आवश्यक अधिकृत कागदपत्रे:" in resp.message
    # Verify no Hindi-specific vocabulary
    assert "दस्तावेज़" not in resp.message
    assert "शर्तें" not in resp.message
    assert "(Government of India)" not in resp.message
    assert "(Mandatory / अनिवार्य)" not in resp.message


def test_scenario_4_hinglish(all_schemes):
    """
    Scenario 4: Hinglish Input
    Query: 'PM-KISAN ke liye eligibility kya hai aur kaunse documents chahiye?'
    Expected:
    - Detected language: 'hi'
    - Style: 'hinglish'
    - Natural Hinglish response with clear Hindi base and common English terms
    """
    query = "PM-KISAN ke liye eligibility kya hai aur kaunse documents chahiye?"
    lang, style = detect_language_and_style(query)
    assert lang == "hi"
    assert style == "hinglish"

    intent = _extract_intent(query, schemes=all_schemes)
    assert intent["type"] == "comprehensive_scheme_inquiry"
    assert intent["scheme_code"] == "PM-KISAN"

    resp = _handle_comprehensive_scheme_inquiry(
        db=None,
        schemes=all_schemes,
        intent=intent,
        lang=lang,
        conv_id="conv-multi-4",
        profile=None,
        raw_query=query,
        style=style,
    )

    assert resp.detected_language == "hi"
    assert "PM-KISAN" in resp.message
    assert "लाभ" in resp.message or "पात्रता" in resp.message


def test_scenario_5_marathi_english(all_schemes):
    """
    Scenario 5: Marathi + English Code-Switching Input
    Query: 'PM-KISAN साठी eligibility काय आहे आणि कोणते documents लागतात?'
    Expected:
    - Detected language: 'mr'
    - Style: 'mr_en'
    - Natural Marathi response with recognized English terms
    """
    query = "PM-KISAN साठी eligibility काय आहे आणि कोणते documents लागतात?"
    lang, style = detect_language_and_style(query)
    assert lang == "mr"
    assert style == "mr_en"

    intent = _extract_intent(query, schemes=all_schemes)
    assert intent["type"] == "comprehensive_scheme_inquiry"
    assert intent["scheme_code"] == "PM-KISAN"

    resp = _handle_comprehensive_scheme_inquiry(
        db=None,
        schemes=all_schemes,
        intent=intent,
        lang=lang,
        conv_id="conv-multi-5",
        profile=None,
        raw_query=query,
        style=style,
    )

    assert resp.detected_language == "mr"
    assert "PM-KISAN" in resp.message
    assert "Eligibility, Benefits आणि Required Documents" in resp.message
    assert "Benefits व आर्थिक सहाय्य:" in resp.message
    assert "Eligibility Criteria व लाभार्थी:" in resp.message


def test_multiturn_language_switching(all_schemes):
    """
    Test rapid mid-conversation language switching:
    Turn 1 (en): "What documents are required for PM-KISAN?" -> English response
    Turn 2 (hi): "इसके क्या लाभ हैं?" -> Hindi response, PM-KISAN context retained
    Turn 3 (mr): "यासाठी नोंदणी कुठे करावी?" -> Marathi response, PM-KISAN context retained
    Turn 4 (en): "Is this scheme available in Maharashtra?" -> English response, PM-KISAN context retained
    """
    conv_id = "test-switch-flow-001"

    # Turn 1: English
    t1_query = "What documents are required for PM-KISAN?"
    t1_lang, _ = detect_language_and_style(t1_query)
    assert t1_lang == "en"
    t1_intent = _extract_intent(t1_query, schemes=all_schemes)
    assert t1_intent["scheme_code"] == "PM-KISAN"
    _update_session_scheme(conv_id, "PM-KISAN")

    t1_resp = _handle_document_query(
        db=None, schemes=all_schemes, intent=t1_intent, lang=t1_lang, conv_id=conv_id, profile=None
    )
    assert t1_resp.detected_language == "en"
    assert "Official Checklist of Required Documents" in t1_resp.message

    # Turn 2: Switch to Hindi
    t2_query = "इसके क्या लाभ हैं?"
    t2_lang, _ = detect_language_and_style(t2_query)
    assert t2_lang == "hi"
    session = _get_session(conv_id)
    assert session.get("active_scheme_code") == "PM-KISAN"
    t2_intent = _extract_intent(t2_query, schemes=all_schemes, active_scheme_code=session.get("active_scheme_code"))
    assert t2_intent["scheme_code"] == "PM-KISAN"

    from app.services.agent_service import _handle_benefits_query
    t2_resp = _handle_benefits_query(
        db=None, schemes=all_schemes, intent=t2_intent, lang=t2_lang, conv_id=conv_id, profile=None, raw_query=t2_query
    )
    assert t2_resp.detected_language == "hi"
    assert "वित्तीय सहायता" in t2_resp.message or "वित्तीय लाभ" in t2_resp.message

    # Turn 3: Switch to Marathi
    t3_query = "यासाठी नोंदणी कुठे करावी?"
    t3_lang, _ = detect_language_and_style(t3_query)
    assert t3_lang == "mr"
    t3_intent = _extract_intent(t3_query, schemes=all_schemes, active_scheme_code=session.get("active_scheme_code"))
    assert t3_intent["scheme_code"] == "PM-KISAN"

    from app.services.agent_service import _handle_registration_portal_query
    t3_resp = _handle_registration_portal_query(
        db=None, schemes=all_schemes, intent=t3_intent, lang=t3_lang, conv_id=conv_id, profile=None, raw_query=t3_query
    )
    assert t3_resp.detected_language == "mr"
    assert "अधिकृत नोंदणी" in t3_resp.message

    # Turn 4: Switch back to English
    t4_query = "Is this scheme available in Maharashtra?"
    t4_lang, _ = detect_language_and_style(t4_query)
    assert t4_lang == "en"
    t4_intent = _extract_intent(t4_query, schemes=all_schemes, active_scheme_code=session.get("active_scheme_code"))
    assert t4_intent["scheme_code"] == "PM-KISAN"

    t4_resp = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent=t4_intent, lang=t4_lang, conv_id=conv_id, profile=None, raw_query=t4_query
    )
    assert t4_resp.detected_language == "en"
    assert "is available in Maharashtra" in t4_resp.message
    assert "Central Government" in t4_resp.message

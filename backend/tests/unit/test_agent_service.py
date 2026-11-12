"""
Unit tests for Scheme Saathi Voice AI Assistant service.
Verifies language detection, intent classification, and query processing.
"""
import pytest
from app.services.agent_service import detect_language, _extract_intent


def test_marathi_language_detection():
    # Native Marathi queries
    assert detect_language("मला सरकारी योजनांबद्दल माहिती हवी आहे.") == "mr"
    assert detect_language("मी शेतकरी आहे. मला कोणत्या योजना मिळू शकतात?") == "mr"
    assert detect_language("मला PM किसान योजनेसाठी पात्रता आहे का?") == "mr"
    assert detect_language("मी PM किसान योजनेसाठी पात्रता आहे का?") == "mr"
    assert detect_language("मला कोणती कागदपत्रे लागतील?") == "mr"

    # Latin-script mixed Marathi (code-mixed)
    assert detect_language("Mala PM Kisan eligibility check karaychi aahe.") == "mr"
    assert detect_language("shetkari yojana mahiti havi aahe") == "mr"


def test_hindi_language_detection():
    # Native Hindi queries
    assert detect_language("मैं महाराष्ट्र का रहने वाला हूँ, मुझे कौन सी सरकारी योजनाएँ मिल सकती हैं?") == "hi"
    assert detect_language("मैं किसान हूँ, मुझे किस योजना का लाभ मिल सकता है?") == "hi"
    assert detect_language("मुझे आवेदन करने के लिए कौन से दस्तावेज चाहिए?") == "hi"

    # Latin-script mixed Hindi (Hinglish)
    assert detect_language("Mujhe farming ke liye government scheme chahiye.") == "hi"
    assert detect_language("kisan yojana ke baare me batao") == "hi"


def test_english_language_detection():
    assert detect_language("Tell me about schemes for farmers in India.") == "en"
    assert detect_language("Am I eligible for PM-KISAN?") == "en"
    assert detect_language("What documents are required to apply for housing?") == "en"


def test_user_language_preference_override():
    # Latest citizen message strictly determines response language; UI preference acts as neutral fallback
    assert detect_language("I want farming scheme", user_preference="mr") == "en"
    assert detect_language("मला माहिती हवी आहे", user_preference="hi") == "mr"
    assert detect_language("मुझे योजना चाहिए", user_preference="en") == "hi"
    assert detect_language("12345", user_preference="mr") == "mr"
    assert detect_language("12345", user_preference="hi") == "hi"
    assert detect_language("12345", user_preference="en") == "en"


def test_intent_classification():
    # Document queries
    doc_intent = _extract_intent("मला PM किसान साठी कोणती कागदपत्रे लागतील?")
    assert doc_intent["type"] == "document_checklist"
    assert doc_intent["scheme_code"] == "PM-KISAN"

    # Eligibility queries
    elig_intent = _extract_intent("मला PM किसान योजनेसाठी पात्रता आहे का?")
    assert elig_intent["type"] == "eligibility_check"
    assert elig_intent["scheme_code"] == "PM-KISAN"

    # Maharashtra state discovery
    mh_intent = _extract_intent("मी महाराष्ट्राचा आहे, मला लाडकी बहीण योजनेची माहिती हवी आहे")
    assert mh_intent["is_maharashtra"] is True
    assert mh_intent["scheme_code"] == "MLBY-MH"

    # Farmer category discovery
    farmer_intent = _extract_intent("मी शेतकरी आहे, मला कोणत्या योजना मिळतील?")
    assert farmer_intent["category"] == "agriculture"


def test_application_procedure_intents():
    # English
    en_res = _extract_intent("I want to apply for PM-KISAN. How can I apply?")
    assert en_res["type"] == "application_procedure"
    assert en_res["scheme_code"] == "PM-KISAN"

    # Marathi
    mr_res = _extract_intent("मला PM किसान योजनेसाठी अर्ज करायचा आहे. कसा करू?")
    assert mr_res["type"] == "application_procedure"
    assert mr_res["scheme_code"] == "PM-KISAN"

    # Hindi with active scheme inheritance
    hi_res = _extract_intent("इस योजना के लिए आवेदन कैसे करें?", active_scheme_code="PM-KISAN")
    assert hi_res["type"] == "application_procedure"
    assert hi_res["scheme_code"] == "PM-KISAN"

    # Hinglish
    hing_res = _extract_intent("Mujhe PM Kisan ke liye apply karna hai.")
    assert hing_res["type"] == "application_procedure"
    assert hing_res["scheme_code"] == "PM-KISAN"


def test_contextual_followup_and_inheritance():
    # Turn 1 sets active scheme code
    t1 = _extract_intent("I want to apply for PM-KISAN. How can I apply?")
    active_scheme = t1["scheme_code"]
    assert active_scheme == "PM-KISAN"

    # Turn 2: "Which documents do I need?" inherits active_scheme
    t2 = _extract_intent("Which documents do I need?", active_scheme_code=active_scheme)
    assert t2["type"] == "document_checklist"
    assert t2["scheme_code"] == "PM-KISAN"

    # Turn 3: "Where can I register?" inherits active_scheme
    t3 = _extract_intent("Where can I register?", active_scheme_code=active_scheme)
    assert t3["type"] == "registration_portal"
    assert t3["scheme_code"] == "PM-KISAN"

    # Turn 4: "How much money will I receive?" inherits active_scheme
    t4 = _extract_intent("How much money will I receive?", active_scheme_code=active_scheme)
    assert t4["type"] == "benefits_inquiry"
    assert t4["scheme_code"] == "PM-KISAN"

    # Turn 5: "Am I eligible for this scheme?" inherits active_scheme
    t5 = _extract_intent("Am I eligible for this scheme?", active_scheme_code=active_scheme)
    assert t5["type"] == "eligibility_check"
    assert t5["scheme_code"] == "PM-KISAN"

    # Turn 6: "What should I do after registration?" inherits active_scheme
    t6 = _extract_intent("What should I do after registration?", active_scheme_code=active_scheme)
    assert t6["type"] == "post_registration_status"
    assert t6["scheme_code"] == "PM-KISAN"


def test_benefits_and_post_registration_multilingual():
    # Benefits in Marathi
    mr_ben = _extract_intent("मला किती पैसे मिळतील?", active_scheme_code="PM-KISAN")
    assert mr_ben["type"] == "benefits_inquiry"

    # Benefits in Hindi
    hi_ben = _extract_intent("कितने पैसे मिलेंगे?", active_scheme_code="PM-KISAN")
    assert hi_ben["type"] == "benefits_inquiry"

    # Post-registration in Marathi
    mr_post = _extract_intent("नोंदणीनंतर काय करावे?", active_scheme_code="PM-KISAN")
    assert mr_post["type"] == "post_registration_status"

    # Post-registration in Hindi
    hi_post = _extract_intent("रजिस्ट्रेशन के बाद क्या करें?", active_scheme_code="PM-KISAN")
    assert hi_post["type"] == "post_registration_status"


def test_multi_user_isolation_same_conv_id():
    """
    Requirement 1, 2, 3: Verify _CONVERSATION_SESSIONS is isolated by authenticated user ID.
    Two different users passing the same conversation ID must NEVER cross-talk.
    """
    from app.services.agent_service import (
        _get_session,
        _update_session_scheme,
        _resolve_active_scheme,
        _CONVERSATION_SESSIONS,
    )
    from app.models.scheme import Scheme

    mock_schemes = [
        Scheme(scheme_code="PM-KISAN", name="Pradhan Mantri Kisan Samman Nidhi", category="agriculture", ministry="Agriculture", benefits="₹6,000/yr"),
        Scheme(scheme_code="NSP-CSSS", name="National Scholarship CSSS", category="education", ministry="Education", benefits="₹12,000/yr"),
    ]

    shared_conv = "shared-session-xyz"
    user_a = "farmer-uid-111"
    user_b = "student-uid-222"

    # User A sets PM-KISAN
    _update_session_scheme(shared_conv, "PM-KISAN", user_id=user_a)

    # User B simultaneously sets NSP-CSSS in the same conversation ID
    _update_session_scheme(shared_conv, "NSP-CSSS", user_id=user_b)

    # Verify session dictionaries are completely isolated
    sess_a = _get_session(shared_conv, user_id=user_a)
    sess_b = _get_session(shared_conv, user_id=user_b)

    assert sess_a["active_scheme_code"] == "PM-KISAN"
    assert sess_b["active_scheme_code"] == "NSP-CSSS"
    assert sess_a["key"] == f"user_{user_a}:{shared_conv}"
    assert sess_b["key"] == f"user_{user_b}:{shared_conv}"

    # Verify follow-up resolution: User A asking "Which documents do I need?" (no scheme code in query)
    res_a = _resolve_active_scheme(None, shared_conv, mock_schemes, user_id=user_a)
    assert res_a.scheme_code == "PM-KISAN"

    # Verify follow-up resolution: User B asking "Which documents do I need?" (no scheme code in query)
    res_b = _resolve_active_scheme(None, shared_conv, mock_schemes, user_id=user_b)
    assert res_b.scheme_code == "NSP-CSSS"


def test_multi_browser_tabs_isolation():
    """
    Requirement 4: Verify multiple browser tabs with separate conversation IDs are isolated.
    """
    from app.services.agent_service import _update_session_scheme, _get_session

    user_id = "citizen-ramesh-777"
    tab1_conv = "conv-tab-1-alpha"
    tab2_conv = "conv-tab-2-beta"

    # Tab 1 explores PM-KISAN
    _update_session_scheme(tab1_conv, "PM-KISAN", user_id=user_id)

    # Tab 2 explores AB-PMJAY
    _update_session_scheme(tab2_conv, "AB-PMJAY", user_id=user_id)

    # Assert both tabs maintain independent context
    assert _get_session(tab1_conv, user_id=user_id)["active_scheme_code"] == "PM-KISAN"
    assert _get_session(tab2_conv, user_id=user_id)["active_scheme_code"] == "AB-PMJAY"


def test_session_expiry_ttl():
    """
    Requirement 5: Check session expiry after idle TTL.
    """
    import time
    from app.services.agent_service import (
        _update_session_scheme,
        _get_session,
        SESSION_TTL_SECONDS,
    )

    conv_id = "conv-expiry-test"
    user_id = "user-expire-123"

    _update_session_scheme(conv_id, "KCC", user_id=user_id)
    session = _get_session(conv_id, user_id=user_id)
    assert session["active_scheme_code"] == "KCC"

    # Advance time beyond SESSION_TTL_SECONDS
    session["last_active_at"] = time.time() - (SESSION_TTL_SECONDS + 10)

    # Next access must expire the session and reset active_scheme_code
    fresh_session = _get_session(conv_id, user_id=user_id)
    assert fresh_session["active_scheme_code"] is None


def test_backend_restart_graceful_handling():
    """
    Requirement 1: Check persistent conversation isolation and restart recovery.
    - Active scheme context is persisted separately for each user AND conversation ID.
    - Two browser tabs belonging to the same user CANNOT overwrite each other's context.
    - Multi-user isolation is strictly preserved.
    - If context is missing after restart, returns None (never guess or default to PM-KISAN).
    """
    from app.services.agent_service import (
        _resolve_active_scheme,
        _CONVERSATION_SESSIONS,
        _persist_active_scheme_to_profile,
        _recover_active_scheme_from_profile,
    )
    from app.models.scheme import Scheme
    from app.models.user_profile import UserProfile

    mock_schemes = [
        Scheme(scheme_code="PM-KISAN", name="PM-KISAN", category="agriculture", ministry="Agri", benefits="Benefit"),
        Scheme(scheme_code="KCC", name="KCC", category="agriculture", ministry="Agri", benefits="Benefit"),
        Scheme(scheme_code="AB-PMJAY", name="Ayushman Bharat", category="health", ministry="Health", benefits="Benefit"),
    ]

    # Wipe in-memory session state completely (simulating backend restart)
    _CONVERSATION_SESSIONS.clear()

    # Case 1: Fresh conversation without prior context or profile MUST return None
    resolved_no_context = _resolve_active_scheme(None, "conv-fresh", mock_schemes, user_id="user-1", profile=None)
    assert resolved_no_context is None

    # Case 2: Same User with TWO simultaneous tabs (Tab 1: KCC, Tab 2: PM-KISAN)
    profile_u1 = UserProfile(user_id="user-1", profile_data={})

    # Tab 1 sets KCC
    resolved_tab1 = _resolve_active_scheme("KCC", "tab-1", mock_schemes, user_id="user-1", profile=profile_u1)
    assert resolved_tab1.scheme_code == "KCC"

    # Tab 2 sets PM-KISAN
    resolved_tab2 = _resolve_active_scheme("PM-KISAN", "tab-2", mock_schemes, user_id="user-1", profile=profile_u1)
    assert resolved_tab2.scheme_code == "PM-KISAN"

    # Verify profile_data stores separate entries per conv_id (NO single shared key!)
    assert "active_conversation_scheme" not in profile_u1.profile_data
    assert "tab-1" in profile_u1.profile_data["active_schemes_by_conv"]
    assert "tab-2" in profile_u1.profile_data["active_schemes_by_conv"]
    assert profile_u1.profile_data["active_schemes_by_conv"]["tab-1"]["scheme_code"] == "KCC"
    assert profile_u1.profile_data["active_schemes_by_conv"]["tab-2"]["scheme_code"] == "PM-KISAN"

    # SIMULATE BACKEND RESTART: Wipe in-memory cache completely
    _CONVERSATION_SESSIONS.clear()

    # Tab 1 recovers KCC
    recovered_tab1 = _resolve_active_scheme(None, "tab-1", mock_schemes, user_id="user-1", profile=profile_u1)
    assert recovered_tab1 is not None
    assert recovered_tab1.scheme_code == "KCC"

    # Tab 2 recovers PM-KISAN
    recovered_tab2 = _resolve_active_scheme(None, "tab-2", mock_schemes, user_id="user-1", profile=profile_u1)
    assert recovered_tab2 is not None
    assert recovered_tab2.scheme_code == "PM-KISAN"

    # Tab 3 (fresh tab for same user without prior context) returns None (Never guesses!)
    recovered_tab3 = _resolve_active_scheme(None, "tab-3", mock_schemes, user_id="user-1", profile=profile_u1)
    assert recovered_tab3 is None

    # Case 3: Multi-User Isolation: User 2 cannot access User 1's conversations
    profile_u2 = UserProfile(user_id="user-2", profile_data={})
    user2_recovered = _resolve_active_scheme(None, "tab-1", mock_schemes, user_id="user-2", profile=profile_u2)
    assert user2_recovered is None


def test_clarification_prompt_when_context_missing():
    """
    Verify that follow-up queries without recoverable scheme context prompt the user
    for clarification rather than assuming any scheme.
    """
    from app.services.agent_service import (
        _handle_application_procedure_query,
        _handle_document_query,
        _handle_benefits_query,
        _CONVERSATION_SESSIONS,
    )
    from app.models.scheme import Scheme

    mock_schemes = [
        Scheme(scheme_code="PM-KISAN", name="PM-KISAN", category="agriculture", ministry="Agri", benefits="Benefit"),
    ]
    _CONVERSATION_SESSIONS.clear()

    # Application procedure query without scheme context
    resp_app = _handle_application_procedure_query(
        db=None,
        schemes=mock_schemes,
        intent={"scheme_code": None},
        lang="en",
        conv_id="conv-missing-ctx",
        profile=None,
        raw_query="How do I apply for this scheme?",
        user_id="user-clarify"
    )
    assert "Which government scheme are you inquiring about?" in resp_app.message
    assert resp_app.response_type.value == "text"
    assert any("PM-KISAN" in chip for chip in resp_app.suggested_followups)

    # Document query without scheme context in Marathi
    resp_doc = _handle_document_query(
        db=None,
        schemes=mock_schemes,
        intent={"scheme_code": None},
        lang="mr",
        conv_id="conv-missing-ctx-mr",
        profile=None,
        user_id="user-clarify-mr"
    )
    assert "कोणत्या शासकीय योजनेबद्दल विचारत आहात?" in resp_doc.message
    assert resp_doc.response_type.value == "text"


def test_authoritative_government_sources():
    """
    Requirement 2 & 3: Verify all application procedures, benefits, and official URLs
    against authoritative Government of India sources, including MISS guidelines.
    """
    from app.services.agent_service import VERIFIED_SCHEME_GUIDES

    # Central Agriculture: PM-KISAN
    pm_kisan = VERIFIED_SCHEME_GUIDES["PM-KISAN"]
    assert pm_kisan["official_url"] == "https://pmkisan.gov.in/"
    assert pm_kisan["application_url"] == "https://pmkisan.gov.in/registrationform.aspx"
    assert "₹6,000" in pm_kisan["benefits_en"]
    assert "₹2,000" in pm_kisan["benefits_en"]
    assert pm_kisan["verification_date"] == "2026-11-10"

    # Central Credit: KCC - verify statutory conditionality of interest subvention
    kcc = VERIFIED_SCHEME_GUIDES["KCC"]
    assert "jansamarth.in" in kcc["application_url"]
    assert "₹3,00,000" in kcc["benefits_en"]
    assert "1.5%" in kcc["benefits_en"]  # Institutional subvention to banks under MISS
    assert "7%" in kcc["benefits_en"]    # Benchmark lending rate
    assert "Prompt Repayment Incentive" in kcc["benefits_en"]
    assert "3%" in kcc["benefits_en"]    # PRI rate
    assert "4%" in kcc["benefits_en"]    # Net effective rate
    assert "delayed beyond the due date" in kcc["benefits_en"]
    assert "₹1.60 Lakh" in kcc["benefits_en"]  # Collateral waiver limit
    assert kcc["verification_date"] == "2026-11-10"

    # Central Health: AB-PMJAY
    pmjay = VERIFIED_SCHEME_GUIDES["AB-PMJAY"]
    assert pmjay["official_url"] == "https://beneficiary.nha.gov.in/"
    assert "₹5,00,000" in pmjay["benefits_en"]
    assert pmjay["verification_date"] == "2026-11-10"

    # Maharashtra State: Ladki Bahin (MLBY-MH) - pending verification status
    mlby = VERIFIED_SCHEME_GUIDES["MLBY-MH"]
    assert mlby["official_url"] == "https://ladkibahin.maharashtra.gov.in/"
    assert mlby["is_pending_verification"] is True
    assert mlby["verification_date"] is None

    # Maharashtra State: Namo Shetkari (NSMSNY-MH)
    nsmsny = VERIFIED_SCHEME_GUIDES["NSMSNY-MH"]
    assert nsmsny["official_url"] == "https://krishi.maharashtra.gov.in/"
    assert "₹6,000" in nsmsny["benefits_en"]
    assert nsmsny["verification_date"] == "2026-11-10"


def test_verification_metadata_staleness_and_pending():
    """
    Requirement 3: Test verification metadata, staleness evaluation (> 180 days),
    and pending verification warnings.
    """
    from app.services.agent_service import _format_verification_metadata
    from app.models.scheme import Scheme
    from datetime import datetime, timezone, timedelta

    # Case 1: Stale scheme (verified in 2024, > 700 days ago)
    stale_scheme = Scheme(
        scheme_code="STALE-01",
        name="Stale Welfare Scheme",
        category="agriculture",
        ministry="Ministry of Agriculture",
        benefits="Some benefits",
        scheme_status="active",
        official_url="https://agricoop.nic.in/",
        source_url="https://agricoop.nic.in/guidelines.pdf",
        last_verified_at=datetime(2024, 9, 15, tzinfo=timezone.utc),
    )
    notice_en, meta_en = _format_verification_metadata(stale_scheme, lang="en")
    assert meta_en["is_stale"] is True
    assert meta_en["is_pending"] is False
    assert "Historical Verification Warning (Stale)" in notice_en
    assert "2024-09-15" in notice_en
    assert "https://agricoop.nic.in/guidelines.pdf" in notice_en

    # Case 2: Pending verification scheme
    pending_scheme = Scheme(
        scheme_code="PENDING-01",
        name="Pending Welfare Scheme",
        category="social_security",
        ministry="Ministry of Social Justice",
        benefits="Benefits",
        scheme_status="pending_verification",
        official_url="https://socialjustice.gov.in/",
        source_url="https://socialjustice.gov.in/scheme.pdf",
        last_verified_at=None,
    )
    notice_mr, meta_mr = _format_verification_metadata(pending_scheme, lang="mr")
    assert meta_mr["is_pending"] is True
    assert meta_mr["is_stale"] is False
    assert "पडताळणी प्रलंबित" in notice_mr

    # Case 3: Active and recently verified scheme (2026)
    active_scheme = Scheme(
        scheme_code="ACTIVE-01",
        name="Active Recent Scheme",
        category="health",
        ministry="Ministry of Health",
        benefits="Health cover",
        scheme_status="active",
        official_url="https://mohfw.gov.in/",
        source_url="https://mohfw.gov.in/guideline.pdf",
        last_verified_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    notice_hi, meta_hi = _format_verification_metadata(active_scheme, lang="hi")
    assert meta_hi["is_stale"] is False
    assert meta_hi["is_pending"] is False
    assert "सक्रिय सत्यापित" in notice_hi


def test_multilingual_and_hinglish_intents():
    """
    Requirement 4: Test query intent extraction in English, Marathi, Hindi, and Hinglish.
    """
    from app.services.agent_service import _extract_intent

    # English application procedure
    int_en = _extract_intent("How can I apply for PM-KISAN?")
    assert int_en["type"] == "application_procedure"
    assert int_en["scheme_code"] == "PM-KISAN"

    # Marathi application procedure
    int_mr = _extract_intent("PM-KISAN योजनेसाठी अर्ज कसा करावा?")
    assert int_mr["type"] == "application_procedure"
    assert int_mr["scheme_code"] == "PM-KISAN"

    # Hindi application procedure
    int_hi = _extract_intent("PM-KISAN योजना में आवेदन कैसे करें?")
    assert int_hi["type"] == "application_procedure"
    assert int_hi["scheme_code"] == "PM-KISAN"

    # Hinglish application procedure
    int_hing = _extract_intent("PM-KISAN me apply kaise kare?")
    assert int_hing["type"] == "application_procedure"
    assert int_hing["scheme_code"] == "PM-KISAN"

    int_hing2 = _extract_intent("KCC form kaise bhare?")
    assert int_hing2["type"] == "application_procedure"
    assert int_hing2["scheme_code"] == "KCC"

    # Hinglish documents
    int_docs = _extract_intent("KCC ke liye kya document lagega?")
    assert int_docs["type"] == "document_checklist"
    assert int_docs["scheme_code"] == "KCC"

    # Hinglish benefits
    int_ben = _extract_intent("PM-KISAN me kitna paisa milega?")
    assert int_ben["type"] == "benefits_inquiry"
    assert int_ben["scheme_code"] == "PM-KISAN"

    # Hinglish eligibility
    int_elig = _extract_intent("kya mai KCC ke liye eligible hu?")
    assert int_elig["type"] == "eligibility_check"
    assert int_elig["scheme_code"] == "KCC"


def test_application_guidance_notice():
    """
    Verify that application procedure responses explicitly include the Application Guidance Notice
    in English, Hindi, and Marathi, clarifying that Scheme Saathi does not directly submit applications.
    """
    from app.services.agent_service import _handle_application_procedure_query
    from app.models.scheme import Scheme

    mock_scheme = Scheme(
        scheme_code="PM-KISAN",
        name="PM-KISAN",
        category="agriculture",
        ministry="Agri",
        benefits="Benefit",
        official_url="https://pmkisan.gov.in/",
        source_url="https://pmkisan.gov.in/Documents/pmkisan_guidelines.pdf",
    )

    # English check
    resp_en = _handle_application_procedure_query(
        db=None,
        schemes=[mock_scheme],
        intent={"scheme_code": "PM-KISAN"},
        lang="en",
        conv_id="conv-notice-en",
        profile=None,
        raw_query="How do I apply for PM-KISAN?",
        user_id="user-notice"
    )
    assert "Application Guidance Notice" in resp_en.message
    assert "Scheme Saathi is NOT an official government filing authority" in resp_en.message

    # Marathi check
    resp_mr = _handle_application_procedure_query(
        db=None,
        schemes=[mock_scheme],
        intent={"scheme_code": "PM-KISAN"},
        lang="mr",
        conv_id="conv-notice-mr",
        profile=None,
        raw_query="PM-KISAN साठी अर्ज कसा करावा?",
        user_id="user-notice"
    )
    assert "मार्गदर्शन सूचना" in resp_mr.message
    assert "योजना साथीद्वारे थेट शासकीय अर्ज सादर केला जात नाही" in resp_mr.message

    # Hindi check
    resp_hi = _handle_application_procedure_query(
        db=None,
        schemes=[mock_scheme],
        intent={"scheme_code": "PM-KISAN"},
        lang="hi",
        conv_id="conv-notice-hi",
        profile=None,
        raw_query="PM-KISAN के लिए आवेदन कैसे करें?",
        user_id="user-notice"
    )
    assert "मार्गदर्शन सूचना" in resp_hi.message
    assert "योजना साथी कोई सरकारी पंजीकरण प्राधिकरण नहीं है" in resp_hi.message


def test_application_links_are_scheme_specific():
    """
    Requirement 4: Verify that official registration and application links are scheme-specific
    and open the correct designated destination.
    """
    from app.services.agent_service import _handle_registration_portal_query, _handle_application_procedure_query
    from app.models.scheme import Scheme

    kcc_scheme = Scheme(
        scheme_code="KCC",
        name="Kisan Credit Card Scheme",
        category="agriculture",
        ministry="Agriculture",
        benefits="Benefit",
        official_url="https://agricoop.nic.in/",
        application_url="https://www.jansamarth.in/",
        source_url="https://agricoop.nic.in/kcc-guidelines.pdf",
    )
    pmkisan_scheme = Scheme(
        scheme_code="PM-KISAN",
        name="PM-KISAN",
        category="agriculture",
        ministry="Agriculture",
        benefits="Benefit",
        official_url="https://pmkisan.gov.in/",
        application_url="https://pmkisan.gov.in/registrationform.aspx",
        source_url="https://pmkisan.gov.in/Documents/pmkisan_guidelines.pdf",
    )

    resp_kcc = _handle_registration_portal_query(
        db=None,
        schemes=[kcc_scheme],
        intent={"scheme_code": "KCC"},
        lang="en",
        conv_id="conv-link-kcc",
        profile=None,
        raw_query="Where can I register for KCC?",
        user_id="user-links"
    )
    assert "https://www.jansamarth.in/" in resp_kcc.message
    assert "https://pmkisan.gov.in/registrationform.aspx" not in resp_kcc.message

    resp_pmkisan = _handle_registration_portal_query(
        db=None,
        schemes=[pmkisan_scheme],
        intent={"scheme_code": "PM-KISAN"},
        lang="en",
        conv_id="conv-link-pmkisan",
        profile=None,
        raw_query="Where can I register for PM-KISAN?",
        user_id="user-links"
    )
    assert "https://pmkisan.gov.in/registrationform.aspx" in resp_pmkisan.message
    assert "https://www.jansamarth.in/" not in resp_pmkisan.message


def test_build_generic_scheme_guide_pending_and_incomplete():
    """
    Requirement 7 & 8: Ensure _build_generic_scheme_guide never invents scheme-specific information
    for schemes with incomplete/pending database records, and clearly marks unverified records.
    """
    from app.services.agent_service import _build_generic_scheme_guide
    from app.models.scheme import Scheme

    pending_scheme = Scheme(
        scheme_code="PENDING-TEST-01",
        name="Mock Pending Welfare Scheme",
        category="social_security",
        ministry="Ministry of Social Justice",
        benefits="Unverified discretionary pension",
        scheme_status="pending_verification",
        official_url=None,
        last_verified_at=None,
        source_url="https://www.india.gov.in/sample-pending",
    )

    # English check
    guide_en = _build_generic_scheme_guide(pending_scheme, "en")
    assert guide_en["is_pending_verification"] is True
    assert any("Pending Verification" in step for step in guide_en["steps_en"])
    assert "does not generate unverified application steps" in guide_en["steps_en"][1]
    assert "https://www.india.gov.in/sample-pending" in guide_en["steps_en"][2]

    # Marathi check
    guide_mr = _build_generic_scheme_guide(pending_scheme, "mr")
    assert guide_mr["is_pending_verification"] is True
    assert any("पडताळणी प्रलंबित" in step for step in guide_mr["steps_mr"])

    # Hindi check
    guide_hi = _build_generic_scheme_guide(pending_scheme, "hi")
    assert guide_hi["is_pending_verification"] is True
    assert any("सत्यापन लंबित" in step for step in guide_hi["steps_hi"])


def test_non_fabrication_application_status():
    """
    Requirement 9: Verify that application status is never fabricated.
    """
    from app.services.agent_service import _handle_post_registration_status_query
    from app.models.scheme import Scheme

    mock_db = None  # Not needed for guide generation
    mock_scheme = Scheme(
        scheme_code="PM-KISAN",
        name="Pradhan Mantri Kisan Samman Nidhi",
        category="agriculture",
        ministry="Agriculture",
        benefits="₹6,000/yr",
        official_url="https://pmkisan.gov.in/",
    )

    resp = _handle_post_registration_status_query(
        db=mock_db,
        schemes=[mock_scheme],
        intent={"scheme_code": "PM-KISAN"},
        lang="en",
        conv_id="test-status-conv",
        profile=None,
        raw_query="What is the status of my application?",
        user_id="user-transparency-check",
    )

    # Assert that transparency notice is present and no fake status is claimed
    assert "Transparency Advisory" in resp.message
    assert "never fabricates application statuses" in resp.message
    assert "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx" in resp.message
    assert resp.response_type.value == "status_tracking"


# ══════════════════════════════════════════════════════════════════════════════
# Universal Scheme Knowledge & All-Scheme Coverage Tests (31 Schemes)
# ══════════════════════════════════════════════════════════════════════════════

def _load_all_test_schemes():
    """Helper to load all 31 scheme JSON files from data/schemes into Scheme models."""
    import glob
    import json
    from pathlib import Path
    from app.models.scheme import Scheme
    from app.models.scheme_document import SchemeDocument

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
    files = sorted(glob.glob(str(data_dir / "*.json")))
    schemes = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fp:
            d = json.load(fp)
            s = Scheme(
                scheme_code=d["scheme_code"],
                name=d["name"],
                short_title=d.get("short_title"),
                description=d["description"],
                ministry=d["ministry"],
                department=d.get("department"),
                category=d["category"],
                geographic_scope=d.get("geographic_scope", "central"),
                target_beneficiaries=d.get("target_beneficiaries", []),
                benefits=d["benefits"],
                official_url=d.get("official_url"),
                application_url=d.get("application_url"),
                source_url=d["source_url"],
                scheme_status=d.get("scheme_status", "active"),
            )
            # Attach documents
            docs = []
            for doc_dict in d.get("required_documents", []):
                doc = SchemeDocument(
                    document_type=doc_dict.get("document_type", "other"),
                    title=doc_dict.get("title", "Document"),
                    description=doc_dict.get("description"),
                    is_mandatory=doc_dict.get("is_mandatory", True),
                    issuing_authority=doc_dict.get("issuing_authority", "Authority"),
                    guidance=doc_dict.get("guidance", ""),
                    source_url=doc_dict.get("source_url", d["source_url"]),
                )
                docs.append(doc)
            s.documents = docs
            schemes.append(s)
    return schemes


def test_universal_scheme_recognition_all_31_schemes():
    """
    Mandatory Requirement 1 & 6: Test that EVERY scheme in the database (all 31)
    is recognized by the dynamic scheme matcher and intent classifier.
    """
    from app.services.agent_service import _match_schemes_from_query, _extract_intent, SCHEME_ALIASES

    all_schemes = _load_all_test_schemes()
    assert len(all_schemes) == 31, f"Expected 31 scheme records, found {len(all_schemes)}"

    all_codes = [s.scheme_code for s in all_schemes]

    # Verify each of the 31 schemes is recognized
    for scheme in all_schemes:
        code = scheme.scheme_code

        # 1. Test by canonical scheme_code
        matched_by_code = _match_schemes_from_query(f"Tell me about {code}", all_schemes)
        assert len(matched_by_code) >= 1, f"Failed to match scheme by code: {code}"
        assert matched_by_code[0].scheme_code == code, f"Expected {code}, got {matched_by_code[0].scheme_code}"

        # 2. Test intent classification with schemes catalogue
        intent = _extract_intent(f"How do I apply for {code}?", schemes=all_schemes)
        assert intent["scheme_code"] == code, f"Intent failed to resolve scheme_code {code}"
        assert intent["type"] == "application_procedure"

        # 3. Test by alias/vernacular term
        aliases = SCHEME_ALIASES.get(code, [])
        if aliases:
            # Pick a representative alias
            sample_alias = aliases[0]
            matched_by_alias = _match_schemes_from_query(f"What is {sample_alias}?", all_schemes)
            assert len(matched_by_alias) >= 1, f"Failed to match {code} by alias '{sample_alias}'"
            assert matched_by_alias[0].scheme_code == code


def test_every_scheme_qna_5_questions():
    """
    Mandatory Requirement 6: For EACH of the 31 schemes, test all 5 core questions:
    1. What is this scheme? (scheme_overview)
    2. What are its benefits? (benefits_inquiry)
    3. Who is eligible? (eligibility_check)
    4. What documents are required? (document_checklist)
    5. How can I apply? (application_procedure)
    Total evaluations: 31 * 5 = 155 test assertions.
    """
    from app.services.agent_service import (
        _handle_scheme_overview_query,
        _handle_benefits_query,
        _handle_eligibility_query,
        _handle_document_query,
        _handle_application_procedure_query,
    )

    all_schemes = _load_all_test_schemes()
    assert len(all_schemes) == 31

    for scheme in all_schemes:
        code = scheme.scheme_code
        conv_id = f"test-qna-{code}"
        intent = {"scheme_code": code}

        # Question 1: What is this scheme?
        res1 = _handle_scheme_overview_query(
            db=None, schemes=all_schemes, intent=intent, lang="en",
            conv_id=conv_id, profile=None, raw_query=f"What is {code}?"
        )
        assert code in res1.message or scheme.name in res1.message, f"Q1 failed for {code}"
        assert scheme.description in res1.message or scheme.benefits in res1.message
        assert res1.data is not None

        # Question 2: What are its benefits?
        res2 = _handle_benefits_query(
            db=None, schemes=all_schemes, intent=intent, lang="en",
            conv_id=conv_id, profile=None, raw_query=f"What are the benefits of {code}?"
        )
        assert "Statutory Benefit" in res2.message, f"Q2 missing benefit header for {code}"
        assert res2.response_type.value == "benefits_info"

        # Question 3: Who is eligible?
        res3 = _handle_eligibility_query(
            db=None, schemes=all_schemes, intent=intent, lang="en",
            conv_id=conv_id, profile=None
        )
        assert "Target Beneficiaries" in res3.message, f"Q3 missing beneficiaries for {code}"
        assert res3.response_type.value == "scheme_cards"

        # Question 4: What documents are required?
        res4 = _handle_document_query(
            db=None, schemes=all_schemes, intent=intent, lang="en",
            conv_id=conv_id, profile=None
        )
        assert res4.response_type.value == "document_checklist"
        assert ("Official Checklist of Required Documents" in res4.message or "Information Currently Unavailable" in res4.message)

        # Question 5: How can I apply?
        res5 = _handle_application_procedure_query(
            db=None, schemes=all_schemes, intent=intent, lang="en",
            conv_id=conv_id, profile=None, raw_query=f"How can I apply for {code}?"
        )
        assert ("Step-by-Step" in res5.message or "Pending Verification" in res5.message), f"Q5 failed for {code}"
        assert "Application Guidance Notice" in res5.message or "मार्गदर्शन सूचना" in res5.message


def test_geographic_availability_in_maharashtra():
    """
    Requirement 3: Test 'Is this available in Maharashtra?'
    Verifies state schemes vs central schemes.
    """
    from app.services.agent_service import _handle_geographic_availability_query, _extract_intent

    all_schemes = _load_all_test_schemes()

    # 1. Central Scheme: PM-KISAN
    res_central_en = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "PM-KISAN"},
        lang="en", conv_id="conv-geo-central", profile=None, raw_query="Is PM-KISAN available in Maharashtra?"
    )
    assert "Yes, Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) is available in Maharashtra." in res_central_en.message
    assert "Central Government" in res_central_en.message
    assert "nationwide implementation" in res_central_en.message

    # Central Scheme in Marathi
    res_central_mr = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "KCC"},
        lang="mr", conv_id="conv-geo-central-mr", profile=None, raw_query="KCC महाराष्ट्रात उपलब्ध आहे का?"
    )
    assert "होय, Kisan Credit Card Scheme (KCC) ही योजना महाराष्ट्रात उपलब्ध आहे." in res_central_mr.message
    assert "केंद्र शासनाची" in res_central_mr.message

    # Central Scheme in Hindi
    res_central_hi = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "PMMY"},
        lang="hi", conv_id="conv-geo-central-hi", profile=None, raw_query="क्या मुद्रा योजना महाराष्ट्र में उपलब्ध है?"
    )
    assert "हाँ, Pradhan Mantri Mudra Yojana (PMMY) योजना महाराष्ट्र में उपलब्ध है।" in res_central_hi.message
    assert "केंद्र सरकार" in res_central_hi.message

    # 2. Maharashtra State Scheme: MLBY-MH
    res_state_en = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "MLBY-MH"},
        lang="en", conv_id="conv-geo-state-en", profile=None, raw_query="Is MLBY-MH available in Maharashtra?"
    )
    assert "Maharashtra State Government" in res_state_en.message

    # Maharashtra State Scheme in Marathi
    res_state_mr = _handle_geographic_availability_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "NSMSNY-MH"},
        lang="mr", conv_id="conv-geo-state-mr", profile=None, raw_query="नमो शेतकरी योजना महाराष्ट्रात उपलब्ध आहे का?"
    )
    assert "महाराष्ट्र शासनाची" in res_state_mr.message
    assert "(Government of Maharashtra)" not in res_state_mr.message

    # Test Intent Extraction for Geographic Availability
    geo_intent = _extract_intent("Is PM-KISAN available in Maharashtra?", schemes=all_schemes)
    assert geo_intent["type"] == "geographic_availability"
    assert geo_intent["scheme_code"] == "PM-KISAN"

    geo_intent_mr = _extract_intent("ही योजना महाराष्ट्रात उपलब्ध आहे का?", schemes=all_schemes, active_scheme_code="KCC")
    assert geo_intent_mr["type"] == "geographic_availability"
    assert geo_intent_mr["scheme_code"] == "KCC"


def test_multi_scheme_query_handling():
    """
    Requirement 2: Test that queries referring to multiple schemes return information
    for all mentioned schemes simultaneously.
    """
    from app.services.agent_service import _extract_intent, _handle_multi_scheme_query

    all_schemes = _load_all_test_schemes()

    # 1. English multi-scheme: PM-KISAN and KCC
    query_en = "Tell me about PM-KISAN and KCC"
    intent_en = _extract_intent(query_en, schemes=all_schemes)
    assert intent_en["type"] == "multi_scheme_query"
    assert "PM-KISAN" in intent_en["scheme_codes"]
    assert "KCC" in intent_en["scheme_codes"]

    res_en = _handle_multi_scheme_query(
        db=None, schemes=all_schemes, matched_schemes=intent_en["matched_schemes"],
        lang="en", conv_id="conv-multi-en", profile=None, raw_query=query_en
    )
    assert "Authoritative Comparative Details for 2 Inquired Schemes" in res_en.message
    assert "PM-KISAN" in res_en.message
    assert "KCC" in res_en.message
    assert len(res_en.data) == 2

    # 2. Marathi multi-scheme: Majhi Ladki Bahin and Namo Shetkari
    query_mr = "मला लाडकी बहीण आणि नमो शेतकरी बद्दल सांगा"
    intent_mr = _extract_intent(query_mr, schemes=all_schemes)
    assert intent_mr["type"] == "multi_scheme_query"
    assert "MLBY-MH" in intent_mr["scheme_codes"]
    assert "NSMSNY-MH" in intent_mr["scheme_codes"]

    res_mr = _handle_multi_scheme_query(
        db=None, schemes=all_schemes, matched_schemes=intent_mr["matched_schemes"],
        lang="mr", conv_id="conv-multi-mr", profile=None, raw_query=query_mr
    )
    assert "तुलनात्मक तपशील" in res_mr.message
    assert len(res_mr.data) == 2


def test_contextual_followups_for_non_hardcoded_schemes():
    """
    Requirement 2 & 3: Multi-turn contextual follow-up sequence for newly integrated schemes (e.g. PMMY - Mudra).
    Verifies that turn-by-turn inheritance works without hardcoded definitions.
    """
    from app.services.agent_service import (
        _extract_intent,
        _resolve_active_scheme,
        _update_session_scheme,
        _get_session,
    )

    all_schemes = _load_all_test_schemes()
    conv_id = "conv-mudra-followup-turn"
    user_id = "user-mudra-ctx"

    # Turn 1: "Tell me about Pradhan Mantri Mudra Yojana"
    t1_intent = _extract_intent("Tell me about Pradhan Mantri Mudra Yojana", schemes=all_schemes)
    assert t1_intent["scheme_code"] == "PMMY"
    scheme_t1 = _resolve_active_scheme(t1_intent["scheme_code"], conv_id, all_schemes, user_id=user_id)
    assert scheme_t1.scheme_code == "PMMY"

    # Turn 2: "What are its benefits?" (no scheme code in message)
    t2_intent = _extract_intent("What are its benefits?", schemes=all_schemes, active_scheme_code=_get_session(conv_id, user_id)["active_scheme_code"])
    assert t2_intent["type"] == "benefits_inquiry"
    assert t2_intent["scheme_code"] == "PMMY"
    scheme_t2 = _resolve_active_scheme(t2_intent["scheme_code"], conv_id, all_schemes, user_id=user_id)
    assert scheme_t2.scheme_code == "PMMY"

    # Turn 3: "Who can apply?"
    t3_intent = _extract_intent("Who can apply?", schemes=all_schemes, active_scheme_code=_get_session(conv_id, user_id)["active_scheme_code"])
    assert t3_intent["type"] == "eligibility_check"
    assert t3_intent["scheme_code"] == "PMMY"

    # Turn 4: "What documents are required?"
    t4_intent = _extract_intent("What documents are required?", schemes=all_schemes, active_scheme_code=_get_session(conv_id, user_id)["active_scheme_code"])
    assert t4_intent["type"] == "document_checklist"
    assert t4_intent["scheme_code"] == "PMMY"

    # Turn 5: "How do I apply?"
    t5_intent = _extract_intent("How do I apply?", schemes=all_schemes, active_scheme_code=_get_session(conv_id, user_id)["active_scheme_code"])
    assert t5_intent["type"] == "application_procedure"
    assert t5_intent["scheme_code"] == "PMMY"

    # Turn 6: "Is this available in Maharashtra?"
    t6_intent = _extract_intent("Is this available in Maharashtra?", schemes=all_schemes, active_scheme_code=_get_session(conv_id, user_id)["active_scheme_code"])
    assert t6_intent["type"] == "geographic_availability"
    assert t6_intent["scheme_code"] == "PMMY"


def test_multilingual_queries_for_state_and_central_schemes():
    """
    Requirement 5: Test Marathi and Hindi vernacular queries across different scheme categories.
    """
    from app.services.agent_service import _extract_intent

    all_schemes = _load_all_test_schemes()

    # 1. Health - Maharashtra state scheme (MPJAY-MH) in Marathi
    res_mpjay = _extract_intent("महात्मा ज्योतिराव फुले जन आरोग्य योजनेसाठी अर्ज कसा करावा?", schemes=all_schemes)
    assert res_mpjay["scheme_code"] == "MPJAY-MH"
    assert res_mpjay["type"] == "application_procedure"

    # 2. Agriculture - PMMSY (Fisheries) in Marathi
    res_pmmsy = _extract_intent("मत्स्य संपदा योजनेचा काय लाभ मिळेल?", schemes=all_schemes)
    assert res_pmmsy["scheme_code"] == "PMMSY"
    assert res_pmmsy["type"] == "benefits_inquiry"

    # 3. Women Welfare - PMMVY (Matru Vandana) in Hindi
    res_pmmvy = _extract_intent("मातृ वंदना योजना क्या है?", schemes=all_schemes)
    assert res_pmmvy["scheme_code"] == "PMMVY"
    assert res_pmmvy["type"] == "scheme_overview"

    # 4. Financial Inclusion - PMJDY (Jan Dhan) in Hindi
    res_pmjdy = _extract_intent("जन धन योजना के लिए आवेदन कैसे करें?", schemes=all_schemes)
    assert res_pmjdy["scheme_code"] == "PMJDY"
    assert res_pmjdy["type"] == "application_procedure"

    # 5. Social Security - PMJJBY (Jeevan Jyoti) in Hindi
    res_pmjjby = _extract_intent("जीवन ज्योति बीमा योजना के लाभ बताएं", schemes=all_schemes)
    assert res_pmjjby["scheme_code"] == "PMJJBY"
    assert res_pmjjby["type"] == "benefits_inquiry"

    # 6. Skill Development - PMKVY in Hindi
    res_pmkvy = _extract_intent("कौशल विकास योजना के लिए कौन पात्र है?", schemes=all_schemes)
    assert res_pmkvy["scheme_code"] == "PMKVY"
    assert res_pmkvy["type"] == "eligibility_check"

    # 7. Employment - DAY-NRLM (Aajeevika) in Hindi
    res_nrlm = _extract_intent("राष्ट्रीय ग्रामीण आजीविका मिशन के बारे में बताएं", schemes=all_schemes)
    assert res_nrlm["scheme_code"] == "DAY-NRLM"
    assert res_nrlm["type"] == "scheme_overview"


def test_no_hardcoded_fallback_urls():
    """
    Requirement 5: Verify that when inquiring about schemes other than PM-KISAN,
    the system NEVER returns pmkisan.gov.in as a fallback URL.
    """
    from app.services.agent_service import (
        _handle_application_procedure_query,
        _handle_registration_portal_query,
        _handle_post_registration_status_query,
    )

    all_schemes = _load_all_test_schemes()
    jsy_scheme = next(s for s in all_schemes if s.scheme_code == "JSY")

    # Application procedure for JSY
    proc_res = _handle_application_procedure_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "JSY"},
        lang="en", conv_id="conv-no-fallback", profile=None, raw_query="How to apply for JSY?"
    )
    assert "https://pmkisan.gov.in/" not in proc_res.message, "pmkisan.gov.in was leaked in JSY procedure!"

    # Registration portal for JSY
    portal_res = _handle_registration_portal_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "JSY"},
        lang="en", conv_id="conv-no-fallback", profile=None, raw_query="Where can I register for JSY?"
    )
    assert "https://pmkisan.gov.in/" not in portal_res.message, "pmkisan.gov.in was leaked in JSY portal!"

    # Post registration status for JSY
    status_res = _handle_post_registration_status_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "JSY"},
        lang="en", conv_id="conv-no-fallback", profile=None, raw_query="Status of JSY?"
    )
    assert "https://pmkisan.gov.in/" not in status_res.message, "pmkisan.gov.in was leaked in JSY status!"


def test_spoken_text_complete_and_untruncated():
    """
    Critical Voice Assistant Fix: Verify that spoken_text is complete, untruncated,
    and preserves all steps, numbers, benefits, and conditions.
    """
    from app.services.agent_service import (
        _clean_markdown_for_speech,
        _handle_application_procedure_query,
        _handle_benefits_query,
    )

    # 1. Test clean markdown transformation retains content and cleans markdown
    raw_md = (
        "**How to Apply for Test Scheme:**\n\n"
        "1. Visit the [Official Portal](https://example.gov.in/).\n"
        "2. Submit your Aadhaar number.\n\n"
        "💰 **Benefits:** ₹10,000 via DBT."
    )
    cleaned = _clean_markdown_for_speech(raw_md, lang="en")
    assert "**" not in cleaned
    assert "💰" not in cleaned
    assert "1. Visit the Official Portal." in cleaned or "Official Portal" in cleaned
    assert "2. Submit your Aadhaar number." in cleaned
    assert "₹10,000 via DBT" in cleaned

    all_schemes = _load_all_test_schemes()

    # 2. PM-KISAN Application Procedure spoken_text must include all steps and be complete (> 400 chars)
    pmkisan_res = _handle_application_procedure_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "PM-KISAN"},
        lang="en", conv_id="conv-tts-full", profile=None, raw_query="How to apply for PM-KISAN?"
    )
    assert len(pmkisan_res.spoken_text) > 400, f"spoken_text was unexpectedly truncated: {len(pmkisan_res.spoken_text)}"
    assert "Farmers Corner" in pmkisan_res.spoken_text
    assert "New Farmer Registration" in pmkisan_res.spoken_text
    assert "Aadhaar" in pmkisan_res.spoken_text
    assert "1." in pmkisan_res.spoken_text
    assert "2." in pmkisan_res.spoken_text

    # 3. KCC Benefits spoken_text must include full MISS, PRI, and rates without [:120] truncation
    kcc_res = _handle_benefits_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "KCC"},
        lang="en", conv_id="conv-tts-kcc", profile=None, raw_query="What are the benefits of KCC?"
    )
    assert len(kcc_res.spoken_text) > 300, f"KCC spoken_text was truncated: {len(kcc_res.spoken_text)}"
    assert "7%" in kcc_res.spoken_text
    assert "3%" in kcc_res.spoken_text
    assert "4%" in kcc_res.spoken_text
    assert "Prompt Repayment Incentive" in kcc_res.spoken_text

    # 4. Marathi MPJAY-MH procedure spoken_text must be complete
    mpjay_res = _handle_application_procedure_query(
        db=None, schemes=all_schemes, intent={"scheme_code": "MPJAY-MH"},
        lang="mr", conv_id="conv-tts-mr", profile=None, raw_query="MPJAY साठी अर्ज कसा करावा?"
    )
    assert len(mpjay_res.spoken_text) > 300
    assert "पडताळणी प्रलंबित" in mpjay_res.spoken_text
    assert "अधिकृत" in mpjay_res.spoken_text


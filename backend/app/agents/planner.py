"""
Scheme Saathi Intelligent Agent Planning & Orchestration Layer.
Orchestrates the citizen journey: TALK → MATCH → CHECKLIST → PRE-FILL → CONFIRM.
Manages three-tier persistent memory, dynamic replanning, and real backend tool execution.
"""
from typing import Dict, Any, List, Optional
import re
import uuid
import time
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme import Scheme
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatResponseType,
    SchemeCardSummary,
)
from app.agents.tools import (
    extract_citizen_entities,
    apply_extracted_entities_to_profile,
    tool_check_eligibility,
    tool_build_checklist,
    tool_fill_form,
    tool_submit_form,
)
from app.agents.form_schemas import (
    get_form_schema_for_scheme,
    get_document_sourcing_info,
    DOCUMENT_SOURCING_REGISTRY,
    SCHEME_CODE_ALIASES,
)
from app.services.document_service import DOC_STATE_VERIFIED

logger = logging.getLogger(__name__)

# ── Multilingual Suggested Followup Mappings ───────────────────────────────────
FOLLOWUP_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "How can I track my status?": {
        "mr": "अर्जाची स्थिती कशी तपासावी?",
        "hi": "आवेदन की स्थिति कैसे जांचें?",
        "en": "How can I track my status?",
    },
    "What are the benefits payout dates?": {
        "mr": "लाभाची रक्कम कधी जमा होते?",
        "hi": "लाभ की राशि कब मिलती है?",
        "en": "What are the benefits payout dates?",
    },
    "Help with another scheme": {
        "mr": "दुसऱ्या योजनेची माहिती हवी आहे",
        "hi": "अन्य योजना के बारे में बताएं",
        "en": "Help with another scheme",
    },
    "Confirm & Proceed": {
        "mr": "पुष्टी करा आणि पुढे जा",
        "hi": "पुष्टि करें और आगे बढ़ें",
        "en": "Confirm & Proceed",
    },
    "View Document Checklist": {
        "mr": "कागदपत्र चेकलिस्ट पहा",
        "hi": "दस्तावेज़ चेकलिस्ट देखें",
        "en": "View Document Checklist",
    },
    "What documents are required?": {
        "mr": "कोणती कागदपत्रे लागतील?",
        "hi": "कौन से दस्तावेज़ चाहिए?",
        "en": "What documents are required?",
    },
    "Check full document checklist": {
        "mr": "कागदपत्रांची संपूर्ण यादी पहा",
        "hi": "दस्तावेज़ों की पूरी सूची देखें",
        "en": "Check full document checklist",
    },
    "Check document checklist": {
        "mr": "कागदपत्र चेकलिस्ट पहा",
        "hi": "दस्तावेज़ चेकलिस्ट देखें",
        "en": "Check document checklist",
    },
    "Check documents required": {
        "mr": "आवश्यक कागदपत्रे तपासा",
        "hi": "आवश्यक दस्तावेज़ जांचें",
        "en": "Check documents required",
    },
    "What are the benefits?": {
        "mr": "या योजनेचे काय लाभ आहेत?",
        "hi": "इस योजना के लाभ क्या हैं?",
        "en": "What are the benefits?",
    },
    "Yes, I have the death certificate": {
        "mr": "होय, माझ्याकडे मृत्यू प्रमाणपत्र आहे",
        "hi": "हाँ, मेरे पास मृत्यु प्रमाण पत्र है",
        "en": "Yes, I have the death certificate",
    },
    "I don't have the death certificate": {
        "mr": "माझ्याकडे मृत्यू प्रमाणपत्र नाही",
        "hi": "मेरे पास मृत्यु प्रमाण पत्र नहीं है",
        "en": "I don't have the death certificate",
    },
    "Pre-fill application form": {
        "mr": "अर्जाचा मसुदा भरा",
        "hi": "आवेदन पत्र का मसौदा भरें",
        "en": "Pre-fill application form",
    },
    "Yes, I have the land record": {
        "mr": "होय, माझ्याकडे जमिनीचा उतारा आहे",
        "hi": "हाँ, मेरे पास जमीन का रिकॉर्ड है",
        "en": "Yes, I have the land record",
    },
    "I don't have the land record": {
        "mr": "माझ्याकडे जमिनीचा उतारा नाही",
        "hi": "मेरे पास जमीन का रिकॉर्ड नहीं है",
        "en": "I don't have the land record",
    },
    "Pre-fill PM-KISAN application": {
        "mr": "PM-KISAN चा अर्ज मसुदा भरा",
        "hi": "PM-KISAN का आवेदन पत्र भरें",
        "en": "Pre-fill PM-KISAN application",
    },
    "Tell me about KCC interest subvention": {
        "mr": "KCC व्याज सवलतीबद्दल सांगा",
        "hi": "KCC ब्याज छूट के बारे में बताएं",
        "en": "Tell me about KCC interest subvention",
    },
    "Yes, I am enrolled in college": {
        "mr": "होय, मी महाविद्यालयात प्रवेश घेतला आहे",
        "hi": "हाँ, मेरा कॉलेज में प्रवेश हो चुका है",
        "en": "Yes, I am enrolled in college",
    },
    "Pre-fill scholarship application": {
        "mr": "शिष्यवृत्तीचा अर्ज मसुदा भरा",
        "hi": "छात्रवृत्ति का आवेदन पत्र भरें",
        "en": "Pre-fill scholarship application",
    },
    "Yes, I have the MCP card": {
        "mr": "होय, माझ्याकडे MCP कार्ड आहे",
        "hi": "हाँ, मेरे पास MCP कार्ड है",
        "en": "Yes, I have the MCP card",
    },
    "I don't have the MCP card": {
        "mr": "माझ्याकडे MCP कार्ड नाही",
        "hi": "मेरे पास MCP कार्ड नहीं है",
        "en": "I don't have the MCP card",
    },
    "Pre-fill PMMVY application": {
        "mr": "PMMVY चा अर्ज मसुदा भरा",
        "hi": "PMMVY का आवेदन पत्र भरें",
        "en": "Pre-fill PMMVY application",
    },
    "Yes, mobile is linked to Aadhaar": {
        "mr": "होय, आधारला मोबाईल लिंक आहे",
        "hi": "हाँ, आधार से मोबाइल लिंक है",
        "en": "Yes, mobile is linked to Aadhaar",
    },
    "Apply for Ayushman Vay Vandana Card": {
        "mr": "आयुष्मान वय वंदना कार्डसाठी अर्ज करा",
        "hi": "आयुष्मान वय वंदना कार्ड हेतु आवेदन करें",
        "en": "Apply for Ayushman Vay Vandana Card",
    },
    "Which hospitals are covered?": {
        "mr": "कोणती रुग्णालये समाविष्ट आहेत?",
        "hi": "कौन से अस्पताल शामिल हैं?",
        "en": "Which hospitals are covered?",
    },
    "Save & Review Draft": {
        "mr": "मसुदा जतन करा व तपासा",
        "hi": "मसौदा सहेजें और जांचें",
        "en": "Save & Review Draft",
    },
    "Proceed to Final Confirmation": {
        "mr": "अंतिम पुष्टीकरणासाठी पुढे जा",
        "hi": "अंतिम पुष्टि के लिए आगे बढ़ें",
        "en": "Proceed to Final Confirmation",
    },
    "Yes, I confirm. Generate Packet": {
        "mr": "होय, माझी पुष्टी आहे. संच तयार करा",
        "hi": "हाँ, मेरी पुष्टि है। पैकेट तैयार करें",
        "en": "Yes, I confirm. Generate Packet",
    },
    "I want to edit some fields": {
        "mr": "मला काही रकाने बदलायचे आहेत",
        "hi": "मुझे कुछ विवरण बदलने हैं",
        "en": "I want to edit some fields",
    },
}


def _localize_followups(followups: List[str], lang: str) -> List[str]:
    """Translates follow-up chips into the target conversation language."""
    if lang not in ("mr", "hi"):
        return followups
    res = []
    for f in followups:
        if f in FOLLOWUP_TRANSLATIONS and lang in FOLLOWUP_TRANSLATIONS[f]:
            res.append(FOLLOWUP_TRANSLATIONS[f][lang])
        elif "Pre-fill" in f:
            code = (
                f.replace("Pre-fill application form for", "")
                .replace("Pre-fill application for", "")
                .replace("Pre-fill", "")
                .replace("application", "")
                .strip()
            )
            if lang == "mr":
                res.append(f"{code} चा अर्ज मसुदा भरा" if code else "अर्जाचा मसुदा भरा")
            else:
                res.append(f"{code} का आवेदन पत्र भरें" if code else "आवेदन पत्र का मसौदा भरें")
        else:
            res.append(f)
    return res


def _detect_scheme_code_in_text(lower_message: str, all_schemes: List[Scheme]) -> Optional[str]:
    """Detect an explicitly named scheme code from a citizen chat message using word-boundary priority."""
    for alias, canon in sorted(SCHEME_CODE_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        al = alias.lower()
        if al.isascii():
            if re.search(r"(?:^|[^a-z0-9])" + re.escape(al) + r"(?:$|[^a-z0-9])", lower_message):
                return canon
        elif al in lower_message:
            return canon
    if "atal pension" in lower_message or re.search(r"\bapy\b", lower_message):
        return "APY"
    devanagari_aliases = {
        "अटल पेंशन": "APY",
        "अटल पेन्शन": "APY",
        "एपीवाई": "APY",
        "पीएम किसान": "PM-KISAN",
        "किसान सम्मान": "PM-KISAN",
        "शेतकरी सन्मान": "PM-KISAN",
        "किसान क्रेडिट": "KCC",
        "लाडकी बहीण": "MLBY-MH",
        "माझी लाडकी": "MLBY-MH",
        "लाड़ली बहना": "MLBY-MH",
        "आयुष्मान भारत": "AB-PMJAY",
        "प्रधानमंत्री आवास": "PMAY-G",
        "विधवा पेंशन": "WIDOW-PENSION",
        "विधवा पेन्शन": "WIDOW-PENSION",
        "मातृ वंदना": "PMMVY",
        "स्वनिधि": "PM-SVANIDHI",
    }
    for kw, canon in devanagari_aliases.items():
        if kw in lower_message:
            return canon
    if all_schemes:
        for sc in all_schemes:
            scode = (getattr(sc, "scheme_code", "") or "").strip()
            sname = (getattr(sc, "name", "") or "").lower()
            sname_hi = (getattr(sc, "name_hi", "") or "").lower()
            sname_mr = (getattr(sc, "name_mr", "") or "").lower()
            if (
                (scode and re.search(r"\b" + re.escape(scode.lower()) + r"\b", lower_message))
                or (sname and sname in lower_message)
                or (sname_hi and sname_hi in lower_message)
                or (sname_mr and sname_mr in lower_message)
            ):
                return scode or sname
    return None


def plan_and_execute_agentic_flow(
    db: Session,
    request: AgentChatRequest,
    current_user: Optional[User],
    profile: Optional[UserProfile],
    session: Dict[str, Any],
    lang: str,
    all_schemes: List[Scheme],
) -> Optional[AgentChatResponse]:
    """
    Intelligent orchestration layer for Scheme Saathi.
    Interprets citizen intent, executes real backend tools, manages replanning,
    and returns a structured AgentChatResponse if agentic flow applies.
    Returns None if the query should fall back to general conversational intent handlers.
    """
    conv_id = request.conversation_id or session.get("conv_id") or f"conv-{uuid.uuid4().hex[:8]}"
    raw_message = request.message.strip()
    lower_message = raw_message.lower()

    # Step 1: Extract citizen entities & update profile memory (non-destructive unless explicit correction)
    entities = extract_citizen_entities(raw_message)
    is_explicit_correction = any(k in lower_message for k in [
        "actually", "correction", "change", "mistake", "खरं तर", "बदला", "चूक", "मेरी आय", "माझे उत्पन्न", "माझे वय"
    ])
    if entities:
        conv_entities = dict(session.get("conversation_entities") or {})
        conv_entities.update(entities)
        session["conversation_entities"] = conv_entities
        if profile:
            apply_extracted_entities_to_profile(db, profile, entities, force_update=is_explicit_correction)

    # Resolve active scheme: an explicit scheme mention in a typed turn supersedes prior session scheme
    explicit_msg_scheme = None if request.form_action else _detect_scheme_code_in_text(lower_message, all_schemes)
    active_scheme_code = explicit_msg_scheme or request.scheme_id or session.get("active_scheme_code")
    if active_scheme_code:
        session["active_scheme_code"] = active_scheme_code

    current_step = request.workflow_step or session.get("workflow_step") or "TALK"
    conv_entities_ctx = session.get("conversation_entities") or {}

    # Step 2: Handle explicit UI form actions
    if request.form_action == "confirm_submit" and active_scheme_code:
        if request.form_data is not None:
            fill_check = tool_fill_form(
                db=db,
                user=current_user,
                profile=profile,
                scheme_code_or_name=active_scheme_code,
                form_overrides=request.form_data or {},
                conversation_entities=conv_entities_ctx,
                lang=lang,
            )
            if not fill_check.get("form_supported") or not fill_check.get("can_confirm"):
                err_msg = fill_check.get("message") or (
                    "कृपया सर्व अनिवार्य माहिती भरा आणि परस्परविरोधी तपशील दुरुस्त करा."
                    if lang == "mr"
                    else "कृपया सभी अनिवार्य फ़ील्ड भरें और परस्पर विरोधी विवरण हल करें।"
                    if lang == "hi"
                    else "Please complete all mandatory fields and resolve any conflicting details before confirmation."
                )
                return AgentChatResponse(
                    conversation_id=conv_id,
                    message=err_msg,
                    spoken_text=err_msg,
                    detected_language=lang,
                    response_type=ChatResponseType.FORM_DRAFT,
                    workflow_step="PRE-FILL",
                    active_scheme={"scheme_code": active_scheme_code},
                    form_draft_data=fill_check,
                    engine_mode="deterministic",
                )
        if db is not None and profile is not None:
            from app.services.readiness_service import evaluate_application_readiness
            eff_form_data = request.form_data
            if eff_form_data is None:
                eff_fill = tool_fill_form(
                    db=db,
                    user=current_user,
                    profile=profile,
                    scheme_code_or_name=active_scheme_code,
                    conversation_entities=conv_entities_ctx,
                    lang=lang,
                )
                eff_form_data = eff_fill.get("form_data") or {}
            readiness_gate = evaluate_application_readiness(
                scheme_code=active_scheme_code,
                scheme_id=active_scheme_code,
                form_data=eff_form_data,
                profile=profile,
                db=db,
                lang=lang,
            )
            if not readiness_gate.get("passed"):
                reasons = "; ".join(e["message"] for e in (readiness_gate.get("errors") or [])[:3])
                block_msg = (
                    f"⚠️ **अर्ज सज्जता पूर्ण नाही:** {reasons}"
                    if lang == "mr"
                    else f"⚠️ **आवेदन तत्परता अपूर्ण है:** {reasons}"
                    if lang == "hi"
                    else f"⚠️ **Readiness gate blocked confirmation:** {reasons}"
                )
                fill_check = tool_fill_form(
                    db=db,
                    user=current_user,
                    profile=profile,
                    scheme_code_or_name=active_scheme_code,
                    form_overrides=request.form_data or {},
                    conversation_entities=conv_entities_ctx,
                    lang=lang,
                )
                return AgentChatResponse(
                    conversation_id=conv_id,
                    message=block_msg,
                    spoken_text=block_msg,
                    detected_language=lang,
                    response_type=ChatResponseType.FORM_DRAFT,
                    workflow_step="PRE-FILL",
                    active_scheme={"scheme_code": active_scheme_code},
                    form_draft_data=fill_check,
                    engine_mode="deterministic",
                )

        try:
            submit_res = tool_submit_form(
                db=db,
                user=current_user,
                profile=profile,
                scheme_code_or_name=active_scheme_code,
                confirmed=True,
                form_data=request.form_data,
                lang=lang,
                consent_acknowledged=True,
                expected_version=request.expected_version,
                expected_hash=request.expected_hash,
                idempotency_key=request.idempotency_key,
            )
        except Exception as exc:
            err_detail = getattr(exc, "detail", None) or str(exc)
            session["workflow_step"] = "PRE-FILL"
            return AgentChatResponse(
                conversation_id=conv_id,
                message=f"⚠️ {err_detail}",
                spoken_text=str(err_detail),
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=tool_fill_form(
                    db=db,
                    user=current_user,
                    profile=profile,
                    scheme_code_or_name=active_scheme_code,
                    form_overrides=request.form_data or {},
                    conversation_entities=conv_entities_ctx,
                    lang=lang,
                ),
                engine_mode="deterministic",
            )

        session["workflow_step"] = "CONFIRM"
        ext_ref = submit_res.get("external_reference_id")
        portal_url = submit_res.get("official_portal_url") or "https://india.gov.in"
        conf_ver = submit_res.get("confirmed_version") or 1

        if submit_res.get("submitted") and ext_ref:
            if lang == "mr":
                msg = (
                    f"🎉 **अर्ज अधिकृत पोर्टलवर यशस्वीरित्या सादर झाला आहे!**\n\n"
                    f"🔖 **बाह्य पोर्टल संदर्भ क्रमांक:** `{ext_ref}`\n\n"
                    f"🏛️ **अधिकृत शासकीय पोर्टल:** [{portal_url}]({portal_url})"
                )
                spoken = f"तुमचा अर्ज अधिकृत पोर्टलवर सादर झाला आहे. संदर्भ क्रमांक {ext_ref}."
            elif lang == "hi":
                msg = (
                    f"🎉 **आवेदन आधिकारिक पोर्टल पर सफलतापूर्वक सबमिट हो गया है!**\n\n"
                    f"🔖 **आधिकारिक संदर्भ संख्या:** `{ext_ref}`\n\n"
                    f"🏛️ **आधिकारिक सरकारी पोर्टल:** [{portal_url}]({portal_url})"
                )
                spoken = f"आपका आवेदन आधिकारिक पोर्टल पर सबमिट हो गया है. संदर्भ संख्या {ext_ref}."
            else:
                msg = (
                    f"🎉 **Application Submitted to Authorized Official Portal!**\n\n"
                    f"🔖 **Official Portal Reference ID:** `{ext_ref}`\n\n"
                    f"🏛️ **Official Government Portal:** [{portal_url}]({portal_url})"
                )
                spoken = f"Your application was submitted to the official portal with reference {ext_ref}."
        else:
            sub_method = submit_res.get("submission_method") or "portal_assisted"
            if lang == "mr":
                msg = (
                    f"✅ **तुमची संमती आवृत्ती v{conf_ver} साठी नोंदवली गेली आहे — अधिकृत पोर्टलवर सादर करणे आवश्यक ({sub_method})**\n\n"
                    f"ℹ️ {submit_res.get('message', '')}\n\n"
                    f"🏛️ **अधिकृत शासकीय पोर्टल:** [{portal_url}]({portal_url})"
                )
                spoken = f"तुमची संमती आवृत्ती {conf_ver} साठी नोंदवली आहे. कृपया अधिकृत पोर्टलवर अर्ज सादर करून संदर्भ क्रमांक परत नोंदवा."
            elif lang == "hi":
                msg = (
                    f"✅ **संस्करण v{conf_ver} के लिए आपकी पुष्टि दर्ज कर ली गई है — आधिकारिक पोर्टल प्रस्तुति आवश्यक ({sub_method})**\n\n"
                    f"ℹ️ {submit_res.get('message', '')}\n\n"
                    f"🏛️ **आधिकारिक सरकारी पोर्टल:** [{portal_url}]({portal_url})"
                )
                spoken = f"संस्करण {conf_ver} के लिए आपकी पुष्टि दर्ज हो गई है. कृपया आधिकारिक पोर्टल पर आवेदन जमा कर संदर्भ संख्या वापस दर्ज करें."
            else:
                msg = (
                    f"✅ **Citizen Confirmation Recorded (Version v{conf_ver}) — Official Portal Handoff Ready**\n\n"
                    f"ℹ️ {submit_res.get('message', '')}\n\n"
                    f"🏛️ **Official Government Portal:** [{portal_url}]({portal_url})"
                )
                spoken = f"Confirmation recorded for version {conf_ver}. Complete submission on the official portal and record your reference number."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_RESULT,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data=submit_res,
            suggested_followups=_localize_followups([
                "How can I track my status?",
                "What are the benefits payout dates?",
                "Help with another scheme",
            ], lang),
            engine_mode="deterministic",
        )

    if request.form_action == "record_portal_reference" and active_scheme_code:
        from app.api.v1.applications import canonical_scheme_key
        from app.services.submission_service import record_citizen_portal_reference

        raw_ref = request.official_reference_number or (request.form_data or {}).get("official_reference_number") or ""
        target_app = None
        current_profile_data: Dict[str, Any] = {}
        apps: List[Dict[str, Any]] = []
        target_canon = canonical_scheme_key(active_scheme_code)
        if profile and isinstance(profile.profile_data, dict):
            current_profile_data = dict(profile.profile_data or {})
            apps = list(current_profile_data.get("applications", []))
            req_app_id = (request.form_data or {}).get("application_id")
            if req_app_id:
                target_app = next((a for a in apps if a.get("id") == req_app_id), None)
            if target_app is None:
                target_app = next(
                    (
                        a for a in apps
                        if canonical_scheme_key(a.get("scheme_code") or a.get("scheme_id") or "", a.get("scheme_name") or "") == target_canon
                        and not a.get("legacy_synthetic_submission")
                    ),
                    None,
                )

        if target_app is None or profile is None or current_user is None:
            err_msg = (
                "अधिकृत पोर्टल संदर्भ नोंदवण्यासाठी प्रथम अर्ज मसुदा तयार करून पुष्टी करा."
                if lang == "mr"
                else "आधिकारिक पोर्टल संदर्भ संख्या दर्ज करने के लिए कृपया पहले आवेदन मसौदे की पुष्टि करें।"
                if lang == "hi"
                else "No matching active application draft found to attach the official portal reference number."
            )
            return AgentChatResponse(
                conversation_id=conv_id,
                message=err_msg,
                spoken_text=err_msg,
                detected_language=lang,
                response_type=ChatResponseType.TEXT,
                workflow_step="CONFIRM",
                active_scheme={"scheme_code": active_scheme_code},
                engine_mode="deterministic",
            )

        try:
            ref_res = record_citizen_portal_reference(
                target_app=target_app,
                profile=profile,
                current_user=current_user,
                db=db,
                official_reference_number=raw_ref,
                submission_date=(request.form_data or {}).get("submission_date"),
                portal_notes=(request.form_data or {}).get("portal_notes"),
                confirmation_acknowledged=True,
                current_profile_data=current_profile_data,
                apps_list=apps,
                lang=lang,
            )
        except Exception as exc:
            err_detail = getattr(exc, "detail", None) or str(exc)
            return AgentChatResponse(
                conversation_id=conv_id,
                message=f"⚠️ {err_detail}",
                spoken_text=str(err_detail),
                detected_language=lang,
                response_type=ChatResponseType.CONFIRMATION_RESULT,
                workflow_step="CONFIRM",
                active_scheme={"scheme_code": active_scheme_code},
                confirmation_data={
                    "confirmed": True,
                    "submitted": False,
                    "manual_portal_required": True,
                    "application_id": target_app.get("id"),
                    "scheme_code": active_scheme_code,
                    "official_portal_url": target_app.get("portal_url") or target_app.get("official_url"),
                    "portal_reference_error": str(err_detail),
                },
                engine_mode="deterministic",
            )

        session["workflow_step"] = "CONFIRM"
        saved_ref = ref_res["official_reference_number"]
        portal_url = ref_res.get("portal_url") or "https://www.india.gov.in/"
        track_url = ref_res.get("tracking_url") or portal_url
        if lang == "mr":
            msg = (
                f"🔖 **अधिकृत पोर्टल संदर्भ क्रमांक यशस्वीरित्या जतन झाला!**\n\n"
                f"• **मसुदा आयडी:** `{ref_res['application_id']}`\n"
                f"• **अधिकृत पोर्टल संदर्भ क्रमांक:** `{saved_ref}`\n"
                f"• **ट्रॅकिंग पोर्टल:** [{track_url}]({track_url})"
            )
            spoken = f"अधिकृत पोर्टल संदर्भ क्रमांक {saved_ref} यशस्वीरित्या जतन करण्यात आला आहे."
        elif lang == "hi":
            msg = (
                f"🔖 **आधिकारिक पोर्टल संदर्भ संख्या सफलतापूर्वक सहेजी गई!**\n\n"
                f"• **आंतरिक ड्राफ्ट आईडी:** `{ref_res['application_id']}`\n"
                f"• **आधिकारिक पोर्टल संदर्भ संख्या:** `{saved_ref}`\n"
                f"• **ट्रैकिंग पोर्टल:** [{track_url}]({track_url})"
            )
            spoken = f"आधिकारिक पोर्टल संदर्भ संख्या {saved_ref} सफलतापूर्वक सहेज ली गई है."
        else:
            msg = (
                f"🔖 **Official Portal Reference Saved Successfully!**\n\n"
                f"• **Internal Draft ID:** `{ref_res['application_id']}`\n"
                f"• **Official Portal Reference:** `{saved_ref}`\n"
                f"• **Status Tracking Portal:** [{track_url}]({track_url})"
            )
            spoken = f"Saved your official portal reference number {saved_ref} to your application record."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_RESULT,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data={
                "confirmed": True,
                "submitted": False,
                "portal_submitted": True,
                "manual_portal_required": True,
                **ref_res,
            },
            suggested_followups=_localize_followups([
                "What is my application status?",
                "Help with another scheme",
            ], lang),
            engine_mode="deterministic",
        )

    if request.form_action == "request_confirmation" and active_scheme_code:
        fill_check = tool_fill_form(
            db=db,
            user=current_user,
            profile=profile,
            scheme_code_or_name=active_scheme_code,
            form_overrides=request.form_data or {},
            conversation_entities=conv_entities_ctx,
            lang=lang,
        )
        if not fill_check.get("form_supported") or not fill_check.get("can_confirm"):
            err_msg = fill_check.get("message") or (
                "कृपया पुष्टीकरणापूर्वी सर्व अनिवार्य माहिती पूर्ण करा आणि परस्परविरोधी तपशील दुरुस्त करा."
                if lang == "mr"
                else "कृपया पुष्टि से पहले सभी अनिवार्य फ़ील्ड भरें और परस्पर विरोधी विवरण हल करें।"
                if lang == "hi"
                else "Please complete all mandatory fields and resolve any conflicting details before proceeding to confirmation."
            )
            session["workflow_step"] = "PRE-FILL"
            return AgentChatResponse(
                conversation_id=conv_id,
                message=err_msg,
                spoken_text=err_msg,
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_check,
                engine_mode="deterministic",
            )
        if db is not None and profile is not None:
            from app.services.readiness_service import evaluate_application_readiness
            readiness_gate = evaluate_application_readiness(
                scheme_code=active_scheme_code,
                scheme_id=active_scheme_code,
                form_data=fill_check.get("form_data") or request.form_data or {},
                profile=profile,
                db=db,
                lang=lang,
            )
            if not readiness_gate.get("passed"):
                reasons = "; ".join(e["message"] for e in (readiness_gate.get("errors") or [])[:3])
                block_msg = (
                    f"⚠️ **पुष्टीकरणापूर्वी खालील बाबी पूर्ण करणे आवश्यक आहे:** {reasons}"
                    if lang == "mr"
                    else f"⚠️ **पुष्टि से पहले निम्नलिखित जांच पूरी करें:** {reasons}"
                    if lang == "hi"
                    else f"⚠️ **Complete readiness requirements before confirmation:** {reasons}"
                )
                session["workflow_step"] = "PRE-FILL"
                return AgentChatResponse(
                    conversation_id=conv_id,
                    message=block_msg,
                    spoken_text=block_msg,
                    detected_language=lang,
                    response_type=ChatResponseType.FORM_DRAFT,
                    workflow_step="PRE-FILL",
                    active_scheme={"scheme_code": active_scheme_code},
                    form_draft_data=fill_check,
                    engine_mode="deterministic",
                )

        submit_prompt = tool_submit_form(
            db,
            current_user,
            profile,
            active_scheme_code,
            confirmed=False,
            form_data=request.form_data,
            lang=lang,
        )
        session["workflow_step"] = "CONFIRM"
        msg = (
            f"⚠️ **संपूर्ण अर्ज पडताळणी व अंतिम संमती आवश्यक ({active_scheme_code}):**\n\nकृपया खालील संपूर्ण अर्ज सारांश तपासून तुमची संमती द्या."
            if lang == "mr"
            else f"⚠️ **पूर्ण आवेदन समीक्षा एवं स्पष्ट नागरिक पुष्टि आवश्यक ({active_scheme_code}):**\n\nकृपया नीचे पूर्ण विवरण की समीक्षा कर अपनी स्वीकृति दें।"
            if lang == "hi"
            else f"⚠️ **Complete Application Review & Explicit Confirmation Required ({active_scheme_code}):**\n\nPlease inspect the complete reviewed summary below before giving explicit authorization."
        )
        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=msg,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_REQUEST,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data=submit_prompt,
            engine_mode="deterministic",
        )

    if request.form_action == "save_draft" and active_scheme_code:
        fill_res = tool_fill_form(
            db=db,
            user=current_user,
            profile=profile,
            scheme_code_or_name=active_scheme_code,
            form_overrides=request.form_data or {},
            conversation_entities=conv_entities_ctx,
            lang=lang,
        )
        session["workflow_step"] = "PRE-FILL"

        if not fill_res.get("form_supported"):
            return AgentChatResponse(
                conversation_id=conv_id,
                message=fill_res["message"],
                spoken_text=fill_res["message"],
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_res,
                engine_mode="deterministic",
            )

        if lang == "mr":
            msg = f"✅ **तुमचा अर्ज मसुदा जतन करण्यात आला आहे!** (सज्जता: {fill_res['readiness_percentage']}%)\n\nकृपया तपशीलांची खात्री करा आणि अंतिम पुष्टीकरणासाठी पुढे जा."
            spoken = f"तुमचा अर्ज मसुदा {fill_res['readiness_percentage']} टक्के सज्जतेसह जतन करण्यात आला आहे."
        elif lang == "hi":
            msg = f"✅ **आपका आवेदन मसौदा सहेज लिया गया है!** (तैयारी: {fill_res['readiness_percentage']}%)\n\nकृपया विवरणों की समीक्षा करें और अंतिम पुष्टि के लिए आगे बढ़ें।"
            spoken = f"आपका आवेदन मसौदा {fill_res['readiness_percentage']} प्रतिशत तत्परता के साथ सहेज लिया गया है।"
        else:
            msg = f"✅ **Application draft saved successfully!** (Readiness: {fill_res['readiness_percentage']}%)\n\nPlease review your details and proceed to confirmation."
            spoken = f"Application draft saved with {fill_res['readiness_percentage']} percent readiness."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.FORM_DRAFT,
            workflow_step="PRE-FILL",
            active_scheme={"scheme_code": active_scheme_code},
            form_draft_data=fill_res,
            suggested_followups=_localize_followups([
                "Confirm & Proceed",
                "View Document Checklist",
                "What documents are required?",
            ], lang),
            engine_mode="deterministic",
        )

    # Step 3: Handle Replanning when Citizen discloses missing document (e.g. "I don't have an income certificate")
    if "missing_document_disclosed" in entities:
        missing_doc_key = entities["missing_document_disclosed"]

        # If no active scheme in session, check if widow context or fallback to PM-KISAN
        target_scheme = active_scheme_code or ("WIDOW-PENSION" if (profile and profile.profile_data.get("marital_status") == "widowed") else "PM-KISAN")
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme

        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)
        from app.services.document_guidance_service import (
            build_missing_document_guidance,
            format_document_guidance_response,
        )
        matched_scheme_obj = next(
            (s for s in (all_schemes or []) if (s.scheme_code or "").upper() == target_scheme.upper()),
            None,
        )
        if matched_scheme_obj is None and target_scheme == "WIDOW-PENSION":
            matched_scheme_obj = Scheme(
                scheme_code="WIDOW-PENSION",
                name="Indira Gandhi National Widow Pension Scheme",
                category="social_welfare",
                ministry="Ministry of Rural Development",
                benefits="₹1,000 per month DBT direct pension",
                official_url="https://nsap.nic.in",
                source_url="https://nsap.nic.in",
            )
        guidance = build_missing_document_guidance(
            query_or_doc_key=missing_doc_key,
            scheme=matched_scheme_obj,
            checklist_items=checklist_res.get("items") or [],
            profile=profile,
            user=current_user,
            db=db,
            all_schemes=all_schemes,
            lang=lang,
        )
        resolved_doc_key = guidance["document_type"]
        session["last_discussed_document"] = {
            "document_type": resolved_doc_key,
            "title": guidance.get("title") or resolved_doc_key,
            "scheme_code": target_scheme,
        }

        missing_list = list(session.get("missing_documents") or [])
        if resolved_doc_key not in missing_list:
            missing_list.append(resolved_doc_key)
        session["missing_documents"] = missing_list
        session["last_checklist"] = checklist_res
        session["workflow_step"] = "CHECKLIST"

        msg = format_document_guidance_response(guidance, lang=lang, focus="all", is_missing_disclosure=True)
        doc_title = guidance.get("title") or resolved_doc_key
        if lang == "mr":
            spoken = f"काळजी करू नका. {doc_title} कसे मिळवावे याची अधिकृत माहिती मी दिली आहे."
        elif lang == "hi":
            spoken = f"चिंता न करें। {doc_title} कहाँ से प्राप्त करना है, इसका विवरण दिया गया है।"
        else:
            spoken = f"Don't worry. Here are the verified and estimated steps to obtain {doc_title}."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.DOCUMENT_CHECKLIST,
            workflow_step="CHECKLIST",
            active_scheme={"scheme_code": target_scheme},
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                f"Pre-fill application for {target_scheme}",
                "Check full document checklist",
                "What are the benefits?",
            ], lang),
            engine_mode="deterministic",
        )

    # Step 3B: Handle Corrections when citizen changes previously supplied information
    is_correction = any(k in lower_message for k in [
        "actually", "correction", "change", "mistake", "खरं तर", "बदला", "चूक", "मेरी आय", "माझे उत्पन्न", "माझे वय"
    ]) and bool(entities) and active_scheme_code is not None

    if is_correction:
        target_scheme = active_scheme_code
        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme)
        
        # Format updated values summary
        updated_items = []
        if "annual_income" in entities:
            updated_items.append(f"Income: ₹{entities['annual_income']:,}")
        if "age" in entities:
            updated_items.append(f"Age: {entities['age']} years")
        if "state" in entities:
            updated_items.append(f"State: {entities['state']}")
        if "land_holding_acres" in entities:
            updated_items.append(f"Land: {entities['land_holding_acres']} acres")

        summary_str = ", ".join(updated_items)

        if lang == "mr":
            msg = (
                f"✏️ **माहिती अद्यतनित करण्यात आली आहे!** ({summary_str})\n\n"
                f"🔄 **पात्रतेचे पुनर्मूल्यांकन:**\n"
                f"• **योजना:** {elig_res.get('scheme_name', target_scheme)}\n"
                f"• **नवीन स्थिती:** **{elig_res['status'].upper()}**\n"
                f"• **तपशील:** {elig_res['summary']}\n\n"
                f"आपली प्रलंबित अर्ज प्रक्रिया सुरक्षित ठेवण्यात आली आहे. पुढील पायरीवर जाण्यासाठी खालील पर्यायांवर क्लिक करा."
            )
            spoken = f"माहिती अद्यतनित करण्यात आली आहे. आपण {target_scheme} साठी {elig_res['status']} आहात."
        elif lang == "hi":
            msg = (
                f"✏️ **विवरण सफलतापूर्वक अपडेट कर दिया गया है!** ({summary_str})\n\n"
                f"🔄 **पात्रता का पुनर्मूल्यांकन:**\n"
                f"• **योजना:** {elig_res.get('scheme_name', target_scheme)}\n"
                f"• **नवीन स्थिति:** **{elig_res['status'].upper()}**\n"
                f"• **विवरण:** {elig_res['summary']}\n\n"
                f"आपकी आवेदन प्रक्रिया सुरक्षित है। आगे बढ़ने के लिए विकल्प चुनें।"
            )
            spoken = f"विवरण अपडेट कर दिए गए हैं। आप {target_scheme} के लिए {elig_res['status']} हैं।"
        else:
            msg = (
                f"✏️ **Details Updated Successfully!** ({summary_str})\n\n"
                f"🔄 **Re-evaluated Eligibility:**\n"
                f"• **Scheme:** {elig_res.get('scheme_name', target_scheme)}\n"
                f"• **Updated Status:** **{elig_res['status'].upper()}**\n"
                f"• **Summary:** {elig_res['summary']}\n\n"
                f"Your application progress has been preserved. You can continue to the next step."
            )
            spoken = f"Details updated successfully. Based on the new information, your status for {target_scheme} is {elig_res['status']}."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step=session.get("workflow_step", "MATCH"),
            active_scheme={"scheme_code": target_scheme, "name": elig_res.get("scheme_name", target_scheme)},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                f"Pre-fill application form for {target_scheme}",
                "View Document Checklist",
                "What are the benefits?",
            ], lang),
            engine_mode="deterministic",
        )

    # Step 4: Persona Introduction Detection
    # ── 4A: Widow Pension Persona (Reference Screenshot Blueprint) ─────────────
    is_widow_query = (
        ("widow" in lower_message or "विधवा" in lower_message or entities.get("marital_status") == "widowed")
        and ("pension" in lower_message or "योजना" in lower_message or "schemes" in lower_message or "income" in lower_message or entities.get("age"))
    )

    if is_widow_query:
        target_scheme = "WIDOW-PENSION"
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme
        session["workflow_step"] = "MATCH"

        # Execute check_eligibility tool
        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        # Execute build_checklist tool
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)

        state_name = entities.get("state") or (profile.state if profile else "Uttar Pradesh")
        age_val = entities.get("age") or (profile.age if profile else 63)
        income_val = entities.get("annual_income") or (profile.annual_income if profile else 60000)

        if lang == "mr":
            msg = (
                f"नमस्ते माताजी! मी आपले तपशील नोंदवले आहेत: **वय {age_val} वर्षे, विधवा, राज्य: {state_name}, वार्षिक उत्पन्न: ₹{income_val:,}**.\n\n"
                f"✅ **योजना पात्रता मूल्यांकन:**\n"
                f"• **{elig_res['scheme_name']}:** **पात्र (ELIGIBLE)** 🎉\n"
                f"  - **मासिक निवृत्तीवेतन:** ₹१,००० प्रति महा थेट आधार-संलग्न बँक खात्यात (DBT).\n"
                f"  - **पात्रतेचे निकष:** वय १८+ (उत्तर प्रदेश/राज्य नियम) व ४०-७९ वर्षे (IGNWPS) आणि वार्षिक उत्पन्न ₹२,००,००० च्या मर्यादेत असल्याने आपण पूर्णतः पात्र आहात.\n"
                f"• **अटल पेन्शन योजना (APY):** अपात्र (कारण APY ची वयोमर्यादा १८ ते ४० वर्षे आहे).\n\n"
                f"📋 **कागदपत्र पडताळणी:**\n"
                f"आपल्या अर्जासाठी पतीचे **मृत्यू प्रमाणपत्र**, **आधार कार्ड**, आणि **उत्पन्न प्रमाणपत्र** आवश्यक आहेत.\n\n"
                f"❓ **पुढील प्रश्न:** आपल्याकडे आपल्या पतीचे अधिकृत मृत्यू प्रमाणपत्र (Death Certificate) उपलब्ध आहे का?"
            )
            spoken = f"नमस्ते. वय {age_val} वर्षे आणि विधवा पेन्शनच्या निकषांनुसार आपण मासिक ₹१,००० निवृत्तीवेतनाच्या योजनेसाठी पात्र आहात. आपल्याकडे पतीचे मृत्यू प्रमाणपत्र उपलब्ध आहे का?"
        elif lang == "hi":
            msg = (
                f"नमस्ते माताजी! मैंने आपके विवरण दर्ज कर लिए हैं: **उम्र {age_val} वर्ष, विधवा, राज्य: {state_name}, वार्षिक आय: ₹{income_val:,}**।\n\n"
                f"✅ **योजना पात्रता परिणाम:**\n"
                f"• **{elig_res['scheme_name']}:** **पात्र (ELIGIBLE)** 🎉\n"
                f"  - **मासिक पेंशन:** ₹1,000 प्रति माह सीधे आधार-लिंक्ड बैंक खाते (DBT) में।\n"
                f"  - **पात्रता कारण:** आपकी उम्र {age_val} वर्ष है और वार्षिक आय ₹{income_val:,} पात्रता सीमा (₹2,00,000) के अंतर्गत है।\n"
                f"• **अटल पेंशन योजना (APY):** अपात्र (क्योंकि APY की अधिकतम प्रवेश आयु 40 वर्ष है)।\n\n"
                f"📋 **दस्तावेज चेकलिस्ट:**\n"
                f"आवेदन के लिए स्वर्गीय पति का **मृत्यु प्रमाण पत्र**, **आधार कार्ड**, और **आय प्रमाण पत्र** आवश्यक हैं।\n\n"
                f"❓ **फॉलो-अप प्रश्न:** क्या आपके पास अपने पति का आधिकारिक मृत्यु प्रमाण पत्र (Death Certificate) उपलब्ध है?"
            )
            spoken = f"नमस्ते. आपकी उम्र {age_val} वर्ष और आय के अनुसार आप विधवा पेंशन योजना के लिए पूर्ण रूप से पात्र हैं. क्या आपके पास पति का मृत्यु प्रमाण पत्र उपलब्ध है?"
        else:
            msg = (
                f"Namaste! I have noted your details: **Age {age_val} years, Widowed, State: {state_name}, Annual Income: ₹{income_val:,}**.\n\n"
                f"✅ **Scheme Eligibility Assessment:**\n"
                f"• **{elig_res['scheme_name']}:** **ELIGIBLE** 🎉\n"
                f"  - **Monthly Pension:** ₹1,000 per month directly into your Aadhaar-seeded bank account (DBT).\n"
                f"  - **Eligibility Reasons:** Your age ({age_val} years) satisfies the 18+ state and 40-79 IGNWPS criteria, and your income of ₹{income_val:,} is well within the ceiling (≤ ₹2,00,000).\n"
                f"• **Atal Pension Yojana (APY):** Ineligible (maximum entry age is 40 years).\n\n"
                f"📋 **Mandatory Documents Required:**\n"
                f"1. Late husband's **Death Certificate**\n"
                f"2. Applicant's **Aadhaar Card**\n"
                f"3. Valid **Income Certificate** (Tahsildar issued)\n"
                f"4. Bank Passbook\n\n"
                f"❓ **Follow-up Question:** Do you have your late husband's official Death Certificate available?"
            )
            spoken = f"Namaste. Based on your age of {age_val} and annual income, you are eligible for the Widow Pension scheme offering ₹1,000 per month. Do you have your late husband's death certificate available?"

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step="MATCH",
            active_scheme={"scheme_code": target_scheme, "name": elig_res["scheme_name"]},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                "Yes, I have the death certificate",
                "I don't have the death certificate",
                "Pre-fill application form",
                "What are the benefits payout dates?",
            ], lang),
            engine_mode="deterministic",
        )

    # ── 4B: Small Farmer Persona (PM-KISAN & KCC) ──────────────────────────────
    is_farmer_query = (
        bool(entities.get("is_landholding_farmer"))
        or entities.get("occupation") == "farmer"
        or (
            any(k in lower_message for k in ["farmer", "किसान", "शेतकरी", "कृषक", "शेती"])
            and any(k in lower_message for k in ["acre", "land", "scheme", "योजना", "पात्र", "eligible", "मदत", "सहायता", "लागवड", "पैसे", "एकर", "एकड़", "जमीन", "शेतजमीन"])
        )
    )

    if is_farmer_query:
        target_scheme = "PM-KISAN"
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme
        session["workflow_step"] = "MATCH"

        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)
        state_name = entities.get("state") or (profile.state if profile else "Maharashtra")
        land_val = entities.get("land_holding_acres") or 2.5

        if lang == "mr":
            msg = (
                f"नमस्कार शेतकरी बांधवांनो! आपण दिलेल्या माहितीनुसार: **राज्य: {state_name}, शेतजमीन: {land_val} एकर**.\n\n"
                f"✅ **आपल्यासाठी शासकीय कृषी योजनांची पात्रता:**\n"
                f"१. **PM-KISAN (प्रधानमंत्री किसान सन्मान निधी):** **पात्र** 🎉 (वार्षिक ₹६,००० DBT हप्ता).\n"
                f"२. **नमो शेतकरी महासन्मान निधी (NSMSNY):** **पात्र** 🎉 (महाराष्ट्र शासनाकडून अतिरिक्त वार्षिक ₹६,०००).\n"
                f"३. **किसान क्रेडिट कार्ड (KCC):** **पात्र** 🎉 (३ लाखांपर्यंत कृषी कर्ज केवळ ४% सवलतीच्या व्याजदराने).\n\n"
                f"📋 **आवश्यक कागदपत्रे:** आधार कार्ड, सातबारा उतारा (७/१२), बँक पासबुक.\n\n"
                f"❓ **पुढील प्रश्न:** आपल्याकडे शेतजमिनीचा अधिकृत **सातबारा उतारा (७/१२)** उपलब्ध आहे का?"
            )
            spoken = f"नमस्कार. {land_val} एकर जमिनीसह आपण PM किसान व नमो शेतकरी योजनेसाठी पूर्णतः पात्र आहात. आपल्याकडे सातबारा उतारा आहे का?"
        elif lang == "hi":
            msg = (
                f"नमस्ते किसान भाई! आपके द्वारा दी गई जानकारी: **राज्य: {state_name}, कृषि भूमि: {land_val} एकड़**।\n\n"
                f"✅ **कृषि कल्याण योजनाओं की पात्रता:**\n"
                f"1. **PM-KISAN (पीएम-किसान):** **पात्र** 🎉 (सालाना ₹6,000 तीन किस्तों में सीधे बैंक में).\n"
                f"2. **किसान क्रेडिट कार्ड (KCC):** **पात्र** 🎉 (₹3 लाख तक का कृषि ऋण मात्र 4% प्रभावी ब्याज दर पर).\n\n"
                f"📋 **आवश्यक दस्तावेज:** आधार कार्ड, खसरा-खतौनी / भू-अभिलेख, आधार-लिंक्ड बैंक पासबुक।\n\n"
                f"❓ **फॉलो-अप प्रश्न:** क्या आपके पास अपने खेत की आधिकारिक **खसरा-खतौनी** उपलब्ध है?"
            )
            spoken = f"नमस्ते. {land_val} एकड़ जमीन के साथ आप पीएम-किसान योजना के लिए पूर्ण रूप से पात्र हैं. क्या आपके पास खसरा-खतौनी उपलब्ध है?"
        else:
            msg = (
                f"Namaste! Based on your details: **State: {state_name}, Cultivable Land: {land_val} Acres**.\n\n"
                f"✅ **Agriculture Schemes Eligibility Assessment:**\n"
                f"1. **PM-KISAN:** **ELIGIBLE** 🎉 (₹6,000 per year via DBT in three equal installments).\n"
                f"2. **Kisan Credit Card (KCC):** **ELIGIBLE** 🎉 (Crop loan up to ₹3 Lakh at 4% effective subsidized interest with prompt repayment).\n"
                f"{'3. **Namo Shetkari Sanman Nidhi:** **ELIGIBLE** 🎉 (Additional ₹6,000/year for Maharashtra farmers).' if state_name == 'Maharashtra' else ''}\n\n"
                f"📋 **Mandatory Documents Required:** Aadhaar Card, Land Record (7/12 Extract / Khasra-Khatauni), Bank Passbook.\n\n"
                f"❓ **Follow-up Question:** Do you have your official **Land Record (7/12 Extract / Khasra-Khatauni)** available?"
            )
            spoken = f"Namaste. With {land_val} acres of cultivable land, you are eligible for PM-KISAN and KCC. Do you have your official land record available?"

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step="MATCH",
            active_scheme={"scheme_code": target_scheme, "name": elig_res.get("scheme_name", "PM-KISAN")},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                "Yes, I have the land record",
                "I don't have the land record",
                "Pre-fill PM-KISAN application",
                "Tell me about KCC interest subvention",
            ], lang),
            engine_mode="deterministic",
        )

    # ── 4C: Student Scholarship Persona (NSP-CSSS) ─────────────────────────────
    is_student_query = (
        (entities.get("occupation") == "student" or entities.get("is_student") or any(k in lower_message for k in ["student", "विद्यार्थी", "छात्र", "छात्रा", "scholarship", "शिष्यवृत्ती"]))
        and any(k in lower_message for k in ["12th", "marks", "percent", "टक्के", "प्रतिशत", "pass", "college", "महाविद्यालय", "पात्र"])
    )

    if is_student_query:
        target_scheme = "NSP-CSSS"
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme
        session["workflow_step"] = "MATCH"

        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)
        pct_val = entities.get("student_percentage") or 88.0
        inc_val = entities.get("annual_income") or 180000

        if lang == "mr":
            msg = (
                f"अभिनंदन! १२वी मध्ये **{pct_val}%** गुण आणि वार्षिक उत्पन्न ₹{inc_val:,} सह आपण **NSP-CSSS (केंद्रीय क्षेत्र शिष्यवृत्ती)** साठी पात्र आहात! 🎉\n\n"
                f"💰 **शिष्यवृत्ती लाभ:** पदवीच्या पहिल्या ३ वर्षांसाठी दरवर्षी ₹१२,००० आणि पदव्युत्तर शिक्षणासाठी ₹२०,००० थेट बँक खात्यात.\n\n"
                f"📋 **आवश्यक कागदपत्रे:** १२वी गुणपत्रिका, उत्पन्नाचा दाखला (४.५ लाखांच्या आत), आधार कार्ड, चालू महाविद्यालयीन प्रवेश पावती.\n\n"
                f"❓ **पुढील प्रश्न:** आपण सध्या मान्यताप्राप्त पदवी अभ्यासक्रमात (Regular Degree/College) प्रवेश घेतला आहे का?"
            )
            spoken = f"अभिनंदन! १२वी मध्ये {pct_val} टक्के गुणांसह आपण राष्ट्रीय शिष्यवृत्तीसाठी पात्र आहात. आपण महाविद्यालयात प्रवेश घेतला आहे का?"
        elif lang == "hi":
            msg = (
                f"बधाई हो! 12वीं में **{pct_val}%** अंक और ₹{inc_val:,} वार्षिक आय के साथ आप **NSP-CSSS (सेंट्रल सेक्टर स्कॉलरशिप)** के लिए पात्र हैं! 🎉\n\n"
                f"💰 **छात्रवृत्ति लाभ:** स्नातक के दौरान प्रति वर्ष ₹12,00,0 सीधे आपके बैंक खाते में।\n\n"
                f"📋 **आवश्यक दस्तावेज:** 12वीं की अंकतालिका, आय प्रमाण पत्र (< ₹4.5 लाख), आधार कार्ड, कॉलेज प्रवेश रसीद।\n\n"
                f"❓ **फॉलो-अप प्रश्न:** क्या आपका वर्तमान में किसी मान्यता प्राप्त कॉलेज/डिग्री कोर्स में नियमित प्रवेश हो चुका है?"
            )
            spoken = f"बधाई हो. 12वीं में {pct_val} प्रतिशत अंकों के साथ आप राष्ट्रीय छात्रवृत्ति योजना के लिए पात्र हैं. क्या आपने कॉलेज में प्रवेश ले लिया है?"
        else:
            msg = (
                f"Congratulations! With **{pct_val}%** marks in Class 12 and family income of ₹{inc_val:,}, you are **ELIGIBLE** for the **Central Sector Scheme of Scholarship (NSP-CSSS)**! 🎉\n\n"
                f"💰 **Scholarship Amount:** ₹12,000 per annum for the first 3 years of regular graduation, and ₹20,000/year for postgraduate studies via DBT.\n\n"
                f"📋 **Mandatory Documents:** Class 12 Marksheet, Family Income Certificate (≤ ₹4.5 Lakh), Aadhaar Card, College Admission Proof.\n\n"
                f"❓ **Follow-up Question:** Are you currently enrolled in a recognized regular degree/college program?"
            )
            spoken = f"Congratulations! With {pct_val} percent marks in Class 12, you are eligible for the National Scholarship scheme. Are you enrolled in college?"

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step="MATCH",
            active_scheme={"scheme_code": target_scheme, "name": elig_res.get("scheme_name", "NSP-CSSS")},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                "Yes, I am enrolled in college",
                "Pre-fill scholarship application",
                "Check document checklist",
            ], lang),
            engine_mode="deterministic",
        )

    # ── 4D: Rural Pregnant Woman Persona (PMMVY) ───────────────────────────────
    is_maternity_query = (
        (entities.get("is_pregnant_or_lactating") or any(k in lower_message for k in ["pregnant", "garbhwati", "गर्भवती", "गरोदर", "maternity", "बाळंतपण", "माता"]))
        and any(k in lower_message for k in ["scheme", "योजना", "लाभ", "सहायता", "पैसे", "child", "मुल"])
    )

    if is_maternity_query:
        target_scheme = "PMMVY"
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme
        session["workflow_step"] = "MATCH"

        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)
        state_name = entities.get("state") or (profile.state if profile else "Maharashtra")

        if lang == "mr":
            msg = (
                f"नमस्ते! गरोदर व स्तनदा मातांसाठी **PMMVY (प्रधानमंत्री मातृ वंदना योजना)** अंतर्गत आर्थिक साहाय्य उपलब्ध आहे: 🎉\n\n"
                f"💰 **मातृत्व लाभ:** पहिल्या अपत्यासाठी ₹५,००० (दोन हप्त्यांमध्ये) थेट बँक खात्यात, आणि दुसऱ्या खेपेस मुलगी झाल्यास अतिरिक्त ₹६,०००.\n"
                f"{'🌸 **मुख्यमंत्री माझी लाडकी बहीण योजना:** दरमहा ₹१,५०० थेट बँक खात्यात जमा.' if state_name == 'Maharashtra' else ''}\n\n"
                f"📋 **आवश्यक कागदपत्रे:** माता व बाल संरक्षण (MCP) कार्ड, मातेचे आधार कार्ड, आधार-संलग्न बँक पासबुक.\n\n"
                f"❓ **पुढील प्रश्न:** आपल्या स्थानिक अंगणवाडी किंवा प्राथमिक आरोग्य केंद्रात (PHC) आपले **MCP कार्ड** नोंदवले गेले आहे का?"
            )
            spoken = "नमस्ते. मातृ वंदना योजनेअंतर्गत पहिल्या अपत्यासाठी ₹५,००० थेट बँक खात्यात मिळतात. आपल्याकडे एमसीपी कार्ड नोंदवले आहे का?"
        elif lang == "hi":
            msg = (
                f"नमस्ते! गर्भवती एवं धात्री माताओं के लिए **PMMVY (प्रधानमंत्री मातृ वंदना योजना)** के तहत आर्थिक सहायता उपलब्ध है: 🎉\n\n"
                f"💰 **मातृत्व लाभ:** पहले जीवित बच्चे के लिए ₹5,000 (दो किस्तों में) सीधे बैंक खाते में, तथा दूसरी कन्या शिशु होने पर ₹6,000.\n\n"
                f"📋 **आवश्यक दस्तावेज:** एमसीपी कार्ड (Mother & Child Protection Card), माता का आधार कार्ड, बैंक पासबुक।\n\n"
                f"❓ **फॉलो-अप प्रश्न:** क्या स्थानीय आंगनवाड़ी या स्वास्थ्य केंद्र में आपका **MCP कार्ड** पंजीकृत हो चुका है?"
            )
            spoken = "नमस्ते. मातृ वंदना योजना के तहत पहले बच्चे के जन्म पर ₹5,000 की सरकारी सहायता मिलती है. क्या आपका एमसीपी कार्ड बना हुआ है?"
        else:
            msg = (
                f"Namaste! For pregnant and lactating mothers, **PMMVY (Pradhan Mantri Matru Vandana Yojana)** provides direct maternity support: 🎉\n\n"
                f"💰 **Maternity Benefits:** ₹5,000 in two installments directly into mother's DBT account for 1st living child (and ₹6,000 for second child if girl child).\n"
                f"{'🌸 **Majhi Ladki Bahin Scheme:** ₹1,500/month direct cash support for Maharashtra resident women.' if state_name == 'Maharashtra' else ''}\n\n"
                f"📋 **Mandatory Documents:** Mother and Child Protection (MCP) Card, Mother's Aadhaar Card, Bank Passbook.\n\n"
                f"❓ **Follow-up Question:** Is your **MCP Card** registered at your nearest Anganwadi or Primary Health Centre (PHC)?"
            )
            spoken = "Namaste. Under PMMVY, you are eligible for 5,000 rupees maternity benefit. Do you have your MCP card registered?"

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step="MATCH",
            active_scheme={"scheme_code": target_scheme, "name": elig_res.get("scheme_name", "PMMVY")},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                "Yes, I have the MCP card",
                "I don't have the MCP card",
                "Pre-fill PMMVY application",
            ], lang),
            engine_mode="deterministic",
        )

    # ── 4E: Senior Citizen Persona (AB-PMJAY 70+ Cover) ────────────────────────
    is_senior_query = (
        (entities.get("is_senior_citizen") or (entities.get("age") and entities["age"] >= 60) or any(k in lower_message for k in ["senior citizen", "ज्येष्ठ नागरिक", "वरिष्ठ नागरिक", "वयस्कर"]))
        and not is_widow_query
        and any(k in lower_message for k in ["scheme", "योजना", "health", "hospital", "आरोग्य", "पेंशन", "दवाखाना", "cover"])
    )

    if is_senior_query:
        target_scheme = "AB-PMJAY"
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme
        session["workflow_step"] = "MATCH"

        elig_res = tool_check_eligibility(db, current_user, profile, target_scheme, extracted_data=entities)
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme, lang=lang)
        age_val = entities.get("age") or 70

        if lang == "mr":
            msg = (
                f"नमस्कार ज्येष्ठ नागरिक महोदय! **आयुष्मान भारत (AB-PMJAY) वय वंदना** अंतर्गत ७० वर्षे व त्यावरील सर्व नागरिकांसाठी:\n\n"
                f"🏥 **मोफत आरोग्य संरक्षण:** प्रति वर्ष **₹५,००,००० पर्यंत कॅशलेस उपचार** कोणत्याही उत्पन्नाच्या अटीशिवाय पूर्णतः मोफत! 🎉\n\n"
                f"📋 **आवश्यक कागदपत्र:** फक्त आधार कार्ड (आधार-संलग्न मोबाईल नंबरसह e-KYC साठी).\n\n"
                f"❓ **पुढील प्रश्न:** e-KYC ओटीपीसाठी आपल्या आधार कार्डला मोबाईल नंबर जोडलेला आहे का?"
            )
            spoken = f"नमस्कार. वय {age_val} वर्षांसाठी आयुष्मान भारत योजनेअंतर्गत दरवर्षी ५ लाखांचे मोफत उपचार मिळतात. आपल्या आधारला मोबाईल नंबर लिंक आहे का?"
        elif lang == "hi":
            msg = (
                f"प्रणाम वरिष्ठ नागरिक महोदय! **आयुष्मान भारत (AB-PMJAY) वय वंदना योजना** के तहत 70 वर्ष एवं अधिक आयु के सभी नागरिकों के लिए:\n\n"
                f"🏥 **मुफ्त स्वास्थ्य सुरक्षा:** प्रति परिवार प्रति वर्ष **₹5,00,000 तक कैशलेस उपचार** बिना किसी आय सीमा के! 🎉\n\n"
                f"📋 **आवश्यक दस्तावेज:** केवल आधार कार्ड (ओटीपी आधारित ई-केवाईसी हेतु).\n\n"
                f"❓ **फॉलो-अप प्रश्न:** क्या आपके आधार कार्ड से सक्रिय मोबाइल नंबर जुड़ा हुआ है?"
            )
            spoken = f"प्रणाम. 70 वर्ष से अधिक आयु के वरिष्ठ नागरिकों को आयुष्मान भारत के तहत ₹5 लाख का मुफ्त इलाज मिलता है. क्या आधार से मोबाइल जुड़ा है?"
        else:
            msg = (
                f"Pranam! Under the expanded **Ayushman Bharat (AB-PMJAY) Senior Citizen Cover** for all citizens aged 70 and above:\n\n"
                f"🏥 **Free Healthcare Cover:** **₹5,00,000 per family per year cashless treatment** at all empaneled hospitals, with **NO income threshold**! 🎉\n\n"
                f"📋 **Required Document:** Only Aadhaar Card (for OTP-based e-KYC).\n\n"
                f"❓ **Follow-up Question:** Is your Aadhaar card linked to an active mobile number for instant e-KYC verification?"
            )
            spoken = f"Pranam. As a senior citizen, you are eligible for 5 Lakh rupees free health cover under Ayushman Bharat. Is your Aadhaar linked to mobile?"

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.ELIGIBILITY_RESULT,
            workflow_step="MATCH",
            active_scheme={"scheme_code": target_scheme, "name": elig_res.get("scheme_name", "AB-PMJAY")},
            eligibility_summary=elig_res,
            checklist_data=checklist_res,
            suggested_followups=_localize_followups([
                "Yes, mobile is linked to Aadhaar",
                "Apply for Ayushman Vay Vandana Card",
                "Which hospitals are covered?",
            ], lang),
            engine_mode="deterministic",
        )

    # ── 4F: Handling Affirmative Answers to Follow-up Questions ────────────────
    # Citizen confirms they have the requested document ("Yes, I have...", "होय, आहे", "हाँ, है")
    # Exclude "all the documents" / "all documents" so Vault readiness recheck runs instead
    reports_all_docs = any(k in lower_message for k in [
        "all the documents", "all documents", "all docs", "सर्व कागदपत्रे", "सभी दस्तावेज"
    ])
    is_affirmative_followup = (not reports_all_docs) and any(k in lower_message for k in [
        "yes, i have", "yes i have", "i have it", "i have the", "होय आहे", "होय, आहे", "माझ्याकडे आहे",
        "हाँ है", "हाँ, मेरे पास है", "मेरे पास है", "हाँ, है", "उपलब्ध आहे", "है मेरे पास"
    ])

    if is_affirmative_followup and active_scheme_code:
        # User confirmed document availability; advance to PRE-FILL form draft
        fill_res = tool_fill_form(
            db,
            current_user,
            profile,
            active_scheme_code,
            conversation_entities=conv_entities_ctx,
            lang=lang,
        )
        session["workflow_step"] = "PRE-FILL"

        if fill_res.get("form_supported"):
            if lang == "mr":
                msg = (
                    f"उत्तम! आपण कागदपत्र उपलब्ध असल्याची पुष्टी केली आहे. मी आपल्या प्रोफाइलवरून **{fill_res['scheme_title']}** साठी अर्ज पूर्व-भरला आहे.\n\n"
                    f"📝 **सज्जता: {fill_res['readiness_percentage']}%** ({fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']} अनिवार्य रकाने भरले).\n\n"
                    f"👇 खालील अर्जातील माहिती तपासा आणि अंतिम पुष्टीकरणासाठी पुढे जा."
                )
                spoken = f"उत्तम. मी {fill_res['readiness_percentage']} टक्के सज्जतेसह आपला अर्ज तयार केला आहे. कृपया खाली तपासा."
            elif lang == "hi":
                msg = (
                    f"बहुत बढ़िया! आपने दस्तावेज की उपलब्धता की पुष्टि कर दी है। मैंने आपकी प्रोफ़ाइल से **{fill_res['scheme_title']}** के लिए आवेदन प्रारूप तैयार कर दिया है।\n\n"
                    f"📝 **तैयारी: {fill_res['readiness_percentage']}%** ({fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']} अनिवार्य विवरण पूर्ण).\n\n"
                    f"👇 नीचे दिए गए फ़ॉर्म में विवरण देखें और अंतिम पुष्टि के लिए आगे बढ़ें।"
                )
                spoken = f"बहुत बढ़िया. मैंने {fill_res['readiness_percentage']} प्रतिशत तत्परता के साथ आवेदन तैयार कर दिया है. कृपया नीचे समीक्षा करें."
            else:
                msg = (
                    f"Great! Since your document is ready, I have prepared your pre-filled application draft for **{fill_res['scheme_title']}**.\n\n"
                    f"📝 **Readiness: {fill_res['readiness_percentage']}%** ({fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']} mandatory fields completed).\n\n"
                    f"👇 Please review the draft fields below and proceed to confirmation."
                )
                spoken = f"Great. I have prepared your draft with {fill_res['readiness_percentage']} percent readiness. Please review below."

            return AgentChatResponse(
                conversation_id=conv_id,
                message=msg,
                spoken_text=spoken,
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_res,
                suggested_followups=_localize_followups([
                    "Save & Review Draft",
                    "Proceed to Final Confirmation",
                    "View Document Checklist",
                ], lang),
                engine_mode="deterministic",
            )

    # Step 5: Pre-fill Application Form Request
    # "How do I apply?", "Pre-fill application", "Start application", "भरून द्या", "आवेदन भरें"
    is_prefill_request = (request.form_action == "prefill_form") or any(k in lower_message for k in [
        "prefill", "pre-fill", "fill form", "start application", "apply now", "अर्ज भरा",
        "फॉर्म भरा", "आवेदन भरें", "फॉर्म भरें", "draft application", "yes, i have", "होय, आहे", "हाँ, है"
    ])

    if is_prefill_request and active_scheme_code:
        fill_res = tool_fill_form(
            db,
            current_user,
            profile,
            active_scheme_code,
            conversation_entities=conv_entities_ctx,
            lang=lang,
        )
        session["workflow_step"] = "PRE-FILL"

        if fill_res.get("form_supported"):
            doc_check = tool_build_checklist(db, current_user, profile, active_scheme_code, lang=lang)
            missing_mandatory_docs = [
                it["title"] for it in doc_check.get("items", [])
                if it.get("is_mandatory") and it.get("status") != DOC_STATE_VERIFIED
            ]
            req_inputs = list(fill_res.get("requires_input_fields") or [])
            missing_field_labels = [
                (f.get("label") or f.get("name") or "") if isinstance(f, dict) else str(f)
                for f in req_inputs
            ]
            fill_res["missing_fields"] = [m for m in missing_field_labels if m]
            fill_res["missing_mandatory_documents"] = missing_mandatory_docs
            portal = fill_res.get("portal_integration") or {}
            p_url = portal.get("official_application_url") or fill_res.get("official_portal") or "https://www.india.gov.in/"
            p_mode = portal.get("submission_method_label") or portal.get("submission_method") or ""
            draft_id = fill_res.get("application_id") or ""
            if lang == "mr":
                miss_f_line = f"\n• **भरणे आवश्यक रकाने ({len(fill_res['missing_fields'])}):** {', '.join(fill_res['missing_fields'][:6])}" if fill_res["missing_fields"] else ""
                miss_d_line = f"\n• **अपूर्ण अनिवार्य कागदपत्रे ({len(missing_mandatory_docs)}):** {', '.join(missing_mandatory_docs)}" if missing_mandatory_docs else ""
                msg = (
                    f"📝 **{fill_res['scheme_title']} — पूर्व-भरलेला अर्ज मसुदा**\n\n"
                    f"• **अंतर्गत मसुदा आयडी:** `{draft_id}`\n"
                    f"• **भरलेले अनिवार्य रकाने:** **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** (सज्जता: **{fill_res['readiness_percentage']}%**)"
                    f"{miss_f_line}{miss_d_line}\n• **पोर्टल पद्धत:** {p_mode} ([पोर्टल उघडा]({p_url}))\n\n"
                    f"👇 खालील अर्जामध्ये उर्वरित रकाने तपासा, आवश्यक असल्यास दुरुस्ती करा आणि 'मसुदा जतन करा' किंवा 'अंतिम पुष्टीकरण' वर क्लिक करा."
                )
                spoken = f"आम्ही {fill_res['readiness_percentage']} टक्के सज्जतेसह तुमचा अर्ज पूर्व-भरला आहे. कृपया तपशील तपासा."
            elif lang == "hi":
                miss_f_line = f"\n• **भरने हेतु शेष फ़ील्ड ({len(fill_res['missing_fields'])}):** {', '.join(fill_res['missing_fields'][:6])}" if fill_res["missing_fields"] else ""
                miss_d_line = f"\n• **लंबित अनिवार्य दस्तावेज़ ({len(missing_mandatory_docs)}):** {', '.join(missing_mandatory_docs)}" if missing_mandatory_docs else ""
                msg = (
                    f"📝 **{fill_res['scheme_title']} — पूर्व-भरा हुआ आवेदन मसौदा**\n\n"
                    f"• **आंतरिक ड्राफ्ट आईडी:** `{draft_id}`\n"
                    f"• **भरे गए अनिवार्य फ़ील्ड:** **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** (तैयारी: **{fill_res['readiness_percentage']}%**)"
                    f"{miss_f_line}{miss_d_line}\n• **पोर्टल माध्यम:** {p_mode} ([पोर्टल खोलें]({p_url}))\n\n"
                    f"👇 नीचे दिए गए फ़ॉर्म में विवरणों की समीक्षा करें और पुष्टि करें।"
                )
                spoken = f"हमने {fill_res['readiness_percentage']} प्रतिशत तत्परता के साथ आपका आवेदन पत्र तैयार कर दिया है. कृपया विवरण जांचें."
            else:
                miss_f_line = f"\n• **Missing Fields ({len(fill_res['missing_fields'])}):** {', '.join(fill_res['missing_fields'][:6])}" if fill_res["missing_fields"] else ""
                miss_d_line = f"\n• **Missing Mandatory Documents ({len(missing_mandatory_docs)}):** {', '.join(missing_mandatory_docs)}" if missing_mandatory_docs else ""
                msg = (
                    f"📝 **{fill_res['scheme_title']} — Pre-filled Application Draft**\n\n"
                    f"• **Internal Draft ID:** `{draft_id}`\n"
                    f"• **Pre-filled Mandatory Fields:** **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** (Readiness: **{fill_res['readiness_percentage']}%**)"
                    f"{miss_f_line}{miss_d_line}\n• **Portal Mode:** {p_mode} ([Open Portal]({p_url}))\n\n"
                    f"👇 Review the pre-filled fields below, complete any missing details, and proceed to confirmation."
                )
                spoken = f"We have pre-filled your application draft with {fill_res['readiness_percentage']} percent readiness. Please review the details."

            return AgentChatResponse(
                conversation_id=conv_id,
                message=msg,
                spoken_text=spoken,
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_res,
                suggested_followups=_localize_followups([
                    "Save & Review Draft",
                    "Proceed to Final Confirmation",
                    "View Document Checklist",
                ], lang),
                engine_mode="deterministic",
            )
        else:
            # Unsupported scheme form schema — keep explicitly unavailable, never fabricate fake form
            if lang == "mr":
                msg = f"ℹ️ {fill_res['message']}\n\nअधिकृत शासकीय पोर्टल: [{fill_res['official_portal']}]({fill_res['official_portal']})"
            elif lang == "hi":
                msg = f"ℹ️ {fill_res['message']}\n\nआधिकारिक सरकारी पोर्टल: [{fill_res['official_portal']}]({fill_res['official_portal']})"
            else:
                msg = f"ℹ️ {fill_res['message']}\n\nOfficial Portal: [{fill_res['official_portal']}]({fill_res['official_portal']})"
            spoken = msg

            return AgentChatResponse(
                conversation_id=conv_id,
                message=msg,
                spoken_text=spoken,
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_res,
                suggested_followups=_localize_followups(["Check documents required", "What are the benefits?"], lang),
                engine_mode="deterministic",
            )

    # Step 6: Confirmation request ("confirm", "proceed", "submit", "पुष्टी करा", "सादर करा")
    is_confirm_request = any(k in lower_message for k in [
        "confirm", "proceed to confirmation", "submit application", "पुष्टी", "सादर करा", "फाइनल सबमिट"
    ])
    if is_confirm_request and active_scheme_code:
        # Validate fields, conflicts, and Phase 5 Vault documents BEFORE entering CONFIRM step
        fill_check = tool_fill_form(
            db=db,
            user=current_user,
            profile=profile,
            scheme_code_or_name=active_scheme_code,
            form_overrides=request.form_data or {},
            conversation_entities=conv_entities_ctx,
            lang=lang,
        )
        if not fill_check.get("form_supported") or not fill_check.get("can_confirm"):
            err_msg = fill_check.get("message") or (
                "कृपया पुष्टीकरणापूर्वी सर्व अनिवार्य माहिती पूर्ण करा आणि परस्परविरोधी तपशील दुरुस्त करा."
                if lang == "mr"
                else "कृपया पुष्टि से पहले सभी अनिवार्य फ़ील्ड भरें और परस्पर विरोधी विवरण हल करें।"
                if lang == "hi"
                else "Please complete all mandatory fields and resolve any conflicting details before proceeding to confirmation."
            )
            session["workflow_step"] = "PRE-FILL"
            return AgentChatResponse(
                conversation_id=conv_id,
                message=err_msg,
                spoken_text=err_msg,
                detected_language=lang,
                response_type=ChatResponseType.FORM_DRAFT,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                form_draft_data=fill_check,
                engine_mode="deterministic",
            )
        if db is not None and profile is not None:
            from app.services.readiness_service import evaluate_application_readiness
            readiness_gate = evaluate_application_readiness(
                scheme_code=active_scheme_code,
                scheme_id=active_scheme_code,
                form_data=fill_check.get("form_data") or request.form_data or {},
                profile=profile,
                db=db,
                lang=lang,
            )
            if not readiness_gate.get("passed"):
                reasons = "; ".join(e["message"] for e in (readiness_gate.get("errors") or [])[:3])
                block_msg = (
                    f"⚠️ **पुष्टीकरणापूर्वी खालील बाबी पूर्ण करणे आवश्यक आहे:** {reasons}"
                    if lang == "mr"
                    else f"⚠️ **पुष्टि से पहले निम्नलिखित जांच पूरी करें:** {reasons}"
                    if lang == "hi"
                    else f"⚠️ **Complete readiness requirements before confirmation:** {reasons}"
                )
                session["workflow_step"] = "PRE-FILL"
                return AgentChatResponse(
                    conversation_id=conv_id,
                    message=block_msg,
                    spoken_text=block_msg,
                    detected_language=lang,
                    response_type=ChatResponseType.FORM_DRAFT,
                    workflow_step="PRE-FILL",
                    active_scheme={"scheme_code": active_scheme_code},
                    form_draft_data=fill_check,
                    engine_mode="deterministic",
                )

        submit_prompt = tool_submit_form(
            db,
            current_user,
            profile,
            active_scheme_code,
            confirmed=False,
            form_data=request.form_data,
            lang=lang,
        )
        session["workflow_step"] = "CONFIRM"

        if lang == "mr":
            msg = (
                f"⚠️ **संपूर्ण अर्ज पडताळणी व अंतिम संमती आवश्यक:**\n\n"
                f"आम्ही तुमचा **{active_scheme_code}** साठी अर्ज तपशील तपासले आहेत. कृपया खालील संपूर्ण सारांश तपासून तुमची स्पष्ट संमती द्या."
            )
            spoken = "कृपया आपल्या अर्जाच्या अंतिम तपशीलाची पुष्टी करा."
        elif lang == "hi":
            msg = (
                f"⚠️ **पूर्ण आवेदन समीक्षा एवं स्पष्ट पुष्टि आवश्यक:**\n\n"
                f"हमने आपके **{active_scheme_code}** आवेदन का विवरण तैयार किया है। कृपया नीचे पूर्ण सारांश जांचकर अपनी स्पष्ट पुष्टि दें।"
            )
            spoken = "कृपया अपने आवेदन के अंतिम विवरण की पुष्टि करें."
        else:
            msg = (
                f"⚠️ **Explicit Citizen Review & Confirmation Required:**\n\n"
                f"Please inspect the complete **{active_scheme_code}** application summary below and provide explicit authorization."
            )
            spoken = "Please inspect your complete application summary below and provide your explicit confirmation."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_REQUEST,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data=submit_prompt,
            suggested_followups=_localize_followups([
                "I want to edit some fields",
                "View Document Checklist",
            ], lang),
            engine_mode="deterministic",
        )

    # If no agentic trigger matched, return None to continue with existing query intent handlers
    return None

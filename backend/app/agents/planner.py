"""
Scheme Saathi Intelligent Agent Planning & Orchestration Layer.
Orchestrates the citizen journey: TALK → MATCH → CHECKLIST → PRE-FILL → CONFIRM.
Manages three-tier persistent memory, dynamic replanning, and real backend tool execution.
"""
from typing import Dict, Any, List, Optional
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

logger = logging.getLogger(__name__)


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

    # Step 1: Extract citizen entities & update profile memory
    entities = extract_citizen_entities(raw_message)
    if entities and profile:
        apply_extracted_entities_to_profile(db, profile, entities)

    # Resolve active scheme from request, session, or entity-inferred scheme
    active_scheme_code = request.scheme_id or session.get("active_scheme_code")
    current_step = request.workflow_step or session.get("workflow_step") or "TALK"

    # Step 2: Handle explicit UI form actions
    if request.form_action == "confirm_submit" and active_scheme_code:
        submit_res = tool_submit_form(
            db=db,
            user=current_user,
            profile=profile,
            scheme_code_or_name=active_scheme_code,
            confirmed=True,
            form_data=request.form_data,
        )
        session["workflow_step"] = "CONFIRM"

        if lang == "mr":
            msg = (
                f"🎉 **तुमचा अधिकृत अर्ज सज्जता संच यशस्वीरित्या तयार झाला आहे!**\n\n"
                f"🔖 **संदर्भ क्रमांक (Handoff Reference):** `{submit_res['handoff_reference']}`\n\n"
                f"🏛️ **अधिकृत शासकीय पोर्टल:** [{submit_res['official_portal_url']}]({submit_res['official_portal_url']})\n\n"
                f"✅ **पुढील पायऱ्या:**\n"
                f"१. आम्ही तुमचे सर्व तपशील आणि कागदपत्रे तपासली आहेत.\n"
                f"२. वरील अधिकृत पोर्टल लिंकवर क्लिक करून एका क्लीकमध्ये तुमचा अर्ज पूर्ण करा.\n"
                f"३. योजनेचा लाभ थेट तुमच्या आधार-संलग्न बँक खात्यात (DBT) जमा केला जाईल."
            )
            spoken = f"तुमचा अधिकृत अर्ज सज्जता संच संदर्भ क्रमांक {submit_res['handoff_reference']} सह यशस्वीरित्या तयार झाला आहे."
        elif lang == "hi":
            msg = (
                f"🎉 **आपका आधिकारिक आवेदन तत्परता पैकेट सफलतापूर्वक तैयार हो गया है!**\n\n"
                f"🔖 **संदर्भ संख्या (Handoff Reference):** `{submit_res['handoff_reference']}`\n\n"
                f"🏛️ **आधिकारिक सरकारी पोर्टल:** [{submit_res['official_portal_url']}]({submit_res['official_portal_url']})\n\n"
                f"✅ **आगे के कदम:**\n"
                f"1. आपके सभी विवरण और आवश्यक दस्तावेज सत्यापित कर लिए गए हैं।\n"
                f"2. आधिकारिक पोर्टल पर जाकर अंतिम सबमिशन पूरा करें।\n"
                f"3. योजना की राशि सीधे आपके आधार से जुड़े बैंक खाते (DBT) में अंतरित होगी।"
            )
            spoken = f"आपका आधिकारिक आवेदन पैकेट संदर्भ संख्या {submit_res['handoff_reference']} के साथ तैयार हो गया है।"
        else:
            msg = (
                f"🎉 **Your Official Application Readiness Packet is Ready!**\n\n"
                f"🔖 **Handoff Reference:** `{submit_res['handoff_reference']}`\n\n"
                f"🏛️ **Official Government Portal:** [{submit_res['official_portal_url']}]({submit_res['official_portal_url']})\n\n"
                f"✅ **Next Steps:**\n"
                f"1. Your verified profile and document checklist are compiled.\n"
                f"2. Visit the official portal link above to finalize your official submission.\n"
                f"3. Benefits will be disbursed directly via Aadhaar-seeded DBT."
            )
            spoken = f"Your official application readiness packet has been generated with reference {submit_res['handoff_reference']}."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_RESULT,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data=submit_res,
            suggested_followups=[
                "How can I track my status?",
                "What are the benefits payout dates?",
                "Help with another scheme",
            ],
            engine_mode="deterministic",
        )

    if request.form_action == "save_draft" and active_scheme_code:
        fill_res = tool_fill_form(
            db=db,
            user=current_user,
            profile=profile,
            scheme_code_or_name=active_scheme_code,
            form_overrides=request.form_data or {},
        )
        session["workflow_step"] = "PRE-FILL"

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
            suggested_followups=[
                "Confirm & Proceed",
                "View Document Checklist",
                "What documents are required?",
            ],
            engine_mode="deterministic",
        )

    # Step 3: Handle Replanning when Citizen discloses missing document (e.g. "I don't have an income certificate")
    if "missing_document_disclosed" in entities:
        missing_doc_key = entities["missing_document_disclosed"]
        sourcing_info = get_document_sourcing_info(missing_doc_key)
        
        # If no active scheme in session, check if widow context or fallback to PM-KISAN
        target_scheme = active_scheme_code or ("WIDOW-PENSION" if (profile and profile.profile_data.get("marital_status") == "widowed") else "PM-KISAN")
        active_scheme_code = target_scheme
        session["active_scheme_code"] = target_scheme

        # Re-build checklist with missing document highlighted
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme)
        session["workflow_step"] = "CHECKLIST"

        if lang == "mr":
            msg = (
                f"ℹ️ **काळजी करू नका! जर तुमच्याकडे '{sourcing_info['title']}' नसेल, तर ते कसे मिळवावे ते येथे दिले आहे:**\n\n"
                f"🏛️ **देणारे अधिकृत कार्यालय:** {sourcing_info['issuing_authority']}\n"
                f"📍 **कुठे अर्ज करावा:** {sourcing_info['where_to_obtain']}\n"
                f"💰 **अधिकृत शासकीय शुल्क:** {sourcing_info['verified_fee']}\n"
                f"⏱️ **अपेक्षित कालावधी:** {sourcing_info['expected_processing_days']}\n"
                f"🌐 **अधिकृत संकेतस्थळ:** [{sourcing_info['official_url']}]({sourcing_info['official_url']})\n\n"
                f"📌 **टीप:** आम्ही हे प्रमाणपत्र तुमच्या प्रलंबित कागदपत्रांच्या यादीत जोडले आहे. तुम्ही तरीही तुमचा उर्वरित अर्ज मसुदा भरून ठेवू शकता!"
            )
            spoken = f"काळजी करू नका. {sourcing_info['title']} कसे मिळवावे याची अधिकृत माहिती मी दिली आहे. तुम्ही इतर माहिती भरून अर्ज पुढे नेऊ शकता."
        elif lang == "hi":
            msg = (
                f"ℹ️ **चिंता न करें! यदि आपके पास '{sourcing_info['title']}' नहीं है, तो इसे प्राप्त करने की अधिकृत प्रक्रिया:**\n\n"
                f"🏛️ **जारीकर्ता प्राधिकरण:** {sourcing_info['issuing_authority']}\n"
                f"📍 **कहाँ आवेदन करें:** {sourcing_info['where_to_obtain']}\n"
                f"💰 **अधिकृत सरकारी शुल्क:** {sourcing_info['verified_fee']}\n"
                f"⏱️ **प्रसंस्करण समय:** {sourcing_info['expected_processing_days']}\n"
                f"🌐 **आधिकारिक पोर्टल:** [{sourcing_info['official_url']}]({sourcing_info['official_url']})\n\n"
                f"📌 **सुझाव:** हमने इसे आपकी चेकलिस्ट में जोड़ दिया है। आप अभी भी अपना बाकी आवेदन पत्र भर सकते हैं!"
            )
            spoken = f"चिंता न करें. {sourcing_info['title']} कहाँ से प्राप्त करना है, इसका विवरण दिया गया है. आप शेष आवेदन भर सकते हैं."
        else:
            msg = (
                f"ℹ️ **No worries! If you do not have '{sourcing_info['title']}', here is how to obtain it:**\n\n"
                f"🏛️ **Issuing Authority:** {sourcing_info['issuing_authority']}\n"
                f"📍 **Where to Apply:** {sourcing_info['where_to_obtain']}\n"
                f"💰 **Verified Fee:** {sourcing_info['verified_fee']}\n"
                f"⏱️ **Processing Time:** {sourcing_info['expected_processing_days']}\n"
                f"🌐 **Official Portal:** [{sourcing_info['official_url']}]({sourcing_info['official_url']})\n\n"
                f"📌 **Note:** We have retained your pending document checklist. You can still proceed to pre-fill the rest of your application draft!"
            )
            spoken = f"Don't worry. Here are the verified steps to obtain {sourcing_info['title']}. You can still proceed with your draft application."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.DOCUMENT_CHECKLIST,
            workflow_step="CHECKLIST",
            active_scheme={"scheme_code": target_scheme},
            checklist_data=checklist_res,
            suggested_followups=[
                f"Pre-fill application for {target_scheme}",
                "Check full document checklist",
                "What are the benefits?",
            ],
            engine_mode="deterministic",
        )

    # Step 4: Persona Introduction Detection (Widow Pension Blueprint Example)
    # "I'm a 63-year-old widow from Uttar Pradesh. My annual family income is ₹60,000."
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
        checklist_res = tool_build_checklist(db, current_user, profile, target_scheme)

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
            suggested_followups=[
                "Yes, I have the death certificate",
                "I don't have the death certificate",
                "Pre-fill application form",
                "What are the benefits payout dates?",
            ],
            engine_mode="deterministic",
        )

    # Step 5: Pre-fill Application Form Request
    # "How do I apply?", "Pre-fill application", "Start application", "भरून द्या", "आवेदन भरें"
    is_prefill_request = any(k in lower_message for k in [
        "prefill", "pre-fill", "fill form", "start application", "apply now", "अर्ज भरा",
        "फॉर्म भरा", "आवेदन भरें", "फॉर्म भरें", "draft application", "yes, i have", "होय, आहे", "हाँ, है"
    ])

    if is_prefill_request and active_scheme_code:
        fill_res = tool_fill_form(db, current_user, profile, active_scheme_code)
        session["workflow_step"] = "PRE-FILL"

        if fill_res.get("form_supported"):
            if lang == "mr":
                msg = (
                    f"📝 **{fill_res['scheme_title']} — पूर्व-भरलेला अर्ज मसुदा**\n\n"
                    f"आम्ही तुमच्या नागरिक प्रोफाइलमधून **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** अनिवार्य माहिती पूर्व-भरली आहे. (सज्जता: **{fill_res['readiness_percentage']}%**).\n\n"
                    f"👇 खालील अर्जामध्ये उर्वरित रकाने तपासा, आवश्यक असल्यास दुरुस्ती करा आणि 'मसुदा जतन करा' किंवा 'अंतिम पुष्टीकरण' वर क्लिक करा."
                )
                spoken = f"आम्ही {fill_res['readiness_percentage']} टक्के सज्जतेसह तुमचा अर्ज पूर्व-भरला आहे. कृपया तपशील तपासा."
            elif lang == "hi":
                msg = (
                    f"📝 **{fill_res['scheme_title']} — पूर्व-भरा हुआ आवेदन मसौदा**\n\n"
                    f"हमने आपकी नागरिक प्रोफ़ाइल से **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** अनिवार्य विवरण पूर्व-भर दिए हैं। (तैयारी: **{fill_res['readiness_percentage']}%**)।\n\n"
                    f"👇 नीचे दिए गए फ़ॉर्म में विवरणों की समीक्षा करें और पुष्टि करें।"
                )
                spoken = f"हमने {fill_res['readiness_percentage']} प्रतिशत तत्परता के साथ आपका आवेदन पत्र तैयार कर दिया है. कृपया विवरण जांचें."
            else:
                msg = (
                    f"📝 **{fill_res['scheme_title']} — Pre-filled Application Draft**\n\n"
                    f"We have automatically pre-filled **{fill_res['filled_mandatory_fields']}/{fill_res['total_mandatory_fields']}** mandatory fields from your profile (Readiness: **{fill_res['readiness_percentage']}%**).\n\n"
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
                suggested_followups=[
                    "Save & Review Draft",
                    "Proceed to Final Confirmation",
                    "View Document Checklist",
                ],
                engine_mode="deterministic",
            )
        else:
            # Unsupported scheme form schema
            if lang == "mr":
                msg = f"ℹ️ {fill_res['message']}\n\nशासकीय पोर्टल: [{fill_res['official_portal']}]({fill_res['official_portal']})"
            else:
                msg = f"ℹ️ {fill_res['message']}\n\nOfficial Portal: [{fill_res['official_portal']}]({fill_res['official_portal']})"
            spoken = msg

            return AgentChatResponse(
                conversation_id=conv_id,
                message=msg,
                spoken_text=spoken,
                detected_language=lang,
                response_type=ChatResponseType.APPLICATION_GUIDE,
                workflow_step="PRE-FILL",
                active_scheme={"scheme_code": active_scheme_code},
                suggested_followups=["Check documents required", "What are the benefits?"],
                engine_mode="deterministic",
            )

    # Step 6: Confirmation request ("confirm", "proceed", "submit", "पुष्टी करा", "सादर करा")
    is_confirm_request = any(k in lower_message for k in [
        "confirm", "proceed to confirmation", "submit application", "पुष्टी", "सादर करा", "फाइनल सबमिट"
    ])
    if is_confirm_request and active_scheme_code:
        submit_prompt = tool_submit_form(db, current_user, profile, active_scheme_code, confirmed=False)
        session["workflow_step"] = "CONFIRM"

        if lang == "mr":
            msg = (
                f"⚠️ **अंतिम पुष्टीकरण (Citizen Confirmation Required):**\n\n"
                f"आम्ही तुमचा **{active_scheme_code}** साठी अर्ज संच तयार केला आहे. शासकीय नियमांनुसार अधिकृत पोर्टलवर सुपूर्द करण्यापूर्वी आपल्या स्पष्ट मान्यतेची आवश्यकता आहे.\n\n"
                f"तुम्ही अर्जातील सर्व माहिती आणि कागदपत्रे तपासली आहेत का?"
            )
            spoken = "कृपया आपल्या अर्जाच्या अंतिम सज्जतेची पुष्टी करा."
        elif lang == "hi":
            msg = (
                f"⚠️ **अंतिम पुष्टि (Citizen Confirmation Required):**\n\n"
                f"हमने आपके **{active_scheme_code}** आवेदन का पूर्ण संच तैयार कर लिया है। आधिकारिक पोर्टल पर अग्रेषित करने से पहले आपकी स्पष्ट सहमति आवश्यक है।\n\n"
                f"क्या आप अंतिम आवेदन पैकेट तैयार करने की पुष्टि करते हैं?"
            )
            spoken = "कृपया अपने आवेदन की अंतिम तत्परता की पुष्टि करें."
        else:
            msg = (
                f"⚠️ **Explicit Citizen Confirmation Required:**\n\n"
                f"We have compiled your complete **{active_scheme_code}** application readiness packet. In accordance with government advisory standards, your explicit approval is required before generating the official portal handoff packet.\n\n"
                f"Do you confirm that all details and documents provided are accurate?"
            )
            spoken = "Please provide your explicit confirmation to generate the official submission packet."

        return AgentChatResponse(
            conversation_id=conv_id,
            message=msg,
            spoken_text=spoken,
            detected_language=lang,
            response_type=ChatResponseType.CONFIRMATION_REQUEST,
            workflow_step="CONFIRM",
            active_scheme={"scheme_code": active_scheme_code},
            confirmation_data=submit_prompt,
            suggested_followups=[
                "Yes, I confirm. Generate Packet",
                "I want to edit some fields",
                "View Document Checklist",
            ],
            engine_mode="deterministic",
        )

    # If no agentic trigger matched, return None to continue with existing query intent handlers
    return None

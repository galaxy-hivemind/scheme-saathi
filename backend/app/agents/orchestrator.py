"""
Scheme Saathi Conversational Intelligence & Gemini Tool-Calling Orchestrator.

Unifies the citizen journey inside a single persistent conversation:
- Real Google Gemini Function Calling (`FunctionDeclaration` + multi-turn tool loop)
  connected exclusively to real backend tools in `tool_registry.py`.
- Deterministic offline / fallback tool orchestrator executing the exact same
  real backend functions when Gemini is unconfigured or unavailable.
- Anaphoric & ordinal reference resolution ('it', 'that scheme', 'the second
  scheme', 'the second document', 'what happens next?') in English, Hindi & Marathi.
- Strict factual grounding, citizen isolation, and zero re-asking of known profile data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatResponseType,
    SchemeCardSummary,
)
from app.agents.form_schemas import SCHEME_CODE_ALIASES
from app.agents.tools import extract_citizen_entities
from app.agents.tool_registry import (
    ToolExecutionContext,
    execute_backend_tool,
    extract_known_profile_attributes,
    get_gemini_tool_declarations,
    _resolve_doc_key_for_scheme,
)
from app.services.document_guidance_service import (
    build_missing_document_guidance,
    format_document_guidance_response,
    identify_document_key,
)
from app.services.language_registry import get_localized_ministry, get_localized_scheme_metadata

logger = logging.getLogger(__name__)

MAX_GEMINI_TOOL_HOPS = 5

ORDINAL_WORDS: Dict[str, int] = {
    "first": 1, "1st": 1, "पहला": 1, "पहली": 1, "पहिले": 1, "पहिल्या": 1, "प्रथम": 1,
    "second": 2, "2nd": 2, "दूसरा": 2, "दूसरी": 2, "दुसरे": 2, "दुसरी": 2, "दुसऱ्या": 2,
    "third": 3, "3rd": 3, "तीसरा": 3, "तीसरी": 3, "तिसरे": 3, "तिसऱ्या": 3,
    "fourth": 4, "4th": 4, "चौथा": 4, "चौथी": 4, "चौथे": 4, "चौथ्या": 4,
    "fifth": 5, "5th": 5, "पांचवा": 5, "पांचवी": 5, "पाचवे": 5, "पाचवी": 5,
    "sixth": 6, "6th": 6,
}


def _clean_markdown_for_speech(text: str, lang: str = "en") -> str:
    """Produces clean, full-content TTS speech text without markdown punctuation."""
    if not text:
        return ""

    def _link_repl(match: re.Match) -> str:
        label = match.group(1).strip()
        if label.startswith(("http://", "https://")):
            return (
                "अधिकृत संकेतस्थळावर" if lang == "mr"
                else "आधिकारिक पोर्टल पर" if lang == "hi"
                else "on the official portal"
            )
        return label

    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_repl, text)
    cleaned = re.sub(r"\s*\(\s*https?://[^\s)]+\s*\)", "", cleaned)
    cleaned = re.sub(r"https?://[^\s)]+", "", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF✅❌⚠️📝💰🏛️📌🌐🔗🔍⏳🎯🔄✏️]", "", cleaned)
    cleaned = re.sub(r"^[ \t]*[•●○■◆]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[ \t]*[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _localize(lang: str, en: str, hi: str, mr: str) -> str:
    if lang == "hi":
        return hi
    if lang == "mr":
        return mr
    return en


def _language_script_valid(text: str, lang: str) -> bool:
    """Checks basic script hygiene so Gemini never leaks Devanagari into pure English replies."""
    if not text or not text.strip():
        return False
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    if lang == "en" and has_devanagari:
        return False
    if lang in ("hi", "mr") and not has_devanagari:
        return False
    return True


def _detect_explicit_scheme(message: str, all_schemes: List[Scheme]) -> Optional[str]:
    """Detects an explicitly named scheme code or alias in user message."""
    lower = message.lower()

    # Fast exact code match (longest first to avoid substring collisions)
    for code in sorted({s.scheme_code for s in all_schemes} | set(SCHEME_CODE_ALIASES.keys()), key=len, reverse=True):
        if not code:
            continue
        pattern = r"(?<![A-Za-z0-9])" + re.escape(code.lower()).replace(r"\-", r"[-\s]?") + r"(?![A-Za-z0-9])"
        if re.search(pattern, lower):
            return SCHEME_CODE_ALIASES.get(code.upper(), code.upper())

    keyword_aliases = {
        "PM-KISAN": ["pm kisan", "pm-kisan", "kisan samman", "पीएम किसान", "पीएम-किसान", "किसान सम्मान"],
        "KCC": ["kisan credit", "kcc", "किसान क्रेडिट", "केसीसी"],
        "AB-PMJAY": ["ayushman bharat", "ayushman", "pmjay", "pm-jay", "आयुष्मान भारत", "आयुष्मान"],
        "PMAY-G": ["awas yojana", "pradhan mantri awas", "pmay", "pmay-g", "आवास योजना", "प्रधानमंत्री आवास", "घरकुल"],
        "APY": ["atal pension", "apy", "अटल पेंशन", "अटल पेन्शन"],
        "NSP-CSSS": ["national scholarship", "nsp", "central sector scheme of scholarship", "राष्ट्रीय छात्रवृत्ति", "शिष्यवृत्ती"],
        "PMMVY": ["matru vandana", "pmmvy", "मातृ वंदना", "मातृवंदना"],
        "PM-SVANIDHI": ["svanidhi", "street vendor", "स्वनिधि", "स्वनिधी"],
        "MLBY-MH": ["ladki bahin", "majhi ladki", "लाडकी बहीण", "माझी लाडकी"],
        "WIDOW-PENSION": ["widow pension", "ignwps", "विधवा पेंशन", "विधवा निवृत्तीवेतन"],
        "PMUY": ["ujjwala", "उज्ज्वला"],
        "PMJDY": ["jan dhan", "जन धन"],
        "PMJJBY": ["jeevan jyoti", "जीवन ज्योति"],
        "PMSBY": ["suraksha bima", "सुरक्षा बीमा"],
        "SSY": ["sukanya samriddhi", "सुकन्या समृद्धि"],
        "PM-VISHWAKARMA": ["vishwakarma", "विश्वकर्मा"],
        "MGNREGA": ["mgnrega", "nrega", "मनरेगा", "नरेगा"],
        "MUDRA": ["mudra", "pmmy", "मुद्रा"],
        "PMFBY": ["fasal bima", "फसल बीमा", "पीक विमा"],
    }
    for code, cues in keyword_aliases.items():
        if any(cue in lower for cue in cues):
            return code

    for s in all_schemes:
        if s.name and len(s.name) > 5 and s.name.lower() in lower:
            return s.scheme_code
    return None


def _extract_ordinal_index(text: str, target_noun: str) -> Optional[int]:
    """
    Extracts 1-based ordinal reference for 'scheme' or 'document'
    (e.g. 'the second scheme', '2nd document', 'दूसरा दस्तावेज़').
    """
    lower = text.lower()
    noun_cues = (
        ("scheme", "schemes", "yojana", "one", "option", "योजना")
        if target_noun == "scheme"
        else ("document", "documents", "doc", "docs", "दस्तावेज", "दस्तावेज़", "कागदपत्र", "कागदपत्रे", "कागजात", "one", "item")
    )
    if not any(n in lower for n in noun_cues):
        return None

    for word, idx in ORDINAL_WORDS.items():
        if re.search(rf"(?<![\w\u0900-\u097F]){re.escape(word)}(?![\w\u0900-\u097F])", lower):
            return idx

    num_match = re.search(r"(?:number|no\.?|#|क्रमांक)?\s*([1-9])\b", lower)
    if num_match and any(n in lower for n in noun_cues):
        # Avoid matching numbers inside 7/12 extract or ₹ amounts
        if "7/12" not in lower and "12th" not in lower:
            return int(num_match.group(1))
    return None


def resolve_conversational_references(
    message: str,
    session: Dict[str, Any],
    all_schemes: List[Scheme],
    request_scheme_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolves explicit mentions, ordinal indexes, anaphoric pronouns ('it', 'that scheme',
    'the second document'), missing document disclosures, and workflow transitions
    strictly against the current user's session memory.
    """
    lower = message.lower().strip()
    entities = extract_citizen_entities(message)

    explicit_scheme = _detect_explicit_scheme(message, all_schemes)
    if not explicit_scheme and request_scheme_id:
        for s in all_schemes:
            if str(getattr(s, "id", "")) == request_scheme_id or s.scheme_code.upper() == request_scheme_id.upper():
                explicit_scheme = s.scheme_code
                break

    scheme_list: List[Dict[str, Any]] = list(
        session.get("last_scheme_list") or session.get("last_eligibility_results") or []
    )
    checklist_items: List[Dict[str, Any]] = list(
        (session.get("last_checklist") or {}).get("items") or []
    )

    ordinal_scheme_idx = _extract_ordinal_index(message, "scheme") if not explicit_scheme else None
    ordinal_scheme_code: Optional[str] = None
    ordinal_scheme_out_of_range = False
    if ordinal_scheme_idx is not None:
        if 1 <= ordinal_scheme_idx <= len(scheme_list):
            ordinal_scheme_code = scheme_list[ordinal_scheme_idx - 1].get("scheme_code")
        else:
            ordinal_scheme_out_of_range = True

    ordinal_doc_idx = _extract_ordinal_index(message, "document")
    resolved_doc_item: Optional[Dict[str, Any]] = None
    ordinal_doc_out_of_range = False
    if ordinal_doc_idx is not None and checklist_items:
        if 1 <= ordinal_doc_idx <= len(checklist_items):
            resolved_doc_item = checklist_items[ordinal_doc_idx - 1]
        else:
            ordinal_doc_out_of_range = True

    # Scheme anaphora detection
    has_scheme_anaphora = any(
        re.search(pat, lower)
        for pat in (
            r"\bit\b", r"\bits\b", r"\bthat scheme\b", r"\bthis scheme\b", r"\bthe scheme\b", r"\bsame scheme\b",
            r"या योजने", r"त्या योजने", r"तिच्या", r"तिची", r"तिचे",
            r"इस योजना", r"उस योजना", r"इसके", r"उसके",
        )
    )

    # Doc anaphora ('that document', 'it' when preceded by a doc check / missing doc)
    has_doc_anaphora = any(
        re.search(pat, lower)
        for pat in (
            r"\bthat document\b", r"\bthis document\b", r"\bthe document\b", r"\bmissing document\b",
            r"\bthose documents\b", r"\bremaining documents\b", r"ते कागदपत्र", r"त्या कागदपत्र",
            r"उस दस्तावेज", r"उस दस्तावेज़", r"यह दस्तावेज",
        )
    )

    # Detect category cues for open discovery
    category_hint: Optional[str] = None
    if any(k in lower for k in ["farmer", "farming", "agriculture", "kisan", "किसान", "शेतकरी", "शेती"]):
        category_hint = "agriculture"
    elif any(k in lower for k in ["student", "scholarship", "education", "छात्र", "विद्यार्थी", "शिक्षण"]):
        category_hint = "education"
    elif any(k in lower for k in ["health", "hospital", "medical", "स्वास्थ्य", "आरोग्य"]):
        category_hint = "health"
    elif any(k in lower for k in ["woman", "women", "mahila", "maternity", "महिला", "स्त्री"]):
        category_hint = "women_welfare"
    elif any(k in lower for k in ["house", "housing", "awas", "घर", "आवास"]):
        category_hint = "housing"

    # Missing document disclosure (named OR ordinal like "I don't have the second document")
    negative_doc_cues = (
        "don't have", "do not have", "don’t have", "missing", "without", "lost my",
        "not have", "haven't got", "unable to get", "can't get", "cannot get",
        "cannot obtain", "can't obtain",
        "नाही", "नाहीये", "नहीं है", "नही है", "उपलब्ध नाही", "उपलब्ध नहीं",
    )
    disclosed_missing_doc = entities.get("missing_document_disclosed")
    if not disclosed_missing_doc and resolved_doc_item and any(c in lower for c in negative_doc_cues):
        disclosed_missing_doc = resolved_doc_item.get("document_type")
    if not disclosed_missing_doc and checklist_items and any(c in lower for c in negative_doc_cues):
        # Try semantic match against active checklist (e.g. "land possession certificate" -> land_records)
        matched_item = _resolve_doc_key_for_scheme(message, checklist_items)
        if matched_item:
            disclosed_missing_doc = matched_item.get("document_type")
    if not disclosed_missing_doc and any(c in lower for c in negative_doc_cues):
        inferred_doc = identify_document_key(message)
        if inferred_doc:
            disclosed_missing_doc = inferred_doc
        else:
            # Capture explicitly named unrecognized document phrases safely (e.g. "... clearance certificate")
            noun_match = re.search(
                r"(?:don['’]?t have|do not have|not have|missing|lost my|without|haven['’]?t got)\s+(?:a|an|my|the)?\s*([a-z0-9\s\-/]+?\b(?:certificate|card|record|records|document|extract|passbook|permit|license|slip|report|proof|marksheet)\b)",
                lower,
            )
            if noun_match:
                disclosed_missing_doc = noun_match.group(1).strip()

    # Document preparation follow-up focus & conversational resolution
    last_discussed_doc: Optional[Dict[str, Any]] = session.get("last_discussed_document")
    explicit_named_doc = identify_document_key(message)

    doc_followup_focus: Optional[str] = None
    is_scheme_apply_or_benefit = (
        bool(explicit_scheme or ordinal_scheme_code)
        or any(
            k in lower
            for k in (
                "scheme", "yojana", "benefit", "benefits", "pension", "subsidy",
                "योजना", "लाभ", "फायदे", "पेन्शन", "पेंशन",
            )
        )
    )
    if any(
        k in lower
        for k in (
            "what if i can't", "what if i cannot", "what if i cant", "what if i don't get",
            "what if i do not get", "unable to obtain", "cannot obtain", "can't obtain",
            "if it is unavailable", "alternative for", "any alternative", "instead of this document",
            "instead of that document", "नहीं मिल", "नहीं बन पाया", "विकल्प", "नाही मिळाले तर", "पर्याय",
        )
    ):
        doc_followup_focus = "fallback"
    elif any(
        k in lower
        for k in (
            "how much will it cost", "how much does it cost", "how much cost",
            "what is the cost", "what is the fee", "what are the fees", "any fee",
            "fee for", "fees for", "charges for", "will it cost", "does it cost",
            "कितना खर्च", "कितना शुल्क", "कितनी फीस", "फीस कितनी", "शुल्क",
            "किती खर्च", "फी किती", "शुल्क किती",
        )
    ) and not any(k in lower for k in ("benefit", "pension", "subsidy", "receive", "योजना", "लाभ")):
        doc_followup_focus = "cost"
    elif any(
        k in lower
        for k in (
            "where do i apply", "where can i apply", "where should i apply", "where to apply",
            "where do i get", "where can i get", "where to get", "where to obtain",
            "which office", "which portal", "office address",
            "कहाँ आवेदन", "कहां आवेदन", "कहाँ से मिल", "कहां से बनवा", "किस कार्यालय",
            "कुठे अर्ज", "कुठे मिळेल", "कोणत्या कार्यालयात",
        )
    ):
        doc_followup_focus = "where_to_apply"
    elif any(
        k in lower
        for k in (
            "how do i get", "how can i get", "how to get", "how do i obtain",
            "how can i obtain", "how to obtain", "how do i apply for this document",
            "how do i apply for that document", "preparation process", "procedure",
            "कैसे प्राप्त", "कैसे बनवाएं", "कैसे निकालें", "प्रक्रिया",
            "कसे मिळवायचे", "कसे काढावे", "कशी मिळवावी",
        )
    ):
        doc_followup_focus = "process"
    elif any(
        k in lower
        for k in (
            "why is it required", "why do i need", "why is this required", "why needed",
            "क्यों आवश्यक", "क्यों जरूरी", "का आवश्यक",
        )
    ):
        doc_followup_focus = "why_required"

    # Distinguish "What if I can't obtain it?" (asks fallback AFTER doc is known) vs cold disclosure
    if doc_followup_focus == "fallback" and last_discussed_doc and not explicit_named_doc:
        disclosed_missing_doc = None

    doc_followup_target: Optional[str] = None
    if resolved_doc_item:
        doc_followup_target = resolved_doc_item.get("document_type")
    elif explicit_named_doc and (doc_followup_focus or has_doc_anaphora):
        doc_followup_target = explicit_named_doc
    elif doc_followup_focus and not is_scheme_apply_or_benefit:
        if last_discussed_doc and last_discussed_doc.get("document_type"):
            doc_followup_target = last_discussed_doc["document_type"]
        elif session.get("missing_documents"):
            doc_followup_target = session["missing_documents"][-1]
        elif has_doc_anaphora and checklist_items:
            doc_followup_target = checklist_items[0].get("document_type")
    elif has_doc_anaphora and not disclosed_missing_doc:
        if last_discussed_doc and last_discussed_doc.get("document_type"):
            doc_followup_target = last_discussed_doc["document_type"]
        elif session.get("missing_documents"):
            doc_followup_target = session["missing_documents"][-1]
        elif checklist_items:
            doc_followup_target = checklist_items[0].get("document_type")

    # Resolving which active scheme applies
    active_scheme_code = explicit_scheme or ordinal_scheme_code or session.get("active_scheme_code")

    # Classify conversational action
    is_all_docs_ready = any(k in lower for k in [
        "now i have all the documents", "i now have all the documents", "i have all the documents",
        "have all the documents now", "all the documents are ready", "all documents ready",
        "got all the documents", "arranged all documents", "collected all documents",
        "अब मेरे पास सभी दस्तावेज", "मेरे पास अब सारे दस्तावेज", "सभी दस्तावेज तैयार",
        "माझ्याकडे आता सर्व कागदपत्रे", "आता सर्व कागदपत्रे आहेत", "सर्व कागदपत्रे तयार",
    ])

    is_what_happens_next = any(k in lower for k in [
        "what happens next", "what next", "what should i do next", "next step", "what's next", "whats next",
        "पुढे काय", "पुढील पायरी", "पुढे काय करावे", "आगे क्या", "आगे क्या करना", "अब क्या करें",
    ])

    is_status_query = any(k in lower for k in [
        "application status", "status of my application", "track my application", "my reference number",
        "where is my application", "अर्जाची स्थिती", "आवेदन की स्थिति", "स्टेटस",
    ])

    is_validate_query = any(k in lower for k in [
        "validate my application", "check application readiness", "am i ready to apply",
        "am i ready to submit", "check my readiness", "माझा अर्ज तपासा", "मेरा आवेदन जांचें",
    ])

    is_start_apply = (
        any(k in lower for k in [
            "help me apply", "help apply", "start my application", "start application",
            "apply for it", "apply for this scheme", "apply for that scheme", "let's apply",
            "apply now", "prefill", "pre-fill", "fill form", "fill the form", "create draft",
            "i want to apply", "want to apply", "wish to apply", "apply for ",
            "अर्ज भरण्यास मदत", "अर्ज सुरू करा", "अर्ज भरा", "अर्ज करायचा", "अर्ज करा",
            "आवेदन करने में मदद", "आवेदन शुरू करें", "आवेदन भरें", "आवेदन करना", "आवेदन करें",
        ])
        and "how can i apply" not in lower
        and "how do i apply" not in lower
        and "how to apply" not in lower
        and "where to apply" not in lower
        and "where can i apply" not in lower
        and "steps to apply" not in lower
        and "am i eligible to apply" not in lower
    )

    is_open_eligibility_discovery = (
        not explicit_scheme
        and not ordinal_scheme_code
        and not has_scheme_anaphora
        and any(k in lower for k in [
            "which government schemes am i eligible", "which schemes am i eligible", "what schemes am i eligible",
            "what government schemes am i eligible", "schemes am i eligible for", "schemes i qualify for",
            "which schemes can i get", "check my eligibility across", "find schemes for me", "eligible schemes for me",
            "show my eligible schemes", "which schemes apply to me", "am i eligible for any",
            "मी कोणत्या योजनांसाठी पात्र", "कोणत्या शासकीय योजनांसाठी पात्र", "माझ्यासाठी कोणत्या योजना",
            "मैं किन योजनाओं के लिए पात्र", "किन सरकारी योजनाओं के लिए पात्र", "मेरे लिए कौन सी योजना",
        ])
    )

    return {
        "explicit_scheme_code": explicit_scheme,
        "ordinal_scheme_idx": ordinal_scheme_idx,
        "ordinal_scheme_code": ordinal_scheme_code,
        "ordinal_scheme_out_of_range": ordinal_scheme_out_of_range,
        "ordinal_doc_idx": ordinal_doc_idx,
        "resolved_doc_item": resolved_doc_item,
        "ordinal_doc_out_of_range": ordinal_doc_out_of_range,
        "has_scheme_anaphora": has_scheme_anaphora,
        "has_doc_anaphora": has_doc_anaphora,
        "active_scheme_code": active_scheme_code,
        "category_hint": category_hint,
        "disclosed_missing_doc": disclosed_missing_doc,
        "doc_followup_focus": doc_followup_focus,
        "doc_followup_target": doc_followup_target,
        "is_all_docs_ready": is_all_docs_ready,
        "is_what_happens_next": is_what_happens_next,
        "is_status_query": is_status_query,
        "is_validate_query": is_validate_query,
        "is_start_apply": is_start_apply,
        "is_open_eligibility_discovery": is_open_eligibility_discovery,
        "entities": entities,
    }


# ── Gemini Function Calling Loop ──────────────────────────────────────────────

def _build_gemini_system_instruction(
    ctx: ToolExecutionContext,
    refs: Dict[str, Any],
) -> str:
    lang_label = {"en": "English", "hi": "Hindi (Devanagari)", "mr": "Marathi (Devanagari)"}[ctx.lang]
    known_attrs = extract_known_profile_attributes(
        ctx.profile, ctx.session.get("conversation_entities")
    )
    active_code = ctx.session.get("active_scheme_code")
    ranked = [
        f"{idx}. {item.get('scheme_code')} ({item.get('name')}) - {item.get('eligibility_status')}"
        for idx, item in enumerate((ctx.session.get("last_scheme_list") or [])[:8], start=1)
    ]
    checklist_summary = [
        f"{item.get('index', idx)}. {item.get('title')} [{item.get('document_type')}] - vault={item.get('status')}"
        for idx, item in enumerate((ctx.session.get("last_checklist") or {}).get("items", []), start=1)
    ]

    context_blob = {
        "active_scheme_code": active_code,
        "workflow_step": ctx.session.get("workflow_step", "TALK"),
        "known_citizen_profile": known_attrs,
        "last_listed_schemes": ranked,
        "last_checklist_numbered": checklist_summary,
        "disclosed_or_vault_missing_documents": ctx.session.get("missing_documents", []),
        "last_discussed_document": ctx.session.get("last_discussed_document"),
        "active_application": ctx.session.get("application_draft_summary"),
        "resolved_reference_hints": {
            "explicit_or_ordinal_scheme": refs.get("explicit_scheme_code") or refs.get("ordinal_scheme_code"),
            "ordinal_doc_item": refs.get("resolved_doc_item"),
            "disclosed_missing_doc": refs.get("disclosed_missing_doc"),
            "doc_followup_target": refs.get("doc_followup_target"),
            "doc_followup_focus": refs.get("doc_followup_focus"),
        },
    }

    return (
        f"You are Scheme Saathi, an official citizen welfare assistant for India.\n"
        f"CRITICAL LANGUAGE RULE: Respond 100% in {lang_label}. Do NOT mix scripts or other languages.\n"
        f"GROUNDING RULES:\n"
        f"1. ALWAYS call backend tools for scheme discovery, eligibility evaluation, details, benefits, "
        f"required documents, Document Vault status, missing document guidance, readiness rechecks, "
        f"application draft creation/prefill, validation, and application status. NEVER invent data.\n"
        f"2. NEVER ask the citizen for profile fields already present in known_citizen_profile "
        f"(e.g., age, state, district, occupation, annual_income, gender, land_holding_acres).\n"
        f"3. NEVER fabricate document verification or government application approval/reference IDs. "
        f"If Vault shows documents are missing or unverified, report that honestly.\n"
        f"4. For missing-document assistance, ALWAYS separate Verified information, Estimated information, "
        f"and Information unavailable using tool output (`get_document_preparation_guidance` / "
        f"`identify_missing_documents`), and NEVER invent fees, local street addresses, or processing timelines.\n"
        f"5. Resolve references like 'it', 'that scheme', 'the second scheme', 'the second document', "
        f"'this document', and 'what happens next?' using the current conversation context below.\n"
        f"6. If the citizen asks follow-up questions with no active scheme in context, ask politely which scheme.\n"
        f"CONVERSATION CONTEXT:\n{json.dumps(context_blob, ensure_ascii=False, default=str)}"
    )


def _response_from_tool_outputs(
    ctx: ToolExecutionContext,
    conv_id: str,
    final_text: str,
    engine_mode: str,
) -> AgentChatResponse:
    """Constructs a frontend-compatible AgentChatResponse attaching real structured tool widgets."""
    lang = ctx.lang
    last_out = ctx.tool_outputs[-1] if ctx.tool_outputs else None
    last_tool = last_out["tool"] if last_out else None
    result = last_out["result"] if last_out else {}

    response_type = ChatResponseType.TEXT
    data: Any = None
    eligibility_summary = None
    checklist_data = None
    form_draft_data = None
    confirmation_data = None
    workflow_step = ctx.session.get("workflow_step") or "TALK"
    followups: List[str] = []

    if last_tool == "check_all_eligible_schemes":
        ranked = result.get("ranked_schemes") or []
        data = [
            SchemeCardSummary(
                id=str(it.get("id") or it["scheme_code"]),
                scheme_code=it["scheme_code"],
                name=it["name"],
                category=it.get("category") or "welfare",
                ministry=it.get("ministry") or "Government of India",
                benefits=it.get("benefits") or "",
                eligibility_status=it.get("eligibility_status"),
                official_url=it.get("official_url"),
            ).model_dump()
            for it in ranked[:6]
        ]
        if data:
            response_type = ChatResponseType.SCHEME_CARDS
            top_code = data[0]["scheme_code"]
            followups = [
                _localize(lang, f"Tell me more about {top_code}", f"{top_code} के बारे में विस्तार से बताएं", f"{top_code} योजनेबद्दल सविस्तर सांगा"),
                _localize(lang, f"What documents are required for {top_code}?", f"{top_code} के लिए कौन से दस्तावेज़ चाहिए?", f"{top_code} साठी कोणती कागदपत्रे लागतील?"),
            ]
        eligibility_summary = result
        workflow_step = "MATCH"

    elif last_tool == "discover_schemes":
        schemes = result.get("schemes") or []
        data = [
            SchemeCardSummary(
                id=str(it.get("id") or it["scheme_code"]),
                scheme_code=it["scheme_code"],
                name=it["name"],
                category=it.get("category") or "welfare",
                ministry=it.get("ministry") or "Government of India",
                benefits=it.get("benefits") or "",
                eligibility_status=it.get("eligibility_status"),
                official_url=it.get("official_url"),
            ).model_dump()
            for it in schemes[:6]
        ]
        if data:
            response_type = ChatResponseType.SCHEME_CARDS
        workflow_step = "TALK"

    elif last_tool == "get_scheme_details" and result.get("found"):
        response_type = ChatResponseType.SCHEME_CARDS
        elig_status = (result.get("citizen_eligibility") or {}).get("status")
        data = [
            SchemeCardSummary(
                id=str(result.get("scheme_id") or result["scheme_code"]),
                scheme_code=result["scheme_code"],
                name=result["name"],
                category=result.get("category") or "welfare",
                ministry=result.get("ministry") or "Government of India",
                benefits=result.get("benefits") or "",
                eligibility_status=elig_status,
                official_url=result.get("official_url"),
            ).model_dump()
        ]
        followups = [
            _localize(lang, "What benefits will I receive?", "कितना लाभ मिलेगा?", "या योजनेचे लाभ काय आहेत?"),
            _localize(lang, "What documents are required?", "कौन से दस्तावेज़ चाहिए?", "कोणती कागदपत्रे लागतील?"),
            _localize(lang, "Help me apply", "आवेदन करने में मदद करें", "अर्ज भरण्यास मदत करा"),
        ]

    elif last_tool == "get_scheme_benefits" and result.get("found"):
        response_type = ChatResponseType.BENEFITS_INFO
        data = {
            "scheme_id": result.get("scheme_id"),
            "scheme_code": result.get("scheme_code"),
            "scheme_name": result.get("scheme_name"),
            "benefits": result.get("benefits") or "",
            "official_url": result.get("official_url"),
        }
        followups = [
            _localize(lang, "What documents are required?", "कौन से दस्तावेज़ चाहिए?", "कोणती कागदपत्रे लागतील?"),
            _localize(lang, "Help me apply", "आवेदन करने में मदद करें", "अर्ज भरण्यास मदत करा"),
        ]

    elif last_tool in (
        "get_required_documents",
        "identify_missing_documents",
        "recheck_application_readiness",
        "check_citizen_document_status",
    ):
        cl = result.get("checklist") if "checklist" in result else result
        if isinstance(cl, dict) and cl.get("items"):
            checklist_data = cl
            data = cl.get("items")
            response_type = ChatResponseType.DOCUMENT_CHECKLIST
            workflow_step = "CHECKLIST"
            if last_tool == "identify_missing_documents":
                followups = [
                    _localize(lang, "How do I get this document?", "यह दस्तावेज़ कैसे प्राप्त करें?", "हे कागदपत्र कसे मिळवायचे?"),
                    _localize(lang, "How much will it cost?", "इसमें कितना शुल्क लगेगा?", "यासाठी किती खर्च येईल?"),
                    _localize(lang, "Where do I apply?", "इसके लिए कहाँ आवेदन करें?", "यासाठी कुठे अर्ज करावा?"),
                    _localize(lang, "Now I have all the documents", "अब मेरे पास सभी दस्तावेज़ हैं", "माझ्याकडे आता सर्व कागदपत्रे आहेत"),
                ]
            else:
                followups = [
                    _localize(lang, "Tell me about the second document", "दूसरे दस्तावेज़ के बारे में बताएं", "दुसऱ्या कागदपत्राबद्दल सांगा"),
                    _localize(lang, "Now I have all the documents", "अब मेरे पास सभी दस्तावेज़ हैं", "माझ्याकडे आता सर्व कागदपत्रे आहेत"),
                    _localize(lang, "Help me apply", "आवेदन करने में मदद करें", "अर्ज भरण्यास मदत करा"),
                ]
        elif result.get("guidance"):
            data = result.get("guidance")
            followups = [
                _localize(lang, "How do I get this document?", "यह दस्तावेज़ कैसे प्राप्त करें?", "हे कागदपत्र कसे मिळवायचे?"),
                _localize(lang, "How much will it cost?", "इसमें कितना शुल्क लगेगा?", "यासाठी किती खर्च येईल?"),
                _localize(lang, "Where do I apply?", "इसके लिए कहाँ आवेदन करें?", "यासाठी कुठे अर्ज करावा?"),
                _localize(lang, "What if I can't obtain it?", "अगर यह दस्तावेज़ न मिल सके तो?", "जर हे कागदपत्र मिळू शकले नाही तर?"),
            ]

    elif last_tool == "get_document_preparation_guidance" and result.get("found"):
        guidance_payload = result.get("guidance")
        if guidance_payload:
            data = guidance_payload
        workflow_step = "CHECKLIST" if ctx.session.get("last_checklist") else (ctx.session.get("workflow_step") or "TALK")
        cur_focus = result.get("focus") or "all"
        doc_followups: List[str] = []
        if cur_focus != "process":
            doc_followups.append(_localize(lang, "How do I get this document?", "यह दस्तावेज़ कैसे प्राप्त करें?", "हे कागदपत्र कसे मिळवायचे?"))
        if cur_focus != "cost":
            doc_followups.append(_localize(lang, "How much will it cost?", "इसमें कितना शुल्क लगेगा?", "यासाठी किती खर्च येईल?"))
        if cur_focus != "where_to_apply":
            doc_followups.append(_localize(lang, "Where do I apply?", "इसके लिए कहाँ आवेदन करें?", "यासाठी कुठे अर्ज करावा?"))
        if cur_focus != "fallback":
            doc_followups.append(_localize(lang, "What if I can't obtain it?", "अगर यह दस्तावेज़ न मिल सके तो?", "जर हे कागदपत्र मिळू शकले नाही तर?"))
        followups = doc_followups[:3] + [
            _localize(lang, "Now I have all the documents", "अब मेरे पास सभी दस्तावेज़ हैं", "माझ्याकडे आता सर्व कागदपत्रे आहेत"),
        ]

    elif last_tool == "create_or_prefill_application_draft" and result.get("found"):
        response_type = ChatResponseType.FORM_DRAFT
        form_draft_data = result
        workflow_step = "PRE-FILL"
        followups = [
            _localize(lang, "What happens next?", "आगे क्या होगा?", "पुढे काय करावे?"),
            _localize(lang, "Validate my application", "मेरा आवेदन जांचें", "माझा अर्ज तपासा"),
        ]

    elif last_tool == "check_scheme_eligibility" and result.get("found"):
        response_type = ChatResponseType.ELIGIBILITY_RESULT
        eligibility_summary = result
        workflow_step = "MATCH"
        followups = [
            _localize(lang, "What documents are required?", "कौन से दस्तावेज़ चाहिए?", "कोणती कागदपत्रे लागतील?"),
            _localize(lang, "Help me apply", "आवेदन करने में मदद करें", "अर्ज भरण्यास मदत करा"),
        ]

    elif last_tool == "get_application_status":
        response_type = ChatResponseType.STATUS_TRACKING
        data = {
            "scheme_id": result.get("scheme_code") or "",
            "scheme_code": result.get("scheme_code") or "",
            "scheme_name": result.get("scheme_name") or "",
            "status_url": result.get("portal_url") or "https://www.india.gov.in/",
            "post_steps": result.get("next_steps") or [],
        }

    active_code = ctx.session.get("active_scheme_code")
    active_scheme = (
        {"scheme_code": active_code, "name": ctx.session.get("active_scheme_name") or active_code}
        if active_code
        else None
    )

    return AgentChatResponse(
        conversation_id=conv_id,
        message=final_text,
        spoken_text=_clean_markdown_for_speech(final_text, lang),
        detected_language=lang,
        response_type=response_type,
        data=data,
        suggested_followups=followups,
        engine_mode=engine_mode,
        workflow_step=workflow_step,
        active_scheme=active_scheme,
        eligibility_summary=eligibility_summary,
        checklist_data=checklist_data,
        form_draft_data=form_draft_data,
        confirmation_data=confirmation_data,
        tool_calls_used=list(ctx.executed_tools),
    )


def _run_gemini_tool_conversation(
    ctx: ToolExecutionContext,
    conv_id: str,
    user_message: str,
    refs: Dict[str, Any],
) -> Optional[AgentChatResponse]:
    """
    Executes native Google Gemini Function Calling against real backend tools.
    Returns None cleanly if API key is absent/placeholder, invocation errors,
    or output fails language consistency checks.
    """
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key or "your-gemini" in api_key.lower() or "placeholder" in api_key.lower():
        return None

    try:
        import google.generativeai as genai
        from google.generativeai import protos

        genai.configure(api_key=api_key)
        gemini_tool = get_gemini_tool_declarations()
        system_instruction = _build_gemini_system_instruction(ctx, refs)

        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            tools=[gemini_tool],
            system_instruction=system_instruction,
        )

        # Build bounded prior conversation history
        contents: List[Any] = []
        prior_turns = list(ctx.session.get("turns") or [])[-8:]
        for turn in prior_turns:
            role = "user" if turn.get("role") == "user" else "model"
            text_val = (turn.get("content") or "").strip()
            if text_val:
                contents.append(protos.Content(role=role, parts=[protos.Part(text=text_val)]))
        contents.append(protos.Content(role="user", parts=[protos.Part(text=user_message)]))

        final_text = ""
        for _hop in range(MAX_GEMINI_TOOL_HOPS):
            response = model.generate_content(contents)
            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                break

            candidate = candidates[0]
            content = getattr(candidate, "content", None)
            parts = list(getattr(content, "parts", None) or [])

            function_calls = []
            text_fragments = []
            for p in parts:
                fc = getattr(p, "function_call", None)
                if fc is not None and getattr(fc, "name", ""):
                    function_calls.append(fc)
                pt = getattr(p, "text", None)
                if pt:
                    text_fragments.append(pt)

            if not function_calls:
                final_text = "\n".join(text_fragments).strip() or (getattr(response, "text", "") or "").strip()
                break

            # Append model turn with its function calls
            contents.append(content)
            response_parts = []
            for fc in function_calls:
                raw_args = dict(getattr(fc, "args", {}) or {})
                tool_result = execute_backend_tool(ctx, fc.name, raw_args)
                response_parts.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=fc.name,
                            response={"result": json.loads(json.dumps(tool_result, default=str))},
                        )
                    )
                )
            contents.append(protos.Content(role="user", parts=response_parts))

        if not _language_script_valid(final_text, ctx.lang):
            return None

        return _response_from_tool_outputs(ctx, conv_id, final_text, engine_mode="gemini_grounded")
    except Exception as exc:
        logger.warning("Gemini tool-calling fallback triggered cleanly: %s", exc)
        return None


# ── Grounded Multilingual Formatting Helpers (Deterministic Tool Mode) ────────

def _format_eligible_discovery_message(res: Dict[str, Any], lang: str) -> str:
    eligible = res.get("eligible_schemes") or []
    potentially = res.get("potentially_eligible_schemes") or []
    insuff = res.get("insufficient_info_schemes") or []
    has_profile = res.get("has_citizen_profile", False)
    missing_profile_labels = res.get("missing_profile_labels") or []

    if not has_profile and not eligible and not potentially:
        catalog_preview = insuff[:5]
        lines = [
            f"{idx}. **{s['name']} ({s['scheme_code']})** — {s.get('benefits') or ''}"
            for idx, s in enumerate(catalog_preview, start=1)
        ]
        body = "\n".join(lines)
        return _localize(
            lang,
            f"I evaluated the active government scheme catalog ({res.get('total_evaluated', 0)} schemes). "
            f"Since your saved citizen profile is not available yet, share your age, state, occupation, and annual income to check personal eligibility.\n\n**Active Schemes You Can Ask About:**\n{body}",
            f"मैंने सक्रिय सरकारी योजना सूची ({res.get('total_evaluated', 0)} योजनाएं) की जांच की। आपकी सहेजी गई नागरिक प्रोफ़ाइल अभी उपलब्ध नहीं है, इसलिए कृपया अपनी आयु, राज्य, व्यवसाय और वार्षिक आय बताएं।\n\n**उपलब्ध प्रमुख योजनाएं:**\n{body}",
            f"मी सक्रिय शासकीय योजनांची यादी ({res.get('total_evaluated', 0)} योजना) तपासली. सध्या जतन केलेली नागरिक प्रोफाईल उपलब्ध नसल्याने कृपया तुमचे वय, राज्य, व्यवसाय आणि वार्षिक उत्पन्न सांगा.\n\n**प्रमुख शासकीय योजना:**\n{body}",
        )

    sections: List[str] = []
    idx_counter = 1

    if eligible:
        el_lines = []
        for s in eligible[:5]:
            el_lines.append(f"{idx_counter}. **{s['name']} ({s['scheme_code']})** — {s.get('benefits') or s.get('explanation')}")
            idx_counter += 1
        sections.append(
            _localize(lang, "**Eligible Schemes:**\n", "**पूर्णतः पात्र योजनाएं:**\n", "**पात्र योजना:**\n")
            + "\n".join(el_lines)
        )

    if potentially:
        pot_lines = []
        for s in potentially[:6]:
            missing_note = ""
            if s.get("missing_fields"):
                needed = ", ".join(m.replace("_", " ") for m in s["missing_fields"][:3])
                missing_note = _localize(
                    lang,
                    f" (Needs confirmation: {needed})",
                    f" (अतिरिक्त विवरण आवश्यक: {needed})",
                    f" (अतिरिक्त माहिती आवश्यक: {needed})",
                )
            pot_lines.append(
                f"{idx_counter}. **{s['name']} ({s['scheme_code']})** — {s.get('benefits') or ''}{missing_note}"
            )
            idx_counter += 1
        sections.append(
            _localize(
                lang,
                "**Potentially Eligible Schemes (based on your saved profile):**\n",
                "**संभावित रूप से पात्र योजनाएं (आपकी प्रोफ़ाइल के आधार पर):**\n",
                "**संभाव्य पात्र योजना (तुमच्या प्रोफाईलनुसार):**\n",
            )
            + "\n".join(pot_lines)
        )

    if not sections and insuff:
        ins_lines = []
        for s in insuff[:5]:
            needed = ", ".join(m.replace("_", " ") for m in (s.get("missing_fields") or [])[:3])
            suffix = (
                _localize(lang, f" — needs: {needed}", f" — आवश्यक विवरण: {needed}", f" — आवश्यक माहिती: {needed}")
                if needed
                else ""
            )
            ins_lines.append(f"{idx_counter}. **{s['name']} ({s['scheme_code']})**{suffix}")
            idx_counter += 1
        sections.append(
            _localize(
                lang,
                "**Schemes Requiring Additional Eligibility Details:**\n",
                "**अतिरिक्त पात्रता विवरण आवश्यक वाली योजनाएं:**\n",
                "**अधिक पात्रता तपशील आवश्यक असलेल्या योजना:**\n",
            )
            + "\n".join(ins_lines)
        )

    if missing_profile_labels:
        missing_str = ", ".join(missing_profile_labels)
        sections.append(
            _localize(
                lang,
                f"ℹ️ To narrow eligibility further, your profile is missing: {missing_str}.",
                f"ℹ️ पात्रता को और सटीक जांचने हेतु आपकी प्रोफ़ाइल में {missing_str} आवश्यक है।",
                f"ℹ️ पात्रता अधिक अचूक तपासण्यासाठी तुमच्या प्रोफाईलमध्ये {missing_str} माहिती आवश्यक आहे.",
            )
        )

    footer = _localize(
        lang,
        "Ask about any scheme by name or number (for example: 'Tell me more about the second scheme' or 'Tell me more about PM-KISAN').",
        "आप किसी भी योजना के बारे में नाम या क्रम से पूछ सकते हैं (उदाहरण: 'दूसरी योजना के बारे में बताएं' या 'PM-KISAN के बारे में बताएं')।",
        "तुम्ही कोणत्याही योजनेबद्दल नाव किंवा क्रमांकावरून विचारू शकता (उदा. 'दुसऱ्या योजनेबद्दल सांगा' किंवा 'PM-KISAN बद्दल सांगा').",
    )
    return "\n\n".join(sections + [footer])


def _format_scheme_details_message(res: Dict[str, Any], lang: str) -> str:
    benefits = res.get("benefits") or _localize(lang, "Details unavailable in database.", "डेटाबेस में उपलब्ध नहीं।", "डेटाबेसमध्ये उपलब्ध नाही.")
    beneficiaries = res.get("target_beneficiaries") or _localize(lang, "Eligible Indian citizens", "पात्र भारतीय नागरिक", "पात्र भारतीय नागरिक")
    elig = res.get("citizen_eligibility")
    elig_line = ""
    if isinstance(elig, dict):
        st = elig.get("status", "")
        if st == "eligible":
            elig_line = _localize(lang, "\n\n✅ **Your Eligibility:** You meet all evaluated criteria based on your profile.", "\n\n✅ **आपकी पात्रता:** आपकी प्रोफ़ाइल के अनुसार आप इस योजना के लिए पात्र हैं।", "\n\n✅ **तुमची पात्रता:** तुमच्या प्रोफाईलनुसार तुम्ही या योजनेसाठी पात्र आहात.")
        elif st == "potentially_eligible":
            elig_line = _localize(lang, "\n\nℹ️ **Your Eligibility:** Potentially eligible based on your saved profile.", "\n\nℹ️ **आपकी पात्रता:** आपकी सहेजी गई प्रोफ़ाइल के अनुसार आप संभावित रूप से पात्र हैं।", "\n\nℹ️ **तुमची पात्रता:** तुमच्या जतन केलेल्या प्रोफाईलनुसार तुम्ही संभाव्य पात्र आहात.")
        elif st == "not_eligible":
            reason = (elig.get("failed_criteria") or [""])[0]
            elig_line = _localize(lang, f"\n\n⚠️ **Your Eligibility:** Currently not eligible ({reason}).", f"\n\n⚠️ **आपकी पात्रता:** वर्तमान में पात्र नहीं ({reason})।", f"\n\n⚠️ **तुमची पात्रता:** सध्या अपात्र ({reason}).")
        elif elig.get("missing_fields"):
            needed = ", ".join(m.replace("_", " ") for m in elig["missing_fields"][:3])
            elig_line = _localize(lang, f"\n\nℹ️ **Eligibility Check Needs:** {needed}.", f"\n\nℹ️ **पात्रता जांच हेतु आवश्यक:** {needed}।", f"\n\nℹ️ **पात्रता तपासणीसाठी आवश्यक:** {needed}.")

    return _localize(
        lang,
        f"**{res['name']} ({res['scheme_code']})**\n\n"
        f"📌 **Purpose:** {res.get('description') or ''}\n\n"
        f"💰 **Benefits:** {benefits}\n\n"
        f"🎯 **Target Beneficiaries:** {beneficiaries}\n\n"
        f"🏛️ **Ministry:** {res.get('ministry')}\n"
        f"🌐 **Official Portal:** [{res.get('official_url')}]({res.get('official_url')})"
        f"{elig_line}",
        f"**{res['name']} ({res['scheme_code']})**\n\n"
        f"📌 **उद्देश्य:** {res.get('description') or ''}\n\n"
        f"💰 **लाभ:** {benefits}\n\n"
        f"🎯 **लक्षित लाभार्थी:** {beneficiaries}\n\n"
        f"🏛️ **मंत्रालय:** {res.get('ministry')}\n"
        f"🌐 **आधिकारिक पोर्टल:** [{res.get('official_url')}]({res.get('official_url')})"
        f"{elig_line}",
        f"**{res['name']} ({res['scheme_code']})**\n\n"
        f"📌 **उद्देश:** {res.get('description') or ''}\n\n"
        f"💰 **लाभ:** {benefits}\n\n"
        f"🎯 **पात्र लाभार्थी:** {beneficiaries}\n\n"
        f"🏛️ **मंत्रालय:** {res.get('ministry')}\n"
        f"🌐 **अधिकृत पोर्टल:** [{res.get('official_url')}]({res.get('official_url')})"
        f"{elig_line}",
    )


def _format_benefits_message(res: Dict[str, Any], lang: str) -> str:
    if not res.get("benefits_available"):
        return _localize(
            lang,
            f"⚠️ Verified benefit figures for **{res['scheme_name']} ({res['scheme_code']})** are currently unavailable in our database. Check official portal: [{res.get('official_url')}]({res.get('official_url')})",
            f"⚠️ **{res['scheme_name']} ({res['scheme_code']})** के सटीक लाभ विवरण अभी डेटाबेस में उपलब्ध नहीं हैं। आधिकारिक पोर्टल देखें: [{res.get('official_url')}]({res.get('official_url')})",
            f"⚠️ **{res['scheme_name']} ({res['scheme_code']})** चे नेमके लाभ सध्या डेटाबेसमध्ये उपलब्ध नाहीत. अधिकृत पोर्टल पहा: [{res.get('official_url')}]({res.get('official_url')})",
        )
    return _localize(
        lang,
        f"**Benefits under {res['scheme_name']} ({res['scheme_code']}):**\n\n💰 {res['benefits']}\n\n🌐 **Official Portal:** [{res.get('official_url')}]({res.get('official_url')})",
        f"**{res['scheme_name']} ({res['scheme_code']}) के अंतर्गत लाभ:**\n\n💰 {res['benefits']}\n\n🌐 **आधिकारिक पोर्टल:** [{res.get('official_url')}]({res.get('official_url')})",
        f"**{res['scheme_name']} ({res['scheme_code']}) अंतर्गत मिळणारे लाभ:**\n\n💰 {res['benefits']}\n\n🌐 **अधिकृत पोर्टल:** [{res.get('official_url')}]({res.get('official_url')})",
    )


def _format_documents_message(res: Dict[str, Any], lang: str) -> str:
    items = res.get("items") or []
    if not items:
        return _localize(
            lang,
            f"⚠️ Document requirements for **{res['scheme_name']} ({res['scheme_code']})** are not available in our catalog yet. Please check [{res.get('official_url')}]({res.get('official_url')}).",
            f"⚠️ **{res['scheme_name']} ({res['scheme_code']})** के आवश्यक दस्तावेजों की सूची अभी डेटाबेस में उपलब्ध नहीं है। कृपया [{res.get('official_url')}]({res.get('official_url')}) देखें।",
            f"⚠️ **{res['scheme_name']} ({res['scheme_code']})** साठी लागणाऱ्या कागदपत्रांची यादी सध्या उपलब्ध नाही. कृपया [{res.get('official_url')}]({res.get('official_url')}) पहा.",
        )

    lines = []
    for item in items:
        mand_tag = (
            _localize(lang, "Mandatory", "अनिवार्य", "अनिवार्य")
            if item.get("is_mandatory")
            else _localize(lang, "Optional", "वैकल्पिक", "पर्यायी")
        )
        status_label = item.get("status_label") or item.get("status")
        auth = (item.get("sourcing") or {}).get("issuing_authority") or ""
        auth_note = f" — *{auth}*" if auth else ""
        lines.append(
            f"{item['index']}. **{item['title']}** ({mand_tag} | Vault: **{status_label}**){auth_note}"
        )

    summary = _localize(
        lang,
        f"**Required Documents for {res['scheme_name']} ({res['scheme_code']}):**\n\n"
        + "\n".join(lines)
        + f"\n\n📋 **Document Vault Status:** {res.get('mandatory_ready', 0)}/{res.get('mandatory_count', 0)} mandatory documents verified. "
        + "You can ask about any document by name or number (for example: 'Tell me about the second document').",
        f"**{res['scheme_name']} ({res['scheme_code']}) के लिए आवश्यक दस्तावेज़:**\n\n"
        + "\n".join(lines)
        + f"\n\n📋 **दस्तावेज़ वॉल्ट स्थिति:** {res.get('mandatory_ready', 0)}/{res.get('mandatory_count', 0)} अनिवार्य दस्तावेज़ सत्यापित हैं। "
        + "आप किसी भी दस्तावेज़ के बारे में नाम या क्रम से पूछ सकते हैं (उदाहरण: 'दूसरे दस्तावेज़ के बारे में बताएं')।",
        f"**{res['scheme_name']} ({res['scheme_code']}) साठी आवश्यक कागदपत्रे:**\n\n"
        + "\n".join(lines)
        + f"\n\n📋 **कागदपत्र तिजोरी स्थिती:** {res.get('mandatory_ready', 0)}/{res.get('mandatory_count', 0)} अनिवार्य कागदपत्रे पडताळलेली आहेत. "
        + "तुम्ही कोणत्याही कागदपत्राबद्दल नाव किंवा क्रमांकावरून विचारू शकता (उदा. 'दुसऱ्या कागदपत्राबद्दल सांगा').",
    )
    return summary


def _format_doc_guidance_message(
    res: Dict[str, Any],
    lang: str,
    is_missing_disclosure: bool = False,
    focus: str = "all",
) -> str:
    guidance = res.get("guidance") if "guidance" in res else (res if "verified_info" in res else None)
    if isinstance(guidance, dict) and guidance:
        return format_document_guidance_response(
            guidance,
            lang=lang,
            focus=focus or res.get("focus") or "all",
            is_missing_disclosure=is_missing_disclosure,
        )

    sourcing = res.get("sourcing") or {}
    title = res.get("title") or sourcing.get("title") or "Document"
    vault_status = res.get("vault_status", "missing")
    return _localize(
        lang,
        f"📄 **{title}** (Vault: **{vault_status}**)\n\n• **Authority:** {sourcing.get('issuing_authority') or 'Information unavailable'}\n• **Where to Apply:** {sourcing.get('where_to_obtain') or 'Information unavailable'}",
        f"📄 **{title}** (वॉल्ट: **{vault_status}**)\n\n• **प्राधिकरण:** {sourcing.get('issuing_authority') or 'जानकारी उपलब्ध नहीं'}\n• **कहाँ आवेदन करें:** {sourcing.get('where_to_obtain') or 'जानकारी उपलब्ध नहीं'}",
        f"📄 **{title}** (व्हॉल्ट: **{vault_status}**)\n\n• **प्राधिकरण:** {sourcing.get('issuing_authority') or 'माहिती उपलब्ध नाही'}\n• **कुठे अर्ज करावा:** {sourcing.get('where_to_obtain') or 'माहिती उपलब्ध नाही'}",
    )


def _format_readiness_recheck_message(res: Dict[str, Any], lang: str) -> str:
    verified = res.get("verified_documents") or []
    pending_review = res.get("pending_review_documents") or []
    missing = res.get("missing_or_rejected_documents") or []
    ready_in_vault = res.get("documents_ready_in_vault", False)
    scheme_name = res.get("scheme_name") or res.get("scheme_code")
    m_ready = res.get("mandatory_verified_count", 0)
    m_total = res.get("mandatory_count", 0)

    if ready_in_vault:
        return _localize(
            lang,
            f"✅ **Great news! I rechecked your Document Vault and readiness for {scheme_name}:**\n\n"
            f"All **{m_ready}/{m_total}** mandatory documents are verified and ready ({', '.join(verified)}).\n\n"
            f"You can say **'Help me apply'** whenever you are ready to pre-fill your application draft.",
            f"✅ **बहुत बढ़िया! मैंने {scheme_name} के लिए आपके डॉक्यूमेंट वॉल्ट और तत्परता की पुनः जांच की:**\n\n"
            f"सभी **{m_ready}/{m_total}** अनिवार्य दस्तावेज़ सत्यापित और तैयार हैं ({', '.join(verified)})।\n\n"
            f"आवेदन शुरू करने के लिए **'आवेदन करने में मदद करें'** कहें।",
            f"✅ **उत्तम! मी {scheme_name} साठी तुमची डॉक्युमेंट व्हॉल्ट आणि अर्ज सज्जता पुन्हा तपासली आहे:**\n\n"
            f"सर्व **{m_ready}/{m_total}** अनिवार्य कागदपत्रे पडताळलेली व तयार आहेत ({', '.join(verified)}).\n\n"
            f"अर्ज सुरू करण्यासाठी **'अर्ज भरण्यास मदत करा'** असे सांगा.",
        )

    parts: List[str] = [
        _localize(
            lang,
            f"🔄 **Document Readiness Recheck for {scheme_name}:** Currently **{m_ready}/{m_total}** mandatory documents are verified in your Document Vault.",
            f"🔄 **{scheme_name} के लिए दस्तावेज़ तत्परता पुनः जांच:** वर्तमान में आपके डॉक्यूमेंट वॉल्ट में **{m_ready}/{m_total}** अनिवार्य दस्तावेज़ सत्यापित हैं।",
            f"🔄 **{scheme_name} साठी कागदपत्र सज्जता पुनर्तपासणी:** सध्या तुमच्या डॉक्युमेंट व्हॉल्टमध्ये **{m_ready}/{m_total}** अनिवार्य कागदपत्रे पडताळलेली आहेत.",
        )
    ]
    if verified:
        parts.append(_localize(lang, f"✅ **Verified:** {', '.join(verified)}", f"✅ **सत्यापित:** {', '.join(verified)}", f"✅ **पडताळलेली:** {', '.join(verified)}"))
    if pending_review:
        parts.append(_localize(lang, f"⏳ **Uploaded (Needs Review/Verification in Vault):** {', '.join(pending_review)}", f"⏳ **अपलोड किए गए (वॉल्ट में समीक्षा/सत्यापन लंबित):** {', '.join(pending_review)}", f"⏳ **अपलोड केलेले (व्हॉल्टमध्ये तपासणी प्रलंबित):** {', '.join(pending_review)}"))
    if missing:
        parts.append(_localize(lang, f"⚠️ **Still Not Uploaded/Verified in Vault:** {', '.join(missing)}", f"⚠️ **वॉल्ट में अभी अपलोड/सत्यापित नहीं:** {', '.join(missing)}", f"⚠️ **व्हॉल्टमध्ये अद्याप अपलोड/पडताळणी नाही:** {', '.join(missing)}"))

    parts.append(
        _localize(
            lang,
            "📌 Since you now have the documents physically, please upload and verify them in **Document Vault** before final submission. Meanwhile, you can say **'Help me apply'** to pre-fill your application draft.",
            "📌 चूंकि अब आपके पास दस्तावेज़ तैयार हैं, कृपया अंतिम सबमिशन से पहले उन्हें **डॉक्यूमेंट वॉल्ट** में अपलोड और सत्यापित करें। इस बीच आप **'आवेदन करने में मदद करें'** कहकर मसौदा शुरू कर सकते हैं।",
            "📌 तुमच्याकडे आता ही कागदपत्रे उपलब्ध असल्याने अंतिम अर्जापूर्वी ती **डॉक्युमेंट व्हॉल्ट**मध्ये अपलोड करून पडताळून घ्या. दरम्यान तुम्ही **'अर्ज भरण्यास मदत करा'** म्हणून अर्जाचा मसुदा सुरू करू शकता.",
        )
    )
    return "\n\n".join(parts)


def _format_application_start_message(res: Dict[str, Any], lang: str) -> str:
    portal = res.get("portal_integration") or {}
    portal_url = portal.get("official_application_url") or res.get("official_portal") or "https://www.india.gov.in/"
    mode_label = portal.get("submission_method_label") or portal.get("submission_method") or ""
    doc_r = res.get("document_readiness") or {}
    pending_docs = res.get("missing_mandatory_documents") or doc_r.get("missing_or_pending") or []
    missing_fields = res.get("missing_fields") or []

    doc_note = ""
    if pending_docs:
        doc_note = _localize(
            lang,
            f"\n• **Missing / Unverified Mandatory Documents ({len(pending_docs)}):** {', '.join(pending_docs)}",
            f"\n• **लंबित / अपूर्ण अनिवार्य दस्तावेज़ ({len(pending_docs)}):** {', '.join(pending_docs)}",
            f"\n• **अपूर्ण / पडताळणी बाकी अनिवार्य कागदपत्रे ({len(pending_docs)}):** {', '.join(pending_docs)}",
        )

    if not res.get("form_supported"):
        req_docs = portal.get("required_documents") or []
        req_titles = [d.get("title") for d in req_docs if d.get("title")]
        req_line = (
            _localize(
                lang,
                f"\n• **Required Documents Checklist:** {', '.join(req_titles)}",
                f"\n• **आवश्यक दस्तावेज़ सूची:** {', '.join(req_titles)}",
                f"\n• **आवश्यक कागदपत्रांची यादी:** {', '.join(req_titles)}",
            )
            if req_titles
            else ""
        )
        mode_line = f"\n• **Submission Channel:** {mode_label}" if mode_label else ""
        return _localize(
            lang,
            f"ℹ️ **{res.get('scheme_name') or res.get('scheme_code')} — Official Portal Guidance**\n\n{res.get('message')}"
            f"{mode_line}{req_line}{doc_note}\n\n🌐 **Official Portal:** [{portal_url}]({portal_url})",
            f"ℹ️ **{res.get('scheme_name') or res.get('scheme_code')} — आधिकारिक पोर्टल मार्गदर्शन**\n\n{res.get('message')}"
            f"{mode_line}{req_line}{doc_note}\n\n🌐 **आधिकारिक पोर्टल:** [{portal_url}]({portal_url})",
            f"ℹ️ **{res.get('scheme_name') or res.get('scheme_code')} — अधिकृत पोर्टल मार्गदर्शन**\n\n{res.get('message')}"
            f"{mode_line}{req_line}{doc_note}\n\n🌐 **अधिकृत पोर्टल:** [{portal_url}]({portal_url})",
        )

    field_note = ""
    if missing_fields:
        field_note = _localize(
            lang,
            f"\n• **Missing Fields Requiring Input ({len(missing_fields)}):** {', '.join(missing_fields[:6])}" + ("..." if len(missing_fields) > 6 else ""),
            f"\n• **भरने हेतु शेष फ़ील्ड ({len(missing_fields)}):** {', '.join(missing_fields[:6])}" + ("..." if len(missing_fields) > 6 else ""),
            f"\n• **भरणे आवश्यक असलेले रकाने ({len(missing_fields)}):** {', '.join(missing_fields[:6])}" + ("..." if len(missing_fields) > 6 else ""),
        )
    draft_id = res.get("application_id") or ""
    mode_badge = f"\n• **Portal Integration:** {mode_label} ([Open Portal]({portal_url}))" if mode_label else ""

    return _localize(
        lang,
        f"📝 **Started Pre-Filled Application Draft for {res['scheme_title']}**\n\n"
        f"• **Internal Draft ID:** `{draft_id}`\n"
        f"• **Pre-filled Mandatory Fields:** **{res['filled_mandatory_fields']}/{res['total_mandatory_fields']}** (Readiness: **{res['readiness_percentage']}%**)"
        f"{field_note}{doc_note}{mode_badge}\n\n👇 Review or edit any fields below, save your draft, and confirm before portal submission.",
        f"📝 **{res['scheme_title']} के लिए पूर्व-भरा हुआ आवेदन मसौदा शुरू किया गया**\n\n"
        f"• **आंतरिक ड्राफ्ट आईडी:** `{draft_id}`\n"
        f"• **भरे गए अनिवार्य फ़ील्ड:** **{res['filled_mandatory_fields']}/{res['total_mandatory_fields']}** (तैयारी: **{res['readiness_percentage']}%**)"
        f"{field_note}{doc_note}{mode_badge}\n\n👇 नीचे दिए गए फ़ॉर्म में शेष विवरण जांचें, सहेजें और पोर्टल सबमिशन से पहले पुष्टि करें।",
        f"📝 **{res['scheme_title']} साठी पूर्व-भरलेला अर्ज मसुदा तयार केला आहे**\n\n"
        f"• **अंतर्गत मसुदा आयडी:** `{draft_id}`\n"
        f"• **भरलेले अनिवार्य रकाने:** **{res['filled_mandatory_fields']}/{res['total_mandatory_fields']}** (सज्जता: **{res['readiness_percentage']}%**)"
        f"{field_note}{doc_note}{mode_badge}\n\n👇 खालील अर्जातील तपशील तपासा, बदल असल्यास जतन करा आणि पोर्टलवर सादर करण्यापूर्वी संमती द्या.",
    )


def _format_status_and_next_steps_message(res: Dict[str, Any], lang: str) -> str:
    scheme_name = res.get("scheme_name") or res.get("scheme_code")
    steps = res.get("next_steps") or []
    steps_md = "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))

    if res.get("has_application"):
        state = res.get("lifecycle_state") or "draft"
        if state == "submission_unknown":
            header = _localize(
                lang,
                f"⏳ **Application Status for {scheme_name}: Submission Reconciliation Required (`submission_unknown`)**\n\nWe did not receive a confirmed portal receipt, so status is unverified. Do not blindly retry before checking in Applications or on the official portal.",
                f"⏳ **{scheme_name} आवेदन स्थिति: सत्यापन/समाधान लंबित (`submission_unknown`)**\n\nबाहरी पोर्टल से अंतिम रसीद की पुष्टि नहीं हुई है। कृपया बिना जांच किए दोबारा सबमिट न करें।",
                f"⏳ **{scheme_name} अर्जाची स्थिती: पडताळणी/समन्वय प्रलंबित (`submission_unknown`)**\n\nबाह्य पोर्टलकडून अंतिम पावतीची खात्री मिळालेली नाही. कृपया पडताळणीशिवाय पुन्हा अर्ज पाठवू नका.",
            )
        elif res.get("verified_government_submission") and res.get("reference_number"):
            header = _localize(
                lang,
                f"✅ **Application Status for {scheme_name}: Submitted** (Official Reference: `{res['reference_number']}`)",
                f"✅ **{scheme_name} आवेदन स्थिति: जमा किया गया** (आधिकारिक संदर्भ संख्या: `{res['reference_number']}`)",
                f"✅ **{scheme_name} अर्जाची स्थिती: सादर केलेला** (अधिकृत संदर्भ क्रमांक: `{res['reference_number']}`)",
            )
        elif res.get("portal_submitted") and res.get("official_reference_number"):
            header = _localize(
                lang,
                f"🏛️ **Application Status for {scheme_name}: Portal Submitted (Citizen-Reported Reference: `{res['official_reference_number']}`)**",
                f"🏛️ **{scheme_name} आवेदन स्थिति: पोर्टल पर जमा (नागरिक-दर्ज संदर्भ संख्या: `{res['official_reference_number']}`)**",
                f"🏛️ **{scheme_name} अर्जाची स्थिती: पोर्टलवर सादर (नोंदवलेला संदर्भ क्रमांक: `{res['official_reference_number']}`)**",
            )
        else:
            header = _localize(
                lang,
                f"📋 **Application Draft Status for {scheme_name}: `{state}`** (Not yet submitted to government portal)",
                f"📋 **{scheme_name} आवेदन मसौदा स्थिति: `{state}`** (सरकारी पोर्टल पर अभी अंतिम जमा नहीं हुआ है)",
                f"📋 **{scheme_name} अर्ज मसुद्याची स्थिती: `{state}`** (अधिकृत शासकीय पोर्टलवर अद्याप सादर झालेला नाही)",
            )
    elif scheme_name:
        header = _localize(
            lang,
            f"📌 **Current Progress for {scheme_name}:** No application draft has been created yet.",
            f"📌 **{scheme_name} की वर्तमान प्रगति:** अभी तक कोई आवेदन मसौदा नहीं बनाया गया है।",
            f"📌 **{scheme_name} ची सध्याची स्थिती:** अद्याप कोणताही अर्ज मसुदा तयार केलेला नाही.",
        )
    else:
        header = _localize(
            lang,
            "📌 **What Happens Next:** Here is how you can proceed in Scheme Saathi:",
            "📌 **आगे के चरण:** आप योजना साथी में निम्न प्रकार आगे बढ़ सकते हैं:",
            "📌 **पुढील पायऱ्या:** तुम्ही योजना साथीमध्ये खालीलप्रमाणे पुढे जाऊ शकता:",
        )

    return _localize(
        lang,
        f"{header}\n\n**Recommended Next Steps:**\n{steps_md}",
        f"{header}\n\n**अगले आवश्यक चरण:**\n{steps_md}",
        f"{header}\n\n**पुढील आवश्यक टप्पे:**\n{steps_md}",
    )


# ── Deterministic Tool Orchestrator ───────────────────────────────────────────

def _run_deterministic_tool_conversation(
    ctx: ToolExecutionContext,
    conv_id: str,
    user_message: str,
    refs: Dict[str, Any],
) -> Optional[AgentChatResponse]:
    """
    Runs the deterministic tool-calling conversational flow using the exact same
    real backend tools when Gemini is unconfigured or unavailable.
    Returns None only when legacy specialized intent handlers should handle the turn.
    """
    lang = ctx.lang
    active_scheme = refs.get("active_scheme_code")

    # Handle explicit out-of-range ordinal lookup honestly instead of guessing
    if refs.get("ordinal_scheme_out_of_range"):
        msg = _localize(
            lang,
            "I could not find a scheme at that position in our current list. Ask 'Which government schemes am I eligible for?' or name the scheme directly.",
            "वर्तमान सूची में उस स्थान पर कोई योजना नहीं मिली। कृपया 'मैं किन योजनाओं के लिए पात्र हूँ?' पूछें या योजना का नाम बताएं।",
            "सध्याच्या यादीत त्या क्रमांकाची योजना उपलब्ध नाही. कृपया 'मी कोणत्या योजनांसाठी पात्र आहे?' विचारा किंवा योजनेचे नाव सांगा.",
        )
        return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

    if refs.get("ordinal_doc_out_of_range"):
        items = (ctx.session.get("last_checklist") or {}).get("items") or []
        msg = _localize(
            lang,
            f"There are only {len(items)} documents in the current checklist. Please choose a number between 1 and {len(items)}.",
            f"वर्तमान सूची में केवल {len(items)} दस्तावेज़ हैं। कृपया 1 से {len(items)} के बीच संख्या चुनें।",
            f"सध्याच्या यादीत फक्त {len(items)} कागदपत्रे आहेत. कृपया १ ते {len(items)} मधील क्रमांक निवडा.",
        )
        return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

    # 1. Citizen states "Now I have all the documents." -> Recheck real Vault readiness
    if refs.get("is_all_docs_ready"):
        if not active_scheme:
            msg = _localize(
                lang,
                "That's great! Which scheme are your documents prepared for so I can verify your Document Vault readiness?",
                "बहुत बढ़िया! कृपया बताएं आप किस योजना के लिए दस्तावेज़ तैयार बता रहे हैं ताकि मैं वॉल्ट की जांच कर सकूं?",
                "उत्तम! कृपया तुमची कागदपत्रे कोणत्या योजनेसाठी तयार आहेत ते सांगा म्हणजे मी तिजोरीतील सज्जता तपासू शकेन?",
            )
            return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

        res = execute_backend_tool(
            ctx,
            "recheck_application_readiness",
            {"scheme_code_or_name": active_scheme, "citizen_claims_all_documents": True},
        )
        return _response_from_tool_outputs(
            ctx, conv_id, _format_readiness_recheck_message(res, lang), engine_mode="deterministic"
        )

    # 2. Missing document disclosed ("I don't have my land possession certificate." / ordinal missing doc)
    if refs.get("disclosed_missing_doc"):
        ident_res = execute_backend_tool(
            ctx,
            "identify_missing_documents",
            {"scheme_code_or_name": active_scheme, "disclosed_missing_document": refs["disclosed_missing_doc"]},
        )
        msg = _format_doc_guidance_message(ident_res, lang, is_missing_disclosure=True, focus="all")
        return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

    # 3. Document ordinal or follow-up preparation guidance
    #    ("Tell me about the second document", "How do I get this document?", "How much will it cost?",
    #     "Where do I apply?", "What if I can't obtain it?")
    doc_target: Optional[str] = refs.get("doc_followup_target")
    doc_focus: str = refs.get("doc_followup_focus") or "all"
    if not doc_target and refs.get("resolved_doc_item"):
        doc_target = refs["resolved_doc_item"].get("document_type")
    elif not doc_target and refs.get("has_doc_anaphora"):
        last_doc = ctx.session.get("last_discussed_document") or {}
        missing_docs = ctx.session.get("missing_documents") or []
        if last_doc.get("document_type"):
            doc_target = last_doc["document_type"]
        elif missing_docs:
            doc_target = missing_docs[-1]
        elif (ctx.session.get("last_checklist") or {}).get("items"):
            doc_target = ctx.session["last_checklist"]["items"][0].get("document_type")

    if doc_target and not refs.get("is_start_apply"):
        last_doc_scheme = (ctx.session.get("last_discussed_document") or {}).get("scheme_code")
        target_scheme = active_scheme or last_doc_scheme
        g_res = execute_backend_tool(
            ctx,
            "get_document_preparation_guidance",
            {
                "document_name_or_ordinal": doc_target,
                "scheme_code_or_name": target_scheme,
                "focus": doc_focus,
            },
        )
        msg = _format_doc_guidance_message(g_res, lang, is_missing_disclosure=False, focus=doc_focus)
        return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

    # 4. Open eligibility discovery across ALL schemes ("Which government schemes am I eligible for?")
    if refs.get("is_open_eligibility_discovery"):
        elig_res = execute_backend_tool(
            ctx,
            "check_all_eligible_schemes",
            {"category": refs.get("category_hint"), "state": refs["entities"].get("state")},
        )
        return _response_from_tool_outputs(
            ctx, conv_id, _format_eligible_discovery_message(elig_res, lang), engine_mode="deterministic"
        )

    # 5. "What happens next?" or Application Status
    if refs.get("is_what_happens_next") or refs.get("is_status_query"):
        st_target = refs.get("explicit_scheme_code") or refs.get("ordinal_scheme_code") or (
            active_scheme if not refs.get("is_what_happens_next") or active_scheme else None
        )
        st_res = execute_backend_tool(ctx, "get_application_status", {"scheme_code_or_name": st_target})
        return _response_from_tool_outputs(
            ctx, conv_id, _format_status_and_next_steps_message(st_res, lang), engine_mode="deterministic"
        )

    # 6. Validate draft / Readiness check
    if refs.get("is_validate_query"):
        if not active_scheme:
            msg = _localize(
                lang,
                "Which scheme's application readiness would you like me to validate?",
                "आप किस योजना के आवेदन की तैयारी की जांच करना चाहते हैं?",
                "तुम्हाला कोणत्या योजनेच्या अर्जाची सज्जता तपासायची आहे?",
            )
            return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")
        readiness_res = execute_backend_tool(
            ctx,
            "recheck_application_readiness",
            {"scheme_code_or_name": active_scheme, "citizen_claims_all_documents": False},
        )
        return _response_from_tool_outputs(
            ctx, conv_id, _format_readiness_recheck_message(readiness_res, lang), engine_mode="deterministic"
        )

    # 7. Start application ("Help me apply", "Apply for it", "Start my application")
    if refs.get("is_start_apply"):
        if not active_scheme:
            msg = _localize(
                lang,
                "Which government scheme would you like me to help you apply for?",
                "आप किस सरकारी योजना के लिए आवेदन करना चाहते हैं?",
                "तुम्हाला कोणत्या शासकीय योजनेसाठी अर्ज करायचा आहे?",
            )
            return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")
        fill_res = execute_backend_tool(
            ctx,
            "create_or_prefill_application_draft",
            {"scheme_code_or_name": active_scheme},
        )
        return _response_from_tool_outputs(
            ctx, conv_id, _format_application_start_message(fill_res, lang), engine_mode="deterministic"
        )

    # 8. Ordinal or Anaphoric Scheme Resolution for Overview / Benefits / Documents / Eligibility
    #    (or explicit single scheme overview like "Tell me more about PM-KISAN.")
    lower = user_message.lower()
    wants_benefits = any(k in lower for k in ["benefit", "benefits", "how much money", "financial assistance", "लाभ", "फायदे", "पैसे", "रुपये"])
    wants_docs = any(k in lower for k in ["document", "documents", "checklist", "कागदपत्र", "दस्तावेज", "दस्तावेज़"])
    wants_elig = any(k in lower for k in ["eligible", "eligibility", "qualify", "पात्र", "पात्रता"])
    wants_overview = any(k in lower for k in ["tell me more", "tell me about", "explain", "what is", "details", "बदल", "बद्दल", "बारे में", "तपशील", "विवरण"])

    target_code = refs.get("explicit_scheme_code") or refs.get("ordinal_scheme_code") or (
        active_scheme if (refs.get("has_scheme_anaphora") or wants_benefits or wants_docs or wants_elig) else None
    )

    if (wants_benefits or wants_docs or wants_overview or wants_elig) and not target_code and not refs.get("explicit_scheme_code"):
        # Unresolved anaphora with NO scheme in memory -> clarify cleanly, never guess
        if refs.get("has_scheme_anaphora") or wants_benefits or wants_docs:
            msg = _localize(
                lang,
                "Which government scheme are you inquiring about? You can name a scheme like PM-KISAN, KCC, or Ayushman Bharat, or ask 'Which government schemes am I eligible for?'.",
                "आप किस सरकारी योजना के बारे में पूछ रहे हैं? कृपया योजना का नाम बताएं (जैसे PM-KISAN, KCC, आयुष्मान भारत) या पूछें 'मैं किन योजनाओं के लिए पात्र हूँ?'।",
                "तुम्ही कोणत्या शासकीय योजनेबद्दल विचारत आहात? कृपया योजनेचे नाव सांगा (उदा. PM-KISAN, KCC, आयुष्मान भारत) किंवा 'मी कोणत्या योजनांसाठी पात्र आहे?' असे विचारा.",
            )
            return _response_from_tool_outputs(ctx, conv_id, msg, engine_mode="deterministic")

    if target_code:
        if wants_docs and not (wants_overview and wants_elig):
            doc_res = execute_backend_tool(ctx, "get_required_documents", {"scheme_code_or_name": target_code})
            if doc_res.get("found"):
                return _response_from_tool_outputs(ctx, conv_id, _format_documents_message(doc_res, lang), engine_mode="deterministic")
        if wants_benefits and not (wants_overview or wants_docs or wants_elig):
            ben_res = execute_backend_tool(ctx, "get_scheme_benefits", {"scheme_code_or_name": target_code})
            if ben_res.get("found"):
                return _response_from_tool_outputs(ctx, conv_id, _format_benefits_message(ben_res, lang), engine_mode="deterministic")
        if (refs.get("ordinal_scheme_code") or (wants_overview and not wants_docs)) and not wants_benefits:
            det_res = execute_backend_tool(ctx, "get_scheme_details", {"scheme_code_or_name": target_code})
            if det_res.get("found"):
                return _response_from_tool_outputs(ctx, conv_id, _format_scheme_details_message(det_res, lang), engine_mode="deterministic")
        if wants_elig and not wants_docs and not wants_overview:
            el_res = execute_backend_tool(ctx, "check_scheme_eligibility", {"scheme_code_or_name": target_code})
            if el_res.get("found"):
                # Build concise tailored summary respecting known profile attributes
                missing_str = ", ".join(el_res.get("missing_information") or [])
                base = _localize(
                    lang,
                    f"**Eligibility for {el_res.get('localized_name', target_code)} ({target_code}):**\n\n"
                    f"• **Status:** **{el_res['status'].upper()}**\n"
                    f"• **Summary:** {el_res.get('summary')}",
                    f"**{el_res.get('localized_name', target_code)} ({target_code}) पात्रता जांच:**\n\n"
                    f"• **स्थिति:** **{el_res['status'].upper()}**\n"
                    f"• **विवरण:** {el_res.get('summary')}",
                    f"**{el_res.get('localized_name', target_code)} ({target_code}) पात्रता तपासणी:**\n\n"
                    f"• **स्थिती:** **{el_res['status'].upper()}**\n"
                    f"• **तपशील:** {el_res.get('summary')}",
                )
                if missing_str:
                    base += _localize(
                        lang,
                        f"\n\nℹ️ Additional detail needed: {missing_str}",
                        f"\n\nℹ️ आवश्यक अतिरिक्त जानकारी: {missing_str}",
                        f"\n\nℹ️ आवश्यक अतिरिक्त माहिती: {missing_str}",
                    )
                return _response_from_tool_outputs(ctx, conv_id, base, engine_mode="deterministic")

    # Update active_scheme_code if an ordinal scheme reference resolved cleanly even when falling through
    if refs.get("ordinal_scheme_code"):
        ctx.session["active_scheme_code"] = refs["ordinal_scheme_code"]

    return None


def run_conversational_orchestrator(
    *,
    db: Optional[Session],
    request: AgentChatRequest,
    current_user: Optional[User],
    profile: Optional[UserProfile],
    session: Dict[str, Any],
    lang: str,
    all_schemes: List[Scheme],
    conv_id: str,
) -> Optional[AgentChatResponse]:
    """
    Main entry point for multi-turn conversational intelligence.
    Merges extracted entities cleanly, resolves conversational references,
    executes Gemini Function Calling when configured, and falls back seamlessly
    to deterministic tool calling using the identical real backend tools.
    """
    refs = resolve_conversational_references(
        request.message,
        session=session,
        all_schemes=all_schemes,
        request_scheme_id=request.scheme_id,
    )

    # Merge any newly mentioned citizen facts into session conversation_entities (without overwriting profile)
    if refs["entities"]:
        conv_ent = dict(session.get("conversation_entities") or {})
        for k, v in refs["entities"].items():
            if k != "missing_document_disclosed":
                conv_ent[k] = v
        session["conversation_entities"] = conv_ent

    ctx = ToolExecutionContext(
        db=db,
        current_user=current_user,
        profile=profile,
        session=session,
        lang=lang,
        all_schemes=list(all_schemes),
    )

    # Path A: Live Gemini Tool Calling when API key is configured
    gemini_resp = _run_gemini_tool_conversation(ctx, conv_id, request.message, refs)
    if gemini_resp is not None:
        return gemini_resp

    # Path B: Deterministic Real-Tool Orchestrator
    return _run_deterministic_tool_conversation(ctx, conv_id, request.message, refs)

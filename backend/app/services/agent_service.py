"""
Multilingual Scheme Saathi AI Voice Assistant Service.
Supports Marathi (mr), Hindi (hi), and English (en) including code-mixed and spoken queries.
Integrates directly with PostgreSQL scheme catalogue, document checklists, and the deterministic AST eligibility engine.
Supports Google Gemini with deterministic, factual grounding against PostgreSQL.
Maintains multi-turn conversation session memory across queries.
"""
from typing import Optional, List, Dict, Any, Tuple
import re
import uuid
import time
import logging
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select, or_, func

from app.core.config import settings
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.models.user import User
from app.models.user_profile import UserProfile
from app.eligibility.engine import evaluate_scheme_eligibility
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatResponseType,
    SchemeCardSummary,
)
from app.agents.tools import tool_build_checklist, tool_fill_form
from app.agents.planner import plan_and_execute_agentic_flow

logger = logging.getLogger(__name__)

# ── Multi-turn Conversation Session Memory ────────────────────────────────────
# In-memory session tracking strictly isolated by authenticated user ID and conversation ID.
# Protected by idle TTL expiry (30 mins) to prevent stale state retention.
SESSION_TTL_SECONDS: int = 1800
_CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _make_session_key(conv_id: str, user_id: Optional[str] = None) -> str:
    """Creates a strictly partitioned session key preventing multi-user cross-talk."""
    user_part = f"user_{user_id}" if user_id else "anon"
    return f"{user_part}:{conv_id}"


def _get_session(conv_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves or initializes an active conversation session with TTL validation."""
    now = time.time()
    key = _make_session_key(conv_id, user_id)
    session = _CONVERSATION_SESSIONS.get(key)

    # Validate session TTL expiry
    if session:
        last_active = session.get("last_active_at", 0)
        if (now - last_active) > SESSION_TTL_SECONDS:
            logger.info("Session %s idle > %ss; expiring and resetting context.", key, SESSION_TTL_SECONDS)
            session = None

    if not session:
        session = {
            "key": key,
            "user_id": user_id,
            "conv_id": conv_id,
            "active_scheme_code": None,
            "last_intent": None,
            "turn_count": 0,
            "created_at": now,
            "last_active_at": now,
        }
        _CONVERSATION_SESSIONS[key] = session
    else:
        session["last_active_at"] = now

    return session


def _update_session_scheme(conv_id: str, scheme_code: str, user_id: Optional[str] = None) -> None:
    """Updates the active scheme context for a specific user and conversation."""
    session = _get_session(conv_id, user_id)
    session["active_scheme_code"] = scheme_code
    session["turn_count"] = session.get("turn_count", 0) + 1
    session["last_active_at"] = time.time()


# ── Language Markers ──────────────────────────────────────────────────────────
MARATHI_MARKERS = [
    "मला", "माहिती", "हवी", "शेतकरी", "मिळू", "शकतात", "पात्रता", "आहे", "का",
    "कागदपत्रे", "लागतील", "महाराष्ट्र", "योजनांबद्दल", "अर्ज", "कसा", "करावा",
    "लाडकी", "बहीण", "नमो", "शासकीय", "योजनांची", "पाहिजे", "आहात", "काय",
    "मी", "साठी", "योजनेसाठी", "माझी", "माझ्या", "मिळेल", "नोंदणी", "पैसे",
    "कुठे", "करावी", "कशी", "हप्ता", "रुपये", "नंतर", "स्थिती",
]

HINDI_MARKERS = [
    "मुझे", "जानकारी", "चाहिए", "किसान", "मिल", "सकती", "सकते", "पात्र", "हूँ",
    "दस्तावेज", "लगेंगे", "रहने वाला", "आवेदन", "कैसे", "करें", "बताओ", "योजनाएं",
    "सरकारी", "फायदा", "लाभ", "क्या", "पंजीकरण", "कहाँ", "रजिस्ट्रेशन", "पैसे",
    "कितना", "किस्त", "बाद", "स्थिति",
]

MARATHI_LATIN = [
    "mala", "aahe", "karaychi", "mahiti", "haviy", "havi", "shetkari", "shethkari",
    "milu", "shaktat", "shakat", "kagadpatre", "lagtil", "yojanabaddal", "kasa",
    "nondani", "karava", "paise", "kuthe", "kashi",
]

HINDI_LATIN = [
    "mujhe", "chahiye", "kisan", "kheti", "batao", "mil", "sakta", "sakti", "sakte",
    "dastavez", "lagengi", "kaise", "karein", "ke liye", "rahne wala", "apply",
    "karna", "paisa", "milega", "kaha", "kare",
]

ENGLISH_WORDS = {
    "tell", "me", "about", "schemes", "scheme", "for", "farmers", "farmer", "in",
    "india", "am", "i", "eligible", "what", "documents", "are", "required", "how",
    "can", "apply", "benefit", "benefits", "to", "my", "is", "the", "check", "where",
    "register", "money", "receive", "status", "after", "registration", "much"
}


def detect_language(text: str, user_preference: Optional[str] = "auto") -> str:
    """
    Detect spoken or written language from query text.
    Returns 'mr' (Marathi), 'hi' (Hindi), or 'en' (English).
    """
    if user_preference in ("mr", "hi", "en"):
        return user_preference

    lower_text = text.lower()
    words = set(re.findall(r"\b\w+\b", lower_text))
    has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in text)

    if not has_devanagari:
        en_word_matches = sum(1 for w in words if w in ENGLISH_WORDS)
        mr_latin_matches = sum(1 for m in MARATHI_LATIN if m in words or m in lower_text)
        hi_latin_matches = sum(1 for h in HINDI_LATIN if h in words or h in lower_text)

        if mr_latin_matches > 0 and mr_latin_matches >= hi_latin_matches:
            return "mr"
        if hi_latin_matches > 0 and en_word_matches <= 2:
            return "hi"
        if en_word_matches >= 2 or (en_word_matches > 0 and not mr_latin_matches and not hi_latin_matches):
            return "en"
        if hi_latin_matches > 0:
            return "hi"
        return "en"

    # For Devanagari text
    mr_score = sum(1 for m in MARATHI_MARKERS if m in lower_text or m in words)
    hi_score = sum(1 for h in HINDI_MARKERS if h in lower_text or h in words)

    if "ळ" in text or "हवी" in text or "आहे" in text or "मला" in text or "शेतकरी" in text or "कागदपत्रे" in text or "मी" in words or "साठी" in text or "मिळेल" in text or "करावा" in text or "कसा" in text or "कुठे" in text:
        mr_score += 6

    if ("हूँ" in text or "मुझे" in text or "चाहिए" in text or "दस्तावेज" in text or "मैं" in words or "कहाँ" in text or "कैसे" in text) and "आहे" not in text and "कसा" not in text:
        hi_score += 6

    if mr_score > hi_score:
        return "mr"
    elif hi_score > mr_score:
        return "hi"
    return "hi"


def _clean_markdown_for_speech(text: str, lang: str = "en") -> str:
    """
    Transforms rich Markdown response text into natural, complete spoken language for Text-to-Speech:
    - Retains ALL substantive information: explanations, numbered steps, bullet points,
      statutory figures, criteria, conditions, and disclaimers.
    - Replaces Markdown links [Title](url) with 'Title' or spoken portal reference.
    - Removes raw URLs or translates them into spoken phrases ('अधिकृत संकेतस्थळावर', 'आधिकारिक पोर्टल पर', 'on the official portal').
    - Removes formatting symbols (**, *, __, _, `, ###, etc.) and decorative emojis.
    - Ensures clean punctuation so TTS synthesizers can speak smoothly without awkward pauses or missing words.
    """
    if not text:
        return ""

    def _link_repl(m):
        label = m.group(1).strip()
        if label.startswith("http://") or label.startswith("https://"):
            if lang == "mr":
                return "अधिकृत संकेतस्थळावर"
            elif lang == "hi":
                return "आधिकारिक पोर्टल पर"
            return "on the official portal"
        return label

    # 1. Replace markdown links [label](url) -> label
    cleaned = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_repl, text)

    # 2. Remove bare URLs and any empty surrounding parentheses
    cleaned = re.sub(r'\s*\(\s*https?://[^\s)]+\s*\)', '', cleaned)
    cleaned = re.sub(r'https?://[^\s)]+', '', cleaned)
    cleaned = re.sub(r'\(\s*\)', '', cleaned)

    # 3. Remove Markdown headings
    cleaned = re.sub(r'#{1,6}\s*', '', cleaned)

    # 4. Remove bold, italics, inline code
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
    cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

    # 5. Remove decorative emojis and bullet icons
    cleaned = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', '', cleaned)
    cleaned = re.sub(r'^[ \t]*[•●○■◆]\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^[ \t]*[-*]\s+', '', cleaned, flags=re.MULTILINE)

    # 6. Normalize whitespace
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


# ── Scheme Procedural Knowledge Base ──────────────────────────────────────────
# Verified application procedures and official guidelines from government sources
VERIFIED_SCHEME_GUIDES: Dict[str, Dict[str, Any]] = {
    "PM-KISAN": {
        "portal_name": "PM-KISAN Official Portal",
        "official_url": "https://pmkisan.gov.in/",
        "application_url": "https://pmkisan.gov.in/registrationform.aspx",
        "status_url": "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
        "source_url": "https://pmkisan.gov.in/Documents/pmkisan_guidelines.pdf",
        "verification_date": "2026-11-10",
        "benefits_en": "Financial benefit of ₹6,000 per year transferred in 3 equal instalments of ₹2,000 every 4 months via Direct Benefit Transfer (DBT) directly into Aadhaar-seeded bank accounts.",
        "benefits_mr": "दरवर्षी ₹६,००० थेट बँक खात्यात. दर ४ महिन्यांनी ₹२,००० चा १ हप्ता (वर्षाला ३ हप्ते) थेट आधारशी जोडलेल्या बँक खात्यावर DBT द्वारे जमा होतो.",
        "benefits_hi": "प्रति वर्ष ₹6,000 की आर्थिक सहायता। हर 4 महीने में ₹2,000 की 3 समान किस्तें सीधे आधार-सीडेड बैंक खाते में डीबीटी (DBT) के माध्यम से भेजी जाती हैं।",
        "steps_en": [
            "Visit the official PM-KISAN portal (https://pmkisan.gov.in/).",
            "Navigate to 'Farmers Corner' on the right side of the homepage.",
            "Select 'New Farmer Registration' (https://pmkisan.gov.in/registrationform.aspx).",
            "Choose Rural or Urban Farmer Registration, enter your 12-digit Aadhaar number, state, and mobile number, then submit for OTP verification.",
            "Fill in landholding records (District, Sub-District, Block, Village, Survey/Khata/Khasra number, and land area in hectares).",
            "Upload your land ownership certificate (7/12 extract / Khatauni) and submit the form to receive your Registration ID."
        ],
        "steps_mr": [
            "अधिकृत PM-KISAN पोर्टलला (https://pmkisan.gov.in/) भेट द्या.",
            "मुख्यपृष्ठावरील 'Farmers Corner' (शेतकरी कक्ष) पर्यायावर जा.",
            "'New Farmer Registration' (नवीन शेतकरी नोंदणी) निवडा.",
            "तुमचा १२ अंकी आधार क्रमांक, राज्य व मोबाईल नंबर टाकून कॅप्चा भरा आणि OTP द्वारे पडताळणी करा.",
            "जिल्हा, तालुका, गाव निवडा आणि शेतजमिनीचा तपशील (७/१२ किंवा खतौनी, खाते क्रमांक, गट/खसरा क्रमांक आणि क्षेत्रफळ) अचूक भरा.",
            "जमिनीचा उतारा अपलोड करा आणि अर्ज सबमिट करून तात्पुरता नोंदणी क्रमांक (Registration ID) जतन करा."
        ],
        "steps_hi": [
            "आधिकारिक PM-KISAN पोर्टल (https://pmkisan.gov.in/) पर जाएं।",
            "होमपेज पर 'Farmers Corner' अनुभाग पर क्लिक करें।",
            "'New Farmer Registration' (नया किसान पंजीकरण) विकल्प चुनें।",
            "अपना 12 अंकों का आधार नंबर, राज्य और मोबाइल नंबर दर्ज करें और OTP सत्यापन पूरा करें।",
            "भूमि स्वामित्व विवरण (जिला, उप-जिला, ब्लॉक, गांव, खसरा/खाता संख्या और भूमि क्षेत्रफल हेक्टेयर में) भरें।",
            "अपनी खतौनी/भूलेख दस्तावेज़ अपलोड करें और आवेदन सबमिट करके रजिस्ट्रेशन आईडी सुरक्षित रखें।"
        ],
        "offline_en": "You can also apply in person at any Common Service Centre (CSC / Village Digital Seva Kendra) or through your local Village Revenue Officer (Patwari / Talathi) or Block Agriculture Office with original Aadhaar, land extract, and bank passbook.",
        "offline_mr": "तुम्ही जवळच्या सीएससी (CSC / आपले सरकार सेवा केंद्र) केंद्रात जाऊन किंवा स्थानिक तलाठी / कृषी सहाय्यक कार्यालयात आधार कार्ड, ७/१२ उतारा आणि बँक पासबुकसह थेट अर्ज करू शकता.",
        "offline_hi": "आप अपने नजदीकी कॉमन सर्विस सेंटर (CSC) पर जा सकते हैं या स्थानीय लेखपाल/पटवारी या ब्लॉक कृषि अधिकारी से संपर्क कर सकते हैं।",
        "post_registration_en": [
            "Complete mandatory e-KYC: Go to Farmers Corner -> 'e-KYC' using Aadhaar OTP or facial recognition on PM-KISAN Mobile App.",
            "Verify Aadhaar-Bank Account Seeding: Ensure your savings account is seeded with NPCI mapper for Direct Benefit Transfer.",
            "Track Application Status: Visit Farmers Corner -> 'Know Your Status' (https://pmkisan.gov.in/BeneficiaryStatus_New.aspx) and enter your Registration Number.",
            "State & District Verification: Local revenue authorities verify your land records before final inclusion in the beneficiary list."
        ],
        "post_registration_mr": [
            "अनिवार्य e-KYC पूर्ण करा: Farmers Corner मधील 'e-KYC' लिंकद्वारे आधार OTP किंवा PM-KISAN मोबाईल ॲपवरून फेस ऑथेंटिकेशन करा.",
            "बँक खाते आधारशी जोडा: तुमचे बँक खाते NPCI मॅपरशी लिंक (DBT Enabled) असल्याची बँकेत खात्री करा.",
            "अर्जाची स्थिती तपासा: Farmers Corner मधील 'Know Your Status' पर्यायावर जाऊन नोंदणी क्रमांक टाकून मंजुरी तपासा.",
            "स्थानिक महसूल तपासणी: तालुका कृषी अधिकारी व तलाठी यांच्याकडून जमिनीच्या नोंदींची पडताळणी झाल्यानंतर हप्ता जमा होतो."
        ],
        "post_registration_hi": [
            "अनिवार्य e-KYC पूरा करें: Farmers Corner में 'e-KYC' लिंक पर आधार OTP या PM-KISAN मोबाइल ऐप से फेस ऑथेंटिकेशन करें।",
            "बैंक खाते में आधार सीडिंग: सुनिश्चित करें कि आपका बैंक खाता NPCI मैपर से जुड़ा है और डीबीटी सक्रिय है।",
            "आवेदन की स्थिति जांचें: Farmers Corner में 'Know Your Status' पर जाकर रजिस्ट्रेशन नंबर से स्थिति ट्रैक करें।",
            "सत्यापन प्रक्रिया: राज्य नोडल अधिकारी और लेखपाल द्वारा भूमि सत्यापन के बाद अंतिम लाभार्थी सूची में नाम शामिल होता है।"
        ]
    },
    "KCC": {
        "portal_name": "JanSamarth National Credit Portal & Ministry of Agriculture",
        "official_url": "https://agricoop.nic.in/",
        "application_url": "https://www.jansamarth.in/",
        "status_url": "https://www.jansamarth.in/",
        "source_url": "https://agricoop.nic.in/kcc-guidelines.pdf",
        "verification_date": "2026-11-10",
        "benefits_en": "Revolving agricultural credit facility up to ₹3,00,000 (sub-limit ₹2,00,000 for allied activities like dairy and fisheries). Benchmark lending rate is 7% per annum (supported by 1.5% institutional interest subvention from GoI to banks under the Modified Interest Subvention Scheme - MISS). Farmers who repay on or before the scheduled due date (tenor up to 1 year) receive an additional 3% Prompt Repayment Incentive (PRI), resulting in an effective net interest rate of 4% per annum. If repayment is delayed beyond the due date, the 3% PRI is forfeited and the full 7% interest rate applies. Collateral-free credit is available up to ₹1.60 Lakh. Mandatory Aadhaar authentication required.",
        "benefits_mr": "अल्पमुदत कृषी पीक कर्ज व खेळते भांडवल सुविधा ₹३,००,००० पर्यंत (दुग्ध/मत्स्य व्यवसाय मर्यादित ₹२,००,०००). बँकांचे कर्ज दर ७% वार्षिक (संशोधित व्याज सवलत योजना MISS अंतर्गत बँकांना केंद्र सरकारकडून १.५% संस्थात्मक सवलत). १ वर्षाच्या मुदतीत वेळेवर परतफेड करणाऱ्या शेतकऱ्यांना ३% त्वरित परतफेड प्रोत्साहन (PRI) मिळून निव्वळ व्याज दर ४% होतो. मुदतीनंतर परतफेड केल्यास ३% सवलत रद्द होऊन पूर्ण ७% व्याज भरावे लागते. ₹१.६० लाखांपर्यंत विनातारण कर्ज उपलब्ध. आधार प्रमाणीकरण अनिवार्य.",
        "benefits_hi": "₹3,00,000 तक की कार्यशील कृषि ऋण सुविधा (पशुपालन/मत्स्य हेतु ₹2,00,000 उप-सीमा)। बैंकों की आधारभूत ऋण दर 7% प्रति वर्ष है (संशोधित ब्याज छूट योजना MISS के तहत केंद्र सरकार द्वारा बैंकों को 1.5% संस्थागत छूट)। 1 वर्ष की निर्धारित देय तिथि तक समय पर भुगतान करने वाले किसानों को 3% शीघ्र पुनर्भुगतान प्रोत्साहन (PRI) मिलता है, जिससे प्रभावी ब्याज दर 4% हो जाती है। समय पर भुगतान न करने पर 3% की छूट समाप्त होकर पूरी 7% दर देय होगी। ₹1.60 लाख तक बिना बंधक ऋण उपलब्ध। आधार प्रमाणीकरण अनिवार्य है।",
        "steps_en": [
            "Visit the JanSamarth National Credit Portal (https://www.jansamarth.in/) or your bank's portal.",
            "Select 'Agri Infrastructure & Kisan Credit Card' under agricultural loan options.",
            "Fill in personal details, landholding area, crops grown, and required credit limit.",
            "Upload identity proof (Aadhaar/Voter ID) and land extract (7/12 extract / Khatauni).",
            "Submit the digital application to your preferred local commercial or regional rural bank branch."
        ],
        "steps_mr": [
            "JanSamarth पोर्टल (https://www.jansamarth.in/) किंवा तुमच्या बँकेच्या अधिकृत पोर्टलला भेट द्या.",
            "'Kisan Credit Card' (किसान क्रेडिट कार्ड) पर्याय निवडा.",
            "वैयक्तिक माहिती, जमिनीचे क्षेत्रफळ आणि पीक पद्धतीची माहिती भरा.",
            "आधार कार्ड आणि ७/१२ व ८-अ उतारा अपलोड करा.",
            "अर्ज सबमिट करून जवळच्या बँकेत जाऊन पावती जमा करा."
        ],
        "steps_hi": [
            "JanSamarth पोर्टल (https://www.jansamarth.in/) या अपने बैंक के पोर्टल पर जाएं।",
            "कृषि ऋण के तहत 'Kisan Credit Card' विकल्प चुनें।",
            "व्यक्तिगत विवरण, कृषि भूमि का रकबा और फसलों का विवरण भरें।",
            "आधार कार्ड और खतौनी/जमीन की नकल अपलोड करें।",
            "आवेदन सबमिट करें और बैंक से 14 दिनों के भीतर कार्ड प्राप्त करें।"
        ],
        "offline_en": "Submit the 1-page simplified KCC application form at any branch of a Commercial Bank, Regional Rural Bank (RRB), or Primary Agricultural Credit Society (PACS).",
        "offline_mr": "जवळच्या कोणत्याही राष्ट्रीयीकृत बँक, ग्रामीण बँक किंवा विकास सेवा सोसायटीत (PACS) १ पानांचा KCC अर्ज भरून द्या.",
        "offline_hi": "किसी भी ग्रामीण बैंक, राष्ट्रीयकृत बैंक या प्राथमिक कृषि सहकारी समिति (PACS) में 1-पेज का सरल KCC फॉर्म जमा करें।"
    },
    "AB-PMJAY": {
        "portal_name": "Ayushman Bharat Beneficiary Portal (NHA)",
        "official_url": "https://beneficiary.nha.gov.in/",
        "application_url": "https://beneficiary.nha.gov.in/",
        "status_url": "https://beneficiary.nha.gov.in/",
        "source_url": "https://beneficiary.nha.gov.in/",
        "verification_date": "2026-11-10",
        "benefits_en": "Cashless hospitalization coverage of up to ₹5,00,000 per family per year for secondary and tertiary care across 27,000+ empanelled public and private hospitals across India.",
        "benefits_mr": "कुटुंबाला दरवर्षी ₹५,००,००० पर्यंत मोफत व कॅशलेस वैद्यकीय उपचार संरक्षण. देशातील २७,००० हून अधिक सरकारी व खाजगी रुग्णालयांमध्ये १,९००+ उपचारांचा समावेश.",
        "benefits_hi": "प्रति परिवार प्रति वर्ष ₹5,00,000 तक का कैशलेस स्वास्थ्य बीमा। देश के 27,000 से अधिक सूचीबद्ध अस्पतालों में द्वितीयक और तृतीयक उपचार उपलब्ध।",
        "steps_en": [
            "Visit the official Beneficiary Portal (https://beneficiary.nha.gov.in/) or download the Ayushman App.",
            "Select 'Beneficiary' login and enter your mobile number for OTP authentication.",
            "Search for your family using State, Scheme (PMJAY), and Family ID (Ration Card Number / Aadhaar).",
            "If your name appears, click 'e-KYC' and authenticate via Aadhaar OTP, IRIS, or biometric scan.",
            "Once approved, click 'Download Ayushman Card' to get your Ayushman Golden Card."
        ],
        "steps_mr": [
            "अधिकृत लाभार्थी पोर्टलला (https://beneficiary.nha.gov.in/) भेट द्या किंवा Ayushman ॲप डाउनलोड करा.",
            "'Beneficiary' पर्याय निवडून मोबाईल नंबरवर OTP मागवून लॉगिन करा.",
            "राज्य, योजना आणि कुटुंब ओळख (रेशन कार्ड किंवा आधार नंबर) टाकून नाव शोधा.",
            "नाव आढळल्यास 'e-KYC' वर क्लिक करून आधार OTP द्वारे बायोमेट्रिक पडताळणी करा.",
            "मंजुरीनंतर तुमचे 'Ayushman Card' (आयुष्मान गोल्डन कार्ड) डाउनलोड करा."
        ],
        "steps_hi": [
            "आधिकारिक पोर्टल (https://beneficiary.nha.gov.in/) पर जाएं या Ayushman ऐप डाउनलोड करें।",
            "'Beneficiary' मोड चुनकर मोबाइल नंबर और OTP से लॉगिन करें।",
            "राज्य, योजना और राशन कार्ड नंबर या आधार नंबर दर्ज करके अपना नाम खोजें।",
            "नाम मिलने पर 'e-KYC' बटन दबाएं और आधार OTP द्वारा सत्यापन पूरा करें।",
            "सत्यापन के तुरंत बाद अपना 'आयुष्मान कार्ड' डाउनलोड करें।"
        ],
        "offline_en": "Visit the Ayushman Mitra helpdesk at any Empanelled Government or Private Hospital, or visit the nearest CSC with your Ration Card and Aadhaar.",
        "offline_mr": "कोणत्याही संलग्न सरकारी किंवा खाजगी रुग्णालयातील 'आयुष्मान मित्र' मदत कक्षात किंवा जवळच्या सीएससी केंद्रात रेशन कार्ड व आधार घेऊन जा.",
        "offline_hi": "किसी भी सूचीबद्ध अस्पताल में 'आयुष्मान मित्र' हेल्पडेस्क पर या नजदीकी CSC केंद्र पर राशन कार्ड और आधार कार्ड लेकर जाएं।"
    },
    "MLBY-MH": {
        "portal_name": "Mukhyamantri Majhi Ladki Bahin Yojana Portal (Maharashtra)",
        "official_url": "https://ladkibahin.maharashtra.gov.in/",
        "application_url": "https://ladkibahin.maharashtra.gov.in/",
        "status_url": "https://ladkibahin.maharashtra.gov.in/",
        "source_url": "https://ladkibahin.maharashtra.gov.in/",
        "is_pending_verification": True,
        "verification_date": None,
        "benefits_en": "[Verification In Progress] Direct financial assistance of ₹1,500 per month (₹18,000 per year) transferred via DBT into the Aadhaar-linked bank accounts of eligible women aged 21-65 years in Maharashtra with family income under ₹2.5 Lakh.",
        "benefits_mr": "[पडताळणी अंतर्गत] महाराष्ट्र राज्यातील २१ ते ६५ वयोगटातील पात्र महिलांना (वार्षिक उत्पन्न ₹२.५ लाखांपर्यंत) दरमहा ₹१,५०० (वर्षाला ₹१८,०००) थेट बँक खात्यात आधार DBT द्वारे दिले जातात.",
        "benefits_hi": "[सत्यापन प्रक्रियाधीन] महाराष्ट्र की 21-65 आयु वर्ग की पात्र महिलाओं (वार्षिक आय ₹2.5 लाख तक) को ₹1,500 प्रति माह (₹18,000 प्रति वर्ष) सीधे आधार लिंक बैंक खाते में DBT द्वारा दिया जाता है।",
        "steps_en": [
            "Visit the official portal (https://ladkibahin.maharashtra.gov.in/) or use the Nari Shakti Doot mobile app.",
            "Click on 'Applicant Login' and register using your mobile number and Aadhaar OTP.",
            "Fill in applicant details, bank account details (Aadhaar linked), and Maharashtra domicile details.",
            "Upload self-declaration of annual family income below ₹2.5 Lakh, Aadhaar card, and Ration Card.",
            "Submit the application and download the acknowledgement receipt with Application ID."
        ],
        "steps_mr": [
            "अधिकृत पोर्टल (https://ladkibahin.maharashtra.gov.in/) किंवा 'नारी शक्ती दूत' ॲपवर जा.",
            "'अर्जदार लॉगिन' वर क्लिक करून मोबाईल नंबर आणि आधार OTP द्वारे नोंदणी करा.",
            "वैयक्तिक माहिती, बँक खाते (आधार जोडलेले) आणि महाराष्ट्राचे अधिवास (Domicile/Ration card) तपशील भरा.",
            "कुटुंबाचे वार्षिक उत्पन्न ₹२.५ लाखांपेक्षा कमी असल्याचे स्वयंघोषणापत्र, आधार कार्ड आणि रेशन कार्ड अपलोड करा.",
            "अर्ज सबमिट करून पावती व अर्ज क्रमांक जतन करा."
        ],
        "steps_hi": [
            "पोर्टल (https://ladkibahin.maharashtra.gov.in/) या 'नारी शक्ति दूत' ऐप पर जाएं।",
            "मोबाइल नंबर और आधार OTP से रजिस्ट्रेशन पूरा करें।",
            "व्यक्तिगत विवरण, आधार से जुड़ा बैंक खाता और महाराष्ट्र निवास प्रमाण दर्ज करें।",
            "वार्षिक आय ₹2.5 लाख से कम होने का स्व-घोषणा पत्र, आधार और राशन कार्ड अपलोड करें।",
            "आवेदन सबमिट करें और रसीद डाउनलोड करें।"
        ],
        "offline_en": "Submit physical application forms at your local Anganwadi Centre, Gram Panchayat, Ward Office, or Setu Suvidha Kendra.",
        "offline_mr": "स्थानिक अंगणवाडी केंद्र, ग्रामपंचायत, प्रभाग कार्यालय किंवा सेतू सुविधा केंद्रात जाऊन विनामूल्य अर्ज सादर करू शकता.",
        "offline_hi": "अपने नजदीकी आंगनवाड़ी केंद्र, ग्राम पंचायत, वार्ड कार्यालय या सेतु सुविधा केंद्र में फॉर्म भरकर जमा करें।"
    },
    "NSMSNY-MH": {
        "portal_name": "Namo Shetkari Maha Samman Nidhi Yojana (Maharashtra Agriculture)",
        "official_url": "https://krishi.maharashtra.gov.in/",
        "application_url": "https://pmkisan.gov.in/",
        "status_url": "https://krishi.maharashtra.gov.in/",
        "source_url": "https://krishi.maharashtra.gov.in/",
        "verification_date": "2026-11-10",
        "benefits_en": "Direct financial aid of ₹6,000 per year (3 instalments of ₹2,000) for Maharashtra farmers, in addition to PM-KISAN, giving Maharashtra farmers a total of ₹12,000 per year.",
        "benefits_mr": "महाराष्ट्र शासनाकडून शेतकऱ्यांना वर्षाला ₹६,००० (३ हप्त्यांमध्ये ₹२,०००). PM-KISAN चे ₹६,००० मिळून महाराष्ट्रातील शेतकऱ्यांना एकूण ₹१२,००० वार्षिक आर्थिक लाभ मिळतो.",
        "benefits_hi": "महाराष्ट्र सरकार द्वारा किसानों को ₹6,000 प्रति वर्ष (₹2,000 की 3 किस्तें)। PM-KISAN के साथ मिलकर महाराष्ट्र के किसानों को कुल ₹12,000 प्रति वर्ष प्राप्त होते हैं।",
        "steps_en": [
            "No separate application form is required for Maharashtra farmers who are already registered and approved under PM-KISAN.",
            "Ensure your PM-KISAN registration is active and verified at https://pmkisan.gov.in/.",
            "The Department of Agriculture, Government of Maharashtra automatically maps all verified PM-KISAN beneficiaries in Maharashtra.",
            "Check that your bank account has active Aadhaar-DBT mapping to receive both Central and Maharashtra state installments."
        ],
        "steps_mr": [
            "नमो शेतकरी योजनेसाठी वेगळा अर्ज करण्याची आवश्यकता नाही. ही योजना PM-KISAN डेटाबेसशी जोडलेली आहे.",
            "जर तुमची PM-KISAN योजनेत यशस्वी नोंदणी झाली असेल आणि हप्ते सुरू असतील, तर तुमचा समावेश आपोआप केला जातो.",
            "महाराष्ट्र कृषी विभाग पीएम-किसानच्या पात्र लाभार्थ्यांना थेट नमो शेतकरी योजनेचे ₹२,००० चे हप्ते वर्ग करतो.",
            "केवळ बँक खात्याला आधार लिंक (NPCI DBT) असणे आणि e-KYC पूर्ण असणे आवश्यक आहे."
        ],
        "steps_hi": [
            "इस योजना के लिए अलग से आवेदन करने की आवश्यकता नहीं है। यह सीधे PM-KISAN से जुड़ी है।",
            "यदि आप PM-KISAN के पंजीकृत और सत्यापित लाभार्थी हैं, तो महाराष्ट्र सरकार स्वचालित रूप से लाभ देती है।",
            "पीएम-किसान के ₹2,000 की किस्त के साथ ही नमो शेतकरी के ₹2,000 की किस्त बैंक खाते में डीबीटी द्वारा भेजी जाती है।",
            "सुनिश्चित करें कि आपका ई-केवाईसी पूरा है और बैंक खाते में आधार सीडिंग सक्रिय है।"
        ]
    }
}


def _build_generic_scheme_guide(scheme: Scheme, lang: str) -> Dict[str, Any]:
    """
    Generates an authentic procedural guide for schemes in PostgreSQL.
    Strictly safeguards factual accuracy:
    - If a scheme is pending verification or lacks official URL documentation,
      never fabricates or guesses online application steps.
    - Clearly marks unverified / pending records with explicit disclaimers.
    """
    is_pending = (
        scheme.scheme_status == "pending_verification"
        or not scheme.official_url
        or scheme.last_verified_at is None
    )

    app_url = scheme.application_url or scheme.official_url or scheme.source_url or "https://www.india.gov.in/"
    off_url = scheme.official_url or scheme.source_url or app_url
    ministry_name = scheme.ministry or "Competent Administrative Authority"

    if is_pending:
        # Factual Accuracy: Never invent unverified steps for pending schemes
        if lang == "mr":
            steps = [
                f"⚠️ **पडताळणी प्रलंबित (Pending Verification):** {scheme.name} ची सविस्तर ऑनलाइन अर्ज प्रक्रिया अद्याप अधिकृत शासकीय स्त्रोतांद्वारे पडताळणी अंतर्गत आहे.",
                "या योजनेसाठी खोट्या किंवा अनधिकृत संकेतस्थळांवर अर्ज करू नका किंवा पैसे देऊ नका.",
                f"अधिकृत माहिती व मार्गदर्शक तत्त्वांचे अवलोकन करण्यासाठी अधिकृत स्त्रोत पहा: {scheme.source_url or off_url}",
                f"ऑफलाइन चौकशीसाठी {ministry_name} च्या स्थानिक कार्यालयाशी किंवा शासकीय मदत केंद्राशी संपर्क साधा."
            ]
            offline = f"अधिकृत पडताळणी प्रलंबित असल्याने {ministry_name} च्या अधिकृत कार्यालयात प्रत्यक्ष संपर्क साधून माहितीची खात्री करा."
            benefits = f"[माहिती पडताळणी अंतर्गत] {scheme.benefits}"
        elif lang == "hi":
            steps = [
                f"⚠️ **सत्यापन लंबित (Pending Verification):** {scheme.name} की विस्तृत ऑनलाइन आवेदन प्रक्रिया अभी आधिकारिक सरकारी स्रोतों द्वारा सत्यापन के अधीन है।",
                "इस योजना के लिए किसी भी अनाधिकृत वेबसाइट या दलाल के झांसे में न आएं।",
                f"आधिकारिक सरकारी सूचना का अवलोकन करने हेतु स्रोत देखें: {scheme.source_url or off_url}",
                f"सटीक जानकारी हेतु {ministry_name} के स्थानीय प्रशासनिक कार्यालय से संपर्क करें।"
            ]
            offline = f"सत्यापन लंबित होने के कारण {ministry_name} के अधिकृत कार्यालय में सीधे संपर्क कर जानकारी प्राप्त करें।"
            benefits = f"[जानकारी सत्यापन के अधीन] {scheme.benefits}"
        else:
            steps = [
                f"⚠️ **Pending Verification:** Official online application procedures for {scheme.name} are currently pending authoritative government verification.",
                "To ensure citizen protection, Scheme Saathi does not generate unverified application steps for this record.",
                f"Verify official gazette notifications and published guidelines directly at: {scheme.source_url or off_url}",
                f"For offline verification, consult the local administrative branch of {ministry_name}."
            ]
            offline = f"Due to pending verification status, consult the regional office of {ministry_name} directly."
            benefits = f"[Verification In Progress] {scheme.benefits}"
    else:
        # Verified Active Schemes with Authoritative URLs
        if lang == "mr":
            steps = [
                f"{scheme.name} च्या अधिकृत शासकीय पोर्टलला ({off_url}) भेट द्या.",
                "योजनेच्या नोंदणी / नवीन अर्ज (Citizen Registration) लिंकवर क्लिक करा.",
                "तुमचा आधार क्रमांक आणि संपर्क माहिती भरून मोबाईल OTP द्वारे पडताळणी करा.",
                "आवश्यक वैयक्तिक, कौटुंबिक आणि बँक खाते तपशील अचूक भरा.",
                "संबंधित अधिकृत कागदपत्रे अपलोड करून अर्ज सबमिट करा आणि पावती जतन करा."
            ]
            offline = f"संबंधित {ministry_name} च्या स्थानिक कार्यालयात किंवा जवळच्या सीएससी (CSC) केंद्रात जाऊन अर्ज करू शकता."
            benefits = scheme.benefits
        elif lang == "hi":
            steps = [
                f"{scheme.name} के आधिकारिक सरकारी पोर्टल ({off_url}) पर जाएं।",
                "योजना के ऑनलाइन आवेदन / नागरिक पंजीकरण (Citizen Registration) लिंक का चयन करें।",
                "अपना आधार नंबर और मोबाइल नंबर दर्ज करके OTP सत्यापन पूरा करें।",
                "व्यक्तिगत, पारिवारिक और आधार-सीडेड बैंक खाते का विवरण भरें।",
                "आवश्यक आधिकारिक दस्तावेज़ अपलोड करें और आवेदन सबमिट करके पावती रसीद प्राप्त करें।"
            ]
            offline = f"संबंधित {ministry_name} के स्थानीय कार्यालय या नजदीकी सीएससी (CSC) केंद्र पर जाकर आवेदन कर सकते हैं।"
            benefits = scheme.benefits
        else:
            steps = [
                f"Visit the official government portal for {scheme.name} at {off_url}.",
                "Navigate to the online citizen registration or application section.",
                "Provide your Aadhaar identity details and complete mobile OTP authentication.",
                "Fill in the required statutory application details and bank account information.",
                "Upload the mandatory documents and submit the application to receive your tracking number."
            ]
            offline = f"You can also submit an offline application through the local office of {ministry_name} or nearest Common Service Centre (CSC)."
            benefits = scheme.benefits

    return {
        "portal_name": f"{scheme.name} Portal",
        "official_url": off_url,
        "application_url": app_url,
        "status_url": off_url,
        "is_pending_verification": is_pending,
        f"benefits_{lang}": benefits,
        f"steps_{lang}": steps,
        f"offline_{lang}": offline,
    }


def _format_verification_metadata(
    scheme: Scheme,
    guide: Optional[Dict[str, Any]] = None,
    lang: str = "en",
) -> Tuple[str, Dict[str, Any]]:
    """
    Evaluates scheme verification status and staleness according to GoI standards:
    - If status is 'pending_verification' or last_verified_at is missing:
      Flags scheme as Pending Verification (never asserts unverified data as authoritative).
    - If last_verified_at is older than 180 days (or historical, e.g. 2024 dates vs 2026):
      Flags scheme with a Historical Verification Warning (Stale), displaying the exact past date
      and warning the citizen to check the official portal.
    - If verified within 180 days:
      Displays Official Verification Date (Verified Active) with official source URL link.
    """
    status = getattr(scheme, "scheme_status", None)
    if guide and guide.get("is_pending_verification"):
        status = "pending_verification"
    if not status:
        status = "pending_verification"

    source_url = (
        getattr(scheme, "source_url", None)
        or getattr(scheme, "official_url", None)
        or (guide.get("source_url") if guide else None)
        or (guide.get("official_url") if guide else None)
        or "https://www.india.gov.in/"
    )

    last_verified = getattr(scheme, "last_verified_at", None)
    verified_date_str: Optional[str] = None
    verified_dt: Optional[datetime] = None

    if isinstance(last_verified, datetime):
        verified_dt = last_verified
        verified_date_str = last_verified.strftime("%Y-%m-%d")
    elif isinstance(last_verified, str) and len(last_verified) >= 10:
        verified_date_str = last_verified[:10]
        try:
            verified_dt = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))
        except Exception:
            pass

    if not verified_date_str and guide:
        guide_date = guide.get("verification_date")
        if guide_date and isinstance(guide_date, str) and len(guide_date) >= 10:
            verified_date_str = guide_date[:10]
            try:
                verified_dt = datetime.strptime(verified_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                pass

    now = datetime.now(timezone.utc)
    is_pending = (status == "pending_verification") or (verified_date_str is None)
    is_stale = False

    if not is_pending and verified_dt:
        days_ago = (now - verified_dt).days
        if days_ago > 180:
            is_stale = True

    meta = {
        "status": status if not is_pending else "pending_verification",
        "last_verified_at": verified_date_str,
        "source_url": source_url,
        "is_stale": is_stale,
        "is_pending": is_pending,
    }

    if is_pending:
        if lang == "mr":
            notice = (
                f"⚠️ **पडताळणी स्थिती:** पडताळणी प्रलंबित (Pending Verification)\n"
                f"या योजनेचे अधिकृत नियम व अटी अधिकृत शासकीय स्त्रोतांद्वारे पडताळणी अंतर्गत आहेत. योजना साथी अपडताळित माहिती तयार करत नाही.\n"
                f"🔗 **अधिकृत स्रोत:** [{source_url}]({source_url})"
            )
        elif lang == "hi":
            notice = (
                f"⚠️ **सत्यापन स्थिति:** सत्यापन लंबित (Pending Verification)\n"
                f"इस योजना के आधिकारिक नियम व शर्तें वर्तमान में सत्यापन प्रक्रिया में हैं। योजना साथी असत्यापित आंकड़े प्रस्तुत नहीं करता।\n"
                f"🔗 **आधिकारिक स्रोत:** [{source_url}]({source_url})"
            )
        else:
            notice = (
                f"⚠️ **Verification Status:** Pending Verification\n"
                f"Official statutory guidelines for this scheme are currently pending authoritative government verification. Scheme Saathi does not generate unverified application steps.\n"
                f"🔗 **Official Source:** [{source_url}]({source_url})"
            )
    elif is_stale:
        if lang == "mr":
            notice = (
                f"⚠️ **जुनी पडताळणी सूचना (Stale Verification Warning):**\n"
                f"शेवटची पडताळणी तारीख: **{verified_date_str}**.\n"
                f"या जुन्या पडताळणीनंतर शासकीय नियम, अनुदान किंवा व्याजदरात बदल झालेला असू शकतो. कृपया अर्ज करण्यापूर्वी अधिकृत पोर्टलवर खात्री करा.\n"
                f"🔗 **अधिकृत स्रोत:** [{source_url}]({source_url})"
            )
        elif lang == "hi":
            notice = (
                f"⚠️ **पुरानी सत्यापन चेतावनी (Stale Verification Warning):**\n"
                f"अंतिम सत्यापन तिथि: **{verified_date_str}**।\n"
                f"इस पुरानी सत्यापन तिथि के बाद सरकारी नियमों, सब्सिडी या ब्याज दरों में बदलाव हो सकता है। कृपया आवेदन से पूर्व आधिकारिक पोर्टल पर वर्तमान नियमों की पुष्टि करें।\n"
                f"🔗 **आधिकारिक स्रोत:** [{source_url}]({source_url})"
            )
        else:
            notice = (
                f"⚠️ **Historical Verification Warning (Stale):**\n"
                f"This scheme information was last verified on **{verified_date_str}**.\n"
                f"Statutory guidelines, subsidy amounts, or lending interest rates may have changed since this date. Please confirm current parameters on the official government portal before proceeding.\n"
                f"🔗 **Official Source:** [{source_url}]({source_url})"
            )
    else:
        if lang == "mr":
            notice = (
                f"📅 **अधिकृत पडताळणी दिनांक:** {verified_date_str} (सक्रिय पडताळणी)\n"
                f"🔗 **अधिकृत स्रोत:** [{source_url}]({source_url})"
            )
        elif lang == "hi":
            notice = (
                f"📅 **आधिकारिक सत्यापन तिथि:** {verified_date_str} (सक्रिय सत्यापित)\n"
                f"🔗 **आधिकारिक स्रोत:** [{source_url}]({source_url})"
            )
        else:
            notice = (
                f"📅 **Official Verification Date:** {verified_date_str} (Verified Active)\n"
                f"🔗 **Official Source:** [{source_url}]({source_url})"
            )

    return notice, meta


def _call_gemini_if_configured(
    query: str,
    grounding_context: Dict[str, Any],
    lang: str,
) -> Optional[str]:
    """
    Invokes Google Gemini when a valid API key is present.
    Strictly grounds the LLM response on verified PostgreSQL scheme data.
    """
    api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""
    if not api_key or "your-gemini" in api_key.lower() or "placeholder" in api_key.lower():
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        lang_name = "Marathi" if lang == "mr" else "Hindi" if lang == "hi" else "Indian English"
        system_prompt = (
            f"You are Scheme Saathi, a trusted regional welfare advisor for Indian citizens. "
            f"Respond directly and empathetically in {lang_name}. "
            f"Address the user's exact intent (e.g. application steps, benefits amount, documents, or status). "
            f"Never hallucinate benefits or procedures. Base your answer strictly on this verified data: {grounding_context}"
        )
        response = model.generate_content(
            f"{system_prompt}\n\nCitizen Question: {query}"
        )
        if response and response.text:
            return response.text.strip()
    except Exception as exc:
        logger.warning("Gemini invocation skipped or failed (%s); using deterministic response.", exc)
    return None


# ── Universal Scheme Alias and Vernacular Synonym Registry ──────────────────
# Maps every canonical scheme code to abbreviations, common names, Hindi, and Marathi terms.
SCHEME_ALIASES: Dict[str, List[str]] = {
    "PM-KISAN": [
        "pm-kisan", "pm kisan", "pmkisan", "pm किसान", "pm-किसान", "पीएम किसान",
        "किसान सम्मान", "kisan samman", "kisan samman nidhi", "पीएम-किसान", "pm kishan",
        "pradhan mantri kisan samman nidhi"
    ],
    "KCC": [
        "kcc", "kisan credit card", "kisan credit", "क्रेडिट कार्ड", "किसान क्रेडिट",
        "किसान क्रेडिट कार्ड", "केसीसी", "kisan card"
    ],
    "AB-PMJAY": [
        "ab-pmjay", "ab pmjay", "abpmjay", "pmjay", "pm-jay", "ayushman bharat", "ayushman",
        "आयुष्मान भारत", "आयुष्मान", "पीएम जन आरोग्य", "आयुष्मान जन आरोग्य", "golden card", "गोल्डन कार्ड",
        "pradhan mantri jan arogya yojana"
    ],
    "APY": [
        "apy", "atal pension yojana", "atal pension", "अटल पेंशन", "अटल पेन्शन",
        "अटल पेंशन योजना", "अटल पेन्शन योजना"
    ],
    "DAY-NRLM": [
        "day-nrlm", "day nrlm", "daynrlm", "nrlm", "aajeevika", "aजीविका", "आजीविका",
        "राष्ट्रीय ग्रामीण आजीविका", "राष्ट्रीय ग्रामीण उपजीविका", "rural livelihoods",
        "deendayal antyodaya", "shg loan", "swayam sahayata", "self help group"
    ],
    "JSY": [
        "jsy", "janani suraksha yojana", "janani suraksha", "जननी सुरक्षा", "जननी सुरक्षा योजना",
        "maternal care", "maternity benefit jsy"
    ],
    "MGNREGA": [
        "mgnrega", "nrega", "manrega", "मनरेगा", "नरेगा", "mahatma gandhi employment",
        "100 days work", "रोजगार हमी", "ग्रामीण रोजगार", "100 days employment"
    ],
    "MLBY-MH": [
        "mlby-mh", "mlby", "majhi ladki bahin", "ladki bahin", "लाडकी बहीण", "लाडकी बहिन",
        "मुख्यमंत्री माझी लाडकी बहीण", "माझी लाडकी बहीण", "ladki bahin yojana", "लाडकी बहीण योजना"
    ],
    "MPJAY-MH": [
        "mpjay-mh", "mpjay", "mjpjay", "mahatma jyotirao phule", "jyotirao phule",
        "महात्मा ज्योतिराव फुले", "ज्योतिराव फुले जन आरोग्य", "महात्मा फुले जन आरोग्य",
        "phule yojana", "महात्मा फुले योजना"
    ],
    "NMMS": [
        "nmms", "nmmss", "national means cum merit", "means-cum-merit",
        "means cum merit scholarship", "एनएमएमएस", "मेधावी छात्रवृत्ति", "means merit"
    ],
    "NSMSNY-MH": [
        "nsmsny-mh", "nsmsny", "namo shetkari", "namo shetkari maha samman",
        "नमो शेतकरी", "नमो शेतकरी महासन्मान", "namo shetkari yojana", "नमो शेतकरी योजना"
    ],
    "NSP-CSSS": [
        "nsp-csss", "nsp csss", "csss", "central sector scheme of scholarship",
        "college scholarship", "university scholarship", "केंद्रीय शिष्यवृत्ती", "nsp scholarship"
    ],
    "PM-KMY": [
        "pm-kmy", "pm kmy", "pmkmy", "kisan maan dhan", "kisan mandhan", "किसान मानधन",
        "किसान मान-धन", "kisan pension", "किसान पेन्शन"
    ],
    "PM-SHRI": [
        "pm-shri", "pm shri", "pmshri", "pm schools for rising india", "schools for rising india",
        "पीएम श्री", "पीएम-श्री", "pm-shri schools"
    ],
    "PM-SVANIDHI": [
        "pm-svanidhi", "pm svanidhi", "svanidhi", "street vendor", "street vendors atmanirbhar",
        "रेहड़ी", "स्ट्रीट वेंडर", "स्वनिधी", "स्वनिधि", "पीएम स्वनिधि", "रेहड़ी पटरी"
    ],
    "PM-VISHWAKARMA": [
        "pm-vishwakarma", "pm vishwakarma", "vishwakarma", "विश्वकर्मा", "पीएम विश्वकर्मा",
        "artisan", "कारीगर", "कारागीर", "vishwakarma scheme", "विश्वकर्मा योजना"
    ],
    "PMAY-G": [
        "pmay-g", "pmay gramin", "pmay rural", "आवास ग्रामीण", "पीएम आवास ग्रामीण",
        "awaas gramin", "pradhan mantri awaas yojana gramin", "pmay-gramin", "ग्रामीण आवास"
    ],
    "PMAY-U": [
        "pmay-u", "pmay urban", "आवास शहरी", "पीएम आवास शहरी", "awaas urban",
        "pradhan mantri awas yojana urban", "pmay-u 2.0", "pmay urban 2.0", "शहरी आवास"
    ],
    "PMEGP": [
        "pmegp", "prime minister employment generation", "employment generation programme",
        "पीएमईजीपी", "रोजगार निर्मिती कार्यक्रम", "prime minister's employment generation",
        "pmegp loan"
    ],
    "PMFBY": [
        "pmfby", "fasal bima", "fasal bima yojana", "पीक विमा", "फसल बीमा",
        "crop insurance", "पीएम फसल बीमा", "पिक विमा योजना"
    ],
    "PMJDY": [
        "pmjdy", "jan dhan", "jan dhan yojana", "जन धन", "जनधन", "जन धन योजना",
        "zero balance account", "पीएम जन धन", "जन-धन"
    ],
    "PMJJBY": [
        "pmjjby", "jeevan jyoti", "jeevan jyoti bima", "जीवन ज्योति", "जीवन ज्योती",
        "जीवन ज्योति बीमा", "pm jeevan jyoti", "जीवन ज्योती विमा"
    ],
    "PMKVY": [
        "pmkvy", "kaushal vikas", "kaushal vikas yojana", "कौशल विकास", "कौशल्य विकास",
        "skill development scheme", "pmkvy 4.0", "कौशल विकास योजना"
    ],
    "PMMSY": [
        "pmmsy", "matsya sampada", "matsya sampada yojana", "मत्स्य संपदा", "मत्स्यसंपदा",
        "fisheries scheme", "मत्स्यपालन", "pm matsya sampada", "मत्स्य पालन योजना"
    ],
    "PMMVY": [
        "pmmvy", "matru vandana", "matru vandana yojana", "मातृ वंदना", "मातृ वंदना योजना",
        "maternity benefit", "pm matru vandana", "मातृत्व वंदना"
    ],
    "PMMY": [
        "pmmy", "mudra", "mudra yojana", "mudra loan", "मुद्रा", "मुद्रा योजना",
        "मुद्रा लोन", "pradhan mantri mudra", "shishu kishor tarun", "मुद्रा कर्ज"
    ],
    "PMS-SC": [
        "pms-sc", "pms sc", "post matric scholarship sc", "post-matric sc",
        "अनुसूचित जाती शिष्यवृत्ती", "पोस्ट मैट्रिक छात्रवृत्ति एससी",
        "post matric scholarship for scheduled caste", "sc scholarship"
    ],
    "PMSBY": [
        "pmsby", "suraksha bima", "suraksha bima yojana", "सुरक्षा बीमा", "सुरक्षा विमा",
        "सुरक्षा बीमा योजना", "accident insurance", "pm suraksha bima", "सुरक्षा विमा योजना"
    ],
    "PMUY": [
        "pmuy", "ujjwala", "ujjwala yojana", "lpg gas", "free gas", "उज्ज्वला",
        "उज्ज्वला योजना", "गॅस योजना", "pmuy 2.0", "उज्वला"
    ],
    "SSY": [
        "ssy", "sukanya samriddhi", "sukanya samriddhi yojana", "सुकन्या समृद्धी",
        "सुकन्या समृद्धि", "sukanya", "girl child savings", "सुकन्या योजना"
    ],
    "STANDUP-INDIA": [
        "standup-india", "stand up india", "standup india", "stand-up india",
        "स्टँड अप इंडिया", "स्टैंड अप इंडिया", "stand up", "stand-up"
    ],
}


def _match_schemes_from_query(text: str, schemes: List[Scheme]) -> List[Scheme]:
    """
    Dynamically identifies all relevant welfare schemes referenced in the user's message.
    Supports:
    - Canonical scheme_code (with and without hyphens, case-insensitive)
    - Full official name and short titles from Scheme records in PostgreSQL
    - Multilingual aliases, acronyms, and vernacular names in English, Hindi, and Marathi
    - Multiple scheme references within a single query
    - Span-based overlap suppression (longer specific scheme names take precedence over subphrases)
    Returns a deduplicated list of matched Scheme records sorted by order of mention.
    """
    lower = text.lower()
    raw_spans: List[Tuple[int, int, Scheme]] = []

    def _find_all_spans(needle: str, scheme_obj: Scheme, require_boundary: bool = False):
        if not needle:
            return
        start = 0
        needle_len = len(needle)
        while True:
            idx = lower.find(needle, start)
            if idx == -1:
                break
            end = idx + needle_len
            valid = True
            if require_boundary:
                if idx > 0 and lower[idx - 1].isalnum():
                    valid = False
                if end < len(lower) and lower[end].isalnum():
                    valid = False
            if valid:
                raw_spans.append((idx, end, scheme_obj))
            start = idx + 1

    for scheme in schemes:
        code = scheme.scheme_code
        code_lower = code.lower()

        # 1. Match from universal alias dictionary
        aliases = SCHEME_ALIASES.get(code, [])
        for alias in aliases:
            req_bound = len(alias) <= 4 and alias.isalnum()
            _find_all_spans(alias, scheme, require_boundary=req_bound)

        # 2. Match canonical code directly (e.g. "KCC", "PM-KISAN", "PM KISAN")
        _find_all_spans(code_lower, scheme, require_boundary=(len(code_lower) <= 4))
        if "-" in code_lower:
            _find_all_spans(code_lower.replace("-", " "), scheme, require_boundary=False)

        # 3. Match short title if present (e.g. "Majhi Ladki Bahin", "Stand-Up India")
        if scheme.short_title:
            _find_all_spans(scheme.short_title.lower(), scheme, require_boundary=False)

        # 4. Match official name
        if scheme.name:
            _find_all_spans(scheme.name.lower(), scheme, require_boundary=False)

    if not raw_spans:
        return []

    # Sort candidates by span length descending (longer, more specific phrases first)
    raw_spans.sort(key=lambda s: (s[1] - s[0]), reverse=True)

    # Greedily accept non-overlapping spans
    accepted_spans: List[Tuple[int, int, Scheme]] = []
    for span in raw_spans:
        s_start, s_end, _ = span
        overlaps = False
        for a_start, a_end, _ in accepted_spans:
            if not (s_end <= a_start or s_start >= a_end):
                overlaps = True
                break
        if not overlaps:
            accepted_spans.append(span)

    # Sort accepted spans by start position (natural query reading order)
    accepted_spans.sort(key=lambda s: s[0])

    deduped_schemes: List[Scheme] = []
    seen_codes = set()
    for _, _, s in accepted_spans:
        if s.scheme_code not in seen_codes:
            seen_codes.add(s.scheme_code)
            deduped_schemes.append(s)

    return deduped_schemes


def _extract_intent(
    text: str,
    schemes: Optional[List[Scheme]] = None,
    active_scheme_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify citizen query intent and dynamically identify target scheme(s)/category.
    Supports multi-turn context inheritance when a scheme was previously identified.
    Supports multi-scheme queries when two or more schemes are inquired.
    """
    lower = text.lower()

    intent: Dict[str, Any] = {
        "type": "discovery",
        "scheme_code": None,
        "scheme_codes": [],
        "matched_schemes": [],
        "category": None,
        "is_maharashtra": False,
    }

    # 1. Dynamically match schemes from database catalogue or alias dictionary
    schemes_to_search = schemes
    if not schemes_to_search:
        schemes_to_search = [Scheme(scheme_code=code, name=code) for code in SCHEME_ALIASES]
    matched_schemes = _match_schemes_from_query(text, schemes_to_search)

    if len(matched_schemes) >= 2:
        intent["type"] = "multi_scheme_query"
        intent["matched_schemes"] = matched_schemes
        intent["scheme_codes"] = [s.scheme_code for s in matched_schemes]
        intent["scheme_code"] = matched_schemes[0].scheme_code
    elif len(matched_schemes) == 1:
        intent["matched_schemes"] = matched_schemes
        intent["scheme_codes"] = [matched_schemes[0].scheme_code]
        intent["scheme_code"] = matched_schemes[0].scheme_code
    else:
        # Contextual inheritance: If no scheme specified in query, inherit from active conversation session
        if active_scheme_code:
            intent["scheme_code"] = active_scheme_code

    # Maharashtra state specific keywords
    if any(k in lower for k in [
        "maharashtra", "महाराष्ट्र", "लाडकी बहीण", "ladki bahin", "mlby",
        "नमो शेतकरी", "namo shetkari", "nsmsny", "mpjay", "jyotirao phule", "phule"
    ]):
        intent["is_maharashtra"] = True

    # 2. Identify Category across all 12 canonical welfare domains
    if any(k in lower for k in ["farmer", "farming", "kisan", "kheti", "किसान", "खेती", "शेतकरी", "शेती", "कृषी", "agriculture", "crop", "fasal", "पीक", "मत्स्य", "fisheries"]):
        intent["category"] = "agriculture"
    elif any(k in lower for k in ["student", "school", "college", "छात्र", "विद्यार्थी", "शिक्षण", "education", "scholarship", "शिष्यवृत्ती", "छात्रवृत्ति"]):
        intent["category"] = "education"
    elif any(k in lower for k in ["health", "hospital", "स्वास्थ्य", "आरोग्य", "उपचार", "medical", "jan arogya", "bimari", "बीमार"]):
        intent["category"] = "health"
    elif any(k in lower for k in ["woman", "women", "mahila", "महिला", "स्त्री", "ladki", "bahin", "बहीण", "बहिन", "maternity", "गर्भवती", "sukanya", "कन्या"]):
        intent["category"] = "women_welfare"
    elif any(k in lower for k in ["housing", "house", "ghar", "घर", "मकान", "आवास", "awas", "shelter"]):
        intent["category"] = "housing"
    elif any(k in lower for k in ["employment", "job", "work", "rojgar", "रोजगार", "काम", "मजदूरी", "mgnrega", "मनरेगा", "livelihoods", "उपजीविका", "आजीविका"]):
        intent["category"] = "employment"
    elif any(k in lower for k in ["financial", "bank", "account", "loan", "mudra", "मुद्रा", "ऋण", "कर्ज", "svanidhi", "स्वनिधि", "street vendor", "रेहड़ी", "jandhan", "जन धन"]):
        intent["category"] = "financial_inclusion"
    elif any(k in lower for k in ["pension", "pension yojana", "पेन्शन", "पेंशन", "bima", "विमा", "बीमा", "insurance", "suraksha", "jeevan jyoti", "apy"]):
        intent["category"] = "social_security"
    elif any(k in lower for k in ["skill", "training", "kaushal", "कौशल", "कौशल्य", "कारीगर", "कारागीर", "artisan", "vishwakarma", "विश्वकर्मा"]):
        intent["category"] = "skill_development"
    elif any(k in lower for k in ["senior citizen", "old age", "वृद्ध", "ज्येष्ठ नागरिक", "बुजुर्ग"]):
        intent["category"] = "senior_citizens"
    elif any(k in lower for k in ["disability", "handicapped", "दिव्यांग", "अपंग", "विकलांग"]):
        intent["category"] = "disability"
    elif any(k in lower for k in ["children", "child", "बाल", "मुले", "पोषण", "poshan"]):
        intent["category"] = "children_welfare"

    # If already identified as multi-scheme query, preserve multi-scheme intent
    if intent["type"] == "multi_scheme_query":
        return intent

    # ── Identify Specific Question Intent Type ────────────────────────────────
    # 0. Geographic / State Availability: "Is this available in Maharashtra?"
    if any(k in lower for k in [
        "available in maharashtra", "is this available in maharashtra", "in maharashtra",
        "is this available in", "available in my state", "is this in maharashtra",
        "महाराष्ट्रात उपलब्ध आहे का", "महाराष्ट्रात चालू आहे का", "महाराष्ट्र मध्ये आहे का",
        "क्या यह महाराष्ट्र में उपलब्ध है", "क्या यह योजना महाराष्ट्र में है",
        "maharashtra me available hai kya", "maharashtra me hai kya", "maharashtrat uplabdha aahe ka"
    ]):
        intent["type"] = "geographic_availability"

    # 1. Application Procedure: "How can I apply?", "Steps to apply", "कसा करू", "आवेदन कैसे करें", "apply kaise kare"
    elif any(k in lower for k in [
        "how can i apply", "how to apply", "how do i apply", "apply for", "application procedure",
        "application process", "steps to apply", "want to apply", "need to apply", "how can we apply",
        "अर्ज कसा करावा", "कसा करू", "अर्ज प्रक्रिया", "अर्ज कसा करायचा", "अर्ज कसा भरायचा",
        "आवेदन कैसे करें", "आवेदन की प्रक्रिया", "आवेदन कैसे करे", "apply kaise kare",
        "apply karna hai", "kaise apply karu", "apply kaise hoga", "form kaise bhare",
        "kaise apply kare", "kaise apply karna hai", "form kaise bharna hai", "apply karne ka process",
        "apply karne ka tarika", "process kya hai", "kaise bhare", "kaise kare apply",
    ]):
        intent["type"] = "application_procedure"

    # 2. Registration Portal & Online Application: "Where can I register?", "Can I apply online?", "कुठे नोंदणी करावी", "कहाँ रजिस्टर करें"
    elif any(k in lower for k in [
        "where can i register", "where do i register", "where to register", "registration link",
        "official portal", "portal link", "website", "where can i apply", "can i apply online",
        "can we apply online", "apply online", "कुठे नोंदणी करावी", "नोंदणी कुठे करायची",
        "नोंदणी कशी करायची", "पोर्टल लिंक", "ऑनलाइन अर्ज करता येईल का", "ऑनलाइन अर्ज करू शकतो का",
        "कहाँ रजिस्टर करें", "कहा आवेदन करे", "कहाँ आवेदन करें", "पोर्टल", "रजिस्ट्रेशन पोर्टल",
        "क्या ऑनलाइन आवेदन कर सकते हैं", "क्या ऑनलाइन आवेदन हो सकता है", "official website",
        "portal", "registration website", "kaha register kare", "kaha apply kare", "online apply",
        "kaha se bhare", "portal kya hai", "website kya hai", "portal link kya hai"
    ]):
        intent["type"] = "registration_portal"

    # 3. Benefits & Financial Aid: "What are its benefits?", "How much money will I receive?", "मला किती पैसे मिळतील", "कितना लाभ मिलेगा"
    elif any(k in lower for k in [
        "what are the benefits", "what are its benefits", "what benefits", "benefits of", "benefits",
        "financial assistance", "financial benefit", "how much money", "how much financial assistance",
        "how much will i get", "how much amount", "money receive", "installment amount", "tell me the benefits",
        "explain the benefits",
        "काय लाभ मिळेल", "लाभाचे स्वरूप", "लाभ काय मिळतात", "किती पैसे मिळतील", "किती रुपये मिळतील", "किती हप्ता मिळेल",
        "लाभ काय आहेत", "लाभ सांगा", "फायदे काय आहेत", "काय फायदा होईल",
        "कितने पैसे मिलेंगे", "कितना लाभ मिलेगा", "कितनी राशि", "कितना पैसा मिलेगा", "राशि", "क्या लाभ मिलेगा",
        "फायदे क्या हैं", "लाभ क्या है", "लाभ बताएं", "लाभ बताओ", "के लाभ", "फायदे बताएं", "फायदे बताओ", "फायदे",
        "kitna paisa milega", "kitna benefit", "kitna paisa", "kitne rupaye", "kitna milega",
        "paisa kitna milega", "kya benefit milega", "kya milega", "labh bataye", "fayde kya hai"
    ]):
        intent["type"] = "benefits_inquiry"

    # 4. Post-Registration & Status: "What should I do after registration?", "Status of my application", "नोंदणीनंतर काय करावे", "status"
    elif any(k in lower for k in [
        "what should i do after registration", "after registration", "after apply", "after applying",
        "track status", "application status", "status of my application", "status of application",
        "what is the status", "check status", "know your status", "check my status", "check application status",
        "status of", "my application status", "track my application", "status",
        "नोंदणीनंतर काय करावे", "अर्जाची स्थिती", "स्थिती कशी तपासावी", "स्टेटस", "अर्जाचे स्टेटस",
        "रजिस्ट्रेशन के बाद क्या करें", "आवेदन की स्थिति", "आवेदन के बाद क्या करें", "स्टेटस कैसे चेक करें", "आवेदन का स्टेटस",
        "status kaise check kare", "status check", "after register", "status kya hai", "status check karna hai"
    ]):
        intent["type"] = "post_registration_status"

    # 5. Document Checklist: "What documents are required?", "Which documents do I need?", "कागदपत्रे", "दस्तावेज"
    elif any(k in lower for k in [
        "what documents are required", "which documents do i need", "documents required", "required documents",
        "documents needed", "what documents", "which documents", "checklist of documents",
        "कागदपत्रे कोणती लागतील", "कोणती कागदपत्रे", "कागदपत्रे", "कागदपत्र",
        "दस्तावेज कौन से लगेंगे", "कौन से दस्तावेज", "दस्तावेज", "कागजात",
        "dastavez", "kagadpatre", "kya document lagega", "kya documents lagenge", "documents kya chahiye",
        "documents kya lagega", "konsa document lagega", "konsa kagaz lagega"
    ]):
        intent["type"] = "document_checklist"

    # 6. Eligibility Check: "Who can apply?", "Who is eligible?", "What is the eligibility?", "Am I eligible?"
    elif any(k in lower for k in [
        "who can apply", "who is eligible", "what is the eligibility", "eligibility criteria",
        "who is eligible for", "am i eligible", "is this scheme for me", "can i get", "check eligibility",
        "my eligibility", "eligibility", "criteria to apply", "target beneficiaries",
        "पात्रता काय आहे", "कोण पात्र आहे", "कोण अर्ज करू शकतो", "पात्रता आहे का", "मी पात्र आहे का", "पात्रता तपासा", "पात्रता निकष",
        "पात्रता क्या है", "कौन आवेदन कर सकता है", "कौन पात्र है", "क्या मैं पात्र हूँ", "पात्रता जांचें", "पात्रता", "eligible", "patrata",
        "mujhe milega kya", "kya mujhe milega", "kya mai eligible hu", "patra hu kya", "kon apply kar sakta hai", "kaun apply kar sakta hai"
    ]):
        intent["type"] = "eligibility_check"

    # 7. Scheme Overview / Explanation: "What is this scheme?", "Explain this scheme", "Tell me about"
    elif any(k in lower for k in [
        "what is", "tell me about", "explain", "overview", "about the scheme",
        "योजना काय आहे", "योजनेबद्दल सांगा", "माहिती सांगा", "माहिती द्या",
        "योजना क्या है", "विस्तार से बताओ", "के बारे में बताएं", "बारे में बताओ",
        "details", "scheme details", "kya scheme hai", "kya yojana hai"
    ]):
        intent["type"] = "scheme_overview"

    else:
        intent["type"] = "discovery"

    return intent


def _persist_active_scheme_to_profile(
    profile: Optional[UserProfile],
    conv_id: str,
    scheme_code: str,
    db: Optional[Session] = None,
) -> None:
    """
    Persists active scheme context separately for each authenticated user AND conversation ID.
    Guarantees two browser tabs or sessions belonging to the same user cannot overwrite each other.
    """
    if not profile or not hasattr(profile, "profile_data"):
        return

    if not isinstance(profile.profile_data, dict):
        profile.profile_data = {}

    # Eliminate legacy unisolated single-scheme key
    profile.profile_data.pop("active_conversation_scheme", None)

    active_map = profile.profile_data.get("active_schemes_by_conv")
    if not isinstance(active_map, dict):
        active_map = {}
        profile.profile_data["active_schemes_by_conv"] = active_map

    active_map[conv_id] = {
        "scheme_code": scheme_code,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Bounded cache per profile: preserve most recent 50 conversations
    if len(active_map) > 50:
        sorted_keys = sorted(
            active_map.keys(),
            key=lambda k: active_map[k].get("updated_at", "") if isinstance(active_map[k], dict) else "",
        )
        for old_k in sorted_keys[: len(active_map) - 50]:
            active_map.pop(old_k, None)

    flag_modified(profile, "profile_data")
    if db:
        try:
            db.commit()
        except Exception as exc:
            logger.warning("Could not persist active scheme to profile: %s", exc)
            db.rollback()


def _recover_active_scheme_from_profile(
    profile: Optional[UserProfile],
    conv_id: str,
    schemes: List[Scheme],
) -> Optional[Scheme]:
    """
    Recovers active scheme context strictly for the specified conversation ID from the authenticated user's profile.
    NEVER defaults to PM-KISAN or another conversation's scheme.
    """
    if not profile or not hasattr(profile, "profile_data") or not isinstance(profile.profile_data, dict):
        return None

    active_map = profile.profile_data.get("active_schemes_by_conv")
    if not isinstance(active_map, dict):
        return None

    conv_entry = active_map.get(conv_id)
    if not conv_entry:
        return None

    persisted_code = conv_entry.get("scheme_code") if isinstance(conv_entry, dict) else conv_entry
    if not persisted_code:
        return None

    return next((s for s in schemes if s.scheme_code == persisted_code), None)


def _resolve_active_scheme(
    intent_scheme_code: Optional[str],
    conv_id: str,
    schemes: List[Scheme],
    request_scheme_id: Optional[str] = None,
    user_id: Optional[str] = None,
    profile: Optional[UserProfile] = None,
    db: Optional[Session] = None,
) -> Optional[Scheme]:
    """
    Resolves the targeted scheme considering query mentions, explicit scheme_id,
    and multi-turn session memory context strictly isolated by user ID and conversation ID.
    Supports persistent per-conversation context recovery via PostgreSQL citizen profile.
    CRITICAL: NEVER defaults to PM-KISAN or any other arbitrary scheme when context is absent.
    Returns None if active scheme cannot be resolved, prompting the citizen for clarification.
    """
    # 1. Explicitly identified in current query
    if intent_scheme_code:
        matched = next((s for s in schemes if s.scheme_code == intent_scheme_code), None)
        if matched:
            _update_session_scheme(conv_id, matched.scheme_code, user_id=user_id)
            _persist_active_scheme_to_profile(profile, conv_id, matched.scheme_code, db=db)
            return matched

    # 2. Passed via API request payload
    if request_scheme_id:
        matched = next((s for s in schemes if str(s.id) == request_scheme_id or s.scheme_code == request_scheme_id), None)
        if matched:
            _update_session_scheme(conv_id, matched.scheme_code, user_id=user_id)
            _persist_active_scheme_to_profile(profile, conv_id, matched.scheme_code, db=db)
            return matched

    # 3. Inherit from active in-memory session (user and conversation isolated)
    session = _get_session(conv_id, user_id=user_id)
    cached_code = session.get("active_scheme_code")
    if cached_code:
        matched = next((s for s in schemes if s.scheme_code == cached_code), None)
        if matched:
            return matched

    # 4. Recover from persistent PostgreSQL storage strictly for THIS conv_id (e.g. after backend restart)
    if profile:
        matched = _recover_active_scheme_from_profile(profile, conv_id, schemes)
        if matched:
            logger.info("Session context recovered from PostgreSQL profile for conv %s: scheme=%s", conv_id, matched.scheme_code)
            _update_session_scheme(conv_id, matched.scheme_code, user_id=user_id)
            return matched

    # 5. NO DEFAULT: Return None so caller can ask the citizen for clarification
    logger.info("No active scheme could be resolved for session %s (user=%s)", conv_id, user_id)
    return None


def _handle_clarification_query(lang: str, conv_id: str) -> AgentChatResponse:
    """
    Politely asks citizen to clarify which scheme they are referring to
    when context cannot be recovered, NEVER defaulting to PM-KISAN or any other scheme.
    """
    if lang == "mr":
        msg = (
            "**कोणत्या शासकीय योजनेबद्दल विचारत आहात?**\n\n"
            "आपल्या प्रश्नामध्ये विशिष्ट शासकीय योजनेचा उल्लेख आढळला नाही (उदा. *या योजनेसाठी अर्ज कसा करावा?* किंवा *कागदपत्रे कोणती लागतील?*).\n\n"
            "कृपया योजनेचे नाव स्पष्ट सांगा, जेणेकरून मी अधिकृत अर्ज प्रक्रिया, आवश्यक कागदपत्रे आणि पात्रता निकष तपासू शकेन.\n\n"
            "**प्रमुख शासकीय योजना:**\n"
            "- **PM-KISAN** (पीएम किसान सन्मान निधी)\n"
            "- **AB-PMJAY** (आयुष्मान भारत जन आरोग्य योजना)\n"
            "- **MLBY-MH** (मुख्यमंत्री माझी लाडकी बहीण योजना)\n"
            "- **KCC** (किसान क्रेडिट कार्ड)\n"
            "- **APY** (अटल पेन्शन योजना)"
        )
        spoken = "आपण कोणत्या विशिष्ट शासकीय योजनेबद्दल विचारत आहात? कृपया योजनेचे नाव सांगा."
        followups = [
            "PM-KISAN योजनेबद्दल सांगा",
            "आयुष्मान भारत योजनेबद्दल सांगा",
            "माझी लाडकी बहीण योजनेबद्दल सांगा",
            "किसान क्रेडिट कार्ड (KCC) बद्दल सांगा",
        ]
    elif lang == "hi":
        msg = (
            "**आप किस सरकारी योजना के बारे में पूछ रहे हैं?**\n\n"
            "आपके प्रश्न में योजना का नाम स्पष्ट नहीं है (जैसे *आवेदन कैसे करें?* या *दस्तावेज कौन से लगेंगे?*).\n\n"
            "कृपया योजना का नाम स्पष्ट करें ताकि मैं आपको संबंधित आधिकारिक आवेदन प्रक्रिया, आवश्यक दस्तावेज़ और पात्रता की सही जानकारी दे सकूँ।\n\n"
            "**प्रमुख सरकारी योजनाएं:**\n"
            "- **PM-KISAN** (पीएम किसान सम्मान निधि)\n"
            "- **AB-PMJAY** (आयुष्मान भारत योजना)\n"
            "- **MLBY-MH** (माझी लाडकी बहिन योजना)\n"
            "- **KCC** (किसान क्रेडिट कार्ड)\n"
            "- **APY** (अटल पेंशन योजना)"
        )
        spoken = "आप किस विशिष्ट सरकारी योजना के बारे में पूछ रहे हैं? कृपया योजना का नाम बताएं।"
        followups = [
            "PM-KISAN योजना के बारे में बताएं",
            "आयुष्मान भारत योजना के बारे में बताएं",
            "माझी लाडकी बहिन योजना के बारे में बताएं",
            "किसान क्रेडिट कार्ड (KCC) के बारे में बताएं",
        ]
    else:
        msg = (
            "**Which government scheme are you inquiring about?**\n\n"
            "I could not identify the specific scheme you are referring to (for example, *How do I apply?*, *Which documents do I need?*, or *Am I eligible?*).\n\n"
            "Please specify the official scheme name so I can provide you with the exact verified procedure, statutory benefits, and required document checklist.\n\n"
            "**Common Welfare Schemes:**\n"
            "- **PM-KISAN** (Pradhan Mantri Kisan Samman Nidhi)\n"
            "- **AB-PMJAY** (Ayushman Bharat - PM Jan Arogya Yojana)\n"
            "- **MLBY-MH** (Mukhyamantri Majhi Ladki Bahin Yojana)\n"
            "- **KCC** (Kisan Credit Card)\n"
            "- **APY** (Atal Pension Yojana)"
        )
        spoken = "Which specific government scheme are you referring to? Please specify the scheme name."
        followups = [
            "Tell me about PM-KISAN",
            "Tell me about Ayushman Bharat",
            "Tell me about Majhi Ladki Bahin",
            "Tell me about Kisan Credit Card",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.TEXT,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


# ── Chat Message Processor ───────────────────────────────────────────────────
def process_chat_message(
    db: Session,
    request: AgentChatRequest,
    current_user: Optional[User] = None,
) -> AgentChatResponse:
    """
    Conversational router for Scheme Saathi assistant:
    - Identifies exact intent (application procedure, benefits, documents, eligibility, portal, status, discovery).
    - Maintains multi-turn context across consecutive questions strictly isolated by user_id and conv_id.
    - Personalizes responses with authenticated citizen profile data.
    - Grounds responses in PostgreSQL and AST engine.
    - Synthesizes concise voice output for browser TTS.
    """
    conv_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:8]}"
    user_id = str(current_user.id) if current_user and current_user.id else None

    # Fetch User Profile if authenticated
    profile: Optional[UserProfile] = None
    if current_user:
        profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()

    # Query Schemes from PostgreSQL
    all_schemes = db.scalars(
        select(Scheme)
        .options(selectinload(Scheme.rule_versions), selectinload(Scheme.documents))
        .where(Scheme.scheme_status.in_(["active", "pending_verification"]))
    ).all()

    # In-memory session tracking with persistence recovery strictly per conversation ID
    session = _get_session(conv_id, user_id=user_id)
    if not session.get("active_scheme_code") and profile:
        recovered = _recover_active_scheme_from_profile(profile, conv_id, all_schemes)
        if recovered:
            _update_session_scheme(conv_id, recovered.scheme_code, user_id=user_id)
            session["active_scheme_code"] = recovered.scheme_code

    lang = detect_language(request.message, request.language)

    # ── Intelligent Agent Planning: TALK → MATCH → CHECKLIST → PRE-FILL → CONFIRM ──
    agentic_response = plan_and_execute_agentic_flow(
        db=db,
        request=request,
        current_user=current_user,
        profile=profile,
        session=session,
        lang=lang,
        all_schemes=all_schemes,
    )
    if agentic_response is not None:
        if session.get("active_scheme_code") and profile:
            _persist_active_scheme_to_profile(profile, conv_id, session["active_scheme_code"], db=db)
        return agentic_response

    intent = _extract_intent(request.message, schemes=all_schemes, active_scheme_code=session.get("active_scheme_code"))

    # Route based on detected intent with user isolation
    if intent["type"] == "multi_scheme_query":
        return _handle_multi_scheme_query(db, all_schemes, intent.get("matched_schemes", []), lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "geographic_availability":
        return _handle_geographic_availability_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "application_procedure":
        return _handle_application_procedure_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "registration_portal":
        return _handle_registration_portal_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "benefits_inquiry":
        return _handle_benefits_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "post_registration_status":
        return _handle_post_registration_status_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    elif intent["type"] == "document_checklist":
        return _handle_document_query(db, all_schemes, intent, lang, conv_id, profile, user_id=user_id)
    elif intent["type"] == "eligibility_check":
        return _handle_eligibility_query(db, all_schemes, intent, lang, conv_id, profile, user_id=user_id)
    elif intent["type"] == "scheme_overview":
        return _handle_scheme_overview_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)
    else:
        return _handle_discovery_query(db, all_schemes, intent, lang, conv_id, profile, request.message, user_id=user_id)


# ── Specific Intent Handlers ──────────────────────────────────────────────────

def _handle_multi_scheme_query(
    db: Session,
    schemes: List[Scheme],
    matched_schemes: List[Scheme],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Handles comparison and multi-scheme inquiries across two or more specific schemes."""
    if not matched_schemes:
        return _handle_clarification_query(lang, conv_id)

    # Set the first mentioned scheme as the primary active scheme for subsequent follow-up turns
    primary = matched_schemes[0]
    _update_session_scheme(conv_id, primary.scheme_code, user_id=user_id)
    _persist_active_scheme_to_profile(profile, conv_id, primary.scheme_code, db=db)

    # Build scheme cards for all matched schemes
    cards: List[Dict[str, Any]] = []
    for s in matched_schemes:
        status_str = "pending_verification" if s.scheme_status == "pending_verification" else "verified"
        if profile:
            eval_res = evaluate_scheme_eligibility(s, profile)
            status_str = eval_res.result.value

        cards.append(
            SchemeCardSummary(
                id=str(s.id),
                scheme_code=s.scheme_code,
                name=s.name,
                category=s.category,
                ministry=s.ministry,
                benefits=s.benefits,
                eligibility_status=status_str,
                official_url=s.official_url or s.source_url,
            ).model_dump()
        )

    # Multilingual comparative message
    scheme_count = len(matched_schemes)
    if lang == "mr":
        msg = f"**आपण विचारलेल्या {scheme_count} कल्याणकारी योजनांचा अधिकृत तुलनात्मक तपशील:**\n\n"
        for s in matched_schemes:
            ver_tag = "📅 पडताळणी: सक्रिय अधिकृत" if s.scheme_status == "active" else "⚠️ पडताळणी: प्रलंबित"
            msg += (
                f"### {s.name} ({s.scheme_code})\n"
                f"🏛️ **मंत्रालय/विभाग:** {s.ministry}\n"
                f"💰 **शासकीय लाभ:** {s.benefits}\n"
                f"🎯 **पात्र लाभार्थी:** {', '.join(s.target_beneficiaries or [])}\n"
                f"🌐 **अधिकृत पोर्टल:** [{s.official_url or s.source_url}]({s.official_url or s.source_url}) ({ver_tag})\n\n"
            )
        spoken = f"आपण विचारलेल्या {scheme_count} योजनांचा तुलनात्मक तपशील खालील कार्डमध्ये उपलब्ध आहे."
        followups = [
            f"{s.scheme_code} साठी अर्ज कसा करावा?" for s in matched_schemes[:2]
        ] + [f"{matched_schemes[0].scheme_code} साठी कोणती कागदपत्रे लागतील?"]
    elif lang == "hi":
        msg = f"**आपके द्वारा पूछी गई {scheme_count} योजनाओं का आधिकारिक तुलनात्मक विवरण:**\n\n"
        for s in matched_schemes:
            ver_tag = "📅 सत्यापन: सक्रिय सत्यापित" if s.scheme_status == "active" else "⚠️ सत्यापन: लंबित"
            msg += (
                f"### {s.name} ({s.scheme_code})\n"
                f"🏛️ **मंत्रालय/विभाग:** {s.ministry}\n"
                f"💰 **सरकारी लाभ:** {s.benefits}\n"
                f"🎯 **लक्षित लाभार्थी:** {', '.join(s.target_beneficiaries or [])}\n"
                f"🌐 **आधिकारिक पोर्टल:** [{s.official_url or s.source_url}]({s.official_url or s.source_url}) ({ver_tag})\n\n"
            )
        spoken = f"आपके द्वारा पूछी गई {scheme_count} योजनाओं का तुलनात्मक विवरण नीचे कार्ड में उपलब्ध है।"
        followups = [
            f"{s.scheme_code} के लिए आवेदन कैसे करें?" for s in matched_schemes[:2]
        ] + [f"{matched_schemes[0].scheme_code} के लिए कौन से दस्तावेज़ चाहिए?"]
    else:
        msg = f"**Authoritative Comparative Details for {scheme_count} Inquired Schemes:**\n\n"
        for s in matched_schemes:
            ver_tag = "📅 Verified Active" if s.scheme_status == "active" else "⚠️ Pending Verification"
            msg += (
                f"### {s.name} ({s.scheme_code})\n"
                f"🏛️ **Administering Ministry:** {s.ministry}\n"
                f"💰 **Statutory Benefits:** {s.benefits}\n"
                f"🎯 **Target Beneficiaries:** {', '.join(s.target_beneficiaries or [])}\n"
                f"🌐 **Official Portal:** [{s.official_url or s.source_url}]({s.official_url or s.source_url}) ({ver_tag})\n\n"
            )
        spoken = f"Retrieved authoritative comparative details for {scheme_count} schemes. Check cards below."
        followups = [
            f"How do I apply for {s.scheme_code}?" for s in matched_schemes[:2]
        ] + [f"What documents are required for {matched_schemes[0].scheme_code}?"]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.SCHEME_CARDS,
        data=cards,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_geographic_availability_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Answers 'Is this available in Maharashtra?' based on official geographic scope."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    ver_notice, _ = _format_verification_metadata(scheme, None, lang)
    is_mh = (scheme.geographic_scope == "state" or "-MH" in scheme.scheme_code)
    portal_url = scheme.official_url or scheme.source_url or "https://www.india.gov.in/"

    if is_mh:
        if lang == "mr":
            msg = (
                f"**होय, {scheme.name} ({scheme.scheme_code}) ही योजना महाराष्ट्रात उपलब्ध आहे.**\n\n"
                f"ही विशेषतः **महाराष्ट्र शासनाची (Government of Maharashtra)** अधिकृत राज्यस्तरीय योजना असून "
                f"केवळ महाराष्ट्रातील कायमस्वरूपी रहिवासी नागरिकांसाठी लागू आहे.\n\n"
                f"🌐 **अधिकृत राज्य पोर्टल:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"होय, {scheme.name} ही विशेषतः महाराष्ट्र शासनाची योजना असून महाराष्ट्रात पूर्णपणे उपलब्ध आहे."
        elif lang == "hi":
            msg = (
                f"**हाँ, {scheme.name} ({scheme.scheme_code}) योजना महाराष्ट्र में उपलब्ध है।**\n\n"
                f"यह विशेष रूप से **महाराष्ट्र शासन (महाराष्ट्र सरकार)** की आधिकारिक योजना है जो केवल "
                f"महाराष्ट्र के मूल निवासियों के लिए संचालित की जा रही है।\n\n"
                f"🌐 **आधिकारिक राज्य पोर्टल:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"हाँ, {scheme.name} विशेष रूप से महाराष्ट्र सरकार की योजना है और महाराष्ट्र में लागू है।"
        else:
            msg = (
                f"**Yes, {scheme.name} ({scheme.scheme_code}) is available in Maharashtra.**\n\n"
                f"This is an official **Maharashtra State Government** welfare scheme specifically designed "
                f"and implemented for permanent residents of Maharashtra.\n\n"
                f"🌐 **Official State Portal:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"Yes, {scheme.name} is a dedicated Maharashtra State Government scheme available in Maharashtra."
    else:
        # Central Scheme
        if lang == "mr":
            msg = (
                f"**होय, {scheme.name} ({scheme.scheme_code}) ही योजना महाराष्ट्रात उपलब्ध आहे.**\n\n"
                f"ही **केंद्र शासनाची (Government of India)** राष्ट्रीय कल्याणकारी योजना असून महाराष्ट्रासह "
                f"देशभरातील सर्व राज्ये व केंद्रशासित प्रदेशांमध्ये लागू आहे. महाराष्ट्रातील सर्व पात्र नागरिक "
                f"या योजनेसाठी अर्ज करू शकतात.\n\n"
                f"🌐 **अधिकृत पोर्टल:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"होय, {scheme.name} ही राष्ट्रीय योजना असून महाराष्ट्रातील सर्व पात्र नागरिकांसाठी उपलब्ध आहे."
        elif lang == "hi":
            msg = (
                f"**हाँ, {scheme.name} ({scheme.scheme_code}) योजना महाराष्ट्र में उपलब्ध है।**\n\n"
                f"यह **केंद्र सरकार (Government of India)** की राष्ट्रव्यापी योजना है जो महाराष्ट्र सहित "
                f"देश के सभी राज्यों में लागू है। महाराष्ट्र के पात्र नागरिक इस योजना के लिए पूरी तरह आवेदन कर सकते हैं।\n\n"
                f"🌐 **आधिकारिक पोर्टल:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"हाँ, {scheme.name} एक केंद्रीय योजना है और महाराष्ट्र के पात्र नागरिकों के लिए उपलब्ध है।"
        else:
            msg = (
                f"**Yes, {scheme.name} ({scheme.scheme_code}) is available in Maharashtra.**\n\n"
                f"This is a **Central Government** welfare program with nationwide implementation across all Indian "
                f"states and Union Territories, including Maharashtra. Eligible citizens residing in Maharashtra can apply directly.\n\n"
                f"🌐 **Official Portal:** [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"Yes, {scheme.name} is a Central Government scheme with nationwide coverage, available in Maharashtra."

    followups = [
        f"{scheme.scheme_code} साठी अर्ज कसा करावा?" if lang == "mr" else f"{scheme.scheme_code} के लिए आवेदन कैसे करें?" if lang == "hi" else f"How do I apply for {scheme.scheme_code}?",
        f"{scheme.scheme_code} साठी कोणती कागदपत्रे लागतील?" if lang == "mr" else f"{scheme.scheme_code} के लिए कौन से दस्तावेज़ चाहिए?" if lang == "hi" else f"Which documents do I need for {scheme.scheme_code}?",
        f"मी या योजनेसाठी पात्र आहे का?" if lang == "mr" else f"क्या मैं इस योजना के लिए पात्र हूँ?" if lang == "hi" else f"Am I eligible for {scheme.scheme_code}?",
    ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.TEXT,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_application_procedure_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Explains the exact step-by-step application procedure with official links and profile checks."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    guide = VERIFIED_SCHEME_GUIDES.get(scheme.scheme_code) or _build_generic_scheme_guide(scheme, lang)
    ver_notice, ver_meta = _format_verification_metadata(scheme, guide, lang)

    app_url = guide.get("application_url") or scheme.application_url or scheme.official_url or scheme.source_url or "https://www.india.gov.in/"
    steps = guide.get(f"steps_{lang}") or guide.get("steps_en") or []
    offline_proc = guide.get(f"offline_{lang}") or guide.get("offline_en") or ""

    # Personalize with citizen profile & eligibility evaluation
    elig_notes = ""
    elig_status = None
    if profile:
        eval_res = evaluate_scheme_eligibility(scheme, profile)
        elig_status = eval_res.result.value

        if elig_status == "eligible":
            if lang == "mr":
                elig_notes = f"✅ **पात्रता पडताळणी:** तुमच्या जतन केलेल्या प्रोफाईलनुसार तुम्ही **{scheme.name}** साठी पात्र आहात. तुम्ही थेट नोंदणी करू शकता."
            elif lang == "hi":
                elig_notes = f"✅ **पात्रता जांच:** आपकी प्रोफ़ाइल के अनुसार आप **{scheme.name}** के लिए पात्र हैं। आप सीधे आवेदन कर सकते हैं।"
            else:
                elig_notes = f"✅ **Eligibility Check:** Based on your saved profile, you satisfy the preliminary eligibility criteria for **{scheme.name}**. You can proceed directly with registration."
        elif elig_status == "not_eligible":
            reason = eval_res.failed_conditions[0].explanation if eval_res.failed_conditions else "काही अटी जुळत नाहीत"
            if lang == "mr":
                elig_notes = f"⚠️ **महत्त्वाची सूचना:** तुमच्या सध्याच्या प्रोफाईलनुसार तुम्ही अपात्र दिसू शकता (कारण: {reason}). अर्ज करण्यापूर्वी अटी तपासा किंवा प्रोफाईल अपडेट करा."
            elif lang == "hi":
                elig_notes = f"⚠️ **महत्वपूर्ण सूचना:** आपके प्रोफाइल के अनुसार आप वर्तमान में अपात्र दिख सकते हैं (कारण: {reason})। आवेदन करने से पहले कृपया शर्तें जांचें।"
            else:
                elig_notes = f"⚠️ **Important Advisory:** Based on your saved profile, you may not currently qualify (Reason: {reason}). Verify requirements before applying."
        elif elig_status == "insufficient_information":
            missing = ", ".join(m.replace("_", " ") for m in eval_res.missing_fields)
            if lang == "mr":
                elig_notes = f"ℹ️ **कागदपत्र सूचना:** अर्जासाठी तुमच्या प्रोफाईलमध्ये **{missing}** ही माहिती आवश्यक आहे. अर्ज भरताना संबंधित कागदपत्रे सोबत ठेवा."
            elif lang == "hi":
                elig_notes = f"ℹ️ **दस्तावेज़ सूचना:** आवेदन हेतु आपकी प्रोफाइल में **{missing}** विवरण आवश्यक है। आवेदन करते समय संबंधित प्रमाण तैयार रखें।"
            else:
                elig_notes = f"ℹ️ **Profile Notice:** Additional details required: **{missing}**. Ensure you have supporting certificates ready when applying."

    # Construct multilingual response text
    steps_formatted = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(steps))

    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) साठी अर्ज कसा करावा:**\n\n"
            f"**ऑनलाईन अर्ज प्रक्रिया (Online Steps):**\n"
            f"{steps_formatted}\n\n"
            f"**अधिकृत नोंदणी पोर्टल:** [{app_url}]({app_url})\n\n"
            f"**ऑफलाइन अर्ज पर्याय:**\n{offline_proc}\n\n"
            f"{ver_notice}\n\n"
            f"ℹ️ **मार्गदर्शन सूचना:** योजना साथी ही शासकीय योजनांची माहिती, आवश्यक कागदपत्रे व अधिकृत लिंक्स उपलब्ध करून देणारी सहाय्यक प्रणाली आहे. योजना साथीद्वारे थेट शासकीय अर्ज सादर केला जात नाही. अधिकृत नोंदणी संबंधित शासकीय पोर्टलवर किंवा सीएससी केंद्रात स्वतः पूर्ण करावी."
        )
        if elig_notes:
            msg += f"\n\n{elig_notes}"
        spoken = f"{scheme.name} साठी अर्ज करण्यासाठी {guide.get('portal_name', 'अधिकृत पोर्टलवर')} जाऊन नवीन नोंदणी पर्याय निवडा. सविस्तर पायऱ्या खाली दिल्या आहेत."
        followups = [
            f"{scheme.scheme_code} साठी कोणती कागदपत्रे लागतील?",
            "नोंदणी कुठे करावी?",
            "मला किती पैसे मिळतील?",
            "नोंदणीनंतर काय करावे?",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) के लिए आवेदन कैसे करें:**\n\n"
            f"**ऑनलाइन आवेदन प्रक्रिया (Online Steps):**\n"
            f"{steps_formatted}\n\n"
            f"**आधिकारिक आवेदन पोर्टल:** [{app_url}]({app_url})\n\n"
            f"**ऑफलाइन आवेदन विकल्प:**\n{offline_proc}\n\n"
            f"{ver_notice}\n\n"
            f"ℹ️ **मार्गदर्शन सूचना:** योजना साथी नागरिकों को आधिकारिक मार्गदर्शन, दस्तावेज चेकलिस्ट और आधिकारिक पोर्टल लिंक प्रदान करता है। योजना साथी कोई सरकारी पंजीकरण प्राधिकरण नहीं है और यह आपका आवेदन सीधे जमा नहीं करता है। आधिकारिक पंजीकरण आपको आधिकारिक सरकारी पोर्टल या अधिकृत सीएससी पर स्वयं पूरा करना होगा।"
        )
        if elig_notes:
            msg += f"\n\n{elig_notes}"
        spoken = f"{scheme.name} में आवेदन के लिए आधिकारिक पोर्टल {guide.get('portal_name', 'पर')} जाकर पंजीकरण पूरा करें। विवरण नीचे दिया गया है।"
        followups = [
            f"{scheme.scheme_code} के लिए कौन से दस्तावेज़ चाहिए?",
            "पंजीकरण कहाँ करें?",
            "कितने पैसे मिलेंगे?",
            "रजिस्ट्रेशन के बाद क्या करें?",
        ]
    else:
        msg = (
            f"**How to Apply for {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"**Step-by-Step Online Procedure:**\n"
            f"{steps_formatted}\n\n"
            f"**Official Registration Portal:** [{app_url}]({app_url})\n\n"
            f"**Offline Application Options:**\n{offline_proc}\n\n"
            f"{ver_notice}\n\n"
            f"ℹ️ **Application Guidance Notice:** Scheme Saathi provides official guidance, document checklists, and portal links to help you prepare your application. Scheme Saathi is NOT an official government filing authority and does NOT directly submit your application. You must complete your official submission directly on the official government portal or at an authorized CSC center."
        )
        if elig_notes:
            msg += f"\n\n{elig_notes}"
        spoken = f"To apply for {scheme.name}, visit the official portal and select New Registration. Detailed step-by-step instructions are provided below."
        followups = [
            f"Which documents do I need for {scheme.scheme_code}?",
            "Where can I register?",
            "How much money will I receive?",
            "What should I do after registration?",
        ]

    # Grounded Gemini enrichment if active
    gemini_reply = _call_gemini_if_configured(
        query=raw_query,
        grounding_context={
            "scheme": scheme.name,
            "steps": steps,
            "portal": app_url,
            "offline": offline_proc,
            "eligibility_notes": elig_notes,
        },
        lang=lang,
    )
    engine_mode = "gemini_grounded" if gemini_reply else "deterministic"
    if gemini_reply:
        msg = gemini_reply

    guide_payload = {
        "scheme_id": str(scheme.id),
        "scheme_code": scheme.scheme_code,
        "scheme_name": scheme.name,
        "official_url": scheme.official_url or app_url,
        "application_url": app_url,
        "source_url": ver_meta["source_url"],
        "last_verified_at": ver_meta["last_verified_at"],
        "verification_status": ver_meta["status"],
        "is_stale": ver_meta["is_stale"],
        "steps": steps,
        "offline_procedure": offline_proc,
        "citizen_eligibility_status": elig_status,
        "citizen_eligibility_notes": elig_notes,
    }

    spoken = _clean_markdown_for_speech(msg, lang)
    form_draft = tool_fill_form(db, None, profile, scheme.scheme_code)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.APPLICATION_GUIDE,
        workflow_step="PRE-FILL",
        active_scheme={"scheme_code": scheme.scheme_code, "name": scheme.name},
        form_draft_data=form_draft if form_draft.get("form_supported") else None,
        data=guide_payload,
        suggested_followups=followups,
        requires_action=True,
        action_type="confirm_submission",
        engine_mode=engine_mode,
    )


def _handle_registration_portal_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Answers 'Where can I register?' with official portals and local centers."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    guide = VERIFIED_SCHEME_GUIDES.get(scheme.scheme_code) or _build_generic_scheme_guide(scheme, lang)

    app_url = guide.get("application_url") or scheme.application_url or scheme.official_url or scheme.source_url or "https://www.india.gov.in/"
    offline = guide.get(f"offline_{lang}") or guide.get("offline_en") or ""

    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) ची अधिकृत नोंदणी खालील ठिकाणी उपलब्ध आहे:**\n\n"
            f"🌐 **अधिकृत ऑनलाईन पोर्टल:** [{app_url}]({app_url})\n\n"
            f"🏛️ **ऑफलाइन नोंदणी केंद्रे:**\n{offline}\n\n"
            f"📌 **टीप:** कोणत्याही अनधिकृत खाजगी एजंट किंवा बनावट वेबसाईटवर पैसे देऊ नका. ही शासकीय नोंदणी पूर्णपणे मोफत किंवा नाममात्र CSC शुल्कासह उपलब्ध आहे."
        )
        spoken = f"{scheme.name} ची अधिकृत नोंदणी {app_url} वर किंवा जवळच्या सीएससी केंद्रात उपलब्ध आहे."
        followups = [
            f"{scheme.scheme_code} साठी अर्ज कसा करावा?",
            "कोणती कागदपत्रे लागतील?",
            "मला किती पैसे मिळतील?",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) का आधिकारिक पंजीकरण यहाँ उपलब्ध है:**\n\n"
            f"🌐 **आधिकारिक ऑनलाइन पोर्टल:** [{app_url}]({app_url})\n\n"
            f"🏛️ **ऑफलाइन पंजीकरण केंद्र:**\n{offline}\n\n"
            f"📌 **महत्वपूर्ण:** किसी भी अनाधिकृत पोर्टल या दलाल से बचें। सरकारी पंजीकरण आधिकारिक पोर्टल या अधिकृत सीएससी पर ही करें।"
        )
        spoken = f"{scheme.name} का आधिकारिक पंजीकरण {app_url} या नजदीकी सीएससी केंद्र पर किया जा सकता है।"
        followups = [
            f"{scheme.scheme_code} के लिए आवेदन कैसे करें?",
            "कौन से दस्तावेज़ चाहिए?",
            "कितने पैसे मिलेंगे?",
        ]
    else:
        msg = (
            f"**Official Registration Portals for {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"🌐 **Official Online Portal:** [{app_url}]({app_url})\n\n"
            f"🏛️ **In-Person Offline Centers:**\n{offline}\n\n"
            f"📌 **Security Notice:** Always use official .gov.in domains or registered CSC Village Level Entrepreneurs. Avoid fraudulent portals."
        )
        spoken = f"Official registration for {scheme.name} is available online at {app_url} and offline at authorized CSC centres."
        followups = [
            f"How do I apply for {scheme.scheme_code}?",
            "Which documents do I need?",
            "How much money will I receive?",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.TEXT,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_benefits_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Answers 'How much money will I receive?' with verified statutory financial figures."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    guide = VERIFIED_SCHEME_GUIDES.get(scheme.scheme_code) or _build_generic_scheme_guide(scheme, lang)
    ver_notice, ver_meta = _format_verification_metadata(scheme, guide, lang)

    benefit_text = guide.get(f"benefits_{lang}") or scheme.benefits

    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) अंतर्गत मिळणारे आर्थिक सहाय्य:**\n\n"
            f"💰 **लाभाचे स्वरूप:** {benefit_text}\n\n"
            f"🏦 **वितरण पद्धत:** सर्व आर्थिक लाभ थेट लाभ हस्तांतरण (DBT) द्वारे कोणत्याही मध्यस्थाशिवाय आधारशी जोडलेल्या थेट बँक खात्यात जमा केले जातात.\n\n"
            f"{ver_notice}"
        )
        spoken = f"{scheme.name} अंतर्गत {benefit_text[:120]} थेट बँक खात्यात दिले जातात."
        followups = [
            f"{scheme.scheme_code} साठी अर्ज कसा करावा?",
            "कोणती कागदपत्रे लागतील?",
            "मी या योजनेसाठी पात्र आहे का?",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) के तहत वित्तीय सहायता:**\n\n"
            f"💰 **वित्तीय लाभ:** {benefit_text}\n\n"
            f"🏦 **भुगतान माध्यम:** संपूर्ण राशि बिना किसी बिचौलिए के प्रत्यक्ष लाभ अंतरण (DBT) के माध्यम से सीधे आपके आधार-सीडेड बैंक खाते में भेजी जाती है।\n\n"
            f"{ver_notice}"
        )
        spoken = f"{scheme.name} के तहत {benefit_text[:120]} सीधे बैंक खाते में प्रदान किए जाते हैं।"
        followups = [
            f"{scheme.scheme_code} के लिए आवेदन कैसे करें?",
            "दस्तावेज कौन से लगेंगे?",
            "क्या मैं इस योजना के लिए पात्र हूँ?",
        ]
    else:
        msg = (
            f"**Financial Assistance & Benefits for {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"💰 **Statutory Benefit:** {benefit_text}\n\n"
            f"🏦 **Disbursement Mechanism:** 100% Direct Benefit Transfer (DBT) credited directly into the beneficiary's Aadhaar-linked bank account without intermediaries.\n\n"
            f"{ver_notice}"
        )
        spoken = f"Under {scheme.name}, {benefit_text[:120]} is disbursed directly via DBT into your bank account."
        followups = [
            f"How can I apply for {scheme.scheme_code}?",
            "Which documents do I need?",
            "Am I eligible for this scheme?",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.BENEFITS_INFO,
        data={
            "scheme_id": str(scheme.id),
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.name,
            "benefits": benefit_text,
            "last_verified_at": ver_meta["last_verified_at"],
            "verification_status": ver_meta["status"],
            "is_stale": ver_meta["is_stale"],
            "source_url": ver_meta["source_url"],
            "official_url": scheme.official_url,
        },
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_post_registration_status_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """
    Answers 'What should I do after registration?' with e-KYC and status check steps.
    Strictly safeguards that application status is NEVER fabricated or simulated.
    """
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    guide = VERIFIED_SCHEME_GUIDES.get(scheme.scheme_code) or _build_generic_scheme_guide(scheme, lang)

    post_steps = guide.get(f"post_registration_{lang}") or guide.get("post_registration_en") or [
        "Check your registered mobile number for SMS confirmation containing your Application ID.",
        "Ensure your bank account is seeded with Aadhaar and active on the NPCI mapper for DBT payments.",
        "Track your application status on the official portal using your Registration Number.",
        "Cooperate with local field verification officers when contacted for land/identity verification."
    ]

    steps_formatted = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(post_steps))
    status_url = guide.get("status_url") or scheme.official_url or scheme.source_url or "https://www.india.gov.in/"

    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) नोंदणीनंतर काय करावे व अर्जाची स्थिती:**\n\n"
            f"{steps_formatted}\n\n"
            f"🔍 **अधिकृत अर्जाची स्थिती तपासा (Know Your Status):** [{status_url}]({status_url})\n\n"
            f"📌 **पारदर्शकता सूचना:** योजना साथी कोणत्याही अर्जाची खोटी किंवा अंदाजे स्थिती तयार करत नाही. खरी स्थिती पाहण्यासाठी अधिकृत सरकारी पोर्टलवर आपला नोंदणी क्रमांक टाका."
        )
        spoken = f"नोंदणीनंतर अनिवार्य e-KYC पूर्ण करा आणि अधिकृत पोर्टलवर नो युवर स्टेटस पर्यायातून अर्जाची स्थिती तपासा."
        followups = [
            f"{scheme.scheme_code} अंतर्गत किती पैसे मिळतात?",
            "नोंदणी कुठे करावी?",
            "इतर शासकीय योजना सांगा",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) पंजीकरण के बाद के चरण और स्थिति ट्रैकिंग:**\n\n"
            f"{steps_formatted}\n\n"
            f"🔍 **आधिकारिक आवेदन की स्थिति जांचें (Know Your Status):** [{status_url}]({status_url})\n\n"
            f"📌 **पारदर्शिता सूचना:** योजना साथी किसी भी नागरिक के आवेदन की मनगढ़ंत या फर्जी स्थिति नहीं बताता। आवेदन की वास्तविक सरकारी स्थिति जानने हेतु केवल आधिकारिक पोर्टल पर अपना रजिस्ट्रेशन नंबर दर्ज करें।"
        )
        spoken = f"पंजीकरण के बाद अनिवार्य ई-केवाईसी पूरी करें और आधिकारिक पोर्टल पर स्टेटस चेक करें।"
        followups = [
            f"{scheme.scheme_code} के तहत कितने पैसे मिलते हैं?",
            "पंजीकरण कहाँ करें?",
            "अन्य योजनाएं बताएं",
        ]
    else:
        msg = (
            f"**Post-Registration Steps & Status Tracking for {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"{steps_formatted}\n\n"
            f"🔍 **Track Official Application Status:** [{status_url}]({status_url})\n\n"
            f"📌 **Transparency Advisory:** Scheme Saathi never fabricates application statuses or simulates government approval. Official real-time status must be verified directly through the designated government portal using your valid Registration ID."
        )
        spoken = f"After registration, complete mandatory e-KYC and track your official application status under Know Your Status."
        followups = [
            f"How much money will I receive under {scheme.scheme_code}?",
            "Where can I register?",
            "Show other eligible schemes",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.STATUS_TRACKING,
        data={
            "scheme_id": str(scheme.id),
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.name,
            "status_url": status_url,
            "post_steps": post_steps,
        },
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_document_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Handles questions asking what documents are required."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)
    docs = scheme.documents or []
    ver_notice, _ = _format_verification_metadata(scheme, None, lang)

    doc_payload = [
        {
            "id": str(d.id),
            "document_type": d.document_type,
            "title": d.title or d.document_type.replace("_", " ").title(),
            "is_mandatory": d.is_mandatory,
            "issuing_authority": d.issuing_authority or "Competent Government Authority",
            "guidance": d.guidance or "",
            "source_url": d.source_url,
        }
        for d in docs
    ]

    portal_url = scheme.official_url or scheme.source_url or "https://www.india.gov.in/"

    if doc_payload:
        doc_list_text = "\n".join(
            f"- **{d['title']}** ({'अनिवार्य / Mandatory' if d['is_mandatory'] else 'पर्यायी / Optional'}): {d['guidance']} [प्राधिकरण: {d['issuing_authority']}]"
            for d in doc_payload
        )
        if lang == "mr":
            msg = (
                f"**{scheme.name} ({scheme.scheme_code}) साठी आवश्यक अधिकृत कागदपत्रे:**\n\n"
                f"{doc_list_text}\n\n"
                f"📌 **महत्त्वाची टीप:** सर्व कागदपत्रांवरील नाव आणि जन्मतारीख आधार कार्डाशी जुळणे आवश्यक आहे.\n\n"
                f"{ver_notice}"
            )
            spoken = f"{scheme.name} साठी आधार कार्ड, बँक पासबुक आणि संबंधित कागदपत्रे लागतील. खालील यादी पहा."
        elif lang == "hi":
            msg = (
                f"**{scheme.name} ({scheme.scheme_code}) के लिए आवश्यक आधिकारिक दस्तावेज:**\n\n"
                f"{doc_list_text}\n\n"
                f"📌 **महत्वपूर्ण सूचना:** सभी दस्तावेजों में नाम और जन्म तिथि आधार कार्ड से मेल खानी चाहिए।\n\n"
                f"{ver_notice}"
            )
            spoken = f"{scheme.name} के लिए आधार कार्ड, बैंक पासबुक और आवश्यक दस्तावेज लगेंगे। नीचे विवरण देखें."
        else:
            msg = (
                f"**Official Checklist of Required Documents for {scheme.name} ({scheme.scheme_code}):**\n\n"
                f"{doc_list_text}\n\n"
                f"📌 **Important Note:** Ensure the name on your bank account and land documents matches your Aadhaar Card exactly.\n\n"
                f"{ver_notice}"
            )
            spoken = f"For {scheme.name}, check the required document checklist below."
    else:
        # Factual transparency: information unavailable in database checklist
        if lang == "mr":
            msg = (
                f"**{scheme.name} ({scheme.scheme_code}) साठी आवश्यक कागदपत्रे:**\n\n"
                f"⚠️ **माहिती अद्याप उपलब्ध नाही:** या योजनेसाठी आवश्यक कागदपत्रांची स्वतंत्र यादी सध्या डेटाबेसमध्ये उपलब्ध नाही.\n\n"
                f"कृपया अधिकृत संकेतस्थळावर थेट खात्री करा किंवा स्थानिक {scheme.ministry} कार्यालयाशी संपर्क साधा: [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"{scheme.name} साठी कागदपत्रांची अधिकृत यादी सध्या डेटाबेसमध्ये उपलब्ध नाही. अधिकृत पोर्टल पहा."
        elif lang == "hi":
            msg = (
                f"**{scheme.name} ({scheme.scheme_code}) के लिए आवश्यक आधिकारिक दस्तावेज:**\n\n"
                f"⚠️ **सूचना उपलब्ध नहीं:** इस योजना के लिए आवश्यक दस्तावेजों की आधिकारिक चेकलिस्ट वर्तमान में डेटाबेस में उपलब्ध नहीं है।\n\n"
                f"कृपया आधिकारिक पोर्टल देखें या संबंधित {scheme.ministry} कार्यालय से पुष्टि करें: [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"{scheme.name} के दस्तावेजों की आधिकारिक सूची डेटाबेस में उपलब्ध नहीं है। आधिकारिक पोर्टल देखें।"
        else:
            msg = (
                f"**Official Checklist of Required Documents for {scheme.name} ({scheme.scheme_code}):**\n\n"
                f"⚠️ **Information Currently Unavailable:** The statutory document checklist for this scheme is currently unavailable in the database records.\n\n"
                f"Please verify required documents directly at the official portal or contact the administrative office of {scheme.ministry}: [{portal_url}]({portal_url})\n\n"
                f"{ver_notice}"
            )
            spoken = f"Official document checklist for {scheme.name} is currently unavailable in the database. Please check the official portal."

    followups = [
        f"{scheme.scheme_code} साठी अर्ज कसा करावा?" if lang == "mr" else f"{scheme.scheme_code} के लिए आवेदन कैसे करें?" if lang == "hi" else f"How do I apply for {scheme.scheme_code}?",
        f"नोंदणी कुठे करावी?" if lang == "mr" else f"पंजीकरण कहाँ करें?" if lang == "hi" else f"Where can I register?",
        f"मला किती पैसे मिळतील?" if lang == "mr" else f"कितने पैसे मिलेंगे?" if lang == "hi" else f"How much money will I receive?",
    ]

    spoken = _clean_markdown_for_speech(msg, lang)
    checklist_result = tool_build_checklist(db, None, profile, scheme.scheme_code)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.DOCUMENT_CHECKLIST,
        workflow_step="CHECKLIST",
        active_scheme={"scheme_code": scheme.scheme_code, "name": scheme.name},
        checklist_data=checklist_result,
        data=doc_payload,
        suggested_followups=followups,
        requires_action=bool(doc_payload),
        action_type="upload_document" if doc_payload else None,
        engine_mode="deterministic",
    )


def _handle_eligibility_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Handles eligibility evaluation and statutory criteria for a specific scheme."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    ver_notice, _ = _format_verification_metadata(scheme, None, lang)

    # 1. Target beneficiaries from database record
    beneficiaries_str = ", ".join(scheme.target_beneficiaries) if scheme.target_beneficiaries else ("All eligible Indian citizens" if lang == "en" else "पात्र भारतीय नागरिक")

    # 2. Personalized evaluation if citizen profile exists
    eval_result = None
    status_str = "pending_verification" if scheme.scheme_status == "pending_verification" else "verified"
    if profile:
        eval_result = evaluate_scheme_eligibility(scheme, profile)
        status_str = eval_result.result.value

    card_data = [
        SchemeCardSummary(
            id=str(scheme.id),
            scheme_code=scheme.scheme_code,
            name=scheme.name,
            category=scheme.category,
            ministry=scheme.ministry,
            benefits=scheme.benefits,
            eligibility_status=status_str,
            official_url=scheme.official_url or scheme.source_url,
        ).model_dump()
    ]

    # Multilingual response combining statutory criteria + profile evaluation
    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) ची अधिकृत पात्रता आणि निकष:**\n\n"
            f"🎯 **पात्र लाभार्थी:** {beneficiaries_str}\n\n"
            f"💰 **शासकीय लाभ:** {scheme.benefits}\n\n"
            f"🏛️ **प्रशासकीय मंत्रालय:** {scheme.ministry}\n\n"
        )
        if eval_result:
            if status_str == "eligible":
                msg += f"✅ **वैयक्तिक पात्रता पडताळणी:** अभिनंदन! आपल्या जतन केलेल्या प्रोफाईलनुसार आपण या योजनेसाठी **पात्र (Eligible)** आहात.\n\n"
            elif status_str == "potentially_eligible":
                msg += f"ℹ️ **वैयक्तिक पात्रता पडताळणी:** आपल्या प्रोफाईलनुसार आपण **संभाव्य पात्र (Potentially Eligible)** आहात. अंतिम मंजुरीसाठी कागदपत्र पडताळणी आवश्यक आहे.\n\n"
            elif status_str == "insufficient_information":
                missing_text = ", ".join(m.replace("_", " ") for m in eval_result.missing_fields)
                msg += f"ℹ️ **प्रोफाईल सूचना:** पात्रता निश्चित करण्यासाठी प्रोफाईलमध्ये **{missing_text}** ही माहिती आवश्यक आहे.\n\n"
            else:
                reason = eval_result.failed_conditions[0].explanation if eval_result.failed_conditions else "काही अटी पूर्ण झालेल्या नाहीत"
                msg += f"⚠️ **वैयक्तिक पात्रता सूचना:** सध्याच्या प्रोफाईलनुसार आपण अपात्र दिसू शकता (कारण: {reason}).\n\n"
        else:
            msg += "ℹ️ **टीप:** आपल्या वैयक्तिक पात्रतेची स्वयंचलित पडताळणी करण्यासाठी कृपया प्रोफाईल पूर्ण करा.\n\n"
        msg += ver_notice
        spoken = f"{scheme.name} साठी पात्र लाभार्थी: {beneficiaries_str[:80]}."

        followups = [
            f"{scheme.scheme_code} साठी अर्ज कसा करावा?",
            f"{scheme.scheme_code} साठी कोणती कागदपत्रे लागतील?",
            f"{scheme.scheme_code} अंतर्गत किती पैसे मिळतील?",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) की आधिकारिक पात्रता व शर्तें:**\n\n"
            f"🎯 **लक्षित लाभार्थी:** {beneficiaries_str}\n\n"
            f"💰 **सरकारी लाभ:** {scheme.benefits}\n\n"
            f"🏛️ **प्रशासनिक मंत्रालय:** {scheme.ministry}\n\n"
        )
        if eval_result:
            if status_str == "eligible":
                msg += f"✅ **व्यक्तिगत पात्रता जांच:** बधाई हो! आपकी सहेजी गई प्रोफ़ाइल के अनुसार आप इस योजना के लिए **पात्र (Eligible)** हैं।\n\n"
            elif status_str == "potentially_eligible":
                msg += f"ℹ️ **व्यक्तिगत पात्रता जांच:** आपकी प्रोफ़ाइल के अनुसार आप **संभावित रूप से पात्र (Potentially Eligible)** हैं। दस्तावेज़ सत्यापन आवश्यक है।\n\n"
            elif status_str == "insufficient_information":
                missing_text = ", ".join(m.replace("_", " ") for m in eval_result.missing_fields)
                msg += f"ℹ️ **प्रोफ़ाइल सूचना:** पात्रता पुष्टि हेतु प्रोफ़ाइल में **{missing_text}** विवरण आवश्यक है।\n\n"
            else:
                reason = eval_result.failed_conditions[0].explanation if eval_result.failed_conditions else "शर्तें पूरी नहीं हुई हैं"
                msg += f"⚠️ **व्यक्तिगत पात्रता सूचना:** आपकी वर्तमान प्रोफ़ाइल के अनुसार आप अपात्र दिख सकते हैं (कारण: {reason})।\n\n"
        else:
            msg += "ℹ️ **नोट:** अपनी व्यक्तिगत पात्रता की स्वचालित जांच के लिए कृपया अपनी प्रोफ़ाइल पूरी करें।\n\n"
        msg += ver_notice
        spoken = f"{scheme.name} के लिए लक्षित लाभार्थी: {beneficiaries_str[:80]}."

        followups = [
            f"{scheme.scheme_code} के लिए आवेदन कैसे करें?",
            f"{scheme.scheme_code} के लिए कौन से दस्तावेज़ चाहिए?",
            f"{scheme.scheme_code} के तहत कितने पैसे मिलते हैं?",
        ]
    else:
        msg = (
            f"**Official Eligibility & Target Beneficiaries for {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"🎯 **Target Beneficiaries:** {beneficiaries_str}\n\n"
            f"💰 **Statutory Benefits:** {scheme.benefits}\n\n"
            f"🏛️ **Administering Ministry:** {scheme.ministry}\n\n"
        )
        if eval_result:
            if status_str == "eligible":
                msg += f"✅ **Personalized Eligibility:** Congratulations! Based on your verified citizen profile, you are **Eligible** for this scheme.\n\n"
            elif status_str == "potentially_eligible":
                msg += f"ℹ️ **Personalized Advisory:** You are **Potentially Eligible**. Baseline conditions match; official documentation verification is required.\n\n"
            elif status_str == "insufficient_information":
                missing_text = ", ".join(m.replace("_", " ") for m in eval_result.missing_fields)
                msg += f"ℹ️ **Profile Update Needed:** To confirm your eligibility, please update your profile with: **{missing_text}**.\n\n"
            else:
                reason = eval_result.failed_conditions[0].explanation if eval_result.failed_conditions else "Statutory exclusion criteria met."
                msg += f"⚠️ **Personalized Advisory:** Based on your current profile, you may not qualify (Reason: {reason}).\n\n"
        else:
            msg += "ℹ️ **Note:** Complete or update your citizen profile to receive automatic personalized eligibility evaluation.\n\n"
        msg += ver_notice
        spoken = f"Target beneficiaries for {scheme.name}: {beneficiaries_str[:80]}."

        followups = [
            f"How do I apply for {scheme.scheme_code}?",
            f"What documents are required for {scheme.scheme_code}?",
            f"How much money will I receive under {scheme.scheme_code}?",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.SCHEME_CARDS,
        data=card_data,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_scheme_overview_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str,
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Answers general explanation / overview requests for a specific scheme."""
    scheme = _resolve_active_scheme(intent.get("scheme_code"), conv_id, schemes, user_id=user_id, profile=profile, db=db)
    if not scheme:
        return _handle_clarification_query(lang, conv_id)

    ver_notice, _ = _format_verification_metadata(scheme, None, lang)
    portal_url = scheme.official_url or scheme.source_url or "https://www.india.gov.in/"

    card_data = [
        SchemeCardSummary(
            id=str(scheme.id),
            scheme_code=scheme.scheme_code,
            name=scheme.name,
            category=scheme.category,
            ministry=scheme.ministry,
            benefits=scheme.benefits,
            eligibility_status="verified" if scheme.scheme_status == "active" else "pending_verification",
            official_url=portal_url,
        ).model_dump()
    ]

    if lang == "mr":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) योजनेचा तपशील:**\n\n"
            f"📌 **उद्देश:** {scheme.description}\n\n"
            f"💰 **लाभ:** {scheme.benefits}\n\n"
            f"🎯 **पात्र लाभार्थी:** {', '.join(scheme.target_beneficiaries or [])}\n\n"
            f"🏛️ **मंत्रालय:** {scheme.ministry}\n\n"
            f"🌐 **अधिकृत पोर्टल:** [{portal_url}]({portal_url})\n\n"
            f"{ver_notice}"
        )
        spoken = f"{scheme.name} चा उद्देश {scheme.description[:120]} असा आहे."
        followups = [
            f"{scheme.scheme_code} साठी अर्ज कसा करावा?",
            f"{scheme.scheme_code} साठी कोणती कागदपत्रे लागतील?",
            "मी या योजनेसाठी पात्र आहे का?",
        ]
    elif lang == "hi":
        msg = (
            f"**{scheme.name} ({scheme.scheme_code}) का संपूर्ण विवरण:**\n\n"
            f"📌 **उद्देश्य:** {scheme.description}\n\n"
            f"💰 **वित्तीय लाभ:** {scheme.benefits}\n\n"
            f"🎯 **लक्षित लाभार्थी:** {', '.join(scheme.target_beneficiaries or [])}\n\n"
            f"🏛️ **मंत्रालय:** {scheme.ministry}\n\n"
            f"🌐 **आधिकारिक पोर्टल:** [{portal_url}]({portal_url})\n\n"
            f"{ver_notice}"
        )
        spoken = f"{scheme.name} का उद्देश्य {scheme.description[:120]} है।"
        followups = [
            f"{scheme.scheme_code} के लिए आवेदन कैसे करें?",
            f"{scheme.scheme_code} के लिए कौन से दस्तावेज़ चाहिए?",
            "क्या मैं इस योजना के लिए पात्र हूँ?",
        ]
    else:
        msg = (
            f"**Overview of {scheme.name} ({scheme.scheme_code}):**\n\n"
            f"📌 **Purpose:** {scheme.description}\n\n"
            f"💰 **Benefits:** {scheme.benefits}\n\n"
            f"🎯 **Target Beneficiaries:** {', '.join(scheme.target_beneficiaries or [])}\n\n"
            f"🏛️ **Administering Ministry:** {scheme.ministry}\n\n"
            f"🌐 **Official Portal:** [{portal_url}]({portal_url})\n\n"
            f"{ver_notice}"
        )
        spoken = f"{scheme.name} is designed to {scheme.description[:120]}."
        followups = [
            f"How do I apply for {scheme.scheme_code}?",
            f"Which documents do I need?",
            "Am I eligible for this scheme?",
        ]

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.SCHEME_CARDS,
        data=card_data,
        suggested_followups=followups,
        engine_mode="deterministic",
    )


def _handle_discovery_query(
    db: Session,
    schemes: List[Scheme],
    intent: Dict[str, Any],
    lang: str,
    conv_id: str,
    profile: Optional[UserProfile],
    raw_query: str = "",
    user_id: Optional[str] = None,
) -> AgentChatResponse:
    """Handles broad scheme discovery (e.g. 'schemes for farmers', 'Maharashtra schemes')."""
    matched_schemes: List[Scheme] = []

    # Priority 1: Specific scheme if explicitly named
    if intent.get("scheme_code"):
        matched_schemes = [s for s in schemes if s.scheme_code == intent["scheme_code"]]
        if matched_schemes:
            _update_session_scheme(conv_id, matched_schemes[0].scheme_code, user_id=user_id)
            _persist_active_scheme_to_profile(profile, conv_id, matched_schemes[0].scheme_code, db=db)

    # Priority 2: Maharashtra State schemes
    elif intent.get("is_maharashtra"):
        mh_schemes = [s for s in schemes if s.geographic_scope == "state" or "-MH" in s.scheme_code]
        central_relevant = [s for s in schemes if s.category in ["agriculture", "women_welfare", "health"] and s not in mh_schemes]
        matched_schemes = mh_schemes + central_relevant[:2]

    # Priority 3: Category match
    elif intent.get("category"):
        matched_schemes = [s for s in schemes if s.category == intent["category"]]

    # Priority 4: Default featured central schemes
    if not matched_schemes:
        featured_codes = ["PM-KISAN", "KCC", "AB-PMJAY", "PMAY-G", "PMUY"]
        matched_schemes = [s for s in schemes if s.scheme_code in featured_codes]
        if not matched_schemes:
            matched_schemes = schemes[:4]

    # Update session active scheme only if a specific scheme was requested
    if matched_schemes and intent.get("scheme_code"):
        _update_session_scheme(conv_id, matched_schemes[0].scheme_code, user_id=user_id)
        _persist_active_scheme_to_profile(profile, conv_id, matched_schemes[0].scheme_code, db=db)

    # Evaluate eligibility if citizen is authenticated
    cards: List[Dict[str, Any]] = []
    for s in matched_schemes[:4]:
        status_str = "pending_verification"
        if profile:
            eval_res = evaluate_scheme_eligibility(s, profile)
            status_str = eval_res.result.value

        cards.append(
            SchemeCardSummary(
                id=str(s.id),
                scheme_code=s.scheme_code,
                name=s.name,
                category=s.category,
                ministry=s.ministry,
                benefits=s.benefits,
                eligibility_status=status_str,
                official_url=s.official_url,
            ).model_dump()
        )

    # Formulate multilingual response
    count = len(cards)
    if lang == "mr":
        if intent.get("is_maharashtra"):
            msg = f"महाराष्ट्र राज्यातील नागरिकांसाठी आणि शेतकऱ्यांसाठी खालील प्रमुख कल्याणकारी योजना उपलब्ध आहेत:"
            spoken = f"महाराष्ट्र राज्यातील नागरिकांसाठी नमो शेतकरी आणि लाडकी बहीण यासह {count} प्रमुख योजना उपलब्ध आहेत."
        elif intent.get("category") == "agriculture":
            msg = f"शेतकरी बांधवांसाठी केंद्र आणि राज्य शासनाच्या खालील प्रमुख योजना उपलब्ध आहेत:"
            spoken = f"शेतकऱ्यांसाठी PM किसान आणि किसान क्रेडिट कार्ड यासह {count} योजना उपलब्ध आहेत. खालील कार्ड पहा."
        else:
            msg = f"तुमच्यासाठी अधिकृत शासकीय योजनांची यादी खाली दिली आहे:"
            spoken = f"तुमच्यासाठी {count} शासकीय योजना उपलब्ध आहेत. कार्डवर क्लिक करून सविस्तर माहिती पहा."

        followups = [
            "मी PM किसान योजनेसाठी पात्र आहे का?",
            "या योजनांसाठी कोणती कागदपत्रे लागतील?",
            "माझी सर्व पात्र योजनांची यादी दाखवा",
        ]
    elif lang == "hi":
        if intent.get("is_maharashtra"):
            msg = f"महाराष्ट्र के निवासियों के लिए नमो शेतकरी और लाड़की बहिन सहित प्रमुख कल्याणकारी योजनाएं उपलब्ध हैं:"
            spoken = f"महाराष्ट्र के नागरिकों के लिए {count} महत्वपूर्ण सरकारी योजनाएं उपलब्ध हैं। नीचे विवरण देखें।"
        elif intent.get("category") == "agriculture":
            msg = f"किसान भाइयों के लिए पीएम-किसान और केसीसी सहित प्रमुख कृषि योजनाएं उपलब्ध हैं:"
            spoken = f"किसानों के लिए {count} प्रमुख सरकारी योजनाएं उपलब्ध हैं। नीचे दिए गए कार्ड देखें।"
        else:
            msg = f"आपके लिए अधिकृत सरकारी योजनाओं की सूची नीचे दी गई है:"
            spoken = f"आपके लिए {count} सरकारी योजनाएं उपलब्ध हैं। नीचे कार्ड में विवरण देखें।"

        followups = [
            "क्या मैं PM-KISAN के लिए पात्र हूँ?",
            "आवेदन के लिए कौन से दस्तावेज चाहिए?",
            "मेरी संपूर्ण पात्र योजनाएं दिखाएं",
        ]
    else:
        if intent.get("is_maharashtra"):
            msg = f"Here are the top state welfare schemes available for residents of Maharashtra:"
            spoken = f"Found {count} welfare schemes available for Maharashtra residents, including Namo Shetkari and Majhi Ladki Bahin."
        elif intent.get("category") == "agriculture":
            msg = f"Here are the primary agricultural and income support schemes for farmers:"
            spoken = f"Found {count} agricultural schemes for farmers, including PM-KISAN and Kisan Credit Card."
        else:
            msg = f"Here are authentic government welfare schemes retrieved from the central catalogue:"
            spoken = f"Retrieved {count} official welfare schemes from the catalogue. Check details below."

        followups = [
            "Am I eligible for PM-KISAN?",
            "What documents are required to apply?",
            "Show all eligible schemes for me",
        ]

    # Explain profile discrepancy if user asks about farming but profile is not a farmer
    if profile and intent.get("category") == "agriculture":
        user_occ = (profile.occupation or "").strip().lower()
        if user_occ != "farmer":
            if lang == "mr":
                msg += f"\n\n*(टीप: तुमच्या जतन केलेल्या प्रोफाईलनुसार तुमचा व्यवसाय '{profile.occupation}' आहे, त्यामुळे शेतकरी योजनांसाठी अपात्र दिसत आहात. खरी माहिती तपासण्यासाठी प्रोफाईल अपडेट करा.)*"
            elif lang == "hi":
                msg += f"\n\n*(नोट: आपकी सहेजी गई प्रोफ़ाइल में आपका व्यवसाय '{profile.occupation}' दर्ज है, इसलिए कृषि योजनाओं में अपात्र दिख रहे हैं। सही पात्रता के लिए प्रोफ़ाइल अपडेट करें।)*"
            else:
                msg += f"\n\n*(Note: Your saved profile occupation is recorded as '{profile.occupation}', which is why agricultural schemes evaluate as ineligible. Update your profile to reflect farmer status.)*"

    # Grounded Gemini integration if configured
    gemini_reply = _call_gemini_if_configured(
        query=raw_query,
        grounding_context={
            "matched_schemes": [c["name"] for c in cards],
            "category": intent.get("category"),
            "language": lang,
        },
        lang=lang,
    )
    engine_mode = "gemini_grounded" if gemini_reply else "deterministic"
    if gemini_reply:
        msg = gemini_reply

    spoken = _clean_markdown_for_speech(msg, lang)

    return AgentChatResponse(
        conversation_id=conv_id,
        message=msg,
        spoken_text=spoken,
        detected_language=lang,
        response_type=ChatResponseType.SCHEME_CARDS,
        data=cards,
        suggested_followups=followups,
        engine_mode=engine_mode,
    )

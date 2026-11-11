"""
Deterministic offline fallback orchestrator for Scheme Saathi.
Activates when GEMINI_API_KEY is not configured, rate limited (429), or experiencing network disruptions.
Uses keyword and regex pattern matching in Hindi, English, and Hinglish.
Zero hallucination: only surfaces verified database records and deterministic AST rule evaluations.
"""
from typing import Dict, Any, List, Optional
import re
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import scheme_service, beneficiary_service, eligibility_service

logger = logging.getLogger(__name__)

# Intent regex patterns (Devanagari, Latin transliterations, English)
SCHEME_SEARCH_PATTERN = re.compile(
    r"(yojana|scheme|kisan|pm-kisan|pension|aarogya|ayushman|awas|sukanya|shiksha|dhoondho|search|find|batao|list|kaunsi|"
    r"योजना|किसान|पेंशन|आरोग्य|आयुष्मान|आवास|सुकन्या|शिक्षा|ढूंढो|खोज|बताओ|सूची|कौनसी)",
    re.IGNORECASE | re.UNICODE,
)
ELIGIBILITY_PATTERN = re.compile(
    r"(eligible|patra|paatrta|check|kya main|milegi|milega|laabh|qualify|status|"
    r"पात्र|पात्रता|जांच|क्या मैं|मिलेगी|मिलेगा|लाभ)",
    re.IGNORECASE | re.UNICODE,
)
BENEFICIARY_PATTERN = re.compile(
    r"(family|beneficiary|parivar|pitaji|mataji|father|mother|spouse|patni|pati|beta|beti|son|daughter|sadasya|"
    r"परिवार|पिताजी|माताजी|पत्नी|पति|बेटा|बेटी|सदस्य|लाभार्थी)",
    re.IGNORECASE | re.UNICODE,
)


class DeterministicFallbackOrchestrator:
    """
    Rule-based, offline conversational intake dispatcher.
    Ensures the service remains functional with zero 500 errors when external LLMs are unavailable.
    """

    def process_message(
        self,
        db: Session,
        current_user: User,
        message: str,
        language: str = "hi",
    ) -> Dict[str, Any]:
        """
        Analyze incoming citizen message and dispatch to local services.
        """
        msg_clean = message.strip()

        # 1. Check for Beneficiary Inquiry Intent
        if BENEFICIARY_PATTERN.search(msg_clean) and not ELIGIBILITY_PATTERN.search(msg_clean):
            return self._handle_beneficiary_query(db, current_user, language)

        # 2. Check for Eligibility Evaluation Intent
        if ELIGIBILITY_PATTERN.search(msg_clean):
            return self._handle_eligibility_query(db, current_user, msg_clean, language)

        # 3. Check for Scheme Search Intent
        if SCHEME_SEARCH_PATTERN.search(msg_clean):
            return self._handle_scheme_search(db, msg_clean, language)

        # 4. Default Clarification / Help Response
        return self._handle_default_help(language)

    def _handle_scheme_search(self, db: Session, message: str, language: str) -> Dict[str, Any]:
        """Extract query keywords and search active verified schemes."""
        stop_words = {
            "yojana", "scheme", "kaunsi", "hain", "hai", "batao", "dhoondho", "search", "for", "the", "me", "mujhe",
            "योजना", "कौनसी", "हैं", "है", "बताओ", "ढूंढो", "खोज", "मुझे", "के", "लिए",
        }
        words = [w for w in re.findall(r"[\w\u0900-\u097F]+", message.lower(), re.UNICODE) if w not in stop_words and len(w) > 1]
        query = " ".join(words) if words else None

        schemes, total = scheme_service.get_schemes(db, q=query, limit=5, include_pending=False)

        if not schemes:
            if language == "hi":
                text = "माफ़ कीजिए, आपके अनुरोध से संबंधित कोई सक्रिय योजना नहीं मिली। कृपया कोई अन्य खोज शब्द आज़माएँ (उदा: 'किसान', 'पेंशन', 'स्वास्थ्य')। (Direct Mode)"
            else:
                text = "Sorry, no active welfare schemes matched your search. Please try another keyword (e.g. 'farmer', 'pension', 'health'). (Direct Mode)"
            return {
                "content": text,
                "response_type": "text",
                "structured_data": {"items": [], "total": 0},
            }

        items = [
            {
                "id": str(s.id),
                "scheme_code": s.scheme_code,
                "name": s.name,
                "ministry": s.ministry,
                "category": s.category,
                "geographic_scope": s.geographic_scope,
            }
            for s in schemes
        ]

        if language == "hi":
            text = f"हमने आपके लिए {len(schemes)} सक्रिय योजनाएं खोजी हैं (डायरेक्ट सेवा मोड सक्रिय है):"
        else:
            text = f"Found {len(schemes)} active welfare schemes for you (Direct service mode active):"

        return {
            "content": text,
            "response_type": "scheme_cards",
            "structured_data": {"items": items, "total": total},
        }

    def _handle_eligibility_query(self, db: Session, current_user: User, message: str, language: str) -> Dict[str, Any]:
        """Evaluate active schemes deterministically against the account holder."""
        batch = eligibility_service.evaluate_all_schemes_for_user(
            db,
            user=current_user,
            include_pending=False,
        )

        eligible = [r for r in batch.results if r.overall_status.value == "PASS"]
        unknown = [r for r in batch.results if r.overall_status.value == "UNKNOWN"]

        items = [r.model_dump(mode="json") for r in batch.results[:5]]

        if language == "hi":
            text = (
                f"आपकी प्रोफ़ाइल के अनुसार पात्रता मूल्यांकन परिणाम (डायरेक्ट सेवा मोड):\n"
                f"• पात्र योजनाएं: {len(eligible)}\n"
                f"• अतिरिक्त जानकारी आवश्यक (अनिर्धारित): {len(unknown)}"
            )
        else:
            text = (
                f"Eligibility evaluation results based on your profile (Direct service mode):\n"
                f"• Eligible schemes: {len(eligible)}\n"
                f"• Information needed (undetermined): {len(unknown)}"
            )

        return {
            "content": text,
            "response_type": "eligibility_result",
            "structured_data": {"results": items, "total_evaluated": batch.total_evaluated},
        }

    def _handle_beneficiary_query(self, db: Session, current_user: User, language: str) -> Dict[str, Any]:
        """List registered family beneficiaries."""
        beneficiaries = beneficiary_service.list_beneficiaries(db, user=current_user)
        items = [b.model_dump(mode="json") for b in beneficiaries]

        if language == "hi":
            text = f"आपके खाते में {len(beneficiaries)} सदस्य (स्वयं और परिवार) पंजीकृत हैं:"
        else:
            text = f"You have {len(beneficiaries)} beneficiary profile(s) (self and family) registered:"

        return {
            "content": text,
            "response_type": "text",
            "structured_data": {"beneficiaries": items},
        }

    def _handle_default_help(self, language: str) -> Dict[str, Any]:
        """Return structured clarification and options."""
        if language == "hi":
            text = (
                "नमस्ते! मैं स्कीम साथी का सहायक हूँ। वर्तमान में डायरेक्ट सेवा मोड सक्रिय है। आप निम्न कार्य कर सकते हैं:\n\n"
                "1. योजनाओं की खोज करें (उदा: 'वृद्धावस्था पेंशन योजना', 'किसान योजना')\n"
                "2. अपनी पात्रता जांचें (उदा: 'मेरी पात्रता चेक करें')\n"
                "3. अपने परिवार के सदस्यों को देखें (उदा: 'मेरे परिवार के सदस्य')"
            )
        else:
            text = (
                "Hello! I am Scheme Saathi's assistant. Direct assistance mode is currently active. You can:\n\n"
                "1. Search welfare schemes (e.g. 'search pension schemes', 'farmer schemes')\n"
                "2. Check your eligibility (e.g. 'check my eligibility')\n"
                "3. View family members (e.g. 'show my family beneficiaries')"
            )

        return {
            "content": text,
            "response_type": "question",
            "structured_data": {
                "suggested_actions": [
                    {"label_hi": "योजनाएं खोजें", "label_en": "Search Schemes", "query": "search schemes"},
                    {"label_hi": "मेरी पात्रता जांचें", "label_en": "Check My Eligibility", "query": "check my eligibility"},
                    {"label_hi": "परिवार के सदस्य", "label_en": "View Family", "query": "show family beneficiaries"},
                ]
            },
        }

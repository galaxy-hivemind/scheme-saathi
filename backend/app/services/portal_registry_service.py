"""
Reusable Official Portal Integration Registry (Step 3).

Maintains authoritative per-scheme official portal metadata across all seeded
and structured schemes, strictly supporting three clean submission modes:
  - Mode A ("direct_api"): Authorized official portal adapter dispatch ONLY when
    genuinely registered and authorized in submission_service._PORTAL_ADAPTER_REGISTRY.
  - Mode B ("portal_assisted"): Official portal link + step-by-step trilingual
    instructions + citizen return with official portal application reference number.
  - Mode C ("manual"): Required documents checklist + official application / CSC /
    offline instructions when direct integration is unavailable or verification is pending.

Security & Honesty Invariants:
  - Never claim or simulate official government API submission without Mode A adapter.
  - Never bypass official OTP, CAPTCHA, Aadhaar e-KYC, or login controls.
  - Strictly respect pending_verification schemes by refusing to invent steps.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agents.form_schemas import SCHEME_CODE_ALIASES, get_form_schema_for_scheme
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument


_DATA_SCHEMES_DIR = Path(__file__).resolve().parents[2] / "data" / "schemes"

SUBMISSION_MODE_DIRECT_API = "direct_api"
SUBMISSION_MODE_PORTAL_ASSISTED = "portal_assisted"
SUBMISSION_MODE_MANUAL = "manual"


def _localize(lang: str, en: str, hi: str, mr: str) -> str:
    if lang == "hi":
        return hi
    if lang == "mr":
        return mr
    return en


@lru_cache(maxsize=1)
def _load_seed_schemes_index() -> Dict[str, Dict[str, Any]]:
    """Load backend/data/schemes/*.json indexed by canonical uppercase scheme_code."""
    index: Dict[str, Dict[str, Any]] = {}
    if not _DATA_SCHEMES_DIR.exists():
        return index
    for path in sorted(_DATA_SCHEMES_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            code = str(payload.get("scheme_code") or "").strip().upper()
            if code:
                index[code] = payload
        except Exception:
            continue
    return index


# Verified scheme-specific portal registry overrides & tracking URLs
_CURATED_PORTAL_METADATA: Dict[str, Dict[str, Any]] = {
    "PM-KISAN": {
        "portal_name": "PM-KISAN Official Portal",
        "official_url": "https://pmkisan.gov.in/",
        "official_application_url": "https://pmkisan.gov.in/registrationform.aspx",
        "tracking_url": "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
        "steps": {
            "en": [
                "Open the official PM-KISAN registration portal (https://pmkisan.gov.in/registrationform.aspx).",
                "Choose Rural or Urban Farmer Registration and enter your 12-digit Aadhaar number and mobile number.",
                "Complete the official portal CAPTCHA and Aadhaar OTP verification directly on pmkisan.gov.in.",
                "Fill in landholding details (District, Sub-District/Tehsil, Block, Village, Survey/Khata/Khasra No., area in hectares) using your prepared Scheme Saathi packet.",
                "Upload your verified land ownership record (7/12 / Khatauni), submit, and save the official Registration ID returned by the portal.",
            ],
            "hi": [
                "आधिकारिक PM-KISAN पंजीकरण पोर्टल (https://pmkisan.gov.in/registrationform.aspx) खोलें।",
                "ग्रामीण या शहरी किसान पंजीकरण चुनें और अपना 12 अंकों का आधार व मोबाइल नंबर दर्ज करें।",
                "पोर्टल पर सीधे कैप्चा और आधार OTP सत्यापन पूरा करें।",
                "Scheme Saathi में तैयार विवरण से जिला, उप-जिला/तहसील, ब्लॉक, गांव और भूमि/खसरा विवरण भरें।",
                "खतौनी/भूमि रिकॉर्ड अपलोड कर सबमिट करें और पोर्टल से प्राप्त आधिकारिक पंजीकरण संख्या सुरक्षित रखें।",
            ],
            "mr": [
                "अधिकृत PM-KISAN नोंदणी पोर्टल (https://pmkisan.gov.in/registrationform.aspx) उघडा.",
                "ग्रामीण किंवा शहरी शेतकरी नोंदणी निवडा आणि १२ अंकी आधार क्रमांक व मोबाईल नंबर टाका.",
                "पोर्टलवर थेट कॅप्चा आणि आधार OTP पडताळणी पूर्ण करा.",
                "Scheme Saathi मध्ये तयार केलेल्या माहितीनुसार जिल्हा, तालुका, गाव आणि शेतजमिनीचा तपशील भरा.",
                "७/१२ किंवा खतौनी उतारा अपलोड करून अर्ज सबमिट करा आणि पोर्टलवरून मिळालेला नोंदणी क्रमांक जतन करा.",
            ],
        },
        "offline": {
            "en": "You can also apply in person at your nearest Common Service Centre (CSC) or Village Revenue Officer (Patwari/Talathi) with Aadhaar, land extract, and bank passbook.",
            "hi": "आप नजदीकी CSC केंद्र या स्थानीय पटवारी/लेखपाल के पास आधार, खतौनी और बैंक पासबुक के साथ भी आवेदन कर सकते हैं।",
            "mr": "तुम्ही जवळच्या CSC केंद्रात किंवा स्थानिक तलाठी / कृषी कार्यालयात आधार, ७/१२ उतारा आणि बँक पासबुकसह अर्ज करू शकता.",
        },
    },
    "AB-PMJAY": {
        "portal_name": "Ayushman Bharat Beneficiary Portal (NHA)",
        "official_url": "https://beneficiary.nha.gov.in/",
        "official_application_url": "https://beneficiary.nha.gov.in/",
        "tracking_url": "https://beneficiary.nha.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
        "steps": {
            "en": [
                "Visit https://beneficiary.nha.gov.in/ or open the official Ayushman App.",
                "Select Beneficiary login and authenticate your mobile number via official OTP.",
                "Search family eligibility using State, Scheme (PMJAY), and Ration Card or Aadhaar number.",
                "Complete Aadhaar OTP or biometric e-KYC on the NHA portal and submit to generate your Ayushman card request.",
                "Save your official NHA Application / Reference Number to record back in Scheme Saathi.",
            ],
            "hi": [
                "आधिकारिक पोर्टल https://beneficiary.nha.gov.in/ पर जाएं या Ayushman ऐप खोलें।",
                "Beneficiary लॉगिन चुनें और आधिकारिक OTP द्वारा मोबाइल सत्यापन करें।",
                "राज्य, योजना (PMJAY) और राशन कार्ड या आधार संख्या से परिवार खोजें।",
                "NHA पोर्टल पर आधार OTP ई-केवाईसी पूरा कर अनुरोध सबमिट करें।",
                "पोर्टल से प्राप्त आधिकारिक संदर्भ संख्या सुरक्षित रखकर Scheme Saathi में दर्ज करें।",
            ],
            "mr": [
                "अधिकृत पोर्टल https://beneficiary.nha.gov.in/ ला भेट द्या किंवा Ayushman ॲप उघडा.",
                "Beneficiary लॉगिन निवडून मोबाईल OTP द्वारे पडताळणी करा.",
                "राज्य, योजना (PMJAY) आणि रेशन कार्ड किंवा आधार क्रमांक वापरून कुटुंबाचे नाव शोधा.",
                "NHA पोर्टलवर आधार OTP ई-केवायसी पूर्ण करून अर्ज सादर करा.",
                "पोर्टलवरून मिळालेला अधिकृत संदर्भ क्रमांक Scheme Saathi मध्ये नोंदवण्यासाठी जतन करा.",
            ],
        },
        "offline": {
            "en": "Visit an Ayushman Mitra helpdesk at any empanelled hospital or nearest CSC with Ration Card and Aadhaar.",
            "hi": "सूचीबद्ध अस्पताल के आयुष्मान मित्र हेल्पडेस्क या नजदीकी CSC पर राशन कार्ड और आधार लेकर जाएं।",
            "mr": "संलग्न रुग्णालयातील आयुष्मान मित्र कक्षात किंवा CSC केंद्रात रेशन कार्ड व आधार घेऊन जा.",
        },
    },
    "KCC": {
        "portal_name": "JanSamarth National Credit Portal",
        "official_url": "https://agricoop.nic.in/",
        "official_application_url": "https://www.jansamarth.in/",
        "tracking_url": "https://www.jansamarth.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PM-SVANIDHI": {
        "portal_name": "PM SVANidhi Portal (MoHUA)",
        "official_url": "https://pmsvanidhi.mohua.gov.in/",
        "official_application_url": "https://pmsvanidhi.mohua.gov.in/Default/ApplicationProcess",
        "tracking_url": "https://pmsvanidhi.mohua.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMAY-G": {
        "portal_name": "Pradhan Mantri Awaas Yojana - Gramin",
        "official_url": "https://pmayg.nic.in/",
        "official_application_url": "https://pmayg.nic.in/",
        "tracking_url": "https://rhreporting.nic.in/netiay/Benificiary.aspx",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMAY-U": {
        "portal_name": "PMAY-Urban 2.0 Portal",
        "official_url": "https://pmay-urban.gov.in/",
        "official_application_url": "https://pmay-urban.gov.in/open-application",
        "tracking_url": "https://pmay-urban.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "NSP-CSSS": {
        "portal_name": "National Scholarship Portal (NSP)",
        "official_url": "https://scholarships.gov.in/",
        "official_application_url": "https://scholarships.gov.in/",
        "tracking_url": "https://scholarships.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMMVY": {
        "portal_name": "PMMVY Citizen Portal (WCD)",
        "official_url": "https://pmmvy.wcd.gov.in/",
        "official_application_url": "https://pmmvy.wcd.gov.in/",
        "tracking_url": "https://pmmvy.wcd.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "MLBY-MH": {
        "portal_name": "Mukhyamantri Majhi Ladki Bahin Portal",
        "official_url": "https://ladkibahin.maharashtra.gov.in/",
        "official_application_url": "https://ladkibahin.maharashtra.gov.in/",
        "tracking_url": "https://ladkibahin.maharashtra.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "WIDOW-PENSION": {
        "portal_name": "NSAP / State Social Welfare Pension Portal",
        "official_url": "https://nsap.nic.in/",
        "official_application_url": "https://nsap.nic.in/",
        "tracking_url": "https://nsap.nic.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PM-VISHWAKARMA": {
        "portal_name": "PM Vishwakarma Portal",
        "official_url": "https://pmvishwakarma.gov.in/",
        "official_application_url": "https://pmvishwakarma.gov.in/",
        "tracking_url": "https://pmvishwakarma.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMEGP": {
        "portal_name": "KVIC PMEGP e-Portal",
        "official_url": "https://kviconline.gov.in/",
        "official_application_url": "https://kviconline.gov.in/pmegpeportal/pmegphome/index.jsp",
        "tracking_url": "https://kviconline.gov.in/pmegpeportal/pmegphome/index.jsp",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMFBY": {
        "portal_name": "Pradhan Mantri Fasal Bima Yojana Portal",
        "official_url": "https://pmfby.gov.in/",
        "official_application_url": "https://pmfby.gov.in/",
        "tracking_url": "https://pmfby.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "NMMS": {
        "portal_name": "National Scholarship Portal (NMMS)",
        "official_url": "https://scholarships.gov.in/",
        "official_application_url": "https://scholarships.gov.in/",
        "tracking_url": "https://scholarships.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "PMS-SC": {
        "portal_name": "National Scholarship Portal (Post-Matric SC)",
        "official_url": "https://scholarships.gov.in/",
        "official_application_url": "https://scholarships.gov.in/",
        "tracking_url": "https://scholarships.gov.in/",
        "default_mode": SUBMISSION_MODE_PORTAL_ASSISTED,
    },
    "APY": {
        "portal_name": "PFRDA / eNPS Atal Pension Portal",
        "official_url": "https://www.pfrda.org.in/",
        "official_application_url": "https://enps.nsdl.com/eNPS/ApySubRegistration.html",
        "tracking_url": "https://enps.nsdl.com/eNPS/ApySubRegistration.html",
        "default_mode": SUBMISSION_MODE_MANUAL,
    },
    "NSMSNY-MH": {
        "portal_name": "Maharashtra Agriculture (Linked via PM-KISAN)",
        "official_url": "https://krishi.maharashtra.gov.in/",
        "official_application_url": "https://pmkisan.gov.in/",
        "tracking_url": "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
        "default_mode": SUBMISSION_MODE_MANUAL,
    },
}


def _resolve_canonical_code(scheme_code_or_name: str, seed_index: Dict[str, Dict[str, Any]]) -> str:
    raw = (scheme_code_or_name or "").strip()
    upper = raw.upper()
    canon = SCHEME_CODE_ALIASES.get(upper) or SCHEME_CODE_ALIASES.get(raw) or upper
    if canon in seed_index or canon in _CURATED_PORTAL_METADATA:
        return canon
    schema = get_form_schema_for_scheme(raw)
    if schema and schema.get("scheme_code"):
        return str(schema["scheme_code"]).upper()
    # Match by scheme name from seed index
    for code, data in seed_index.items():
        if raw.lower() == str(data.get("name") or "").strip().lower():
            return code
        if raw.lower() == str(data.get("short_title") or "").strip().lower():
            return code
    return canon


def _extract_required_documents(
    scheme_code: str,
    scheme: Optional[Scheme],
    seed_entry: Optional[Dict[str, Any]],
    db: Optional[Session],
) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    seen_types = set()

    if db is not None and scheme is not None and getattr(scheme, "id", None) is not None:
        try:
            db_docs = (
                db.query(SchemeDocument)
                .filter(SchemeDocument.scheme_id == scheme.id, SchemeDocument.is_active.is_(True))
                .all()
            )
            for d in db_docs:
                dt = str(d.document_type or "").strip().lower()
                if not dt or dt in seen_types:
                    continue
                seen_types.add(dt)
                docs.append({
                    "document_type": dt,
                    "title": d.title,
                    "description": d.description,
                    "is_mandatory": bool(d.is_mandatory),
                    "alternatives": list(d.alternatives or []),
                    "issuing_authority": getattr(d, "issuing_authority", None),
                    "guidance": getattr(d, "guidance", None),
                })
        except Exception:
            pass

    if not docs and seed_entry:
        for d in seed_entry.get("required_documents", []) or []:
            if not isinstance(d, dict):
                continue
            dt = str(d.get("document_type") or "").strip().lower()
            if not dt or dt in seen_types:
                continue
            seen_types.add(dt)
            docs.append({
                "document_type": dt,
                "title": d.get("title") or dt.replace("_", " ").title(),
                "description": d.get("description"),
                "is_mandatory": bool(d.get("is_mandatory", True)),
                "alternatives": list(d.get("alternatives") or []),
                "issuing_authority": d.get("issuing_authority"),
                "guidance": d.get("guidance"),
            })

    return docs


def get_portal_integration_entry(
    scheme_code_or_name: str,
    db: Optional[Session] = None,
    scheme: Optional[Scheme] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Build normalized Step 3 Portal Integration Registry metadata for any scheme.
    Dynamically inspects submission_service.get_portal_adapter(canon_code) so
    Mode A ('direct_api') is reported ONLY when a genuine authorized adapter is active.
    """
    from app.services.submission_service import get_portal_adapter

    lang = lang if lang in ("en", "hi", "mr") else "en"
    seed_index = _load_seed_schemes_index()
    canon = _resolve_canonical_code(scheme_code_or_name, seed_index)
    seed_entry = seed_index.get(canon)

    if scheme is None and db is not None and canon:
        try:
            scheme = db.query(Scheme).filter(Scheme.scheme_code == canon).first()
        except Exception:
            scheme = None

    curated = _CURATED_PORTAL_METADATA.get(canon, {})
    schema = get_form_schema_for_scheme(canon)

    scheme_name = (
        (getattr(scheme, "name", None) if scheme else None)
        or (seed_entry.get("name") if seed_entry else None)
        or (schema.get("scheme_name") if schema else None)
        or canon
    )
    scheme_status = (
        (getattr(scheme, "scheme_status", None) if scheme else None)
        or (seed_entry.get("scheme_status") if seed_entry else None)
        or "active"
    )
    official_url = (
        curated.get("official_url")
        or (getattr(scheme, "official_url", None) if scheme else None)
        or (seed_entry.get("official_url") if seed_entry else None)
        or (schema.get("official_portal") if schema else None)
        or "https://www.india.gov.in/"
    )
    official_application_url = (
        curated.get("official_application_url")
        or (getattr(scheme, "application_url", None) if scheme else None)
        or (seed_entry.get("application_url") if seed_entry else None)
        or (schema.get("official_portal") if schema else None)
        or official_url
    )
    tracking_url = curated.get("tracking_url") or official_application_url or official_url
    portal_name = (
        curated.get("portal_name")
        or f"{scheme_name} Official Portal"
    )
    source_url = (
        (getattr(scheme, "source_url", None) if scheme else None)
        or (seed_entry.get("source_url") if seed_entry else None)
        or official_url
    )

    adapter = get_portal_adapter(canon)
    supported_api = adapter is not None and bool(getattr(adapter, "is_authorized", False))
    api_provider = getattr(adapter, "provider_name", None) if supported_api else None

    is_pending = scheme_status == "pending_verification"
    has_structured_schema = schema is not None

    if supported_api:
        submission_method = SUBMISSION_MODE_DIRECT_API
        application_availability = "direct_api_available"
    elif curated.get("default_mode") == SUBMISSION_MODE_PORTAL_ASSISTED or (
        has_structured_schema and not is_pending
    ) or (official_application_url and official_application_url != official_url and not is_pending):
        submission_method = SUBMISSION_MODE_PORTAL_ASSISTED
        application_availability = (
            "pending_verification" if is_pending else "online_portal_available"
        )
    else:
        submission_method = SUBMISSION_MODE_MANUAL
        application_availability = (
            "pending_verification" if is_pending else "manual_or_offline"
        )

    # Instructions: use verified steps if present; never fabricate for pending schemes without curated steps
    curated_steps = (curated.get("steps") or {}).get(lang)
    curated_offline = (curated.get("offline") or {}).get(lang)
    ministry = (
        (getattr(scheme, "ministry", None) if scheme else None)
        or (seed_entry.get("ministry") if seed_entry else None)
        or _localize(lang, "Competent Government Authority", "संबंधित सरकारी प्राधिकरण", "संबंधित शासकीय प्राधिकरण")
    )

    if curated_steps:
        online_steps = list(curated_steps)
    elif is_pending and not has_structured_schema:
        online_steps = [
            _localize(
                lang,
                f"Official online portal workflow for {scheme_name} is pending verification. Verify guidelines at {source_url}.",
                f"{scheme_name} की आधिकारिक ऑनलाइन प्रक्रिया सत्यापन के अधीन है। कृपया {source_url} पर विवरण जांचें।",
                f"{scheme_name} ची अधिकृत ऑनलाइन प्रक्रिया पडताळणी अंतर्गत आहे. कृपया {source_url} वर माहिती तपासा.",
            ),
            _localize(
                lang,
                f"Consult your nearest CSC or regional office of {ministry} before submitting personal documents.",
                f"दस्तावेज़ जमा करने से पहले नजदीकी CSC या {ministry} के कार्यालय से पुष्टि करें।",
                f"कागदपत्रे सादर करण्यापूर्वी जवळच्या CSC किंवा {ministry} कार्यालयात खात्री करा.",
            ),
        ]
    else:
        online_steps = [
            _localize(
                lang,
                f"Open the official application portal for {scheme_name}: {official_application_url}.",
                f"{scheme_name} के लिए आधिकारिक आवेदन पोर्टल खोलें: {official_application_url}।",
                f"{scheme_name} साठी अधिकृत अर्ज पोर्टल उघडा: {official_application_url}.",
            ),
            _localize(
                lang,
                "Complete citizen registration / login and authenticate OTP or CAPTCHA directly on the official portal.",
                "नागरिक पंजीकरण/लॉगिन करें और सीधे आधिकारिक पोर्टल पर OTP या कैप्चा सत्यापन पूरा करें।",
                "नागरिक नोंदणी/लॉगिन करून थेट अधिकृत पोर्टलवर OTP किंवा कॅप्चा पडताळणी पूर्ण करा.",
            ),
            _localize(
                lang,
                "Enter your validated details from Scheme Saathi, upload required verified documents, and submit.",
                "Scheme Saathi में सत्यापित विवरण भरें, आवश्यक दस्तावेज़ अपलोड करें और सबमिट करें।",
                "Scheme Saathi मध्ये तपासलेला तपशील भरा, आवश्यक कागदपत्रे अपलोड करा आणि अर्ज सबमिट करा.",
            ),
            _localize(
                lang,
                "Save the official acknowledgment/reference number returned by the portal and enter it in Scheme Saathi for tracking.",
                "पोर्टल से प्राप्त आधिकारिक संदर्भ संख्या सुरक्षित रखें और ट्रैकिंग के लिए Scheme Saathi में दर्ज करें।",
                "पोर्टलवरून मिळालेला अधिकृत संदर्भ क्रमांक जतन करा आणि ट्रॅकिंगसाठी Scheme Saathi मध्ये नोंदवा.",
            ),
        ]

    offline_process = curated_offline or _localize(
        lang,
        f"You may also apply via an authorized Common Service Centre (CSC) or local office of {ministry} with original documents.",
        f"आप मूल दस्तावेजों के साथ नजदीकी कॉमन सर्विस सेंटर (CSC) या {ministry} के स्थानीय कार्यालय में भी आवेदन कर सकते हैं।",
        f"तुम्ही मूळ कागदपत्रांसह जवळच्या CSC केंद्रात किंवा {ministry} च्या स्थानिक कार्यालयातही अर्ज करू शकता.",
    )

    required_documents = _extract_required_documents(canon, scheme, seed_entry, db)

    mode_labels = {
        SUBMISSION_MODE_DIRECT_API: _localize(
            lang, "Mode A: Direct Authorized API", "मोड A: प्रत्यक्ष अधिकृत API", "पद्धत A: थेट अधिकृत API"
        ),
        SUBMISSION_MODE_PORTAL_ASSISTED: _localize(
            lang, "Mode B: Portal-Assisted Guided Submission", "मोड B: पोर्टल-सहाय्यित निर्देशित आवेदन", "पद्धत B: पोर्टल-सहाय्यित मार्गदर्शित अर्ज"
        ),
        SUBMISSION_MODE_MANUAL: _localize(
            lang, "Mode C: Manual / Official Channel Submission", "मोड C: मैन्युअल / आधिकारिक माध्यम आवेदन", "पद्धत C: मॅन्युअल / अधिकृत कार्यालय अर्ज"
        ),
    }

    availability_labels = {
        "direct_api_available": _localize(
            lang, "Authorized API Integration Active", "अधिकृत API एकीकरण सक्रिय", "अधिकृत API जोडणी सक्रिय"
        ),
        "online_portal_available": _localize(
            lang, "Official Online Portal Available", "आधिकारिक ऑनलाइन पोर्टल उपलब्ध", "अधिकृत ऑनलाइन पोर्टल उपलब्ध"
        ),
        "manual_or_offline": _localize(
            lang, "Official Portal / Offline Channel Only", "केवल आधिकारिक पोर्टल / ऑफलाइन माध्यम", "केवळ अधिकृत पोर्टल / ऑफलाइन माध्यम"
        ),
        "pending_verification": _localize(
            lang, "Verification Pending — Official Guidelines Only", "सत्यापन लंबित — केवल आधिकारिक दिशानिर्देश", "पडताळणी प्रलंबित — केवळ अधिकृत मार्गदर्शक तत्त्वे"
        ),
    }

    security_notice = _localize(
        lang,
        "Official login, OTP, CAPTCHA, and biometric e-KYC controls must be completed directly by you on the official government portal. Scheme Saathi never bypasses portal security or submits without your explicit confirmation.",
        "आधिकारिक लॉगिन, OTP, कैप्चा और ई-केवाईसी आपको सीधे सरकारी पोर्टल पर स्वयं पूरे करने होंगे। Scheme Saathi कभी भी पोर्टल सुरक्षा को बायपास नहीं करता और आपकी स्पष्ट पुष्टि के बिना सबमिट नहीं करता।",
        "अधिकृत लॉगिन, OTP, कॅप्चा आणि ई-केवायसी तुम्हाला स्वतःलाच शासकीय पोर्टलवर पूर्ण करावे लागतील. Scheme Saathi कधीही पोर्टल सुरक्षा बायपास करत नाही आणि तुमच्या स्पष्ट संमतीशिवाय अर्ज सादर करत नाही.",
    )

    return {
        "scheme_code": canon,
        "scheme_name": scheme_name,
        "portal_name": portal_name,
        "official_url": official_url,
        "official_application_url": official_application_url,
        "tracking_url": tracking_url,
        "source_url": source_url,
        "submission_method": submission_method,
        "submission_method_label": mode_labels[submission_method],
        "supported_api_integration": supported_api,
        "api_provider": api_provider,
        "application_availability": application_availability,
        "application_availability_label": availability_labels.get(application_availability, application_availability),
        "structured_form_supported": has_structured_schema,
        "official_instructions": {
            "online_steps": online_steps,
            "offline_process": offline_process,
            "verification_status": "pending_verification" if is_pending else "verified",
            "source_url": source_url,
        },
        "required_documents": required_documents,
        "security_controls_notice": security_notice,
    }


def list_portal_registry(db: Optional[Session] = None, lang: str = "en") -> List[Dict[str, Any]]:
    """Return Step 3 portal integration registry entries for all seeded & structured schemes."""
    seed_index = _load_seed_schemes_index()
    codes = sorted(set(seed_index.keys()) | {"WIDOW-PENSION"})
    if db is not None:
        try:
            db_schemes = db.query(Scheme).all()
            db_by_code = {str(s.scheme_code or "").upper(): s for s in db_schemes if s.scheme_code}
            codes = sorted(set(codes) | set(db_by_code.keys()))
            return [
                get_portal_integration_entry(code, db=db, scheme=db_by_code.get(code), lang=lang)
                for code in codes
            ]
        except Exception:
            pass
    return [get_portal_integration_entry(code, db=db, lang=lang) for code in codes]

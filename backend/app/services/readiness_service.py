"""
Unified Application Readiness & Scheme-Specific Document Applicability Engine.

Computes deterministic application readiness across three distinct, unconfused pillars:
1. Citizen Profile Completeness (baseline UserProfile attributes)
2. Scheme-Specific Mandatory Form Field Completion & Format Validation
3. Authoritative Scheme Document Requirements & Lifecycle Verification State
   (recognizing canonical aliases, evaluating scheme/citizen conditional applicability,
    and strictly distinguishing uploaded vs reviewed vs verified vs missing vs rejected)

Supports pure single-language output in English ('en'), Hindi ('hi'), and Marathi ('mr').
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.agents.form_schemas import get_form_schema_for_scheme
from app.models.scheme import Scheme
from app.models.scheme_document import SchemeDocument
from app.models.user_profile import UserProfile
from app.services.document_service import (
    DOC_STATE_AWAITING_REVIEW,
    DOC_STATE_EXTRACTED,
    DOC_STATE_REJECTED,
    DOC_STATE_REVIEWED,
    DOC_STATE_UPLOADED,
    DOC_STATE_VERIFIED,
    doc_types_match,
    get_localized_doc_label,
    get_localized_status_label,
    normalize_vault_document,
)

logger = logging.getLogger(__name__)
SCHEME_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"

PROFILE_FIELD_LABELS: Dict[str, Dict[str, str]] = {
    "full_name": {"en": "Full Name", "hi": "पूरा नाम", "mr": "पूर्ण नाव"},
    "age": {"en": "Age / Date of Birth", "hi": "आयु / जन्म तिथि", "mr": "वय / जन्मतारीख"},
    "gender": {"en": "Gender", "hi": "लिंग", "mr": "लिंग"},
    "state": {"en": "State", "hi": "राज्य", "mr": "राज्य"},
    "district": {"en": "District", "hi": "जिला", "mr": "जिल्हा"},
    "residence_type": {"en": "Residence Type (Rural / Urban)", "hi": "निवास प्रकार (ग्रामीण / शहरी)", "mr": "निवास प्रकार (ग्रामीण / शहरी)"},
    "occupation": {"en": "Occupation", "hi": "व्यवसाय", "mr": "व्यवसाय"},
    "annual_family_income": {"en": "Annual Family Income", "hi": "वार्षिक पारिवारिक आय", "mr": "वार्षिक कौटुंबिक उत्पन्न"},
}


def _clean_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in ("", "null", "undefined", "none"):
        return True
    return False


def evaluate_profile_completeness(profile: Optional[UserProfile], lang: str = "en") -> Dict[str, Any]:
    """Evaluates baseline citizen profile completeness separately from document verification."""
    required_keys = [
        "full_name",
        "age",
        "gender",
        "state",
        "district",
        "residence_type",
        "occupation",
        "annual_family_income",
    ]
    if not profile:
        missing = [PROFILE_FIELD_LABELS[k].get(lang, k) for k in required_keys]
        return {
            "complete": False,
            "percentage": 0.0,
            "filled_count": 0,
            "total_count": len(required_keys),
            "missing_fields": required_keys,
            "missing_labels": missing,
        }

    missing_keys: List[str] = []
    for key in required_keys:
        if key == "age":
            val = profile.age or profile.date_of_birth
        elif key == "annual_family_income":
            val = profile.annual_income if profile.annual_income is not None else profile.annual_family_income
        else:
            val = getattr(profile, key, None)

        if key == "full_name" and isinstance(val, str) and val.strip().lower() == "citizen":
            val = None
        if _clean_empty(val) and not (key == "annual_family_income" and val == 0):
            missing_keys.append(key)

    filled = len(required_keys) - len(missing_keys)
    pct = round((filled / len(required_keys)) * 100, 1)
    return {
        "complete": len(missing_keys) == 0,
        "percentage": pct,
        "filled_count": filled,
        "total_count": len(required_keys),
        "missing_fields": missing_keys,
        "missing_labels": [PROFILE_FIELD_LABELS[k].get(lang, k) for k in missing_keys],
    }


def _load_seed_documents_fallback(scheme_code: str) -> List[Dict[str, Any]]:
    """Loads authoritative required_documents from scheme JSON file when DB session has no Scheme rows."""
    if not SCHEME_DATA_DIR.exists():
        return []
    target_upper = (scheme_code or "").strip().upper()
    for file_path in SCHEME_DATA_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if (data.get("scheme_code") or "").strip().upper() == target_upper:
                return [
                    {
                        "document_type": d.get("document_type", ""),
                        "title": d.get("title"),
                        "is_mandatory": bool(d.get("is_mandatory", True)),
                        "alternatives": d.get("alternatives") or [],
                        "issuing_authority": d.get("issuing_authority"),
                        "guidance": d.get("guidance"),
                        "source_url": d.get("source_url"),
                    }
                    for d in data.get("required_documents", [])
                ]
        except Exception:
            continue
    return []


def get_authoritative_scheme_documents(
    scheme_code: str,
    scheme_id: Optional[str],
    db: Optional[Session],
) -> List[Dict[str, Any]]:
    """
    Retrieves authoritative document requirements strictly for the given scheme.
    Never copies requirements between unrelated schemes.
    """
    db_docs: List[SchemeDocument] = []
    if db is not None:
        scheme_uuid: Optional[uuid.UUID] = None
        if scheme_id:
            try:
                scheme_uuid = uuid.UUID(str(scheme_id))
            except (ValueError, AttributeError):
                scheme_uuid = None

        if scheme_uuid is None and scheme_code:
            scheme_obj = db.query(Scheme).filter(
                (Scheme.scheme_code == scheme_code) |
                (Scheme.scheme_code == scheme_code.upper())
            ).first()
            if scheme_obj:
                scheme_uuid = scheme_obj.id

        if scheme_uuid is not None:
            try:
                db_docs = db.query(SchemeDocument).filter(
                    SchemeDocument.scheme_id == scheme_uuid,
                    SchemeDocument.is_active == True,
                ).all()
            except Exception as exc:
                logger.warning("Failed querying SchemeDocument for %s: %s", scheme_code, exc)

    if db_docs:
        return [
            {
                "document_type": d.document_type,
                "title": d.title,
                "is_mandatory": bool(d.is_mandatory),
                "alternatives": d.alternatives or [],
                "issuing_authority": d.issuing_authority,
                "guidance": d.guidance,
                "source_url": d.source_url,
            }
            for d in db_docs
        ]

    # Authoritative JSON seed fallback for unit tests or code-referenced schemes
    return _load_seed_documents_fallback(scheme_code)


def _evaluate_doc_applicability(
    scheme_code: str,
    doc_type: str,
    is_mandatory: bool,
    profile: Optional[UserProfile],
    form_data: Dict[str, Any],
    lang: str,
) -> Tuple[bool, Optional[str]]:
    """
    Determines whether a statutory document requirement applies conditionally to this specific
    citizen and application draft.
    Returns (is_applicable_mandatory, localized_waiver_reason_or_none).
    """
    if not is_mandatory:
        return False, None

    canon_scheme = (scheme_code or "").strip().upper()
    norm_doc = (doc_type or "").strip().lower()

    if canon_scheme == "PMAY-G":
        # 1. Homestead land possession is exempt at draft stage if citizen is landless seeking allotment
        if norm_doc == "land_possession":
            plot_status = str(form_data.get("land_plot_availability") or "").strip().lower()
            if "landless" in plot_status or "assistance required" in plot_status:
                reasons = {
                    "en": "Exempt at application draft stage because you selected 'Landless / Assistance Required'. State/Gram Panchayat land allotment occurs prior to release of construction tranches.",
                    "hi": "आवेदन ड्राफ्ट चरण में छूट प्राप्त है क्योंकि आपने 'भूमिहीन / सहायता आवश्यक' चुना है। निर्माण किस्त से पूर्व ग्राम पंचायत / राज्य स्तर पर आवासीय भूमि आवंटित की जाती है।",
                    "mr": "अर्ज मसुदा टप्प्यावर सूट दिली आहे कारण आपण 'भूमिहीन / मदत आवश्यक' निवडले आहे. बांधकाम हप्त्यापूर्वी ग्रामपंचायत / राज्य स्तरावर जागा वाटप केले जाते.",
                }
                return False, reasons.get(lang, reasons["en"])

        # 2. MGNREGA Job Card is required under PMAY-G ONLY when availing MGNREGA 90/95 days wage convergence
        if norm_doc == "job_card":
            convergence_flag = str(form_data.get("mgnrega_wage_convergence") or "").strip().lower()
            is_mgnrega_worker = (profile.profile_data or {}).get("is_mgnrega_worker") if profile and profile.profile_data else None
            if convergence_flag != "yes" and not is_mgnrega_worker:
                reasons = {
                    "en": "Conditional requirement waived: MGNREGA Job Card is only required if opting into the 90/95-day unskilled wage convergence component.",
                    "hi": "सशर्त दस्तावेज़ से छूट: मनरेगा जॉब कार्ड केवल तभी आवश्यक है जब आप 90/95 दिनों की अकुशल मजदूरी सहायता चुन रहे हों।",
                    "mr": "अटीनुसार सूट: मनरेगा अंतर्गत ९०/९५ दिवसांच्या अकुशल मजुरी लाभाचा पर्याय निवडल्यासच मनरेगा जॉब कार्ड आवश्यक असते.",
                }
                return False, reasons.get(lang, reasons["en"])

    return True, None


def _select_best_vault_doc(required_type: str, vault_docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Finds the best matching document in citizen vault using canonical aliases.
    Priority: verified > reviewed > extracted/awaiting_citizen_review > uploaded > rejected.
    """
    priority = {
        DOC_STATE_VERIFIED: 5,
        DOC_STATE_REVIEWED: 4,
        DOC_STATE_EXTRACTED: 3,
        DOC_STATE_AWAITING_REVIEW: 3,
        DOC_STATE_UPLOADED: 2,
        DOC_STATE_REJECTED: 1,
    }
    matches = [
        d for d in vault_docs
        if doc_types_match(required_type, d.get("document_type", ""))
    ]
    if not matches:
        return None
    matches.sort(key=lambda d: priority.get(d.get("lifecycle_status", ""), 0), reverse=True)
    return matches[0]


def _localized_doc_status_reason(doc_label: str, status_key: str, lang: str, rejection_reason: Optional[str] = None) -> str:
    if status_key == "missing":
        return {
            "en": f"{doc_label}: Missing from Document Vault. Please upload and verify it.",
            "hi": f"{doc_label}: दस्तावेज़ वॉल्ट में अनुपलब्ध है। कृपया अपलोड और सत्यापित करें।",
            "mr": f"{doc_label}: दस्तऐवज व्हॉल्टमध्ये उपलब्ध नाही. कृपया अपलोड करून पडताळणी करा.",
        }.get(lang, f"{doc_label}: Missing from Document Vault.")
    if status_key in (DOC_STATE_UPLOADED, DOC_STATE_EXTRACTED, DOC_STATE_AWAITING_REVIEW):
        return {
            "en": f"{doc_label}: Uploaded to Vault, awaiting your review & verification in Document Vault.",
            "hi": f"{doc_label}: वॉल्ट में अपलोड किया गया है; दस्तावेज़ वॉल्ट में समीक्षा व सत्यापन लंबित है।",
            "mr": f"{doc_label}: व्हॉल्टमध्ये अपलोड केले आहे; दस्तऐवज व्हॉल्टमध्ये तपासणी आणि पडताळणी प्रलंबित आहे.",
        }.get(lang, f"{doc_label}: Uploaded, awaiting citizen review & verification.")
    if status_key == DOC_STATE_REVIEWED:
        return {
            "en": f"{doc_label}: Citizen review saved; run verification in Document Vault to finalize.",
            "hi": f"{doc_label}: नागरिक समीक्षा सहेजी गई; अंतिम सत्यापन चलाने के लिए दस्तावेज़ वॉल्ट खोलें।",
            "mr": f"{doc_label}: नागरिक तपासणी जतन केली आहे; अंतिम पडताळणी पूर्ण करण्यासाठी दस्तऐवज व्हॉल्ट तपासा.",
        }.get(lang, f"{doc_label}: Reviewed; awaiting verification.")
    if status_key == DOC_STATE_REJECTED:
        reason_suffix = f" ({rejection_reason})" if rejection_reason else ""
        return {
            "en": f"{doc_label}: Rejected during verification{reason_suffix}. Please upload a valid document.",
            "hi": f"{doc_label}: सत्यापन में अस्वीकृत{reason_suffix}। कृपया वैध दस्तावेज़ पुनः अपलोड करें।",
            "mr": f"{doc_label}: पडताळणीत नाकारले गेले{reason_suffix}. कृपया वैध दस्तऐवज पुन्हा अपलोड करा.",
        }.get(lang, f"{doc_label}: Rejected{reason_suffix}.")
    return doc_label


def _safe_float(val: Any) -> Optional[float]:
    if _clean_empty(val):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _evaluate_scheme_specific_rules(
    scheme_code: str,
    form_data: Dict[str, Any],
    lang: str,
) -> List[Dict[str, str]]:
    """
    Validate scheme-specific domain rules whenever relevant fields have values.
    Prevents domain-invalid applications (e.g. negative land area, wrong gender for women-only
    schemes, or senior-citizen 70+ selection when age < 70) from passing validation.
    """
    code = (scheme_code or "").strip().upper()
    rule_errors: List[Dict[str, str]] = []

    def add_err(field: str, en: str, hi: str, mr: str) -> None:
        rule_errors.append({
            "field": field,
            "message": hi if lang == "hi" else (mr if lang == "mr" else en),
        })

    if code in ("PM-KISAN", "KCC"):
        land = _safe_float(form_data.get("land_area_acres"))
        if land is not None and land <= 0:
            add_err(
                "land_area_acres",
                "Cultivable land holding must be greater than 0 acres.",
                "कृषि योग्य भूमि क्षेत्रफल 0 एकड़ से अधिक होना चाहिए।",
                "लागवडीखालील जमीन क्षेत्रफळ ० एकरपेक्षा जास्त असणे आवश्यक आहे.",
            )

    if code == "KCC":
        age = _safe_float(form_data.get("age"))
        if age is not None and not (18 <= age <= 75):
            add_err(
                "age",
                "KCC applicant age must be between 18 and 75 years.",
                "केसीसी आवेदक की आयु 18 से 75 वर्ष के बीच होनी चाहिए।",
                "केसीसी अर्जदाराचे वय १८ ते ७५ वर्षांच्या दरम्यान असणे आवश्यक आहे.",
            )
        req_amt = _safe_float(form_data.get("requested_amount"))
        if req_amt is not None and req_amt <= 0:
            add_err(
                "requested_amount",
                "Requested credit limit must be greater than ₹0.",
                "अनुरोधित ऋण सीमा ₹0 से अधिक होनी चाहिए।",
                "मागितलेली कर्ज मर्यादा ₹० पेक्षा जास्त असणे आवश्यक आहे.",
            )

    if code == "MLBY-MH":
        gender = str(form_data.get("gender") or "").strip().upper()
        if gender and gender != "FEMALE":
            add_err(
                "gender",
                "Mukhyamantri Majhi Ladki Bahin Yojana requires female applicant eligibility.",
                "मुख्यमंत्री माझी लाड़की बहीण योजना केवल महिला आवेदकों के लिए है।",
                "मुख्यमंत्री माझी लाडकी बहीण योजना केवळ महिला अर्जदारांसाठी लागू आहे.",
            )
        age = _safe_float(form_data.get("age"))
        if age is not None and not (21 <= age <= 65):
            add_err(
                "age",
                "Applicant age must be between 21 and 65 years for MLBY-MH.",
                "एमएलबीवाई योजना के लिए आयु 21 से 65 वर्ष के बीच होनी चाहिए।",
                "माझी लाडकी बहीण योजनेसाठी वय २१ ते ६५ वर्षांच्या दरम्यान असणे आवश्यक आहे.",
            )
        inc = _safe_float(form_data.get("annual_family_income"))
        if inc is not None and inc > 250000:
            add_err(
                "annual_family_income",
                "Annual family income must not exceed ₹2,50,000 for MLBY-MH.",
                "एमएलबीवाई योजना के लिए वार्षिक पारिवारिक आय ₹2,50,000 से अधिक नहीं होनी चाहिए।",
                "माझी लाडकी बहीण योजनेसाठी वार्षिक कौटुंबिक उत्पन्न ₹२,५०,००० पेक्षा जास्त नसावे.",
            )

    if code == "WIDOW-PENSION":
        gender = str(form_data.get("gender") or "").strip().upper()
        if gender and gender != "FEMALE":
            add_err(
                "gender",
                "Widow Pension scheme applies only to female applicants.",
                "विधवा पेंशन योजना केवल महिला आवेदकों पर लागू होती है।",
                "विधवा निवृत्तीवेतन योजना केवळ महिला अर्जदारांसाठी लागू आहे.",
            )
        age = _safe_float(form_data.get("age"))
        if age is not None and age < 18:
            add_err(
                "age",
                "Applicant must be at least 18 years old for Widow Pension.",
                "विधवा पेंशन के लिए आवेदक की आयु कम से कम 18 वर्ष होनी चाहिए।",
                "विधवा निवृत्तीवेतनासाठी अर्जदाराचे वय किमान १८ वर्षे असणे आवश्यक आहे.",
            )

    if code == "AB-PMJAY":
        cov = str(form_data.get("coverage_category") or "").strip()
        age = _safe_float(form_data.get("age"))
        if "70+" in cov and age is not None and age < 70:
            add_err(
                "coverage_category",
                "Senior Citizen (70+ Universal Cover) requires applicant age of 70 years or older.",
                "वरिष्ठ नागरिक (70+ कवर) चुनने के लिए आयु 70 वर्ष या अधिक होनी चाहिए।",
                "ज्येष्ठ नागरिक (७०+ योजना) निवडण्यासाठी वय किमान ७० वर्षे असणे आवश्यक आहे.",
            )

    if code == "NSP-CSSS":
        pct = _safe_float(form_data.get("class_12_percentage"))
        if pct is not None and not (0 <= pct <= 100):
            add_err(
                "class_12_percentage",
                "Class 12 marks percentage must be between 0 and 100.",
                "कक्षा 12 प्रतिशत 0 से 100 के बीच होना चाहिए।",
                "इयत्ता १२ वीची टक्केवारी ० ते १०० दरम्यान असावी.",
            )
        yr = _safe_float(form_data.get("class_12_passing_year"))
        if yr is not None and not (1990 <= yr <= 2026):
            add_err(
                "class_12_passing_year",
                "Class 12 passing year must be between 1990 and 2026.",
                "कक्षा 12 उत्तीर्ण वर्ष 1990 से 2026 के बीच होना चाहिए।",
                "इयत्ता १२ वी उत्तीर्ण वर्ष १९९० ते २०२६ दरम्यान असावे.",
            )

    return rule_errors


def evaluate_application_readiness(
    scheme_code: str,
    scheme_id: Optional[str],
    form_data: Dict[str, Any],
    profile: Optional[UserProfile],
    db: Optional[Session],
    lang: str = "en",
    resolved_conflicts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Authoritative Application Readiness Engine.
    Evaluates:
    1. Profile completeness
    2. Form field completeness, regex validation & cross-source conflict status (requires verified schema)
    3. Scheme-specific document requirements & vault lifecycle verification states
    """
    from app.services.prefill_service import run_universal_prefill

    lang = lang if lang in ("en", "hi", "mr") else "en"
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    # ── Pillar 1: Citizen Profile Completeness ───────────────────────────────
    profile_eval = evaluate_profile_completeness(profile, lang=lang)
    if not profile_eval["complete"]:
        missing_str = ", ".join(profile_eval["missing_labels"])
        msg = {
            "en": f"Citizen profile incomplete. Missing details: {missing_str}.",
            "hi": f"नागरिक प्रोफ़ाइल अधूरी है। अनुपलब्ध विवरण: {missing_str}।",
            "mr": f"नागरिक प्रोफाईल अपूर्ण आहे. आवश्यक माहिती: {missing_str}.",
        }[lang]
        errors.append({"field": "profile", "message": msg})

    # ── Pillar 2: Scheme Form Field Completeness, Conflicts & Formats ────────
    schema = get_form_schema_for_scheme(scheme_code)
    schema_available = bool(schema and "sections" in schema)
    total_mandatory_fields = 0
    filled_mandatory_fields = 0
    missing_form_fields: List[str] = []
    invalid_form_fields: List[str] = []
    conflicting_form_fields: List[Dict[str, Any]] = []

    if schema_available:
        for section in schema["sections"]:
            for field in section.get("fields", []):
                fname = field["name"]
                label = field.get("label", fname.replace("_", " ").title())
                val = form_data.get(fname)
                is_empty = _clean_empty(val)

                # Conditional form-field checks (PMAY-G MGNREGA Job Card number only mandatory if convergence opted)
                is_required = bool(field.get("required"))
                if (scheme_code or "").upper() == "PMAY-G" and fname == "mgnrega_job_card_number":
                    conv = str(form_data.get("mgnrega_wage_convergence") or "").strip().lower()
                    is_required = (conv == "yes")

                if is_required:
                    total_mandatory_fields += 1
                    if is_empty:
                        missing_form_fields.append(fname)
                        msg = {
                            "en": f"Mandatory field '{label}' is not provided.",
                            "hi": f"अनिवार्य फ़ील्ड '{label}' भरा नहीं गया है।",
                            "mr": f"अनिवार्य माहिती '{label}' भरलेली नाही.",
                        }[lang]
                        errors.append({"field": fname, "message": msg})
                    else:
                        filled_mandatory_fields += 1

                if not is_empty and field.get("pattern"):
                    str_val = str(val).strip()
                    if not re.match(field["pattern"], str_val):
                        invalid_form_fields.append(fname)
                        msg = {
                            "en": f"Invalid format for '{label}'.",
                            "hi": f"'{label}' का प्रारूप अमान्य है।",
                            "mr": f"'{label}' चा नमुना अवैध आहे.",
                        }[lang]
                        errors.append({"field": fname, "message": msg})

        # Evaluate scheme-specific business rules
        scheme_rule_errs = _evaluate_scheme_specific_rules(scheme_code, form_data, lang)
        for s_err in scheme_rule_errs:
            if s_err["field"] not in invalid_form_fields and s_err["field"] not in missing_form_fields:
                invalid_form_fields.append(s_err["field"])
            errors.append(s_err)

        # Surface unresolved cross-source conflicts if draft data disagrees with verified profile/documents
        if profile is not None:
            try:
                prefill_check = run_universal_prefill(
                    scheme_code_or_name=scheme_code,
                    profile=profile,
                    db=db,
                    existing_draft={"form_data": form_data, "resolved_conflicts": resolved_conflicts or {}},
                    lang=lang,
                )
                conflicting_form_fields = prefill_check.get("conflicting_fields") or []
                for c in conflicting_form_fields:
                    errors.append({"field": c["field"], "message": c["message"]})
            except Exception as exc:
                logger.warning("Conflict audit skipped due to %s", exc)
    else:
        # Strict Schema Integrity: never report fake 100% form completion for unmodeled schemes
        msg = {
            "en": f"Verified application form schema and field mapping are unavailable for '{scheme_code}'. Complete submission directly on the official portal.",
            "hi": f"'{scheme_code}' के लिए सत्यापित आवेदन फ़ॉर्म स्कीमा उपलब्ध नहीं है। कृपया आधिकारिक सरकारी पोर्टल पर सीधे आवेदन करें।",
            "mr": f"'{scheme_code}' साठी पडताळलेला अर्ज फॉर्म नमुना उपलब्ध नाही. कृपया अधिकृत शासकीय पोर्टलवर थेट अर्ज करा.",
        }[lang]
        errors.append({"field": "schema", "message": msg})

    valid_filled = max(0, filled_mandatory_fields - len([f for f in invalid_form_fields if f not in missing_form_fields]))
    if not schema_available:
        form_pct = 0.0
        form_complete = False
    else:
        form_pct = round((valid_filled / total_mandatory_fields) * 100, 1) if total_mandatory_fields > 0 else 100.0
        form_complete = (
            len(missing_form_fields) == 0
            and len(invalid_form_fields) == 0
            and len(conflicting_form_fields) == 0
        )

    # ── Pillar 3: Authoritative Scheme Document Requirements & Lifecycle ─────
    vault_docs_raw = (profile.profile_data or {}).get("documents", []) if profile and profile.profile_data else []
    vault_docs = [normalize_vault_document(d) for d in vault_docs_raw]

    auth_docs = get_authoritative_scheme_documents(scheme_code, scheme_id, db)

    doc_items: List[Dict[str, Any]] = []
    applicable_mandatory_count = 0
    verified_count = 0
    reviewed_count = 0
    awaiting_review_count = 0
    rejected_count = 0
    missing_count = 0
    waived_count = 0
    doc_weighted_score = 0.0

    for req in auth_docs:
        req_type = req["document_type"]
        raw_mandatory = bool(req.get("is_mandatory", True))
        doc_label = get_localized_doc_label(req_type, lang)

        is_applicable_mandatory, waiver_reason = _evaluate_doc_applicability(
            scheme_code=scheme_code,
            doc_type=req_type,
            is_mandatory=raw_mandatory,
            profile=profile,
            form_data=form_data,
            lang=lang,
        )

        matched_vault = _select_best_vault_doc(req_type, vault_docs)

        if not raw_mandatory:
            vault_state = matched_vault["lifecycle_status"] if matched_vault else "optional_missing"
            doc_items.append({
                "document_type": req_type,
                "title": doc_label,
                "is_mandatory": False,
                "applicable": False,
                "status": matched_vault["lifecycle_status"] if matched_vault else "missing",
                "status_label": get_localized_status_label(matched_vault["lifecycle_status"] if matched_vault else "missing", lang),
                "vault_document_id": matched_vault.get("id") if matched_vault else None,
            })
            continue

        if not is_applicable_mandatory:
            waived_count += 1
            if waiver_reason:
                warnings.append({"field": f"doc_{req_type}", "message": waiver_reason})
            doc_items.append({
                "document_type": req_type,
                "title": doc_label,
                "is_mandatory": True,
                "applicable": False,
                "status": "waived",
                "status_label": get_localized_status_label("waived", lang),
                "reason": waiver_reason,
                "vault_document_id": matched_vault.get("id") if matched_vault else None,
            })
            continue

        # Strictly applicable mandatory document
        applicable_mandatory_count += 1
        if not matched_vault:
            missing_count += 1
            reason_msg = _localized_doc_status_reason(doc_label, "missing", lang)
            errors.append({"field": f"doc_{req_type}", "message": reason_msg})
            doc_items.append({
                "document_type": req_type,
                "title": doc_label,
                "is_mandatory": True,
                "applicable": True,
                "status": "missing",
                "status_label": get_localized_status_label("missing", lang),
                "reason": reason_msg,
                "vault_document_id": None,
            })
        else:
            v_state = matched_vault["lifecycle_status"]
            if v_state == DOC_STATE_VERIFIED:
                verified_count += 1
                doc_weighted_score += 1.0
            elif v_state == DOC_STATE_REVIEWED:
                reviewed_count += 1
                doc_weighted_score += 0.6
                reason_msg = _localized_doc_status_reason(doc_label, v_state, lang)
                errors.append({"field": f"doc_{req_type}", "message": reason_msg})
            elif v_state == DOC_STATE_REJECTED:
                rejected_count += 1
                reason_msg = _localized_doc_status_reason(
                    doc_label, v_state, lang, matched_vault.get("rejection_reason")
                )
                errors.append({"field": f"doc_{req_type}", "message": reason_msg})
            else:
                awaiting_review_count += 1
                doc_weighted_score += 0.25
                reason_msg = _localized_doc_status_reason(doc_label, v_state, lang)
                errors.append({"field": f"doc_{req_type}", "message": reason_msg})

            doc_items.append({
                "document_type": req_type,
                "title": doc_label,
                "is_mandatory": True,
                "applicable": True,
                "status": v_state,
                "status_label": get_localized_status_label(v_state, lang),
                "reason": None if v_state == DOC_STATE_VERIFIED else reason_msg,
                "vault_document_id": matched_vault.get("id"),
            })

    doc_pct = round((doc_weighted_score / applicable_mandatory_count) * 100, 1) if applicable_mandatory_count > 0 else 100.0
    docs_complete = (applicable_mandatory_count == verified_count)

    # Overall weighted percentage: Profile (20%) + Form Fields (40%) + Verified Documents (40%)
    overall_pct = round(
        (profile_eval["percentage"] * 0.20) + (form_pct * 0.40) + (doc_pct * 0.40),
        1,
    )
    passed = (len(errors) == 0 and profile_eval["complete"] and form_complete and docs_complete)

    if passed:
        ready_msg = {
            "en": "All profile details, mandatory fields, and applicable documents are verified. Application packet is 100% ready for explicit citizen confirmation.",
            "hi": "नागरिक प्रोफ़ाइल, सभी अनिवार्य विवरण और आवश्यक दस्तावेज़ सत्यापित हैं। आवेदन पैकेट स्पष्ट पुष्टि के लिए 100% तैयार है।",
            "mr": "नागरिक प्रोफाईल, सर्व अनिवार्य माहिती आणि आवश्यक कागदपत्रे पडताळली आहेत. अर्ज संच स्पष्ट संमतीसाठी १००% तयार आहे.",
        }[lang]
        warnings.append({"field": "ready", "message": ready_msg})

    return {
        "passed": passed,
        "overall_percentage": overall_pct,
        "errors": errors,
        "warnings": warnings,
        "breakdown": {
            "profile": profile_eval,
            "form": {
                "complete": form_complete,
                "schema_available": schema_available,
                "percentage": form_pct,
                "filled_mandatory": valid_filled,
                "total_mandatory": total_mandatory_fields,
                "missing_fields": missing_form_fields,
                "invalid_fields": invalid_form_fields,
                "conflicting_fields": conflicting_form_fields,
            },
            "documents": {
                "complete": docs_complete,
                "percentage": doc_pct,
                "applicable_mandatory": applicable_mandatory_count,
                "verified": verified_count,
                "reviewed": reviewed_count,
                "awaiting_review": awaiting_review_count,
                "rejected": rejected_count,
                "missing": missing_count,
                "waived": waived_count,
                "items": doc_items,
            },
        },
    }

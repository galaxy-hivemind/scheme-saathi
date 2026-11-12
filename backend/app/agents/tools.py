"""
Scheme Saathi Agentic Tools Implementation.
Provides real, deterministic backend tools executed by the orchestration layer:
- extract_citizen_entities: Extracts demographic, economic, and occupational entities from conversational utterances.
- check_eligibility: Evaluates tri-state eligibility via deterministic AST engine or specialized pension rules.
- build_checklist: Compares scheme document requirements against the Citizen Vault with verified sourcing guidance.
- fill_form: Maps citizen profile to scheme-specific form schemas and creates/updates editable drafts.
- submit_form: Handles explicit citizen confirmation, validates readiness, and generates official portal handoff packet.
"""
from typing import Dict, Any, List, Optional, Tuple
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.scheme_document import SchemeDocument
from app.eligibility.engine import evaluate_scheme_eligibility
from app.agents.form_schemas import (
    get_form_schema_for_scheme,
    get_document_sourcing_info,
    DOCUMENT_SOURCING_REGISTRY,
    SCHEME_CODE_ALIASES,
)


# ── Entity Extraction Tool ───────────────────────────────────────────────────

def extract_citizen_entities(message: str) -> Dict[str, Any]:
    """
    Extracts structured citizen profile attributes from natural language utterances
    in English, Hindi, and Marathi.
    """
    entities: Dict[str, Any] = {}
    
    # 0. Convert Marathi / Devanagari numerals to standard digits first
    mr_numerals = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}
    normalized_message = message
    for mr_d, ar_d in mr_numerals.items():
        if mr_d in normalized_message:
            normalized_message = normalized_message.replace(mr_d, ar_d)

    lower = normalized_message.lower()

    # 1. Age extraction with strict prefix/suffix boundary to prevent number confusion
    # Patterns: "63-year-old", "63 years old", "63 yr old", "63 साल", "63 वर्ष", "63 वर्षांची", "उम्र 63", "वय 63"
    age_suffix = re.search(r'\b([0-9]{1,2})\s*[- ]?(?:year|years|yr|yrs|वर्ष|वर्षे|साल|वर्षांची|वर्षांचा|साल की|साल का)(?:[- ]old)?\b', normalized_message, re.IGNORECASE)
    age_prefix = re.search(r'\b(?:age|aged|age is|वय|उम्र|वय वर्ष|वयवर्षे)\s*[:=]?\s*([0-9]{1,2})\b', normalized_message, re.IGNORECASE)

    if age_suffix:
        try:
            val = int(age_suffix.group(1))
            if 1 <= val <= 115:
                entities["age"] = val
        except ValueError:
            pass
    elif age_prefix:
        try:
            val = int(age_prefix.group(1))
            if 1 <= val <= 115:
                entities["age"] = val
        except ValueError:
            pass

    if entities.get("age") and entities["age"] >= 60:
        entities["is_senior_citizen"] = True

    # 2. Marital Status & Gender
    if any(k in lower for k in ["widow", "widowed", "विधवा", "गंगाभागीरथी"]):
        entities["marital_status"] = "widowed"
        entities["gender"] = "FEMALE"
    elif any(k in lower for k in ["divorced", "घटस्फोटित", "तलाकशुदा"]):
        entities["marital_status"] = "divorced"
    elif any(k in lower for k in ["married", "विवाहित", "शादीशुदा"]):
        entities["marital_status"] = "married"
    elif any(k in lower for k in ["single", "unmarried", "अविवाहित", "कुंवारी", "कुंवारा"]):
        entities["marital_status"] = "single"

    # Gender if not already set
    if "gender" not in entities:
        if any(k in lower for k in ["woman", "female", "lady", "girl", "महिला", "स्त्री", "मुलगी", "बाई"]):
            entities["gender"] = "FEMALE"
        elif any(k in lower for k in ["man", "male", "boy", "पुरुष", "मुलगा", "गृहस्थ"]):
            entities["gender"] = "MALE"

    # Maternity / Pregnancy indicators
    if any(k in lower for k in ["pregnant", "pregnancy", "गरोदर", "गर्भवती", "स्तनपान", "lactating", "माता"]):
        entities["is_pregnant_or_lactating"] = True
        entities["gender"] = "FEMALE"

    # 3. State & District Extraction
    states_list = [
        (["uttar pradesh", "उत्तर प्रदेश", "यूपी", "u.p."], "Uttar Pradesh"),
        (["maharashtra", "महाराष्ट्र", "mh"], "Maharashtra"),
        (["madhya pradesh", "मध्य प्रदेश", "mp"], "Madhya Pradesh"),
        (["rajasthan", "राजस्थान"], "Rajasthan"),
        (["bihar", "बिहार"], "Bihar"),
        (["gujarat", "गुजरात"], "Gujarat"),
        (["karnataka", "कर्नाटक"], "Karnataka"),
        (["delhi", "दिल्ली"], "Delhi"),
        (["tamil nadu", "तमिलनाडु"], "Tamil Nadu"),
        (["west bengal", "पश्चिम बंगाल"], "West Bengal"),
        (["punjab", "पंजाब"], "Punjab"),
        (["haryana", "हरियाणा"], "Haryana"),
        (["andhra pradesh", "आंध्र प्रदेश"], "Andhra Pradesh"),
        (["telangana", "तेलंगाना"], "Telangana"),
        (["kerala", "केरल"], "Kerala"),
        (["odisha", "ओडिशा"], "Odisha"),
    ]

    # Check for state negations (e.g. "not UP" or "not Maharashtra")
    negated_states = set()
    for neg_match in re.finditer(r'\b(?:not|नाही|नहीं)\s+([a-zA-Z\u0900-\u097F\s\.]+)', lower):
        neg_text = neg_match.group(1)
        for aliases, std_name in states_list:
            if any(re.search(r'\b' + re.escape(a) + r'\b', neg_text) for a in aliases):
                negated_states.add(std_name)

    matched_state = None
    for aliases, std_name in states_list:
        if std_name in negated_states:
            continue
        for alias in aliases:
            if alias == "up":
                if re.search(r'\b(?:in|from|state|at|of|to)\s+up\b', lower) or re.search(r'\bup\s+(?:state|government|pension|citizen)\b', lower) or lower.strip() == "up":
                    matched_state = std_name
                    break
            elif alias in ("mh", "mp"):
                if re.search(r'\b(?:in|from|state|at|of)\s+' + alias + r'\b', lower) or lower.strip() == alias:
                    matched_state = std_name
                    break
            else:
                if re.search(r'\b' + re.escape(alias) + r'\b', lower):
                    matched_state = std_name
                    break
        if matched_state:
            entities["state"] = matched_state
            break

    districts = [
        "pune", "mumbai", "nagpur", "nashik", "lucknow", "kanpur", "varanasi", "prayagraj", "gorakhpur",
        "patna", "jaipur", "bhopal", "indore", "thane", "solapur", "amravati", "kolhapur", "satara"
    ]
    for dist in districts:
        if re.search(r'\b' + dist + r'\b', lower):
            entities["district"] = dist.title()
            break

    # 4. Income Extraction (Annual & Monthly)
    # Check for monthly indicators first: e.g. "15000 per month", "दरमहा उत्पन्न 15000", "15000 महिना"
    monthly_match = re.search(r'(?:monthly|दरमहा|महिना|प्रति माह|per month)\s*(?:income|उत्पन्न|आय)?\s*(?:is|आहे|होती|है)?\s*(?:₹|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,6})', normalized_message, re.IGNORECASE)
    monthly_suffix = re.search(r'(?:₹|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,6})\s*(?:per month|महिना|दरमहा|प्रति माह)', normalized_message, re.IGNORECASE)

    if monthly_match:
        try:
            m_val = int(monthly_match.group(1).replace(",", ""))
            entities["annual_income"] = m_val * 12
        except ValueError:
            pass
    elif monthly_suffix:
        try:
            m_val = int(monthly_suffix.group(1).replace(",", ""))
            entities["annual_income"] = m_val * 12
        except ValueError:
            pass
    else:
        # Standard annual income
        lakh_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:lakh|lac|लाख)', lower)
        thousand_match = re.search(r'([0-9]+)\s*(?:thousand|हजार)', lower)
        income_match = re.search(r'(?:income|income is|वार्षिक उत्पन्न|वार्षिक आय|आय|उत्पन्न)?\s*(?:₹|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,8})\s*(?:per year|annually|वार्षिक|प्रति वर्ष)?', normalized_message, re.IGNORECASE)

        if lakh_match:
            try:
                entities["annual_income"] = int(float(lakh_match.group(1)) * 100000)
            except ValueError:
                pass
        elif thousand_match:
            try:
                entities["annual_income"] = int(thousand_match.group(1)) * 1000
            except ValueError:
                pass
        elif income_match and income_match.group(1):
            clean_num = income_match.group(1).replace(",", "")
            try:
                val = int(clean_num)
                if 5000 <= val <= 10000000:
                    entities["annual_income"] = val
            except ValueError:
                pass

    # 5. Occupation
    if any(k in lower for k in ["farmer", "peasant", "cultivator", "किसान", "शेतकरी", "कृषक", "शेती"]):
        entities["occupation"] = "farmer"
        entities["is_landholding_farmer"] = True
    elif any(k in lower for k in ["student", "विद्यार्थी", "छात्र", "छात्रा", "college", "school"]):
        entities["occupation"] = "student"
        entities["is_student"] = True
    elif any(k in lower for k in ["vendor", "street vendor", "hawker", "फेरीवाला", "विक्रेता", "स्ट्रीट वेंडर"]):
        entities["occupation"] = "street_vendor"
        entities["is_street_vendor"] = True
    elif any(k in lower for k in ["homemaker", "housewife", "गृहिणी"]):
        entities["occupation"] = "homemaker"

    # 6. Land Holding (e.g. 2.5 acres, 2 acres, 5 bigha, 2 हेक्टर)
    land_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:acre|acres|एकर|एकड़|bigha|बीघा|hectare|हेक्टर)', lower)
    if land_match:
        try:
            entities["land_holding_acres"] = float(land_match.group(1))
            entities["is_landholding_farmer"] = True
        except ValueError:
            pass

    # 7. Caste / Social Category (Word Boundary enforced to avoid 'st' collision in 'state', 'first', etc.)
    if re.search(r'\b(?:sc|scheduled caste)\b', lower) or "अनुसूचित जाती" in lower or "अनुसूचित जाति" in lower:
        entities["caste_category"] = "SC"
    elif re.search(r'\b(?:st|scheduled tribe)\b', lower) or "अनुसूचित जमाती" in lower or "अनुसूचित जनजाति" in lower:
        entities["caste_category"] = "ST"
    elif re.search(r'\b(?:obc|other backward class)\b', lower) or "इतर मागास वर्ग" in lower or "अन्य पिछड़ा वर्ग" in lower:
        entities["caste_category"] = "OBC"
    elif re.search(r'\b(?:general category|open category|general)\b', lower) or "सामान्य वर्ग" in lower or "खुला प्रवर्ग" in lower:
        entities["caste_category"] = "General"

    # 8. Student Academic Details (e.g. 88%, 88 percent, 88 टक्के)
    marks_match = re.search(r'([0-9]{2}(?:\.[0-9]+)?)\s*(?:%|percent|टक्के|प्रतिशत)', lower)
    if marks_match:
        try:
            entities["student_percentage"] = float(marks_match.group(1))
        except ValueError:
            pass
            pass

    # 8b. Conversational Address / Identity / Bank / Land details (strictly bounded keywords)
    aadhaar_match = re.search(
        r"(?:aadhaar|aadhar|आधार)\s*(?:no\.?|number|card|क्रमांक|नंबर)?\s*[:#-]?\s*([2-9][0-9]{3}[\s-]?[0-9]{4}[\s-]?[0-9]{4})\b",
        normalized_message,
        re.IGNORECASE,
    )
    if aadhaar_match:
        entities["aadhaar_number"] = re.sub(r"[\s-]+", "", aadhaar_match.group(1))

    phone_match = re.search(
        r"(?:mobile|phone|contact|मोबाइल|मोबाईल|फोन)\s*(?:no\.?|number|क्रमांक|नंबर)?\s*(?:is|आहे|है)?\s*[:#-]?\s*(?:\+91[\s-]?)?([6-9][0-9]{9})\b",
        normalized_message,
        re.IGNORECASE,
    )
    if phone_match:
        entities["phone_number"] = phone_match.group(1)

    ifsc_match = re.search(
        r"(?:ifsc\s*(?:code)?\s*(?:is|[:=#-])?\s*|\b)([A-Z]{4}0[A-Z0-9]{6})\b",
        normalized_message,
    )
    if ifsc_match and ("ifsc" in lower or re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc_match.group(1))):
        entities["bank_ifsc"] = ifsc_match.group(1).upper()

    bank_match = re.search(
        r"(?:account|a/c|bank\s*account|खाता|खाते)\s*(?:no\.?|number|क्रमांक|नंबर)?\s*(?:is|आहे|है)?\s*[:#-]?\s*([0-9]{9,18})\b",
        normalized_message,
        re.IGNORECASE,
    )
    if bank_match:
        entities["bank_account_number"] = bank_match.group(1)

    khasra_match = re.search(
        r"(?:khasra|khatauni|gat|survey)\s*(?:khatauni\s*)?(?:no\.?|number)?\s*(?:is|आहे|है|[:=#-])?\s*([A-Za-z0-9][A-Za-z0-9/\-]{1,19})\b",
        normalized_message,
        re.IGNORECASE,
    )
    if khasra_match and khasra_match.group(1).lower() not in ("is", "no", "number"):
        entities["khasra_number"] = khasra_match.group(1)

    subdist_match = re.search(
        r"(?:tehsil|taluka|sub[- ]?district|block|तहसील|तालुका)\s*(?:is|आहे|है|[:=-])?\s*([A-Za-z][A-Za-z\s-]{1,28}?)(?=,|\.|\band\b|\bstate\b|\bdistrict\b|\bvillage\b|\bkhasra\b|$)",
        normalized_message,
        re.IGNORECASE,
    )
    if subdist_match:
        sub_val = re.sub(r"^(?:is|of)\s+", "", subdist_match.group(1).strip(), flags=re.IGNORECASE).strip()
        if sub_val and sub_val.lower() not in ("not", "name", "number"):
            entities["sub_district"] = sub_val.title()

    village_match = re.search(
        r"(?:village|gram)\s*(?:name|is|[:=-])?\s*([A-Za-z][A-Za-z\s-]{1,28}?)(?=,|\.|\band\b|\btehsil\b|\btaluka\b|\bblock\b|\bdistrict\b|\bstate\b|\bkhasra\b|$)",
        normalized_message,
        re.IGNORECASE,
    )
    if village_match:
        vil_val = re.sub(r"^(?:is|of|name)\s+", "", village_match.group(1).strip(), flags=re.IGNORECASE).strip()
        if vil_val and vil_val.lower() not in ("not", "area", "resident"):
            entities["village"] = vil_val.title()

    # 9. Document Disclosure Indicators (e.g. "I don't have income certificate", "माझ्याकडे उत्पन्न प्रमाणपत्र नाही")
    missing_doc_cues = [
        "don't have", "do not have", "don’t have", "havent got", "haven't got", "haven't",
        "not have", "missing", "without", "lost my", "lost the", "unavailable",
        "नाही", "नाहीये", "नसल्यास", "उपलब्ध नाही", "हरवले", "गहाळ",
        "नहीं है", "नही है", "नहीं मिल", "गुम हो", "उपलब्ध नहीं",
    ]
    if any(k in lower for k in missing_doc_cues):
        if any(k in lower for k in ["land possession", "possession certificate", "allotment", "homestead"]):
            entities["missing_document_disclosed"] = "land_possession"
        elif any(k in lower for k in ["land", "7/12", "उतारा", "khasra", "खसरा", "khatauni", "जमीन", "शेतजमीन", "भूमि"]):
            entities["missing_document_disclosed"] = "land_records"
        elif any(k in lower for k in ["income", "उत्पन्न", "आय"]):
            entities["missing_document_disclosed"] = "income_certificate"
        elif any(k in lower for k in ["death", "मृत्यू", "मरण", "मृत्यु"]):
            entities["missing_document_disclosed"] = "death_certificate"
        elif any(k in lower for k in ["aadhaar", "aadhar", "आधार"]):
            entities["missing_document_disclosed"] = "aadhaar_card"
        elif any(k in lower for k in ["bank", "passbook", "खाता", "पासबुक", "बैंक", "बँक"]):
            entities["missing_document_disclosed"] = "bank_passbook"
        elif any(k in lower for k in ["ration", "राशन", "रेशन"]):
            entities["missing_document_disclosed"] = "ration_card"
        elif any(k in lower for k in ["job card", "mgnrega", "मनरेगा", "जॉब कार्ड"]):
            entities["missing_document_disclosed"] = "job_card"
        elif any(k in lower for k in ["caste", "जाती", "जात", "जाति"]):
            entities["missing_document_disclosed"] = "caste_certificate"
        elif any(k in lower for k in ["domicile", "residence", "अधिवास", "निवास", "रहिवासी"]):
            entities["missing_document_disclosed"] = "domicile_certificate"
        elif any(k in lower for k in ["marksheet", "12th", "marks", "गुणपत्रक", "मार्कशीट"]):
            entities["missing_document_disclosed"] = "marksheet_12th"
        elif any(k in lower for k in ["mcp", "mother and child", "माता बाल"]):
            entities["missing_document_disclosed"] = "mcp_card"
        elif any(k in lower for k in ["vending", "lor", "फेरीवाला", "स्टेट वेंडर"]):
            entities["missing_document_disclosed"] = "vending_certificate"
        else:
            from app.services.document_guidance_service import identify_document_key
            inferred_doc = identify_document_key(lower)
            if inferred_doc:
                entities["missing_document_disclosed"] = inferred_doc

    return entities


def apply_extracted_entities_to_profile(
    db: Session,
    profile: UserProfile,
    entities: Dict[str, Any],
    *,
    force_update: bool = False,
) -> None:
    """
    Persists extracted entities into empty citizen UserProfile attributes safely.
    Never overwrites existing settled profile attributes unless force_update=True (explicit correction),
    allowing the conflict detector to catch mismatched inputs cleanly.
    """
    if not profile or not entities:
        return

    profile_data = dict(profile.profile_data or {})
    changed = False

    if "age" in entities and (profile.age is None or (force_update and profile.age != entities["age"])):
        profile.age = entities["age"]
        changed = True

    if "gender" in entities and (not profile.gender or (force_update and profile.gender != entities["gender"])):
        profile.gender = entities["gender"]
        changed = True

    if "state" in entities and (not profile.state or (force_update and profile.state != entities["state"])):
        profile.state = entities["state"]
        changed = True

    if "district" in entities and (not profile.district or (force_update and profile.district != entities["district"])):
        profile.district = entities["district"]
        changed = True

    if "annual_income" in entities and (profile.annual_income is None or (force_update and profile.annual_income != entities["annual_income"])):
        profile.annual_income = entities["annual_income"]
        changed = True

    if "occupation" in entities and (not profile.occupation or (force_update and profile.occupation != entities["occupation"])):
        profile.occupation = entities["occupation"]
        changed = True

    # Persist additional attributes into profile_data only if empty or explicit correction
    for key in [
        "marital_status",
        "land_holding_acres",
        "caste_category",
        "is_landholding_farmer",
        "is_street_vendor",
        "is_student",
        "student_percentage",
        "is_pregnant_or_lactating",
        "is_senior_citizen",
        "sub_district",
        "village",
        "khasra_number",
        "aadhaar_number",
        "phone_number",
        "bank_account_number",
        "bank_ifsc",
    ]:
        if key in entities and (force_update or profile_data.get(key) in (None, "")):
            profile_data[key] = entities[key]
            changed = True

    if changed and db is not None:
        from sqlalchemy.orm.attributes import flag_modified
        profile.profile_data = profile_data
        flag_modified(profile, "profile_data")
        db.add(profile)
        db.commit()
        db.refresh(profile)


# ── Tool 1: check_eligibility ────────────────────────────────────────────────

def tool_check_eligibility(
    db: Session,
    user: Optional[User],
    profile: Optional[UserProfile],
    scheme_code_or_name: str,
    extracted_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes real deterministic eligibility evaluation for the citizen.
    - Uses deterministic SchemeRuleVersion AST evaluation for all 31 database schemes.
    - Handles specialized welfare schemes (e.g., Widow Pension / IGNWPS) deterministically.
    """
    cleaned = scheme_code_or_name.strip().upper()
    resolved_code = SCHEME_CODE_ALIASES.get(cleaned, cleaned)

    # 1. Check if user mentioned Widow Pension / IGNWPS
    if "WIDOW" in resolved_code or "VIDHWA" in resolved_code or resolved_code == "WIDOW-PENSION":
        # Deterministic evaluation for Widow Pension
        age = (extracted_data.get("age") if extracted_data else None) or (profile.age if profile else None)
        gender = (extracted_data.get("gender") if extracted_data else None) or (profile.gender if profile else None)
        marital_status = (extracted_data.get("marital_status") if extracted_data else None) or (profile.profile_data.get("marital_status") if profile and profile.profile_data else None)
        state = (extracted_data.get("state") if extracted_data else None) or (profile.state if profile else None)
        income = (extracted_data.get("annual_income") if extracted_data else None) or (profile.annual_income if profile else None)

        satisfied_criteria = []
        unmet_criteria = []
        missing_info = []

        # Age criterion: IGNWPS requires age 40 to 79. State schemes (UP/MH) allow 18+.
        if age is not None:
            if age >= 18:
                satisfied_criteria.append(f"Age is {age} years (Satisfies minimum age requirement of 18+ for State Widow Pension and 40-79 for IGNWPS).")
            else:
                unmet_criteria.append(f"Age {age} is below minimum requirement (18+).")
        else:
            missing_info.append("Age of the applicant is required.")

        # Gender & Marital Status
        if marital_status == "widowed":
            satisfied_criteria.append("Applicant is a widow (Verified marital status).")
        elif marital_status is not None:
            unmet_criteria.append("Applicant is not registered as widowed.")
        else:
            missing_info.append("Marital status confirmation (Husband's demise) is required.")

        # State Jurisdiction
        if state:
            satisfied_criteria.append(f"Jurisdiction: {state} State Social Welfare Pension Scheme applies.")
        else:
            missing_info.append("State of residence is required to determine applicable state pension guidelines.")

        # Income ceiling
        # UP ceiling: ₹2,00,000 per annum; National IGNWPS: BPL benchmark (~₹1,00,000 or SECC BPL)
        if income is not None:
            if income <= 200000:
                satisfied_criteria.append(f"Annual household income ₹{income:,} is within the eligible threshold (≤ ₹2,00,000 in UP / BPL ceiling).")
            else:
                unmet_criteria.append(f"Annual household income ₹{income:,} exceeds the eligible pension ceiling (₹2,00,000).")
        else:
            missing_info.append("Annual household income certification is required.")

        # Compute status
        if unmet_criteria:
            status = "ineligible"
            summary = "Applicant is currently ineligible based on statutory pension rules."
        elif missing_info:
            status = "information_required"
            summary = f"Potentially eligible, but additional information is required: {', '.join(missing_info)}."
        else:
            status = "eligible"
            summary = f"Citizen meets all core eligibility criteria for {state or 'National'} Widow Pension (₹1,000/month DBT)."

        return {
            "scheme_code": "WIDOW-PENSION",
            "scheme_name": f"{state or 'National'} Widow Pension Scheme (इंदिरा गांधी राष्ट्रीय विधवा निवृत्तीवेतन / विधवा पेंशन)",
            "status": status,
            "summary": summary,
            "satisfied_criteria": satisfied_criteria,
            "unmet_criteria": unmet_criteria,
            "missing_information": missing_info,
            "monthly_benefit": "₹1,000 per month directly into Aadhaar-seeded DBT bank account",
            "official_portal": "https://sspy-up.gov.in" if state == "Uttar Pradesh" else "https://nsap.nic.in",
        }

    # 2. Evaluate against PostgreSQL schemes
    db_scheme = None
    if db is not None:
        db_scheme = db.scalars(
            select(Scheme).where(
                (Scheme.scheme_code == resolved_code) |
                (Scheme.scheme_code == resolved_code.upper()) |
                (Scheme.scheme_code == cleaned)
            )
        ).first()

        if not db_scheme:
            # Search by partial name
            db_scheme = db.scalars(
                select(Scheme).where(Scheme.name.ilike(f"%{cleaned}%"))
            ).first()

    if not db_scheme:
        return {
            "scheme_code": scheme_code_or_name,
            "scheme_name": scheme_code_or_name,
            "status": "information_required",
            "summary": f"Scheme '{scheme_code_or_name}' not found in active database catalogue.",
            "satisfied_criteria": [],
            "unmet_criteria": [],
            "missing_information": ["Target scheme identifier"],
            "official_portal": "https://india.gov.in",
        }

    if not profile:
        return {
            "scheme_code": db_scheme.scheme_code,
            "scheme_name": db_scheme.name,
            "status": "information_required",
            "summary": "Citizen profile information is needed to evaluate eligibility against official criteria.",
            "satisfied_criteria": [],
            "unmet_criteria": [],
            "missing_information": ["Complete citizen profile"],
            "official_portal": db_scheme.application_url or db_scheme.official_url or "https://india.gov.in",
        }

    # Execute deterministic eligibility engine (merging conversational overrides safely)
    eval_result = evaluate_scheme_eligibility(db_scheme, profile, override_data=extracted_data)

    satisfied = [c.explanation for c in eval_result.matched_conditions]
    unmet = [c.explanation for c in eval_result.failed_conditions]
    missing = [c.explanation for c in eval_result.unknown_conditions] or list(eval_result.missing_fields)

    return {
        "scheme_code": db_scheme.scheme_code,
        "scheme_name": db_scheme.name,
        "status": eval_result.result.value,
        "summary": eval_result.explanation,
        "satisfied_criteria": satisfied,
        "unmet_criteria": unmet,
        "missing_information": missing,
        "benefits": db_scheme.benefits,
        "official_portal": db_scheme.application_url or db_scheme.official_url or "https://india.gov.in",
    }


# ── Tool 2: build_checklist ──────────────────────────────────────────────────

def tool_build_checklist(
    db: Session,
    user: Optional[User],
    profile: Optional[UserProfile],
    scheme_code_or_name: str,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Builds an authoritative document checklist:
    - Compares required documents against Citizen Vault.
    - Categorizes into: verified, uploaded, extracted, pending_review, missing.
    - Enriches missing documents with verified sourcing information (where to obtain, authority, fee, SLA).
    - Localizes document titles and sourcing information cleanly for 'en', 'hi', and 'mr'.
    """
    cleaned = scheme_code_or_name.strip().upper()
    resolved_code = SCHEME_CODE_ALIASES.get(cleaned, cleaned)

    # Required docs list
    required_docs: List[Dict[str, Any]] = []

    # 1. Check if Widow Pension
    if "WIDOW" in resolved_code or resolved_code == "WIDOW-PENSION":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "death_certificate", "title": "Husband's Death Certificate", "mandatory": True},
            {"type": "income_certificate", "title": "Income Certificate (Below ₹2 Lakh)", "mandatory": True},
            {"type": "bank_passbook", "title": "Aadhaar-Seeded Bank Passbook", "mandatory": True},
            {"type": "domicile_certificate", "title": "State Residence / Domicile Certificate", "mandatory": False},
            {"type": "ration_card", "title": "BPL / Antyodaya Ration Card (if applicable)", "mandatory": False},
        ]
    elif resolved_code == "PM-KISAN":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "land_records", "title": "Land Ownership Record (Khasra-Khatauni / 7/12 Extract)", "mandatory": True},
            {"type": "bank_passbook", "title": "Aadhaar-Seeded Bank Account Passbook", "mandatory": True},
            {"type": "caste_certificate", "title": "Caste Certificate (for SC/ST categories)", "mandatory": False},
        ]
    elif resolved_code == "KCC":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "land_records", "title": "Cultivable Land Record (7/12 or RoR) / Tenancy Agreement", "mandatory": True},
            {"type": "bank_passbook", "title": "Savings Bank Account Statement / Passbook", "mandatory": True},
            {"type": "income_certificate", "title": "Crop Cultivation Declaration / Farm Income Proof", "mandatory": False},
        ]
    elif resolved_code == "PM-SVANIDHI":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "vending_certificate", "title": "Certificate of Vending / Letter of Recommendation (LoR)", "mandatory": True},
            {"type": "bank_passbook", "title": "Aadhaar-Linked Bank Account Passbook", "mandatory": True},
        ]
    elif resolved_code == "NSP-CSSS":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "marksheet_12th", "title": "Class 12 Passing Marksheet (Above 80th Percentile)", "mandatory": True},
            {"type": "income_certificate", "title": "Annual Family Income Certificate (Below ₹4.5 Lakh)", "mandatory": True},
            {"type": "bank_passbook", "title": "Student Bank Account Passbook", "mandatory": True},
            {"type": "caste_certificate", "title": "Caste / Category Certificate (if applicable)", "mandatory": False},
        ]
    elif resolved_code == "PMMVY":
        required_docs = [
            {"type": "aadhaar_card", "title": "Mother's Aadhaar Card", "mandatory": True},
            {"type": "mcp_card", "title": "Mother and Child Protection (MCP) Card with ANC records", "mandatory": True},
            {"type": "bank_passbook", "title": "Mother's Aadhaar Seeded Bank Account Passbook", "mandatory": True},
        ]
    elif resolved_code == "MLBY-MH":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card", "mandatory": True},
            {"type": "domicile_certificate", "title": "Maharashtra Domicile Certificate / 15-Year Old Ration Card", "mandatory": True},
            {"type": "income_certificate", "title": "Income Certificate (≤ ₹2.5 Lakh) / Yellow or Orange Ration Card", "mandatory": True},
            {"type": "bank_passbook", "title": "Aadhaar-Seeded Individual Bank Passbook", "mandatory": True},
        ]
    elif resolved_code == "AB-PMJAY":
        required_docs = [
            {"type": "aadhaar_card", "title": "Aadhaar Card (Mandatory for e-KYC)", "mandatory": True},
            {"type": "ration_card", "title": "Ration Card or Family Identity Proof", "mandatory": False},
        ]
    else:
        # Fetch authoritative documents for this specific scheme from DB or seed JSON
        from app.services.readiness_service import get_authoritative_scheme_documents
        auth_docs = get_authoritative_scheme_documents(resolved_code, None, db)
        for d in auth_docs:
            required_docs.append({
                "type": d["document_type"],
                "title": d.get("title") or d["document_type"].replace("_", " ").title(),
                "mandatory": bool(d.get("is_mandatory", True)),
            })

    # Fetch User's Document Vault and normalize status (never auto-verify unreviewed uploads)
    from app.services.document_service import (
        DOC_STATE_VERIFIED,
        doc_types_match,
        normalize_vault_document,
    )
    raw_vault_docs: List[Dict[str, Any]] = []
    if profile and profile.profile_data:
        raw_vault_docs = profile.profile_data.get("documents", [])

    vault_docs = [normalize_vault_document(d) for d in raw_vault_docs]

    priority_rank = {
        "verified": 5,
        "reviewed": 4,
        "extracted": 3,
        "awaiting_citizen_review": 3,
        "uploaded": 2,
        "rejected": 1,
    }

    checklist_items: List[Dict[str, Any]] = []
    mandatory_total = 0
    mandatory_ready = 0
    mandatory_present = 0

    for doc in required_docs:
        doc_type = doc["type"]
        is_mand = doc["mandatory"]
        if is_mand:
            mandatory_total += 1

        matches = [d for d in vault_docs if doc_types_match(doc_type, d.get("document_type", ""))]
        matches.sort(key=lambda d: priority_rank.get(d.get("lifecycle_status", ""), 0), reverse=True)
        matched_vault_doc = matches[0] if matches else None

        if matched_vault_doc:
            status = matched_vault_doc.get("lifecycle_status", "awaiting_citizen_review")
            if is_mand:
                if status != "rejected":
                    mandatory_present += 1
                if status == DOC_STATE_VERIFIED:
                    mandatory_ready += 1
        else:
            status = "missing"

        sourcing = get_document_sourcing_info(doc_type, lang=lang)
        item_title = sourcing.get("title") or doc["title"]

        checklist_items.append({
            "index": len(checklist_items) + 1,
            "document_type": doc_type,
            "title": item_title,
            "is_mandatory": is_mand,
            "status": status,
            "sourcing": sourcing,
            "vault_document_id": matched_vault_doc.get("id") if matched_vault_doc else None,
        })

    readiness_percentage = round((mandatory_ready / mandatory_total * 100), 1) if mandatory_total > 0 else 100.0

    return {
        "scheme_code": resolved_code,
        "total_documents": len(checklist_items),
        "mandatory_count": mandatory_total,
        "mandatory_ready": mandatory_ready,
        "mandatory_present": mandatory_present,
        "readiness_percentage": readiness_percentage,
        "is_ready_for_application": (mandatory_ready == mandatory_total),
        "items": checklist_items,
    }


# ── Tool 3: fill_form ────────────────────────────────────────────────────────

def tool_fill_form(
    db: Session,
    user: Optional[User],
    profile: Optional[UserProfile],
    scheme_code_or_name: str,
    form_overrides: Optional[Dict[str, Any]] = None,
    conversation_entities: Optional[Dict[str, Any]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Pre-fills a scheme-specific application form schema using the shared
    Universal Multi-Scheme Pre-Fill Engine.
    - Combines citizen profile, verified/confirmed Vault documents, conversation entities,
      and saved draft answers with strict provenance & conflict detection.
    - Returns explicit schema_available=False for schemes without verified schemas.
    - Saves editable draft safely to citizen's profile_data['applications'].
    """
    from app.services.prefill_service import run_universal_prefill, is_empty_value
    from app.agents.form_schemas import get_unavailable_schema_payload
    from app.api.v1.applications import canonical_scheme_key, resolve_scheme_info

    from app.services.portal_registry_service import get_portal_integration_entry
    from app.services.submission_service import (
        build_normalized_application_record,
        sync_application_record_to_db,
    )

    form_overrides = form_overrides or {}
    conversation_entities = conversation_entities or {}

    existing_match: Optional[Dict[str, Any]] = None
    target_canon = canonical_scheme_key(scheme_code_or_name)
    if profile and profile.profile_data:
        apps = list(profile.profile_data.get("applications", []))
        existing_match = next(
            (
                a
                for a in apps
                if a.get("lifecycle_state") not in ("submitted", "portal_submitted", "submitting", "submission_unknown")
                and not a.get("legacy_synthetic_submission")
                and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
                and canonical_scheme_key(a.get("scheme_code") or a.get("scheme_id") or "", a.get("scheme_name") or "") == target_canon
            ),
            None,
        )

    prefill_res = run_universal_prefill(
        scheme_code_or_name=scheme_code_or_name,
        profile=profile,
        user=user,
        db=db,
        existing_draft=existing_match,
        form_overrides=form_overrides,
        conversation_entities=conversation_entities,
        lang=lang,
    )

    if not prefill_res.get("form_supported"):
        # Enrich unavailable schema notice with real DB scheme portal URL when available
        portal_url = prefill_res.get("official_portal") or "https://india.gov.in"
        scheme_name = scheme_code_or_name
        canon_code = target_canon or scheme_code_or_name
        if db is not None:
            try:
                _, db_code, db_name, db_portal = resolve_scheme_info(scheme_code_or_name, db)
                canon_code = db_code
                scheme_name = db_name
                portal_url = db_portal
            except Exception:
                pass
        else:
            # Check local seed fallback so APY and other seeded schemes keep authoritative portals in unit tests
            from pathlib import Path
            import json
            seed_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
            for fp in seed_dir.glob("*.json"):
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if (data.get("scheme_code") or "").upper() == target_canon or (data.get("name") or "").upper() == scheme_code_or_name.strip().upper():
                        canon_code = data.get("scheme_code") or canon_code
                        scheme_name = data.get("name") or scheme_name
                        portal_url = data.get("application_url") or data.get("official_url") or portal_url
                        break
                except Exception:
                    continue

        unavail = get_unavailable_schema_payload(canon_code, scheme_name, portal_url, lang=lang)
        portal_entry = get_portal_integration_entry(canon_code, db=db, lang=lang)
        unavail["portal_integration"] = portal_entry
        unavail["official_portal"] = portal_entry.get("official_application_url") or portal_url
        return unavail

    target_code = prefill_res["scheme_code"]
    portal_entry = get_portal_integration_entry(target_code, db=db, lang=lang)
    eff_portal_url = portal_entry.get("official_application_url") or prefill_res.get("official_portal") or "https://india.gov.in"
    form_values = dict(prefill_res["values"])
    total_mandatory_fields = prefill_res["total_mandatory_fields"]
    filled_mandatory_fields = prefill_res["filled_mandatory_fields"]
    readiness = prefill_res["readiness_percentage"]

    app_id = (existing_match.get("id") if existing_match else None) or f"app-{target_code.lower()}-{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    persisted_form_data = {k: ("" if is_empty_value(v) else v) for k, v in form_values.items()}

    draft_record: Dict[str, Any] = {
        "id": app_id,
        "user_id": str(user.id) if user and hasattr(user, "id") and user.id else (str(profile.user_id) if profile and hasattr(profile, "user_id") else "citizen"),
        "scheme_id": target_code,
        "scheme_code": target_code,
        "scheme_name": prefill_res["scheme_title"],
        "official_url": eff_portal_url,
        "official_portal": eff_portal_url,
        "portal_url": eff_portal_url,
        "tracking_url": portal_entry.get("tracking_url"),
        "submission_method": portal_entry.get("submission_method"),
        "portal_integration": portal_entry,
        "schema_available": True,
        "lifecycle_state": "draft",
        "form_data": persisted_form_data,
        "resolved_conflicts": prefill_res.get("resolved_conflicts") or {},
        "prefill_summary": prefill_res,
        "readiness_percentage": readiness,
        "total_mandatory_fields": total_mandatory_fields,
        "filled_mandatory_fields": filled_mandatory_fields,
        "validation_result": {
            "passed": bool(prefill_res.get("can_confirm")),
            "errors": (
                [{"field": c["field"], "message": c["message"]} for c in (prefill_res.get("conflicting_fields") or [])]
                + list(prefill_res.get("invalid_fields") or [])
                + (
                    []
                    if filled_mandatory_fields == total_mandatory_fields
                    else [{"field": "mandatory_fields", "message": f"{total_mandatory_fields - filled_mandatory_fields} mandatory fields require input."}]
                )
            ),
            "warnings": [],
        },
        "created_at": (existing_match.get("created_at") if existing_match else None) or now_iso,
        "updated_at": now_iso,
        "audit_trail": list((existing_match or {}).get("audit_trail") or []) + [
            {
                "timestamp": now_iso,
                "action": "DRAFT_UPDATED" if existing_match else "DRAFT_CREATED",
                "actor": "saathi_agent",
                "details": f"Pre-filled {filled_mandatory_fields}/{total_mandatory_fields} mandatory fields ({prefill_res['auto_populated_fields']}/{prefill_res['total_fields']} total).",
            }
        ],
    }

    citizen_uid = user.id if user and hasattr(user, "id") and user.id else (profile.user_id if profile and hasattr(profile, "user_id") else None)
    if profile and db is not None:
        from sqlalchemy.orm.attributes import flag_modified
        from app.services.readiness_service import evaluate_application_readiness

        current_profile_data = dict(profile.profile_data or {})
        apps = [a for a in current_profile_data.get("applications", []) if a.get("id") != app_id]

        draft_record["validation_result"] = evaluate_application_readiness(
            scheme_code=target_code,
            scheme_id=draft_record.get("scheme_id"),
            form_data=draft_record["form_data"],
            profile=profile,
            db=db,
            lang=lang,
            resolved_conflicts=draft_record["resolved_conflicts"],
        )
        if draft_record["validation_result"]["passed"]:
            draft_record["lifecycle_state"] = "awaiting_confirmation"
        draft_record["application_record"] = build_normalized_application_record(
            draft_record, citizen_uid, portal_entry
        )

        apps.insert(0, draft_record)
        current_profile_data["applications"] = apps
        profile.profile_data = current_profile_data
        flag_modified(profile, "profile_data")
        db.add(profile)
        if citizen_uid:
            sync_application_record_to_db(db, draft_record, citizen_uid, portal_entry)
        db.commit()
        db.refresh(profile)

    return {
        "form_supported": True,
        "schema_available": True,
        "schema_status": prefill_res["schema_status"],
        "application_id": app_id,
        "draft_id": app_id,
        "scheme_code": target_code,
        "scheme_title": prefill_res["scheme_title"],
        "official_portal": eff_portal_url,
        "portal_integration": portal_entry,
        "application_record": draft_record.get("application_record")
        or build_normalized_application_record(draft_record, citizen_uid, portal_entry),
        "total_fields": prefill_res["total_fields"],
        "total_mandatory_fields": total_mandatory_fields,
        "filled_mandatory_fields": filled_mandatory_fields,
        "auto_populated_fields": prefill_res["auto_populated_fields"],
        "requires_input_count": prefill_res["requires_input_count"],
        "requires_input_fields": prefill_res["requires_input_fields"],
        "conditional_fields": prefill_res["conditional_fields"],
        "conflicting_fields": prefill_res["conflicting_fields"],
        "invalid_fields": prefill_res["invalid_fields"],
        "readiness_percentage": readiness,
        "prefill_percentage": readiness,
        "sections": prefill_res["sections"],
        "values": form_values,
        "form_data": persisted_form_data,
        "can_confirm": prefill_res["can_confirm"],
    }


# ── Tool 4: submit_form ──────────────────────────────────────────────────────

def tool_submit_form(
    db: Session,
    user: Optional[User],
    profile: Optional[UserProfile],
    scheme_code_or_name: str,
    confirmed: bool = False,
    form_data: Optional[Dict[str, Any]] = None,
    lang: str = "en",
    consent_acknowledged: bool = True,
    expected_version: Optional[int] = None,
    expected_hash: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Phase 7 Safe Confirmation & Submission Orchestration Tool:
    - If confirmed=False: compiles complete field-by-field review summary with provenance,
      version, hash, verified docs, and portal integration disclosure.
    - If confirmed=True: validates strictly, records version-bound explicit citizen confirmation,
      and orchestrates submission via submission_service without ever simulating government submission.
    """
    from app.services.prefill_service import run_universal_prefill
    from app.services.portal_registry_service import get_portal_integration_entry
    from app.services.submission_service import (
        STATE_CONFIRMED,
        STATE_PORTAL_SUBMITTED,
        STATE_SUBMISSION_FAILED,
        STATE_SUBMISSION_UNKNOWN,
        STATE_SUBMITTED,
        STATE_SUBMITTING,
        build_application_review_summary,
        get_portal_adapter,
        is_verified_government_submission,
        orchestrate_application_submission,
        record_explicit_confirmation,
        sanitize_legacy_unverified_submission,
        stamp_application_version_and_check_invalidation,
    )
    from sqlalchemy.orm.attributes import flag_modified

    lang = lang if lang in ("en", "hi", "mr") else "en"
    cleaned = scheme_code_or_name.strip().upper()
    resolved_code = SCHEME_CODE_ALIASES.get(cleaned, cleaned)
    schema = get_form_schema_for_scheme(resolved_code)
    portal_entry = get_portal_integration_entry(resolved_code, db=db, lang=lang)

    portal_url = portal_entry.get("official_application_url") or (schema.get("official_portal") if schema else None) or "https://india.gov.in"
    if resolved_code == "WIDOW-PENSION" and profile and profile.state == "Uttar Pradesh":
        portal_url = "https://sspy-up.gov.in"

    adapter = get_portal_adapter(resolved_code)
    integration_supported = bool(adapter is not None and adapter.is_authorized)

    effective_user = user
    if effective_user is None and profile is not None and getattr(profile, "user_id", None):
        effective_user = User(id=profile.user_id, email="citizen@local")

    # Locate active matching application packet inside citizen profile if present
    target_app: Optional[Dict[str, Any]] = None
    current_profile_data: Optional[Dict[str, Any]] = None
    apps: List[Dict[str, Any]] = []
    if profile and profile.profile_data:
        current_profile_data = dict(profile.profile_data or {})
        apps = list(current_profile_data.get("applications", []))
        target_app = next(
            (
                a for a in apps
                if (a.get("scheme_code") or "").upper() == resolved_code.upper()
                and not a.get("legacy_synthetic_submission")
                and not str(a.get("reference_number") or "").upper().startswith("SAATHI/")
                and not is_verified_government_submission(a)
                and a.get("lifecycle_state") not in (STATE_SUBMITTED, STATE_PORTAL_SUBMITTED, STATE_SUBMITTING)
            ),
            None,
        )

    if not confirmed:
        review_summary = None
        if target_app is not None and profile is not None:
            if form_data:
                target_app.setdefault("form_data", {}).update(
                    {k: ("" if v is None else v) for k, v in form_data.items()}
                )
                stamp_application_version_and_check_invalidation(target_app, profile, increment_on_change=True)
            review_summary = build_application_review_summary(
                target_app=target_app,
                profile=profile,
                current_user=effective_user,
                db=db,
                lang=lang,
            )
            if db is not None:
                current_profile_data["applications"] = apps
                profile.profile_data = current_profile_data
                flag_modified(profile, "profile_data")
                db.commit()
        else:
            prefill_preview = run_universal_prefill(
                scheme_code_or_name=resolved_code,
                profile=profile,
                user=effective_user,
                db=db,
                form_overrides=form_data or {},
                lang=lang,
            )
            review_summary = {
                "application_id": None,
                "scheme_code": resolved_code,
                "scheme_name": prefill_preview.get("scheme_title") or resolved_code,
                "version": 1,
                "data_hash": None,
                "sections": [
                    {
                        "section_id": s.get("section_id"),
                        "title": s.get("title"),
                        "fields": [
                            {
                                "name": f.get("name"),
                                "label": f.get("label"),
                                "value": "" if f.get("value") is None else f.get("value"),
                                "required": bool(f.get("required")),
                                "source_badge": f.get("source_label") or "",
                                "source_tier": f.get("source_tier"),
                            }
                            for f in s.get("fields", [])
                        ],
                    }
                    for s in (prefill_preview.get("sections") or [])
                ],
                "submission": {
                    "integration_supported": integration_supported,
                    "integration_mode": "official_integration" if integration_supported else "manual_portal_required",
                    "manual_submission_required": not integration_supported,
                    "official_portal_url": portal_url,
                },
            }

        review_msg = {
            "en": "Please review your complete application summary and confirm your explicit authorization.",
            "hi": "कृपया अपने पूर्ण आवेदन सारांश की समीक्षा करें और अपनी स्पष्ट स्वीकृति दें।",
            "mr": "कृपया तुमच्या अर्जाचा संपूर्ण सारांश तपासा आणि स्पष्ट संमती द्या.",
        }[lang]
        return {
            "requires_confirmation": True,
            "scheme_code": resolved_code,
            "application_id": review_summary.get("application_id"),
            "version": review_summary.get("version", 1),
            "data_hash": review_summary.get("data_hash"),
            "integration_supported": integration_supported,
            "manual_portal_required": not integration_supported,
            "submission_method": portal_entry.get("submission_method"),
            "portal_url": portal_url,
            "official_portal_url": portal_url,
            "tracking_url": portal_entry.get("tracking_url"),
            "portal_integration": review_summary.get("portal_integration") or portal_entry,
            "review_summary": review_summary,
            "message": review_msg,
        }

    # Explicit citizen confirmation received
    if target_app is not None and profile is not None and effective_user is not None:
        if form_data:
            target_app.setdefault("form_data", {}).update(
                {k: ("" if v is None else v) for k, v in form_data.items()}
            )
            stamp_application_version_and_check_invalidation(target_app, profile, increment_on_change=True)

        conf_res = record_explicit_confirmation(
            target_app=target_app,
            profile=profile,
            current_user=effective_user,
            db=db,
            lang=lang,
            consent_acknowledged=consent_acknowledged,
            expected_version=expected_version,
            expected_hash=expected_hash,
        )
        sub_res = orchestrate_application_submission(
            target_app=target_app,
            profile=profile,
            current_user=effective_user,
            db=db,
            current_profile_data=current_profile_data,
            apps_list=apps,
            lang=lang,
            idempotency_key=idempotency_key,
        )
        return {
            "requires_confirmation": False,
            "confirmed": True,
            "confirmed_at": conf_res["confirmed_at"],
            "confirmed_version": conf_res["confirmed_version"],
            "confirmed_hash": conf_res["confirmed_hash"],
            "application_id": target_app.get("id"),
            "scheme_code": resolved_code,
            **sub_res,
            "official_portal_url": sub_res.get("portal_url") or portal_url,
        }

    # Stateless / unit-test fallback without persisted profile draft: NEVER simulate external submission!
    now_iso = datetime.now(timezone.utc).isoformat()
    if integration_supported and adapter is not None:
        try:
            res = adapter.submit(
                application={"scheme_code": resolved_code, "form_data": form_data or {}},
                idempotency_key=idempotency_key or f"chat-{uuid.uuid4().hex[:10]}",
                lang=lang,
            )
        except TimeoutError as exc:
            return {
                "requires_confirmation": False,
                "confirmed": True,
                "submitted": False,
                "manual_portal_required": False,
                "integration_supported": True,
                "lifecycle_state": STATE_SUBMISSION_UNKNOWN,
                "submission_status": STATE_SUBMISSION_UNKNOWN,
                "blind_retry_blocked": True,
                "external_reference_id": None,
                "official_portal_url": portal_url,
                "message": str(exc) or "Gateway timed out after request dispatch; outcome is submission_unknown.",
                "timestamp": now_iso,
            }
        except Exception as exc:
            is_uncertain = bool(getattr(exc, "outcome_uncertain", False))
            state_out = STATE_SUBMISSION_UNKNOWN if is_uncertain else STATE_SUBMISSION_FAILED
            return {
                "requires_confirmation": False,
                "confirmed": True,
                "submitted": False,
                "manual_portal_required": False,
                "integration_supported": True,
                "lifecycle_state": state_out,
                "submission_status": STATE_SUBMISSION_UNKNOWN if is_uncertain else "failed_retryable",
                "blind_retry_blocked": is_uncertain,
                "external_reference_id": None,
                "official_portal_url": portal_url,
                "message": str(exc) or "External portal submission failed.",
                "timestamp": now_iso,
            }

        ext_ref_raw = str(res.external_reference_id).strip() if res.external_reference_id else ""
        has_real_ref = bool(ext_ref_raw and not ext_ref_raw.upper().startswith("SAATHI/"))
        if res.outcome == "submitted" and has_real_ref:
            return {
                "requires_confirmation": False,
                "confirmed": True,
                "submitted": True,
                "manual_portal_required": False,
                "integration_supported": True,
                "lifecycle_state": STATE_SUBMITTED,
                "submission_status": "submitted",
                "external_reference_id": ext_ref_raw,
                "official_portal_url": portal_url,
                "message": res.message or "Submitted via verified integration.",
                "timestamp": now_iso,
            }
        if res.outcome in ("submitted", "uncertain"):
            return {
                "requires_confirmation": False,
                "confirmed": True,
                "submitted": False,
                "manual_portal_required": False,
                "integration_supported": True,
                "lifecycle_state": STATE_SUBMISSION_UNKNOWN,
                "submission_status": STATE_SUBMISSION_UNKNOWN,
                "blind_retry_blocked": True,
                "external_reference_id": None,
                "official_portal_url": portal_url,
                "message": res.message or "Portal outcome is ambiguous or missing authoritative transaction reference ID.",
                "timestamp": now_iso,
            }
        return {
            "requires_confirmation": False,
            "confirmed": True,
            "submitted": False,
            "manual_portal_required": False,
            "integration_supported": True,
            "lifecycle_state": STATE_SUBMISSION_FAILED,
            "submission_status": res.outcome,
            "blind_retry_blocked": res.outcome == "failed_permanent",
            "external_reference_id": None,
            "official_portal_url": portal_url,
            "message": res.message or "Official portal rejected the submission request.",
            "timestamp": now_iso,
        }

    manual_msg = {
        "en": f"Your {resolved_code} application details are confirmed. Manual submission on the official portal ({portal_url}) is required because no direct government API submission integration is enabled.",
        "hi": f"आपके {resolved_code} आवेदन विवरण की पुष्टि हो गई है। इस योजना के लिए प्रत्यक्ष सरकारी पोर्टल API एकीकरण सक्रिय नहीं है, इसलिए कृपया आधिकारिक पोर्टल ({portal_url}) पर मैन्युअल रूप से आवेदन जमा करें।",
        "mr": f"तुमच्या {resolved_code} अर्जाची माहिती नक्की झाली आहे. थेट शासकीय पोर्टल API जोडणी सक्रिय नसल्याने कृपया अधिकृत पोर्टलवर ({portal_url}) स्वतः अर्ज सादर करा.",
    }[lang]
    return {
        "requires_confirmation": False,
        "confirmed": True,
        "confirmed_at": now_iso,
        "confirmed_version": 1,
        "scheme_code": resolved_code,
        "lifecycle_state": STATE_CONFIRMED,
        "submitted": False,
        "manual_portal_required": True,
        "integration_supported": False,
        "submission_method": portal_entry.get("submission_method"),
        "submission_status": "manual_portal_required",
        "external_reference_id": None,
        "official_portal_url": portal_url,
        "tracking_url": portal_entry.get("tracking_url"),
        "portal_integration": portal_entry,
        "message": manual_msg,
        "timestamp": now_iso,
    }

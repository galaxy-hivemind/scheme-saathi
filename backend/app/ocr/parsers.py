"""
Pattern matching, demographic field extractors, and PII masking rules
for canonical Indian welfare documents.
"""
from typing import Dict, Any, Optional, Tuple, List
import re
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def normalize_date(date_str: str) -> Optional[str]:
    """
    Normalizes diverse date formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD) into ISO YYYY-MM-DD.
    Validates range between 1900 and current year + 1.
    """
    if not date_str:
        return None

    cleaned = date_str.strip().replace(".", "-").replace("/", "-")
    current_year = datetime.now(timezone.utc).year

    # Match DD-MM-YYYY
    match_dmy = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", cleaned)
    if match_dmy:
        d, m, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
        try:
            dt = datetime(year=y, month=m, day=d)
            if 1900 <= y <= current_year + 1:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Match YYYY-MM-DD
    match_ymd = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if match_ymd:
        y, m, d = int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3))
        try:
            dt = datetime(year=y, month=m, day=d)
            if 1900 <= y <= current_year + 1:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def extract_gender(text: str) -> Optional[str]:
    """
    Extracts normalized gender (male, female, transgender) from English or Hindi text.
    """
    lower = text.lower()
    # Check Hindi first
    if "महिला" in text:
        return "female"
    if "पुरुष" in text:
        return "male"

    # English patterns with word boundaries
    if re.search(r"\b(?:female|f)\b", lower) and not re.search(r"\bmale\b", lower):
        return "female"
    if re.search(r"\b(?:male|m)\b", lower):
        # Double check it wasn't female
        if re.search(r"\bfemale\b", lower):
            return "female"
        return "male"
    if re.search(r"\b(?:transgender|trans|third gender)\b", lower):
        return "transgender"

    return None


def extract_aadhaar_fields(text: str) -> Dict[str, Any]:
    """
    Extracts fields from Aadhaar Card text with mandatory UID masking.
    Never stores or returns unmasked 12-digit Aadhaar numbers.
    """
    fields: Dict[str, Any] = {}

    # Match 12-digit Aadhaar UID (space separated or continuous)
    uid_match = re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", text)
    if uid_match:
        last_4 = uid_match.group(3)
        fields["masked_uid"] = f"XXXXXXXX{last_4}"

    # Match Date of Birth: "DOB: DD/MM/YYYY" or "जन्म तिथि: DD/MM/YYYY" or "Year of Birth: YYYY"
    dob_match = re.search(
        r"(?:DOB|Date of Birth|जन्म तिथि|जन्म वर्ष)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4})",
        text,
        re.IGNORECASE,
    )
    if dob_match:
        raw_dob = dob_match.group(1)
        if len(raw_dob) == 4:
            # Year only: do not fabricate day/month
            fields["year_of_birth"] = int(raw_dob)
        else:
            norm = normalize_date(raw_dob)
            if norm:
                fields["date_of_birth"] = norm
    else:
        # Fallback date search
        date_cand = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", text)
        if date_cand:
            norm = normalize_date(date_cand.group(1))
            if norm:
                fields["date_of_birth"] = norm

    # Match Gender
    gender = extract_gender(text)
    if gender:
        fields["gender"] = gender

    # Match Candidate Name (often line above DOB or following "To")
    name_match = re.search(
        r"(?:To|Name|नाम)[\s:]*([A-Za-z\s]{3,40})(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if name_match:
        cand = name_match.group(1).strip()
        # Filter out common UI tokens
        if cand.lower() not in ["government of india", "unique identification authority", "father", "male", "female"]:
            fields["name"] = cand

    return fields


def extract_pan_fields(text: str) -> Dict[str, Any]:
    """
    Extracts fields from Permanent Account Number (PAN) Card.
    Format: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F).
    """
    fields: Dict[str, Any] = {}

    # Match 10-char PAN
    pan_match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", text.upper())
    if pan_match:
        fields["pan_number"] = pan_match.group(1)

    # Match DOB
    dob_match = re.search(
        r"(?:Date of Birth|DOB|जन्म तारीख)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        re.IGNORECASE,
    )
    if dob_match:
        norm = normalize_date(dob_match.group(1))
        if norm:
            fields["date_of_birth"] = norm
    else:
        date_cand = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", text)
        if date_cand:
            norm = normalize_date(date_cand.group(1))
            if norm:
                fields["date_of_birth"] = norm

    # Match Name
    name_match = re.search(r"(?:Name|नाम)[\s:]*([A-Za-z\s]{3,40})(?:\n|$)", text, re.IGNORECASE)
    if name_match:
        cand = name_match.group(1).strip()
        if cand.lower() not in ["income tax department", "govt of india", "permanent account number"]:
            fields["name"] = cand

    return fields


def extract_income_fields(text: str) -> Dict[str, Any]:
    """
    Extracts annual income (INR), certificate number, issuing authority, and DOB if present.
    """
    fields: Dict[str, Any] = {}

    # Match Annual Income amount
    # Matches patterns like "Rs. 1,20,000/-" or "₹ 90000" or "Annual Income: 150000" or "वार्षिक आय: 80,000"
    income_match = re.search(
        r"(?:Annual Income|Total Income|वार्षिक आय|आय)[\s:]*(?:Rs\.?|INR|₹)?[\s:]*([0-9,]+)",
        text,
        re.IGNORECASE,
    )
    if not income_match:
        # Secondary fallback: looking for "Rs. XXXXXX" or "INR XXXXXX"
        income_match = re.search(r"(?:Rs\.?|INR|₹)[\s:]*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,8})", text)

    if income_match:
        raw_amt = income_match.group(1).replace(",", "").strip()
        try:
            amt = int(raw_amt)
            if 1000 <= amt <= 100000000:  # Reasonable threshold (₹1k to ₹10 Cr)
                fields["annual_family_income"] = amt
        except ValueError:
            pass

    # Match Certificate Number (must contain digits)
    cert_match = re.search(
        r"(?:Certificate\s*(?:No\.?|Number|#)?|Cert\s*No\.?|प्रमाण\s*पत्र\s*संख्या|Application\s*No\.?)[\s:]*([A-Za-z0-9/-]*\d[A-Za-z0-9/-]{4,30})",
        text,
        re.IGNORECASE,
    )
    if cert_match:
        fields["certificate_number"] = cert_match.group(1).strip()

    # Match Issuing Authority
    auth_match = re.search(
        r"\b(Tehsildar|Tahasildar|SDO|Sub-Divisional Officer|District Magistrate|Revenue Officer|तहसीलदार)\b",
        text,
        re.IGNORECASE,
    )
    if auth_match:
        fields["issuing_authority"] = auth_match.group(1).capitalize()

    # Match Issue Date
    date_match = re.search(
        r"(?:Date|Dated|दिनांक)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        re.IGNORECASE,
    )
    if date_match:
        norm = normalize_date(date_match.group(1))
        if norm:
            fields["issue_date"] = norm

    # Match DOB if explicitly present on document
    dob_match = re.search(
        r"(?:Date of Birth|DOB|जन्म तिथि)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        re.IGNORECASE,
    )
    if dob_match:
        norm_dob = normalize_date(dob_match.group(1))
        if norm_dob:
            fields["date_of_birth"] = norm_dob

    return fields


def extract_caste_fields(text: str) -> Dict[str, Any]:
    """
    Extracts category (SC, ST, OBC, General), certificate number, and jurisdiction.
    """
    fields: Dict[str, Any] = {}

    lower = text.lower()
    if re.search(r"\b(?:scheduled caste|अनुसूचित जाति)\b", lower) or re.search(r"\bcategory\s*:\s*sc\b", lower):
        fields["caste_category"] = "SC"
    elif re.search(r"\b(?:scheduled tribe|अनुसूचित जनजाति)\b", lower) or re.search(r"\bcategory\s*:\s*st\b", lower):
        fields["caste_category"] = "ST"
    elif re.search(r"\b(?:other backward class|अन्य पिछड़ा वर्ग|obc)\b", lower):
        fields["caste_category"] = "OBC"
    elif re.search(r"\b(?:general|सामान्य)\b", lower):
        fields["caste_category"] = "General"

    # Match Certificate Number (must contain digits)
    cert_match = re.search(
        r"(?:Certificate\s*(?:No\.?|Number|#)?|Cert\s*No\.?|प्रमाण\s*पत्र\s*संख्या|Application\s*No\.?)[\s:]*([A-Za-z0-9/-]*\d[A-Za-z0-9/-]{4,30})",
        text,
        re.IGNORECASE,
    )
    if cert_match:
        fields["certificate_number"] = cert_match.group(1).strip()

    # Match State and District if present (avoid matching "District Magistrate")
    state_match = re.search(r"(?:State|राज्य)[\s:]*([A-Za-z\s]{3,30})(?:\n|,|$)", text, re.IGNORECASE)
    if state_match:
        fields["state"] = state_match.group(1).strip()

    dist_match = re.search(
        r"(?:District|ज़िला|जिला)[\s:]+(?!Magistrate|Court|Collector|Office)([A-Za-z\s]{3,30})(?:\n|,|$)",
        text,
        re.IGNORECASE,
    )
    if dist_match:
        fields["district"] = dist_match.group(1).strip()

    return fields


def extract_land_fields(text: str) -> Dict[str, Any]:
    """
    Extracts landholding area (in acres) and Khasra / Khata numbers.
    """
    fields: Dict[str, Any] = {}

    # Match Area
    # e.g. "Area: 2.5 Acres" or "1.2 Hectare" or "रकबा: 1.5 एकड़"
    area_match = re.search(
        r"(?:Area|Total Land|रकबा|क्षेत्रफल)[\s:]*([0-9.]+)\s*(Acres?|Hectares?|एकड़|हेक्टेयर)",
        text,
        re.IGNORECASE,
    )
    if area_match:
        val = float(area_match.group(1))
        unit = area_match.group(2).lower()
        if "hectare" in unit or "हेक्टेयर" in unit:
            # Convert 1 Hectare to 2.471 Acres
            fields["land_area_acres"] = round(val * 2.47105, 2)
        else:
            fields["land_area_acres"] = round(val, 2)

    # Match Khasra Number
    khasra_match = re.search(
        r"(?:Khasra|Khasra No\.?|खसरा संख्या|खसरा)[\s#:]*([0-9/-]+)",
        text,
        re.IGNORECASE,
    )
    if khasra_match:
        fields["khasra_number"] = khasra_match.group(1).strip()

    # Match Khata Number
    khata_match = re.search(
        r"(?:Khata|Khata No\.?|खाता संख्या|खाता)[\s#:]*([0-9/-]+)",
        text,
        re.IGNORECASE,
    )
    if khata_match:
        fields["khata_number"] = khata_match.group(1).strip()

    return fields


def extract_bank_fields(text: str) -> Dict[str, Any]:
    """
    Extracts bank passbook metadata with IFSC and account number masking.
    """
    fields: Dict[str, Any] = {}

    # Match 11-char IFSC (4 letters, 0, 6 alphanumeric)
    ifsc_match = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text.upper())
    if ifsc_match:
        fields["ifsc_code"] = ifsc_match.group(1)

    # Match Account Number (9 to 18 digits)
    acc_match = re.search(
        r"(?:A/C No\.?|Account No|खाता संख्या)[\s:]*(\d{9,18})",
        text,
        re.IGNORECASE,
    )
    if not acc_match:
        acc_match = re.search(r"\b(\d{11,18})\b", text)

    if acc_match:
        raw_acc = acc_match.group(1)
        last_4 = raw_acc[-4:]
        fields["masked_account_number"] = f"XXXXXXXX{last_4}"

    return fields


def parse_document_text(document_type: str, text: str) -> Tuple[Dict[str, Any], float]:
    """
    Dispatches extracted text to the appropriate canonical document extractor.
    Returns (extracted_fields, confidence_score).
    """
    norm_type = document_type.lower().replace("-", "_")

    if "aadhaar" in norm_type:
        fields = extract_aadhaar_fields(text)
    elif "pan" in norm_type:
        fields = extract_pan_fields(text)
    elif "income" in norm_type:
        fields = extract_income_fields(text)
    elif "caste" in norm_type:
        fields = extract_caste_fields(text)
    elif "land" in norm_type or "ror" in norm_type or "khasra" in norm_type:
        fields = extract_land_fields(text)
    elif "bank" in norm_type or "passbook" in norm_type:
        fields = extract_bank_fields(text)
    else:
        # Generic extractor: tries DOB, Gender, and common tokens
        fields = {}
        dob_cand = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", text)
        if dob_cand:
            norm = normalize_date(dob_cand.group(1))
            if norm:
                fields["date_of_birth"] = norm
        g = extract_gender(text)
        if g:
            fields["gender"] = g

    # Calculate heuristic confidence score based on fields found
    if not fields:
        confidence = 0.0
    else:
        # Baseline confidence starts at 0.70 when at least one structured field matches
        confidence = min(0.95, 0.70 + (len(fields) * 0.10))

    return fields, round(confidence, 2)

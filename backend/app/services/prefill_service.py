"""
Universal Multi-Scheme Application Pre-Fill Engine.

Provides a single, reusable, schema-driven pre-fill pipeline consumed uniformly across
chat agents (tools.py / planner.py) and REST application workflows (applications.py).

Design guarantees:
1. Scheme-independent configuration-driven canonical attribute mapping — no hardcoded
   scheme-specific prefill logic inside the resolution engine.
2. Strict provenance hierarchy distinguishing:
   - citizen_override (explicit citizen edits/resolutions for this draft)
   - existing_saved_draft (previously persisted values on this draft)
   - verified_document (Vault document with lifecycle_status == 'verified')
   - citizen_confirmed_document (Vault document with lifecycle_status == 'reviewed' & confirmed)
   - citizen_profile (UserProfile columns & structured profile_data)
   - conversation_entity (entities captured in the citizen's active session)
   - prior_saved_draft (verified identity/address/bank fields entered by this same citizen elsewhere)
   - system_default (legitimate non-personal UI/protocol defaults, e.g. ekyc_mode)
   - extracted_ocr_unverified (unreviewed OCR extraction — NEVER auto-populates or auto-verifies)
3. Zero fabrication: never invents personal facts, never substitutes district for sub_district,
   excludes placeholder 'Citizen' names, and leaves unavailable fields empty for citizen input.
4. Explicit conflict detection: never silently picks one value when trusted sources disagree;
   surfaces candidate values cleanly in 'en', 'hi', and 'mr' for citizen resolution.
5. Strict schema integrity: schemes without a verified schema return form_supported=False and
   schema_available=False with clear portal guidance instead of synthetic fallback forms.
"""
from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agents.form_schemas import (
    get_form_schema_for_scheme,
    get_unavailable_schema_payload,
)
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.document_service import (
    DOC_STATE_REVIEWED,
    DOC_STATE_VERIFIED,
    doc_types_match,
    normalize_vault_document,
)

# ── Provenance Constants ─────────────────────────────────────────────────────

SOURCE_CITIZEN_OVERRIDE = "citizen_override"
SOURCE_EXISTING_DRAFT = "existing_saved_draft"
SOURCE_VERIFIED_DOC = "verified_document"
SOURCE_CONFIRMED_DOC = "citizen_confirmed_document"
SOURCE_PROFILE = "citizen_profile"
SOURCE_CONVERSATION = "conversation_entity"
SOURCE_PRIOR_DRAFT = "prior_saved_draft"
SOURCE_SYSTEM_DEFAULT = "system_default"
SOURCE_UNVERIFIED_OCR = "extracted_ocr_unverified"

TRUSTED_SOURCE_PRIORITY: Tuple[str, ...] = (
    SOURCE_CITIZEN_OVERRIDE,
    SOURCE_EXISTING_DRAFT,
    SOURCE_VERIFIED_DOC,
    SOURCE_CONFIRMED_DOC,
    SOURCE_PROFILE,
    SOURCE_CONVERSATION,
    SOURCE_PRIOR_DRAFT,
    SOURCE_SYSTEM_DEFAULT,
)

SOURCE_LABELS: Dict[str, Dict[str, str]] = {
    SOURCE_CITIZEN_OVERRIDE: {
        "en": "Citizen Entry",
        "hi": "नागरिक प्रविष्टि",
        "mr": "नागरिक नोंद",
    },
    SOURCE_EXISTING_DRAFT: {
        "en": "Saved Draft",
        "hi": "सहेजा गया ड्राफ्ट",
        "mr": "जतन केलेला मसुदा",
    },
    SOURCE_VERIFIED_DOC: {
        "en": "Verified Document",
        "hi": "सत्यापित दस्तावेज़",
        "mr": "पडताळलेला दस्तऐवज",
    },
    SOURCE_CONFIRMED_DOC: {
        "en": "Citizen-Confirmed Document (Unverified)",
        "hi": "नागरिक-पुष्ट दस्तावेज़ (सत्यापन शेष)",
        "mr": "नागरिक-पुष्ट दस्तऐवज (पडताळणी बाकी)",
    },
    SOURCE_PROFILE: {
        "en": "Citizen Profile",
        "hi": "नागरिक प्रोफ़ाइल",
        "mr": "नागरिक प्रोफाईल",
    },
    SOURCE_CONVERSATION: {
        "en": "Conversation Answer",
        "hi": "वार्तालाप विवरण",
        "mr": "संभाषण माहिती",
    },
    SOURCE_PRIOR_DRAFT: {
        "en": "Previous Draft Packet",
        "hi": "पिछला आवेदन ड्राफ्ट",
        "mr": "मागील अर्ज मसुदा",
    },
    SOURCE_SYSTEM_DEFAULT: {
        "en": "System Channel Option",
        "hi": "सिस्टम विकल्प",
        "mr": "प्रणाली पर्याय",
    },
    SOURCE_UNVERIFIED_OCR: {
        "en": "Unverified OCR (Review Required)",
        "hi": "असत्यापित OCR (समीक्षा आवश्यक)",
        "mr": "अपडताळलेला OCR (तपासणी आवश्यक)",
    },
}

# Stable personal/location/bank canonical keys safe to reuse across this citizen's own drafts
CROSS_DRAFT_REUSABLE_CANONICAL_KEYS = {
    "full_name",
    "date_of_birth",
    "age",
    "gender",
    "marital_status",
    "caste_category",
    "aadhaar_number",
    "phone_number",
    "state",
    "district",
    "sub_district",
    "village",
    "annual_income",
    "bank_account_number",
    "ifsc_code",
    "khasra_number",
    "land_holding_acres",
    "land_registration_date",
    "domicile_certificate_number",
    "ration_card_number",
    "job_card_number",
}


# ── Declarative Semantic Attribute Mapping Table ─────────────────────────────

CANONICAL_ATTRIBUTE_MAP: Dict[str, Dict[str, Any]] = {
    "full_name": {
        "profile_keys": ("full_name",),
        "entity_keys": ("full_name", "applicant_name"),
        "doc_specs": [
            ("aadhaar_card", ("holder_name", "full_name_on_document")),
            ("bank_passbook", ("holder_name", "full_name_on_document")),
            ("domicile_certificate", ("holder_name", "full_name_on_document")),
            ("income_certificate", ("holder_name", "full_name_on_document")),
            ("caste_certificate", ("holder_name", "full_name_on_document")),
            ("marksheet_12th", ("holder_name", "full_name_on_document")),
            ("pan_card", ("holder_name", "full_name_on_document")),
            ("ration_card", ("holder_name", "full_name_on_document")),
        ],
        "draft_keys": ("applicant_name", "beneficiary_name", "vendor_name", "student_name"),
        "compare_mode": "ci_text",
    },
    "date_of_birth": {
        "profile_keys": ("date_of_birth", "dob"),
        "entity_keys": ("date_of_birth", "dob"),
        "doc_specs": [
            ("aadhaar_card", ("date_of_birth", "dob")),
            ("marksheet_12th", ("date_of_birth", "dob")),
            ("birth_certificate", ("date_of_birth", "dob")),
        ],
        "draft_keys": ("date_of_birth",),
        "compare_mode": "date",
    },
    "age": {
        "profile_keys": ("age",),
        "entity_keys": ("age",),
        "doc_specs": [],
        "draft_keys": ("age",),
        "compare_mode": "number",
    },
    "gender": {
        "profile_keys": ("gender",),
        "entity_keys": ("gender",),
        "doc_specs": [
            ("aadhaar_card", ("gender",)),
        ],
        "draft_keys": ("gender",),
        "compare_mode": "select",
    },
    "marital_status": {
        "profile_keys": ("marital_status",),
        "entity_keys": ("marital_status",),
        "doc_specs": [],
        "draft_keys": ("marital_status",),
        "compare_mode": "select",
    },
    "caste_category": {
        "profile_keys": ("caste_category", "category", "social_category"),
        "entity_keys": ("caste_category", "category"),
        "doc_specs": [
            ("caste_certificate", ("caste_category", "category")),
        ],
        "draft_keys": ("category", "caste_category"),
        "compare_mode": "select",
    },
    "aadhaar_number": {
        "profile_keys": ("aadhaar_number", "aadhaar", "uidai_number"),
        "entity_keys": ("aadhaar_number", "aadhaar"),
        "doc_specs": [
            ("aadhaar_card", ("document_number", "aadhaar_number")),
        ],
        "draft_keys": ("aadhaar_number",),
        "compare_mode": "digits",
    },
    "phone_number": {
        "profile_keys": ("phone_number", "mobile_number", "mobile", "phone"),
        "entity_keys": ("phone_number", "mobile_number"),
        "doc_specs": [
            ("aadhaar_card", ("mobile_number", "phone_number")),
            ("bank_passbook", ("mobile_number", "phone_number")),
        ],
        "draft_keys": ("mobile_number", "phone_number"),
        "compare_mode": "digits",
    },
    "state": {
        "profile_keys": ("state", "state_of_domicile"),
        "entity_keys": ("state", "state_of_domicile"),
        "doc_specs": [
            ("domicile_certificate", ("state",)),
            ("aadhaar_card", ("state",)),
        ],
        "draft_keys": ("state", "state_of_domicile"),
        "compare_mode": "ci_text",
    },
    "district": {
        "profile_keys": ("district",),
        "entity_keys": ("district",),
        "doc_specs": [
            ("domicile_certificate", ("district",)),
            ("aadhaar_card", ("district",)),
        ],
        "draft_keys": ("district",),
        "compare_mode": "ci_text",
    },
    "sub_district": {
        # Strictly NEVER substitute district here
        "profile_keys": ("sub_district", "sub_district_block", "tehsil", "taluka", "block", "block_panchayat", "block_tehsil", "city_town_ulb"),
        "entity_keys": ("sub_district", "tehsil", "taluka", "block"),
        "doc_specs": [
            ("land_records", ("sub_district", "tehsil", "taluka")),
            ("domicile_certificate", ("sub_district", "tehsil", "taluka")),
            ("ration_card", ("sub_district", "tehsil", "block")),
        ],
        "draft_keys": ("sub_district_block", "sub_district", "block_tehsil", "block_panchayat", "city_town_ulb"),
        "compare_mode": "ci_text",
    },
    "village": {
        "profile_keys": ("village", "village_town", "ward_locality", "gram_panchayat"),
        "entity_keys": ("village", "village_town", "ward_locality"),
        "doc_specs": [
            ("land_records", ("village",)),
            ("ration_card", ("village",)),
            ("job_card", ("village",)),
        ],
        "draft_keys": ("village", "village_town", "ward_locality"),
        "compare_mode": "ci_text",
    },
    "annual_income": {
        "profile_keys": ("annual_family_income", "annual_income"),
        "entity_keys": ("annual_income", "annual_family_income"),
        "doc_specs": [
            ("income_certificate", ("declared_income", "annual_income")),
        ],
        "draft_keys": ("annual_family_income",),
        "compare_mode": "number",
    },
    "bank_account_number": {
        "profile_keys": ("bank_account_number", "account_number"),
        "entity_keys": ("bank_account_number", "account_number"),
        "doc_specs": [
            ("bank_passbook", ("document_number", "account_number", "bank_account_number")),
        ],
        "draft_keys": ("bank_account_number",),
        "compare_mode": "text",
    },
    "ifsc_code": {
        "profile_keys": ("bank_ifsc", "ifsc_code", "ifsc"),
        "entity_keys": ("ifsc_code", "bank_ifsc", "ifsc"),
        "doc_specs": [
            ("bank_passbook", ("ifsc_code", "bank_ifsc")),
        ],
        "draft_keys": ("ifsc_code",),
        "compare_mode": "ci_text",
    },
    "preferred_bank": {
        "profile_keys": ("preferred_bank", "bank_name"),
        "entity_keys": ("preferred_bank", "bank_name"),
        "doc_specs": [
            ("bank_passbook", ("bank_name", "issuing_authority")),
        ],
        "draft_keys": ("preferred_bank",),
        "compare_mode": "ci_text",
    },
    "land_holding_acres": {
        "profile_keys": ("land_holding_acres",),
        "entity_keys": ("land_holding_acres",),
        "doc_specs": [
            ("land_records", ("land_area_acres", "land_holding_acres")),
        ],
        "draft_keys": ("land_area_acres", "cultivable_land_acres"),
        "compare_mode": "number",
    },
    "khasra_number": {
        "profile_keys": ("khasra_number", "khasra_khatauni_no", "survey_number"),
        "entity_keys": ("khasra_number", "khasra_khatauni_no"),
        "doc_specs": [
            ("land_records", ("khasra_number", "document_number", "survey_number")),
        ],
        "draft_keys": ("khasra_khatauni_no",),
        "compare_mode": "ci_text",
    },
    "land_registration_date": {
        "profile_keys": ("land_registration_date", "land_transfer_date"),
        "entity_keys": ("land_registration_date", "land_transfer_date"),
        "doc_specs": [
            ("land_records", ("registration_date", "land_transfer_date")),
        ],
        "draft_keys": ("land_transfer_date",),
        "compare_mode": "date",
    },
    "land_ownership_type": {
        "profile_keys": ("land_ownership_type",),
        "entity_keys": ("land_ownership_type",),
        "doc_specs": [
            ("land_records", ("ownership_type", "land_ownership_type")),
        ],
        "draft_keys": (),
        "compare_mode": "select",
    },
    "domicile_certificate_number": {
        "profile_keys": ("domicile_certificate_number",),
        "entity_keys": ("domicile_certificate_number",),
        "doc_specs": [
            ("domicile_certificate", ("document_number",)),
        ],
        "draft_keys": ("domicile_certificate_number",),
        "compare_mode": "ci_text",
    },
    "ration_card_number": {
        "profile_keys": ("ration_card_number", "bpl_ration_card_number"),
        "entity_keys": ("ration_card_number",),
        "doc_specs": [
            ("ration_card", ("document_number",)),
        ],
        "draft_keys": ("ration_card_number", "bpl_ration_card_number"),
        "compare_mode": "ci_text",
    },
    "death_certificate_number": {
        "profile_keys": ("death_certificate_number",),
        "entity_keys": ("death_certificate_number",),
        "doc_specs": [
            ("death_certificate", ("document_number",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "issuing_registrar": {
        "profile_keys": ("issuing_registrar",),
        "entity_keys": ("issuing_registrar",),
        "doc_specs": [
            ("death_certificate", ("issuing_authority",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "deceased_husband_name": {
        "profile_keys": ("deceased_husband_name",),
        "entity_keys": ("deceased_husband_name",),
        "doc_specs": [
            ("death_certificate", ("deceased_name",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "husband_name": {
        "profile_keys": ("husband_name",),
        "entity_keys": ("husband_name",),
        "doc_specs": [
            ("mcp_card", ("husband_name",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "mcp_card_registration_number": {
        "profile_keys": ("mcp_card_registration_number",),
        "entity_keys": ("mcp_card_registration_number",),
        "doc_specs": [
            ("mcp_card", ("document_number",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "certificate_number": {
        "profile_keys": ("vending_certificate_number", "certificate_number"),
        "entity_keys": ("certificate_number",),
        "doc_specs": [
            ("vending_certificate", ("document_number",)),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "job_card_number": {
        "profile_keys": ("mgnrega_job_card_number", "job_card_number"),
        "entity_keys": ("mgnrega_job_card_number", "job_card_number"),
        "doc_specs": [
            ("job_card", ("document_number",)),
        ],
        "draft_keys": ("mgnrega_job_card_number",),
        "compare_mode": "ci_text",
    },
    "mgnrega_wage_convergence": {
        "profile_keys": ("mgnrega_wage_convergence",),
        "entity_keys": ("mgnrega_wage_convergence",),
        "doc_specs": [],
        "draft_keys": (),
        "compare_mode": "select",
    },
    "student_percentage": {
        "profile_keys": ("student_percentage", "class_12_percentage"),
        "entity_keys": ("student_percentage", "class_12_percentage"),
        "doc_specs": [
            ("marksheet_12th", ("percentage", "student_percentage")),
        ],
        "draft_keys": (),
        "compare_mode": "number",
    },
    "class_12_roll_no": {
        "profile_keys": ("class_12_roll_no",),
        "entity_keys": ("class_12_roll_no",),
        "doc_specs": [
            ("marksheet_12th", ("document_number", "roll_number")),
        ],
        "draft_keys": (),
        "compare_mode": "ci_text",
    },
    "income_tax_payer": {
        "profile_keys": ("income_tax_payer_in_family", "is_income_tax_payer"),
        "entity_keys": ("is_income_tax_payer", "income_tax_payer_in_family"),
        "doc_specs": [],
        "draft_keys": (),
        "compare_mode": "select",
    },
    "owns_pucca_house": {
        "profile_keys": ("owns_pucca_house", "ownership_of_pucca_house", "owns_pucca_house_in_india"),
        "entity_keys": ("owns_pucca_house",),
        "doc_specs": [],
        "draft_keys": (),
        "compare_mode": "select",
    },
}

PROFILE_FIELD_TO_CANONICAL: Dict[str, str] = {
    "full_name": "full_name",
    "date_of_birth": "date_of_birth",
    "age": "age",
    "gender": "gender",
    "marital_status": "marital_status",
    "caste_category": "caste_category",
    "aadhaar_number": "aadhaar_number",
    "phone_number": "phone_number",
    "state": "state",
    "district": "district",
    "sub_district": "sub_district",
    "village": "village",
    "annual_income": "annual_income",
    "bank_account_number": "bank_account_number",
    "bank_ifsc": "ifsc_code",
    "ifsc_code": "ifsc_code",
    "preferred_bank": "preferred_bank",
    "land_holding_acres": "land_holding_acres",
    "khasra_number": "khasra_number",
    "land_registration_date": "land_registration_date",
    "land_ownership_type": "land_ownership_type",
    "student_percentage": "student_percentage",
}

FIELD_NAME_TO_CANONICAL: Dict[str, str] = {
    "applicant_name": "full_name",
    "beneficiary_name": "full_name",
    "vendor_name": "full_name",
    "student_name": "full_name",
    "state_of_domicile": "state",
    "sub_district_block": "sub_district",
    "sub_district": "sub_district",
    "block_tehsil": "sub_district",
    "block_panchayat": "sub_district",
    "city_town_ulb": "sub_district",
    "village": "village",
    "village_town": "village",
    "ward_locality": "village",
    "category": "caste_category",
    "mobile_number": "phone_number",
    "annual_family_income": "annual_income",
    "ifsc_code": "ifsc_code",
    "preferred_bank": "preferred_bank",
    "khasra_khatauni_no": "khasra_number",
    "land_area_acres": "land_holding_acres",
    "cultivable_land_acres": "land_holding_acres",
    "land_transfer_date": "land_registration_date",
    "land_ownership_type": "land_ownership_type",
    "domicile_certificate_number": "domicile_certificate_number",
    "ration_card_number": "ration_card_number",
    "bpl_ration_card_number": "ration_card_number",
    "death_certificate_number": "death_certificate_number",
    "issuing_registrar": "issuing_registrar",
    "deceased_husband_name": "deceased_husband_name",
    "husband_name": "husband_name",
    "mcp_card_registration_number": "mcp_card_registration_number",
    "certificate_number": "certificate_number",
    "mgnrega_job_card_number": "job_card_number",
    "mgnrega_wage_convergence": "mgnrega_wage_convergence",
    "class_12_percentage": "student_percentage",
    "class_12_roll_no": "class_12_roll_no",
    "income_tax_payer_in_family": "income_tax_payer",
    "ownership_of_pucca_house": "owns_pucca_house",
    "owns_pucca_house_in_india": "owns_pucca_house",
}


# ── Cleaning, Normalization & Validation Helpers ─────────────────────────────

_EMPTY_SENTINELS = {"", "null", "undefined", "none", "n/a", "na"}


def clean_scalar(value: Any) -> Any:
    """Strips dirty empty/null sentinel strings without fabricating replacements."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.lower() in _EMPTY_SENTINELS:
            return ""
        return trimmed
    return value


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    return str(value).strip().lower() in _EMPTY_SENTINELS


def _resolve_canonical_key(field: Dict[str, Any]) -> Optional[str]:
    if field.get("canonical_key"):
        return str(field["canonical_key"])
    pfield = field.get("profile_field")
    if pfield and pfield in PROFILE_FIELD_TO_CANONICAL:
        return PROFILE_FIELD_TO_CANONICAL[pfield]
    fname = field.get("name", "")
    if fname in FIELD_NAME_TO_CANONICAL:
        return FIELD_NAME_TO_CANONICAL[fname]
    return pfield


def normalize_field_value(
    raw_value: Any,
    field: Dict[str, Any],
    *,
    strict_enum: bool = False,
) -> Any:
    """
    Normalizes values across text, numbers, dates, booleans, and select dropdowns
    while preserving explicit invalid citizen inputs when validating so validation
    catches errors cleanly instead of silently mutating invalid text into passable form.
    """
    cleaned = clean_scalar(raw_value)
    if is_empty_value(cleaned):
        return ""

    ftype = (field.get("type") or "text").lower()
    fname = field.get("name", "")

    # Convert boolean to Yes/No or option strings when bound to a select field
    if isinstance(cleaned, bool):
        cleaned = "Yes" if cleaned else "No"

    if ftype == "select":
        options = [str(o) for o in (field.get("options") or [])]
        str_val = str(cleaned).strip()
        # Exact match first
        for opt in options:
            if opt == str_val:
                return opt
        # Case-insensitive or semantic normalization (e.g. 'male' -> 'MALE', 'obc' -> 'OBC')
        low = str_val.lower()
        for opt in options:
            if opt.lower() == low:
                return opt
        # Common semantic aliases for dropdowns
        if low in ("true", "yes", "होय", "हाँ") and any(o.lower() == "yes" for o in options):
            return next(o for o in options if o.lower() == "yes")
        if low in ("false", "no", "नाही", "नहीं") and any(o.lower() == "no" for o in options):
            return next(o for o in options if o.lower() == "no")
        if low in ("widow", "widowed", "विधवा") and any(o.lower() == "widowed" for o in options):
            return next(o for o in options if o.lower() == "widowed")
        if low in ("open", "gen") and any(o.lower() == "general" for o in options):
            return next(o for o in options if o.lower() == "general")
        return "" if strict_enum else str_val

    if ftype == "number":
        if isinstance(cleaned, (int, float)):
            return cleaned
        num_str = str(cleaned).replace(",", "").replace("₹", "").strip()
        try:
            fval = float(num_str)
            return int(fval) if fval.is_integer() else round(fval, 2)
        except ValueError:
            return str(cleaned)

    if ftype == "date":
        str_val = str(cleaned).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", str_val):
            return str_val
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(str_val, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return str_val

    # Text cleaning for well-known formats without inventing missing characters
    str_val = str(cleaned).strip()
    if "aadhaar" in fname and re.fullmatch(r"[0-9\s-]{12,16}", str_val):
        compact = re.sub(r"[\s-]+", "", str_val)
        if re.fullmatch(r"[0-9]{12}", compact):
            return compact
    if "mobile" in fname or "phone" in fname:
        compact = re.sub(r"[\s-]+", "", str_val)
        if compact.startswith("+91") and len(compact) == 13:
            compact = compact[3:]
        if re.fullmatch(r"[6-9][0-9]{9}", compact):
            return compact
    if "ifsc" in fname and re.fullmatch(r"[A-Za-z]{4}0[A-Za-z0-9]{6}", str_val):
        return str_val.upper()
    return str_val


def _comparison_signature(value: Any, field: Dict[str, Any], compare_mode: str) -> str:
    norm = normalize_field_value(value, field)
    if is_empty_value(norm):
        return ""
    s = str(norm).strip()
    if compare_mode == "digits":
        return re.sub(r"\D+", "", s)
    if compare_mode == "number":
        try:
            return f"{float(s):.4f}"
        except ValueError:
            return s.lower()
    if compare_mode in ("ci_text", "select"):
        return re.sub(r"\s+", " ", s).lower()
    return re.sub(r"\s+", " ", s)


def _validate_field_value(
    value: Any,
    field: Dict[str, Any],
    is_required: bool,
    lang: str,
) -> Optional[str]:
    label = field.get("label", field["name"].replace("_", " ").title())
    if is_empty_value(value):
        if is_required:
            return {
                "en": f"Mandatory field '{label}' requires citizen input.",
                "hi": f"अनिवार्य फ़ील्ड '{label}' के लिए नागरिक प्रविष्टि आवश्यक है।",
                "mr": f"अनिवार्य माहिती '{label}' भरणे आवश्यक आहे.",
            }.get(lang, f"Mandatory field '{label}' requires citizen input.")
        return None

    str_val = str(value).strip()
    ftype = (field.get("type") or "text").lower()

    if ftype == "select" and field.get("options"):
        opts = [str(o) for o in field["options"]]
        if str_val not in opts:
            return {
                "en": f"Invalid selection for '{label}'.",
                "hi": f"'{label}' के लिए चयन अमान्य है।",
                "mr": f"'{label}' साठी निवडलेला पर्याय अवैध आहे.",
            }.get(lang, f"Invalid selection for '{label}'.")

    if ftype == "number":
        try:
            float(str_val)
        except ValueError:
            return {
                "en": f"'{label}' must be a valid number.",
                "hi": f"'{label}' एक मान्य संख्या होनी चाहिए।",
                "mr": f"'{label}' ही वैध संख्या असणे आवश्यक आहे.",
            }.get(lang, f"'{label}' must be a valid number.")

    if ftype == "date":
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str_val):
            return {
                "en": f"'{label}' must be in YYYY-MM-DD date format.",
                "hi": f"'{label}' की तिथि YYYY-MM-DD प्रारूप में होनी चाहिए।",
                "mr": f"'{label}' तारीख YYYY-MM-DD स्वरूपात असावी.",
            }.get(lang, f"'{label}' must be in YYYY-MM-DD date format.")
        try:
            datetime.strptime(str_val, "%Y-%m-%d")
        except ValueError:
            return {
                "en": f"'{label}' is not a valid calendar date.",
                "hi": f"'{label}' एक मान्य कैलेंडर तिथि नहीं है।",
                "mr": f"'{label}' ही वैध दिनांक नाही.",
            }.get(lang, f"'{label}' is not a valid calendar date.")

    if field.get("pattern"):
        if not re.match(field["pattern"], str_val):
            return {
                "en": f"Invalid format for '{label}'.",
                "hi": f"'{label}' का प्रारूप अमान्य है।",
                "mr": f"'{label}' चा नमुना अवैध आहे.",
            }.get(lang, f"Invalid format for '{label}'.")

    return None


# ── Citizen-Isolated Context Extraction Helpers ──────────────────────────────

def assert_citizen_profile_ownership(
    user: Optional[User],
    profile: Optional[UserProfile],
) -> Optional[str]:
    """
    Strictly verifies citizen-level ownership isolation between User and UserProfile.
    Raises PermissionError if user and profile IDs mismatch.
    """
    uid = str(user.id) if user and getattr(user, "id", None) else None
    pid = str(profile.user_id) if profile and getattr(profile, "user_id", None) else None
    if uid and pid and uid != pid:
        raise PermissionError("Cross-citizen profile access is strictly forbidden.")
    return uid or pid


def _extract_profile_source_values(
    user: Optional[User],
    profile: Optional[UserProfile],
    canonical_key: str,
) -> Optional[Any]:
    if not profile:
        return None
    spec = CANONICAL_ATTRIBUTE_MAP.get(canonical_key) or {"profile_keys": (canonical_key,)}
    profile_data = dict(profile.profile_data or {})

    for pk in spec.get("profile_keys", (canonical_key,)):
        raw = None
        if pk == "phone_number" and user is not None and getattr(user, "phone_number", None):
            raw = getattr(user, "phone_number")
        elif pk == "age":
            raw = profile.age if profile.age is not None else profile_data.get("age")
        elif pk in ("annual_family_income", "annual_income"):
            raw = profile.annual_income if profile.annual_income is not None else profile_data.get(pk)
        elif hasattr(profile, pk) and getattr(profile, pk) is not None:
            raw = getattr(profile, pk)
        elif pk in profile_data:
            raw = profile_data.get(pk)

        if canonical_key == "full_name" and isinstance(raw, str) and raw.strip().lower() == "citizen":
            raw = None

        if canonical_key == "income_tax_payer":
            # Only populate household tax status when explicitly known as boolean/string
            if isinstance(raw, bool):
                return "Yes" if raw else "No"
            if isinstance(raw, str) and raw.strip().lower() in ("yes", "no", "true", "false"):
                return "Yes" if raw.strip().lower() in ("yes", "true") else "No"
            continue

        if canonical_key == "owns_pucca_house":
            if isinstance(raw, bool):
                return "Yes" if raw else "No"
            if isinstance(raw, str) and raw.strip().lower() in ("yes", "no", "true", "false"):
                return "Yes" if raw.strip().lower() in ("yes", "true") else "No"
            continue

        if not is_empty_value(clean_scalar(raw)):
            return raw

    # Explicit unit derivation: hectares -> acres (only when acres is not explicitly present)
    if canonical_key == "land_holding_acres":
        hectares = profile_data.get("land_size_hectares")
        if hectares not in (None, "") and isinstance(hectares, (int, float)) and float(hectares) > 0:
            return round(float(hectares) * 2.47105, 2)

    return None


def _extract_document_candidates(
    vault_docs: List[Dict[str, Any]],
    canonical_key: str,
) -> Tuple[Optional[Tuple[Any, str, str]], Optional[Tuple[Any, str]]]:
    """
    Inspects normalized Vault documents owned by this citizen.
    Returns (trusted_match, unverified_ocr_hint):
    - trusted_match: (value, source_tier, doc_title) from 'verified' or 'reviewed' (confirmed) doc
    - unverified_ocr_hint: (value, doc_id) ONLY for unreviewed OCR hint display (never auto-fills)
    """
    spec = CANONICAL_ATTRIBUTE_MAP.get(canonical_key)
    if not spec:
        return None, None
    doc_specs = spec.get("doc_specs") or []
    if not doc_specs:
        return None, None

    # Sort verified docs ahead of citizen-confirmed ('reviewed') docs
    verified_match: Optional[Tuple[Any, str, str]] = None
    confirmed_match: Optional[Tuple[Any, str, str]] = None
    unverified_hint: Optional[Tuple[Any, str]] = None

    for req_doc_type, field_keys in doc_specs:
        for doc in vault_docs:
            if not doc_types_match(req_doc_type, doc.get("document_type", "")):
                continue
            state = doc.get("lifecycle_status")
            reviewed_fields = doc.get("reviewed_fields") or {}
            extracted_fields = doc.get("extracted_fields") or {}

            if state == DOC_STATE_VERIFIED:
                for fk in field_keys:
                    cand = clean_scalar(reviewed_fields.get(fk))
                    if is_empty_value(cand):
                        cand = clean_scalar(extracted_fields.get(fk))
                    if not is_empty_value(cand):
                        verified_match = (cand, SOURCE_VERIFIED_DOC, doc.get("document_type", req_doc_type))
                        break
            elif state == DOC_STATE_REVIEWED and doc.get("citizen_confirmed_accurate"):
                for fk in field_keys:
                    cand = clean_scalar(reviewed_fields.get(fk))
                    if not is_empty_value(cand):
                        confirmed_match = confirmed_match or (cand, SOURCE_CONFIRMED_DOC, doc.get("document_type", req_doc_type))
                        break
            elif state not in ("rejected",):
                # Uploaded / extracted / awaiting review — strictly unverified hint only!
                for fk in field_keys:
                    cand = clean_scalar(extracted_fields.get(fk))
                    if not is_empty_value(cand):
                        unverified_hint = unverified_hint or (cand, doc.get("id", ""))
                        break
            if verified_match:
                break
        if verified_match:
            break

    return verified_match or confirmed_match, unverified_hint


def _extract_conversation_entity_value(
    conversation_entities: Dict[str, Any],
    canonical_key: str,
) -> Optional[Any]:
    if not conversation_entities:
        return None
    spec = CANONICAL_ATTRIBUTE_MAP.get(canonical_key) or {"entity_keys": (canonical_key,)}
    for ek in spec.get("entity_keys", (canonical_key,)):
        if ek in conversation_entities:
            val = clean_scalar(conversation_entities[ek])
            if not is_empty_value(val):
                return val
    return None


def _extract_prior_draft_value(
    prior_apps: List[Dict[str, Any]],
    current_draft_id: Optional[str],
    canonical_key: str,
) -> Optional[Any]:
    if canonical_key not in CROSS_DRAFT_REUSABLE_CANONICAL_KEYS:
        return None
    spec = CANONICAL_ATTRIBUTE_MAP.get(canonical_key) or {}
    draft_keys = spec.get("draft_keys", ())
    if not draft_keys:
        return None
    for app in prior_apps:
        if current_draft_id and app.get("id") == current_draft_id:
            continue
        fd = app.get("form_data") or {}
        for dk in draft_keys:
            val = clean_scalar(fd.get(dk))
            if not is_empty_value(val):
                return val
    return None


def _evaluate_field_conditional_requirement(
    scheme_code: str,
    field: Dict[str, Any],
    current_values: Dict[str, Any],
) -> Tuple[bool, bool]:
    """
    Returns (is_conditional_field, is_currently_required_for_this_citizen).
    """
    base_required = bool(field.get("required"))
    fname = field["name"]
    canon = (scheme_code or "").upper()

    if canon == "PMAY-G" and fname == "mgnrega_job_card_number":
        conv = str(current_values.get("mgnrega_wage_convergence") or "").strip().lower()
        return True, (conv == "yes")

    if canon == "AB-PMJAY" and fname == "ration_card_number":
        cat = str(current_values.get("coverage_category") or "").strip().lower()
        return True, ("ration card" in cat or "nfsa" in cat)

    return False, base_required


# ── Primary Universal Engine Entry Point ─────────────────────────────────────

def run_universal_prefill(
    scheme_code_or_name: str,
    profile: Optional[UserProfile],
    user: Optional[User] = None,
    db: Optional[Session] = None,
    existing_draft: Optional[Dict[str, Any]] = None,
    form_overrides: Optional[Dict[str, Any]] = None,
    conversation_entities: Optional[Dict[str, Any]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Executes the universal schema-driven application pre-fill pipeline.
    Never fabricates schemas for unsupported schemes and never invents missing facts.
    """
    lang_code = lang if lang in ("en", "hi", "mr") else "en"
    owner_id = assert_citizen_profile_ownership(user, profile)

    schema = get_form_schema_for_scheme(scheme_code_or_name)
    if not schema or not schema.get("form_supported"):
        return get_unavailable_schema_payload(
            scheme_code=scheme_code_or_name,
            scheme_name=scheme_code_or_name,
            lang=lang_code,
        )

    scheme_code = schema["scheme_code"]
    form_overrides = form_overrides or {}
    conversation_entities = conversation_entities or {}
    existing_draft = existing_draft or {}

    profile_data = dict(profile.profile_data or {}) if profile else {}
    resolved_conflicts: Dict[str, str] = dict(existing_draft.get("resolved_conflicts") or {})

    # Citizen-isolated Vault documents & prior drafts
    raw_docs = list(profile_data.get("documents", []))
    vault_docs = [
        normalize_vault_document(d)
        for d in raw_docs
        if not owner_id or not d.get("user_id") or str(d.get("user_id")) == owner_id
    ]
    raw_apps = list(profile_data.get("applications", []))
    own_apps = [
        a
        for a in raw_apps
        if not owner_id or not a.get("user_id") or str(a.get("user_id")) == owner_id
    ]
    existing_form_data = dict(existing_draft.get("form_data") or {})

    # Step 1: Collect raw candidates per field across all isolated sources
    raw_sections = schema.get("sections", [])
    resolved_values: Dict[str, Any] = {}
    field_meta_by_name: Dict[str, Dict[str, Any]] = {}
    conflicting_fields: List[Dict[str, Any]] = []
    unverified_ocr_hints: Dict[str, Dict[str, Any]] = {}

    for sec in raw_sections:
        for field in sec.get("fields", []):
            fname = field["name"]
            canon_key = _resolve_canonical_key(field)
            compare_mode = (CANONICAL_ATTRIBUTE_MAP.get(canon_key or "", {}) or {}).get("compare_mode", "text")

            candidates: List[Dict[str, Any]] = []

            # 1a. Citizen explicit override (resolves any conflict immediately for this field)
            override_present = False
            if fname in form_overrides:
                ov_clean = clean_scalar(form_overrides[fname])
                if not is_empty_value(ov_clean):
                    ov_norm = normalize_field_value(ov_clean, field)
                    candidates.append({"value": ov_norm, "source_tier": SOURCE_CITIZEN_OVERRIDE, "source_label": SOURCE_LABELS[SOURCE_CITIZEN_OVERRIDE][lang_code]})
                    resolved_conflicts[fname] = _comparison_signature(ov_norm, field, compare_mode)
                    override_present = True

            # 1b. Existing saved draft value
            if fname in existing_form_data:
                ed_clean = clean_scalar(existing_form_data[fname])
                if not is_empty_value(ed_clean):
                    ed_norm = normalize_field_value(ed_clean, field)
                    candidates.append({"value": ed_norm, "source_tier": SOURCE_EXISTING_DRAFT, "source_label": SOURCE_LABELS[SOURCE_EXISTING_DRAFT][lang_code]})

            # 1c. Vault documents (Verified / Citizen-Confirmed vs Unverified OCR hint)
            doc_match, ocr_hint = _extract_document_candidates(vault_docs, canon_key or fname)
            if doc_match:
                d_val, d_tier, d_type = doc_match
                d_norm = normalize_field_value(d_val, field)
                if not is_empty_value(d_norm):
                    candidates.append({"value": d_norm, "source_tier": d_tier, "source_label": f"{SOURCE_LABELS[d_tier][lang_code]} ({d_type})"})
            if ocr_hint:
                hint_val, hint_doc_id = ocr_hint
                unverified_ocr_hints[fname] = {
                    "suggested_value": normalize_field_value(hint_val, field),
                    "source_tier": SOURCE_UNVERIFIED_OCR,
                    "source_label": SOURCE_LABELS[SOURCE_UNVERIFIED_OCR][lang_code],
                    "document_id": hint_doc_id,
                }

            # 1d. Citizen profile (strictly isolated)
            p_val = _extract_profile_source_values(user, profile, canon_key or fname)
            if p_val is not None and not is_empty_value(clean_scalar(p_val)):
                p_norm = normalize_field_value(p_val, field)
                if not is_empty_value(p_norm):
                    candidates.append({"value": p_norm, "source_tier": SOURCE_PROFILE, "source_label": SOURCE_LABELS[SOURCE_PROFILE][lang_code]})

            # 1e. Conversation entity
            c_val = _extract_conversation_entity_value(conversation_entities, canon_key or fname)
            if c_val is not None:
                c_norm = normalize_field_value(c_val, field)
                if not is_empty_value(c_norm):
                    candidates.append({"value": c_norm, "source_tier": SOURCE_CONVERSATION, "source_label": SOURCE_LABELS[SOURCE_CONVERSATION][lang_code]})

            # 1f. Prior saved draft (stable identity/bank/location attributes only)
            pr_val = _extract_prior_draft_value(own_apps, existing_draft.get("id"), canon_key or fname)
            if pr_val is not None:
                pr_norm = normalize_field_value(pr_val, field)
                if not is_empty_value(pr_norm):
                    candidates.append({"value": pr_norm, "source_tier": SOURCE_PRIOR_DRAFT, "source_label": SOURCE_LABELS[SOURCE_PRIOR_DRAFT][lang_code]})

            # Step 2: Conflict Detection across distinct trusted sources
            conflict_obj: Optional[Dict[str, Any]] = None
            selected_val: Any = None
            selected_tier: Optional[str] = None
            selected_label: Optional[str] = None

            if override_present:
                chosen = candidates[0]
                selected_val = chosen["value"]
                selected_tier = chosen["source_tier"]
                selected_label = chosen["source_label"]
            elif candidates:
                # Check if distinct values conflict across independent non-override sources
                sig_groups: Dict[str, List[Dict[str, Any]]] = {}
                for cand in candidates:
                    sig = _comparison_signature(cand["value"], field, compare_mode)
                    if sig:
                        sig_groups.setdefault(sig, []).append(cand)

                # If user already explicitly resolved this field previously, honor that choice unless another new higher-trust conflict arose
                previously_resolved_sig = resolved_conflicts.get(fname)
                if (
                    len(sig_groups) > 1
                    and not (previously_resolved_sig and previously_resolved_sig in sig_groups and len(sig_groups) == 2 and existing_form_data.get(fname))
                ):
                    unique_candidates = [grp[0] for grp in sig_groups.values()]
                    conflict_msg = {
                        "en": f"Conflicting values detected for '{field['label']}'. Please select or enter the accurate value.",
                        "hi": f"'{field['label']}' के लिए परस्पर विरोधी मान मिले हैं। कृपया सही विवरण चुनें या दर्ज करें।",
                        "mr": f"'{field['label']}' साठी परस्परविरोधी माहिती आढळली आहे. कृपया अचूक माहिती निवडा किंवा भरा.",
                    }[lang_code]
                    conflict_obj = {
                        "field": fname,
                        "label": field["label"],
                        "candidates": unique_candidates,
                        "message": conflict_msg,
                    }
                    conflicting_fields.append(conflict_obj)
                    # Never silently pretend conflict is resolved; leave empty for citizen resolution
                    selected_val = ""
                    selected_tier = "conflict_unresolved"
                    selected_label = SOURCE_LABELS[SOURCE_EXISTING_DRAFT][lang_code]
                else:
                    # Pick highest-priority candidate cleanly
                    explicit_override_tiers = dict(existing_draft.get("field_sources") or {})
                    def _prio_key(c: Dict[str, Any]) -> int:
                        try:
                            return TRUSTED_SOURCE_PRIORITY.index(c["source_tier"])
                        except ValueError:
                            return 99

                    ordered = sorted(candidates, key=_prio_key)
                    chosen = ordered[0]
                    # Preserve originating provenance (verified doc / profile) when saved draft merely echoes the same value without an explicit citizen edit
                    if (
                        chosen["source_tier"] == SOURCE_EXISTING_DRAFT
                        and explicit_override_tiers.get(fname) != SOURCE_CITIZEN_OVERRIDE
                    ):
                        chosen_sig = _comparison_signature(chosen["value"], field, compare_mode)
                        origin_match = next(
                            (
                                c for c in ordered[1:]
                                if c["source_tier"] in (SOURCE_VERIFIED_DOC, SOURCE_CONFIRMED_DOC, SOURCE_PROFILE, SOURCE_CONVERSATION)
                                and _comparison_signature(c["value"], field, compare_mode) == chosen_sig
                            ),
                            None,
                        )
                        if origin_match is not None:
                            chosen = origin_match
                    # Prefer strict enum match on select fields when resolving sources
                    strict_val = normalize_field_value(chosen["value"], field, strict_enum=(field.get("type") == "select"))
                    if field.get("type") == "select" and is_empty_value(strict_val) and not override_present:
                        # Option value doesn't match allowed select choices -> leave empty rather than corrupt select state
                        selected_val = None
                    else:
                        selected_val = chosen["value"]
                        selected_tier = chosen["source_tier"]
                        selected_label = chosen["source_label"]

            # 1g. System default ONLY if no conflict, no source value, and no profile_field (never personal defaults)
            if (selected_val is None or selected_val == "") and not conflict_obj and "default" in field and not field.get("profile_field"):
                selected_val = field["default"]
                selected_tier = SOURCE_SYSTEM_DEFAULT
                selected_label = SOURCE_LABELS[SOURCE_SYSTEM_DEFAULT][lang_code]

            resolved_values[fname] = selected_val
            field_meta_by_name[fname] = {
                "canonical_key": canon_key,
                "source_tier": selected_tier,
                "source_label": selected_label,
                "conflict": conflict_obj,
                "unverified_ocr_hint": unverified_ocr_hints.get(fname),
            }

    # Step 3: Second pass for conditional fields, validation, and readiness metrics
    prefilled_sections: List[Dict[str, Any]] = []
    total_fields = 0
    total_mandatory_fields = 0
    filled_mandatory_fields = 0
    auto_populated_fields = 0
    requires_input_fields: List[str] = []
    conditional_fields: List[str] = []
    invalid_fields: List[Dict[str, str]] = []

    for sec in raw_sections:
        sec_fields_out: List[Dict[str, Any]] = []
        for field in sec.get("fields", []):
            total_fields += 1
            fname = field["name"]
            val = resolved_values.get(fname)
            meta = field_meta_by_name[fname]

            is_conditional, eff_required = _evaluate_field_conditional_requirement(
                scheme_code, field, resolved_values
            )
            if is_conditional:
                conditional_fields.append(fname)

            has_conflict = meta["conflict"] is not None
            is_filled = (not is_empty_value(val)) and (not has_conflict)
            val_error = _validate_field_value(val, field, eff_required, lang_code) if not has_conflict else meta["conflict"]["message"]

            if has_conflict:
                requires_input_fields.append(fname)
            elif val_error and not is_empty_value(val):
                invalid_fields.append({"field": fname, "label": field["label"], "message": val_error})

            if eff_required:
                total_mandatory_fields += 1
                if is_filled and not val_error:
                    filled_mandatory_fields += 1

            if is_filled:
                auto_populated_fields += 1
            elif not has_conflict and (eff_required or field.get("required") is False):
                requires_input_fields.append(fname)

            sec_fields_out.append({
                "name": fname,
                "label": field["label"],
                "type": field["type"],
                "required": eff_required,
                "base_required": bool(field.get("required")),
                "conditional": is_conditional,
                "value": val,
                "is_prefilled": is_filled,
                "requires_input": (not is_filled) or has_conflict,
                "source_tier": meta["source_tier"],
                "source_label": meta["source_label"],
                "conflict": meta["conflict"],
                "unverified_ocr_hint": meta["unverified_ocr_hint"],
                "validation_error": val_error,
                "placeholder": field.get("placeholder", ""),
                "options": field.get("options"),
                "pattern": field.get("pattern"),
            })

        prefilled_sections.append({
            "section_id": sec["section_id"],
            "title": sec["title"],
            "fields": sec_fields_out,
        })

    # Clean up form_values for clean persistence (None stays None when unset unless cleaned for REST)
    prefill_percentage = (
        round((filled_mandatory_fields / total_mandatory_fields) * 100, 1)
        if total_mandatory_fields > 0
        else 100.0
    )

    return {
        "form_supported": True,
        "schema_available": True,
        "schema_status": schema.get("schema_nature", "structured_draft"),
        "scheme_code": scheme_code,
        "scheme_title": schema["title"],
        "official_portal": schema.get("official_portal"),
        "total_fields": total_fields,
        "total_mandatory_fields": total_mandatory_fields,
        "filled_mandatory_fields": filled_mandatory_fields,
        "auto_populated_fields": auto_populated_fields,
        "requires_input_count": len([f for f in requires_input_fields]),
        "requires_input_fields": requires_input_fields,
        "conditional_fields": conditional_fields,
        "conflicting_fields": conflicting_fields,
        "invalid_fields": invalid_fields,
        "resolved_conflicts": resolved_conflicts,
        "field_sources": {k: m["source_tier"] for k, m in field_meta_by_name.items() if m.get("source_tier")},
        "readiness_percentage": prefill_percentage,
        "prefill_percentage": prefill_percentage,
        "sections": prefilled_sections,
        "values": resolved_values,
        "can_confirm": (prefill_percentage == 100.0 and not conflicting_fields and not invalid_fields),
    }

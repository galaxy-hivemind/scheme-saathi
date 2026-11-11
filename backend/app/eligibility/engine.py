"""
Deterministic Tri-State Eligibility Evaluation Engine.
Evaluates structured SchemeRuleVersion AST criteria against citizen profiles.
Pure Python, type-safe, non-evaluating, and transparent.
Enforces independent authority checks, strict boolean handling, and criteria completeness.
"""
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.user_profile import UserProfile
from app.eligibility.operators import evaluate_operator, parse_strict_bool, OPERATORS
from app.schemas.eligibility import (
    TriStateStatus,
    EligibilityResultStatus,
    ConditionResult,
    NextQuestion,
    EligibilityResult,
)


FIELD_QUESTIONS: Dict[str, Tuple[str, str, str, Optional[List[str]]]] = {
    "is_landholding_farmer": (
        "Do you or your family own cultivable agricultural land?",
        "क्या आपके या आपके परिवार के नाम पर कृषि योग्य भूमि है?",
        "boolean",
        None,
    ),
    "is_institutional_landholder": (
        "Are you an institutional landholder (e.g., trust, company, or institution)?",
        "क्या आप संस्थागत भूमिधारक (जैसे ट्रस्ट, कंपनी या संस्था) हैं?",
        "boolean",
        None,
    ),
    "is_income_tax_payer": (
        "Did you or any member of your household pay income tax in the last assessment year?",
        "क्या आपने या आपके परिवार के किसी सदस्य ने पिछले निर्धारण वर्ष में आयकर का भुगतान किया था?",
        "boolean",
        None,
    ),
    "is_street_vendor": (
        "Are you engaged in street vending or urban hawking?",
        "क्या आप शहरी क्षेत्र में स्ट्रीट वेंडर या फेरीवाले का कार्य करते हैं?",
        "boolean",
        None,
    ),
    "has_vending_certificate_or_lor": (
        "Do you possess a Certificate of Vending or Letter of Recommendation (LoR) issued by the ULB?",
        "क्या आपके पास नगर निकाय द्वारा जारी वेंडिंग प्रमाण पत्र या सिफारिश पत्र (LoR) है?",
        "boolean",
        None,
    ),
    "owns_pucca_house_in_india": (
        "Do you or any member of your family own a pucca (permanent) house anywhere in India?",
        "क्या आपके या आपके परिवार के किसी सदस्य के पास भारत में कहीं भी पक्का मकान है?",
        "boolean",
        None,
    ),
    "is_urban_resident": (
        "Do you reside in an urban area?",
        "क्या आप शहरी क्षेत्र में निवास करते हैं?",
        "boolean",
        None,
    ),
    "is_rural_resident": (
        "Do you reside in a rural area?",
        "क्या आप ग्रामीण क्षेत्र में निवास करते हैं?",
        "boolean",
        None,
    ),
    "is_secc_deprived_family": (
        "Is your family categorized under the SECC 2011 deprivation criteria or RSBY/PMJAY eligible list?",
        "क्या आपका परिवार SECC 2011 सामाजिक-आर्थिक अभावग्रस्त श्रेणी या पात्र सूची में आता है?",
        "boolean",
        None,
    ),
    "has_existing_lpg_connection": (
        "Does any member of your household already have an active LPG gas connection?",
        "क्या आपके परिवार में पहले से किसी के नाम पर एलपीजी गैस कनेक्शन है?",
        "boolean",
        None,
    ),
    "age": (
        "What is your current age (or date of birth)?",
        "आपकी वर्तमान आयु (या जन्म तिथि) क्या है?",
        "number",
        None,
    ),
    "applicant_age": (
        "What is the applicant's age?",
        "आवेदक की आयु क्या है?",
        "number",
        None,
    ),
    "applicant_gender": (
        "What is the applicant's gender?",
        "आवेदक का लिंग क्या है?",
        "string",
        ["female", "male", "transgender"],
    ),
    "gender": (
        "What is your gender?",
        "आपका लिंग क्या है?",
        "string",
        ["female", "male", "transgender"],
    ),
    "annual_family_income": (
        "What is your total annual family income in Rupees?",
        "आपके परिवार की कुल वार्षिक आय (रुपये में) कितनी है?",
        "number",
        None,
    ),
    "annual_income": (
        "What is your total annual family income in Rupees?",
        "आपके परिवार की कुल वार्षिक आय (रुपये में) कितनी है?",
        "number",
        None,
    ),
    "is_farmer": (
        "Are you an active farmer or cultivator?",
        "क्या आप सक्रिय किसान या काश्तकार हैं?",
        "boolean",
        None,
    ),
    "is_student": (
        "Are you currently an enrolled regular student?",
        "क्या आप वर्तमान में किसी मान्यता प्राप्त संस्थान में नियमित छात्र हैं?",
        "boolean",
        None,
    ),
    "is_artisan": (
        "Are you engaged in traditional craftsmanship or artisan trade?",
        "क्या आप पारंपरिक शिल्प या दस्तकारी कार्य में संलग्न हैं?",
        "boolean",
        None,
    ),
    "land_size_hectares": (
        "How much agricultural land do you own in hectares?",
        "आपके स्वामित्व में कितने हेक्टेयर कृषि भूमि है?",
        "number",
        None,
    ),
    "caste_category": (
        "What is your social / caste category?",
        "आपकी सामाजिक या जाति श्रेणी क्या है?",
        "string",
        ["general", "obc", "sc", "st", "ews"],
    ),
    "has_pucca_house": (
        "Do you own a pucca house?",
        "क्या आपके पास पक्का मकान है?",
        "boolean",
        None,
    ),
    "state": (
        "What is your state of residence?",
        "आपका निवास राज्य कौन सा है?",
        "string",
        None,
    ),
    "is_rural": (
        "Do you reside in a rural area?",
        "क्या आप ग्रामीण क्षेत्र में निवास करते हैं?",
        "boolean",
        None,
    ),
    "is_urban": (
        "Do you reside in an urban area?",
        "क्या आप शहरी क्षेत्र में निवास करते हैं?",
        "boolean",
        None,
    ),
}

# Explicit supported residence categories
VALID_RESIDENCE_TYPES: Set[str] = {"rural", "urban", "semi_urban"}


def _calculate_age(dob: Optional[date]) -> Optional[int]:
    """Calculate age in years from date of birth."""
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def extract_profile_field(
    field_name: str,
    profile: Optional[UserProfile],
    override_data: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, bool]:
    """
    Extract a profile field from direct columns, derived calculations, or profile_data JSONB.
    Returns (value, is_present). If is_present is False or value is None, the field is considered missing.
    """
    # 1. Check override_data first if provided
    if override_data and field_name in override_data:
        val = override_data[field_name]
        return val, val is not None

    if profile is None:
        return None, False

    # 2. Check derived fields
    if field_name in ("age", "applicant_age"):
        if profile.profile_data and field_name in profile.profile_data:
            val = profile.profile_data[field_name]
            if val is not None:
                return val, True
        age = _calculate_age(profile.date_of_birth)
        if age is not None:
            return age, True
        return None, False

    if field_name in ("applicant_gender", "gender"):
        if profile.gender:
            return profile.gender.strip().lower(), True
        if profile.profile_data and "applicant_gender" in profile.profile_data:
            val = profile.profile_data["applicant_gender"]
            if val:
                return str(val).strip().lower(), True
        return None, False

    if field_name in ("is_urban_resident", "is_urban"):
        if profile.residence_type:
            rt = profile.residence_type.strip().lower()
            if rt == "urban":
                return True, True
            elif rt in ("rural", "semi_urban"):
                return False, True
            else:
                # Unknown residence_type must not imply anything; return UNKNOWN
                return None, False
        if profile.profile_data and field_name in profile.profile_data:
            val = profile.profile_data[field_name]
            return val, val is not None
        return None, False

    if field_name in ("is_rural_resident", "is_rural"):
        if profile.residence_type:
            rt = profile.residence_type.strip().lower()
            if rt == "rural":
                return True, True
            elif rt in ("urban", "semi_urban"):
                return False, True
            else:
                return None, False
        if profile.profile_data and field_name in profile.profile_data:
            val = profile.profile_data[field_name]
            return val, val is not None
        return None, False

    if field_name in ("annual_income", "annual_family_income"):
        if profile.annual_family_income is not None:
            return profile.annual_family_income, True
        if profile.profile_data and field_name in profile.profile_data:
            val = profile.profile_data[field_name]
            if val is not None:
                return val, True

    if field_name == "is_farmer":
        if profile.profile_data and "is_farmer" in profile.profile_data:
            return profile.profile_data["is_farmer"], True
        if profile.occupation:
            return profile.occupation.strip().lower() == "farmer", True

    if field_name == "is_student":
        if profile.profile_data and "is_student" in profile.profile_data:
            return profile.profile_data["is_student"], True
        if profile.occupation:
            return profile.occupation.strip().lower() == "student", True

    if field_name == "is_artisan":
        if profile.profile_data and "is_artisan" in profile.profile_data:
            return profile.profile_data["is_artisan"], True
        if profile.occupation:
            return profile.occupation.strip().lower() in ("artisan", "craftsman"), True

    if field_name == "is_landholding_farmer":
        if profile.profile_data and "is_landholding_farmer" in profile.profile_data:
            val = profile.profile_data["is_landholding_farmer"]
            if val is not None:
                return bool(val), True
        if profile.occupation and profile.occupation.strip().lower() == "farmer":
            acres = (profile.profile_data or {}).get("land_holding_acres") or (profile.profile_data or {}).get("land_size_hectares")
            if acres is not None:
                try:
                    return float(acres) > 0, True
                except (ValueError, TypeError):
                    pass
            return True, True
        if profile.occupation and profile.occupation.strip().lower() != "farmer":
            return False, True

    if field_name == "land_size_hectares":
        if profile.profile_data and "land_size_hectares" in profile.profile_data:
            return profile.profile_data["land_size_hectares"], True
        if profile.profile_data and "land_holding_acres" in profile.profile_data:
            acres = profile.profile_data["land_holding_acres"]
            try:
                return round(float(acres) * 0.404686, 2), True
            except (ValueError, TypeError):
                pass

    if field_name == "caste_category":
        if profile.profile_data and "caste_category" in profile.profile_data:
            val = profile.profile_data["caste_category"]
            if val:
                return str(val).strip().lower(), True

    if field_name == "is_income_tax_payer":
        if profile.profile_data and "is_income_tax_payer" in profile.profile_data:
            return profile.profile_data["is_income_tax_payer"], True
        if profile.annual_family_income is not None:
            try:
                return float(profile.annual_family_income) > 300000, True
            except (ValueError, TypeError):
                pass

    if field_name == "is_institutional_landholder":
        if profile.profile_data and "is_institutional_landholder" in profile.profile_data:
            return profile.profile_data["is_institutional_landholder"], True
        return False, True

    # 3. Direct UserProfile model columns
    if hasattr(profile, field_name):
        val = getattr(profile, field_name)
        if val is not None:
            if isinstance(val, str):
                return val.strip().lower(), True
            return val, True

    # 4. JSONB dynamic profile_data dictionary
    if profile.profile_data and field_name in profile.profile_data:
        val = profile.profile_data[field_name]
        if val is not None:
            if isinstance(val, str):
                return val.strip().lower(), True
            return val, True

    return None, False


def evaluate_condition_node(
    condition: Dict[str, Any],
    profile: Optional[UserProfile],
    override_data: Optional[Dict[str, Any]] = None,
) -> ConditionResult:
    """
    Evaluate a single leaf condition node.
    Returns a ConditionResult with PASS, FAIL, or UNKNOWN.
    """
    field = condition.get("field")
    operator = condition.get("operator")
    expected = condition.get("value")

    if not field or not operator:
        raise ValueError(f"Malformed condition node missing 'field' or 'operator': {condition}")

    if operator not in OPERATORS:
        raise ValueError(f"Unsupported eligibility operator '{operator}' in condition: {condition}")

    actual, is_present = extract_profile_field(field, profile, override_data)

    # Special handling for operator 'exists'
    if operator == "exists":
        passed = evaluate_operator("exists", actual if is_present else None, expected)
        status = TriStateStatus.PASS if passed else TriStateStatus.FAIL
        return ConditionResult(
            field=field,
            operator=operator,
            expected_value=expected,
            actual_value=actual,
            status=status,
            passed=passed,
            explanation=f"Requirement {'satisfied' if passed else 'not satisfied'}: {field} existence is {actual is not None} (expected {expected}).",
        )

    # If field is missing from citizen profile -> UNKNOWN
    if not is_present or actual is None:
        return ConditionResult(
            field=field,
            operator=operator,
            expected_value=expected,
            actual_value=None,
            status=TriStateStatus.UNKNOWN,
            passed=None,
            explanation=f"Information required: Field '{field}' is missing from your profile.",
        )

    # Evaluate operator
    try:
        passed = evaluate_operator(operator, actual, expected)
        status = TriStateStatus.PASS if passed else TriStateStatus.FAIL
        explanation = (
            f"Requirement satisfied: {field} ({actual}) {operator} {expected}."
            if passed
            else f"Requirement not satisfied: {field} is {actual}, but expected {operator} {expected}."
        )
        return ConditionResult(
            field=field,
            operator=operator,
            expected_value=expected,
            actual_value=actual,
            status=status,
            passed=passed,
            explanation=explanation,
        )
    except Exception as e:
        return ConditionResult(
            field=field,
            operator=operator,
            expected_value=expected,
            actual_value=actual,
            status=TriStateStatus.UNKNOWN,
            passed=None,
            explanation=f"Evaluation error for '{field}': {str(e)}",
        )


def evaluate_ast(
    node: Dict[str, Any],
    profile: Optional[UserProfile],
    override_data: Optional[Dict[str, Any]] = None,
) -> Tuple[TriStateStatus, List[ConditionResult]]:
    """
    Recursively evaluate an eligibility AST node (supporting nested 'all' and 'any' combinators).
    Rejects malformed or empty combinators with a controlled ValueError.
    Returns (overall_status, list_of_leaf_condition_results).
    """
    if not isinstance(node, dict):
        raise ValueError(f"AST node must be a dictionary, got {type(node).__name__}: {node!r}")

    # 1. Combinator 'all':
    # - Any FAIL -> FAIL
    # - All PASS -> PASS
    # - Otherwise -> UNKNOWN
    if "all" in node:
        children = node["all"]
        if not isinstance(children, list) or len(children) == 0:
            raise ValueError(f"Combinator 'all' must be a non-empty list of condition nodes, got: {children!r}")

        all_leaf_results: List[ConditionResult] = []
        child_statuses: List[TriStateStatus] = []

        for child in children:
            child_status, leaf_results = evaluate_ast(child, profile, override_data)
            child_statuses.append(child_status)
            all_leaf_results.extend(leaf_results)

        if any(s == TriStateStatus.FAIL for s in child_statuses):
            return TriStateStatus.FAIL, all_leaf_results
        if all(s == TriStateStatus.PASS for s in child_statuses):
            return TriStateStatus.PASS, all_leaf_results
        return TriStateStatus.UNKNOWN, all_leaf_results

    # 2. Combinator 'any':
    # - Any PASS -> PASS
    # - All FAIL -> FAIL
    # - Otherwise -> UNKNOWN
    if "any" in node:
        children = node["any"]
        if not isinstance(children, list) or len(children) == 0:
            raise ValueError(f"Combinator 'any' must be a non-empty list of condition nodes, got: {children!r}")

        all_leaf_results = []
        child_statuses = []

        for child in children:
            child_status, leaf_results = evaluate_ast(child, profile, override_data)
            child_statuses.append(child_status)
            all_leaf_results.extend(leaf_results)

        if any(s == TriStateStatus.PASS for s in child_statuses):
            return TriStateStatus.PASS, all_leaf_results
        if all(s == TriStateStatus.FAIL for s in child_statuses):
            return TriStateStatus.FAIL, all_leaf_results
        return TriStateStatus.UNKNOWN, all_leaf_results

    # 3. Leaf condition node:
    if "field" in node and "operator" in node:
        res = evaluate_condition_node(node, profile, override_data)
        return res.status, [res]

    raise ValueError(f"Invalid AST node; must contain non-empty 'all', 'any', or a leaf condition: {node}")


def get_next_question(field_name: str, preferred_language: str = "hi") -> NextQuestion:
    """Generate human-readable question in English and Hindi for a missing field."""
    meta = FIELD_QUESTIONS.get(field_name)
    if meta:
        q_en, q_hi, field_type, options = meta
        return NextQuestion(
            field=field_name,
            question=q_en,
            question_hi=q_hi,
            field_type=field_type,
            options=options,
        )

    # Fallback for dynamic fields
    pretty_name = field_name.replace("_", " ").capitalize()
    return NextQuestion(
        field=field_name,
        question=f"Please provide your {pretty_name} to check your eligibility.",
        question_hi=f"कृपया अपनी पात्रता जांचने के लिए {pretty_name} प्रदान करें।",
        field_type="string",
        options=None,
    )


def evaluate_scheme_eligibility(
    scheme: Scheme,
    profile: Optional[UserProfile],
    override_data: Optional[Dict[str, Any]] = None,
) -> EligibilityResult:
    """
    Evaluate citizen profile against a scheme's active rule version.
    Enforces:
      - Active rule selection respecting effective_from and effective_to.
      - Independent authority enforcement (pending schemes are never authoritative).
      - Criteria completeness (incomplete criteria cannot return eligible=True).
    Returns a complete, transparent EligibilityResult.
    """
    now = datetime.now(timezone.utc)
    today = date.today()
    preferred_lang = profile.preferred_language if profile else "hi"

    # 1. Select the active rule version respecting effective date ranges
    active_rules = [
        r for r in scheme.rule_versions
        if r.is_active
        and (r.effective_from is None or r.effective_from <= today)
        and (r.effective_to is None or r.effective_to >= today)
    ]
    active_rule: Optional[SchemeRuleVersion] = (
        max(active_rules, key=lambda r: r.version) if active_rules else None
    )

    # Handle schemes with no active rule version or null criteria
    if active_rule is None or not active_rule.eligibility_criteria:
        return EligibilityResult(
            scheme_id=scheme.id,
            scheme_code=scheme.scheme_code,
            scheme_name=scheme.name,
            overall_status=TriStateStatus.UNKNOWN,
            result=EligibilityResultStatus.INSUFFICIENT_INFORMATION,
            eligible=None,
            rule_version_id=active_rule.id if active_rule else None,
            rule_version=active_rule.version if active_rule else None,
            is_authoritative=False,
            is_provisional=True,
            criteria_complete=False,
            limitations="No structured eligibility criteria AST is defined for this scheme.",
            matched_conditions=[],
            failed_conditions=[],
            unknown_conditions=[],
            condition_results=[],
            missing_fields=[],
            next_questions=[],
            explanation=(
                "पात्रता निर्धारित नहीं की जा सकी क्योंकि इस योजना के लिए कोई सक्रिय पात्रता नियम परिभाषित नहीं हैं।"
                if preferred_lang == "hi"
                else "Eligibility cannot be determined because no active rules are defined for this scheme."
            ),
            evaluated_at=now,
        )

    criteria = active_rule.eligibility_criteria

    # 2. Independent Authority Enforcement (Blocker C)
    # Authority is determined by scheme status & verified evidence, NOT AST claims alone.
    scheme_is_verified = (
        scheme.scheme_status == "active"
        and scheme.last_verified_at is not None
        and bool(scheme.source_evidence)
        and all(
            isinstance(e, dict) and e.get("verification_status") == "verified"
            for e in scheme.source_evidence
        )
    )
    ast_claims_authoritative = bool(criteria.get("is_authoritative", False))
    # An unverified or pending scheme cannot be elevated to authoritative by its AST
    is_authoritative = scheme_is_verified and ast_claims_authoritative
    is_provisional = not is_authoritative or bool(criteria.get("is_provisional", False))

    # 3. Criteria Completeness (Blocker B)
    # Default to incomplete (False) if missing from metadata
    criteria_complete = bool(criteria.get("criteria_complete", False))
    limitations = criteria.get("limitations")

    # 4. Evaluate AST
    overall_status, leaf_results = evaluate_ast(criteria, profile, override_data)

    matched = [r for r in leaf_results if r.status == TriStateStatus.PASS]
    failed = [r for r in leaf_results if r.status == TriStateStatus.FAIL]
    unknown = [r for r in leaf_results if r.status == TriStateStatus.UNKNOWN]

    # Deduplicate missing fields maintaining order
    missing_fields: List[str] = list(dict.fromkeys(r.field for r in unknown))
    next_questions = [get_next_question(f, preferred_lang) for f in missing_fields]

    # 5. Derive Decision and Enforce Safe Incomplete Criteria Outcomes
    if overall_status == TriStateStatus.PASS:
        if not criteria_complete:
            # Blocker B Requirement: When all represented conditions pass but criteria are incomplete,
            # must NOT return definitive eligible=True. Return UNKNOWN / POTENTIALLY_ELIGIBLE.
            overall_status = TriStateStatus.UNKNOWN
            result = EligibilityResultStatus.POTENTIALLY_ELIGIBLE
            eligible = None
            explanation = (
                f"संभावित रूप से पात्र! आपके द्वारा प्रदान किए गए सभी {len(matched)} जांचे गए मानदंड पूरे होते हैं, "
                f"लेकिन {scheme.name} के सभी वैधानिक मानदंड अभी तक पूरी तरह से मॉडल नहीं किए गए हैं। "
                f"अंतिम पात्रता निर्णय के लिए अतिरिक्त सरकारी सत्यापन आवश्यक है。"
                if preferred_lang == "hi"
                else f"Potentially eligible! All {len(matched)} evaluated criteria were satisfied, but complete statutory "
                f"eligibility rules for {scheme.name} are not fully modelled in the catalogue (limitations: {limitations or 'additional statutory exclusion criteria'})."
            )
        else:
            result = EligibilityResultStatus.ELIGIBLE
            eligible = True
            explanation = (
                f"बधाई हो! आप {scheme.name} के लिए पात्र हैं। आपके द्वारा प्रदान की गई सभी {len(matched)} शर्तें पूरी होती हैं।"
                if preferred_lang == "hi"
                else f"Eligible! You satisfy all {len(matched)} evaluated eligibility criteria for {scheme.name}."
            )
    elif overall_status == TriStateStatus.FAIL:
        # Known mandatory exclusions establish definitive FAIL regardless of criteria completeness
        result = EligibilityResultStatus.NOT_ELIGIBLE
        eligible = False
        failed_fields = ", ".join(f"'{r.field}'" for r in failed)
        explanation = (
            f"आप {scheme.name} के लिए पात्र नहीं हैं। निम्नलिखित मानदंड पूरे नहीं हुए: {failed_fields}।"
            if preferred_lang == "hi"
            else f"Not eligible for {scheme.name}. The following criteria were not satisfied: {failed_fields}."
        )
    else:
        # UNKNOWN due to missing fields
        eligible = None
        if len(matched) > 0 and len(failed) == 0:
            result = EligibilityResultStatus.POTENTIALLY_ELIGIBLE
            explanation = (
                f"संभावित रूप से पात्र! आप {len(matched)} शर्तों को पूरा करते हैं, लेकिन अंतिम पात्रता पुष्टि के लिए {len(missing_fields)} विवरण आवश्यक हैं।"
                if preferred_lang == "hi"
                else f"Potentially eligible! You satisfy {len(matched)} conditions, but {len(missing_fields)} missing profile attributes are required for a final decision."
            )
        else:
            result = EligibilityResultStatus.INSUFFICIENT_INFORMATION
            explanation = (
                f"अधूरी जानकारी: {scheme.name} के लिए आपकी पात्रता जांचने हेतु {len(missing_fields)} आवश्यक विवरण दर्ज करें।"
                if preferred_lang == "hi"
                else f"Insufficient information: {len(missing_fields)} required profile attributes must be provided to determine eligibility for {scheme.name}."
            )

    return EligibilityResult(
        scheme_id=scheme.id,
        scheme_code=scheme.scheme_code,
        scheme_name=scheme.name,
        overall_status=overall_status,
        result=result,
        eligible=eligible,
        rule_version_id=active_rule.id,
        rule_version=active_rule.version,
        is_authoritative=is_authoritative,
        is_provisional=is_provisional,
        criteria_complete=criteria_complete,
        limitations=limitations,
        matched_conditions=matched,
        failed_conditions=failed,
        unknown_conditions=unknown,
        condition_results=leaf_results,
        missing_fields=missing_fields,
        next_questions=next_questions,
        explanation=explanation,
        evaluated_at=now,
    )

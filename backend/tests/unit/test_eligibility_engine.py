"""
Unit tests for Deterministic Tri-State Eligibility Engine and safe operators.
Tests all operators, AST combinators (all/any), boundary conditions, missing fields,
and next-question generation.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import uuid
import pytest

from app.eligibility.operators import (
    evaluate_operator,
    op_equals,
    op_not_equals,
    op_greater_than,
    op_greater_than_or_equal,
    op_less_than,
    op_less_than_or_equal,
    op_in,
    op_not_in,
    op_exists,
    op_contains,
    OPERATORS,
)
from app.eligibility.engine import (
    evaluate_condition_node,
    evaluate_ast,
    extract_profile_field,
    get_next_question,
    evaluate_scheme_eligibility,
    _calculate_age,
)
from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.user_profile import UserProfile
from app.schemas.eligibility import TriStateStatus, EligibilityResultStatus


# ── Operator Unit Tests ──────────────────────────────────────────────────────

def test_operator_equality_and_inequality():
    """Verify type-safe, case-insensitive equality and inequality."""
    assert evaluate_operator("equals", "Urban", "urban") is True
    assert evaluate_operator("equals", "  rural  ", "rural") is True
    assert evaluate_operator("equals", "female", "male") is False
    assert evaluate_operator("equals", 25, 25.0) is True
    assert evaluate_operator("equals", Decimal("100.50"), "100.50") is True
    assert evaluate_operator("equals", True, True) is True
    assert evaluate_operator("equals", True, False) is False
    assert evaluate_operator("equals", None, None) is True
    assert evaluate_operator("equals", None, 5) is False

    assert evaluate_operator("not_equals", "urban", "rural") is True
    assert evaluate_operator("not_equals", "urban", "URBAN") is False
    assert evaluate_operator("not_equals", 20, 25) is True


def test_operator_comparisons_and_boundaries():
    """Verify numeric and date comparisons including strict boundary cases."""
    # Greater than
    assert evaluate_operator("greater_than", 19, 18) is True
    assert evaluate_operator("greater_than", 18, 18) is False
    assert evaluate_operator("greater_than", 17, 18) is False

    # Greater than or equal
    assert evaluate_operator("greater_than_or_equal", 70, 70) is True
    assert evaluate_operator("greater_than_or_equal", 71, 70) is True
    assert evaluate_operator("greater_than_or_equal", 69, 70) is False

    # Less than
    assert evaluate_operator("less_than", 40, 45) is True
    assert evaluate_operator("less_than", 45, 45) is False
    assert evaluate_operator("less_than", 50, 45) is False

    # Less than or equal
    assert evaluate_operator("less_than_or_equal", 40, 40) is True
    assert evaluate_operator("less_than_or_equal", 39, 40) is True
    assert evaluate_operator("less_than_or_equal", 41, 40) is False

    # Date comparison
    d1 = date(2026, 1, 1)
    d2 = date(2025, 1, 1)
    assert evaluate_operator("greater_than", d1, d2) is True
    assert evaluate_operator("less_than", d2, d1) is True


def test_operator_in_not_in_exists_contains():
    """Verify set membership, existence, and containment."""
    # In / Not In
    assert evaluate_operator("in", "agriculture", ["agriculture", "health"]) is True
    assert evaluate_operator("in", "AGRICULTURE", ["agriculture", "health"]) is True
    assert evaluate_operator("in", "education", ["agriculture", "health"]) is False
    assert evaluate_operator("in", 5, [1, 2, 5, 10]) is True
    assert evaluate_operator("in", None, [1, 2]) is False
    assert evaluate_operator("not_in", "education", ["agriculture", "health"]) is True

    # Exists
    assert evaluate_operator("exists", "some_value", True) is True
    assert evaluate_operator("exists", None, True) is False
    assert evaluate_operator("exists", None, False) is True

    # Contains
    assert evaluate_operator("contains", "Pradhan Mantri Awas Yojana", "Awas") is True
    assert evaluate_operator("contains", ["aadhaar", "pan"], "aadhaar") is True
    assert evaluate_operator("contains", ["aadhaar", "pan"], "passport") is False


def test_operator_invalid_and_unsupported_inputs():
    """Verify safe rejection of unsupported operators and incompatible operand types."""
    with pytest.raises(ValueError, match="Unsupported eligibility operator 'execute_sql'"):
        evaluate_operator("execute_sql", 1, 1)

    with pytest.raises(ValueError, match="Cannot convert string 'not-a-number' to numeric"):
        evaluate_operator("greater_than", "not-a-number", 10)

    with pytest.raises(ValueError, match="Operator 'in' requires expected value to be list"):
        evaluate_operator("in", "value", 12345)


# ── Profile Field Extraction & Age Derivation ───────────────────────────────

def test_age_calculation_from_dob():
    """Verify age calculation handles leap years and birthday anniversaries accurately."""
    today = date.today()
    dob_exact_25 = date(today.year - 25, today.month, today.day)
    assert _calculate_age(dob_exact_25) == 25

    # Birthday hasn't occurred yet this year
    if today.month < 12:
        dob_upcoming = date(today.year - 25, 12, 28)
        assert _calculate_age(dob_upcoming) == 24


def test_extract_profile_field_hierarchy():
    """Verify extraction hierarchy: override_data > derived/columns > profile_data."""
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        full_name="Ramesh Kumar",
        gender="male",
        residence_type="urban",
        date_of_birth=date(1990, 5, 15),
        profile_data={
            "is_landholding_farmer": True,
            "custom_attribute": "custom_val",
        },
    )

    # 1. Direct column
    val, present = extract_profile_field("full_name", profile)
    assert present is True
    assert val == "ramesh kumar"

    # 2. Derived age from DOB
    val, present = extract_profile_field("age", profile)
    assert present is True
    assert val == _calculate_age(date(1990, 5, 15))

    # 3. Derived urban residence
    val, present = extract_profile_field("is_urban_resident", profile)
    assert present is True
    assert val is True

    # 4. Profile data JSONB
    val, present = extract_profile_field("is_landholding_farmer", profile)
    assert present is True
    assert val is True

    # 5. Missing field
    val, present = extract_profile_field("non_existent_field", profile)
    assert present is False
    assert val is None

    # 6. Override data taking precedence
    val, present = extract_profile_field(
        "is_landholding_farmer",
        profile,
        override_data={"is_landholding_farmer": False},
    )
    assert present is True
    assert val is False


# ── Condition & AST Evaluation Tests ─────────────────────────────────────────

def test_condition_evaluation_tri_state():
    """Verify leaf condition evaluation returns PASS, FAIL, or UNKNOWN."""
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        gender="female",
        profile_data={"is_landholding_farmer": True},
    )

    # PASS
    cond_pass = {"field": "is_landholding_farmer", "operator": "equals", "value": True}
    res_pass = evaluate_condition_node(cond_pass, profile)
    assert res_pass.status == TriStateStatus.PASS
    assert res_pass.passed is True

    # FAIL
    cond_fail = {"field": "gender", "operator": "equals", "value": "male"}
    res_fail = evaluate_condition_node(cond_fail, profile)
    assert res_fail.status == TriStateStatus.FAIL
    assert res_fail.passed is False

    # UNKNOWN (missing field)
    cond_unk = {"field": "is_income_tax_payer", "operator": "equals", "value": False}
    res_unk = evaluate_condition_node(cond_unk, profile)
    assert res_unk.status == TriStateStatus.UNKNOWN
    assert res_unk.passed is None
    assert "missing from your profile" in res_unk.explanation


def test_ast_all_combinator_tri_state_logic():
    """
    Verify 'all' combinator semantics:
    - Any FAIL -> FAIL (short-circuit property)
    - All PASS -> PASS
    - Otherwise (no FAIL, at least one UNKNOWN) -> UNKNOWN
    """
    profile_all_pass = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={
            "cond1": True,
            "cond2": True,
        },
    )
    ast = {
        "all": [
            {"field": "cond1", "operator": "equals", "value": True},
            {"field": "cond2", "operator": "equals", "value": True},
        ]
    }
    status, leaves = evaluate_ast(ast, profile_all_pass)
    assert status == TriStateStatus.PASS

    # One fails
    profile_one_fail = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"cond1": True, "cond2": False},
    )
    status, leaves = evaluate_ast(ast, profile_one_fail)
    assert status == TriStateStatus.FAIL

    # One missing, other passes -> UNKNOWN
    profile_one_missing = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"cond1": True},
    )
    status, leaves = evaluate_ast(ast, profile_one_missing)
    assert status == TriStateStatus.UNKNOWN

    # One fails, one missing -> FAIL (failing a mandatory condition guarantees non-eligibility!)
    profile_fail_and_missing = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"cond1": False},
    )
    status, leaves = evaluate_ast(ast, profile_fail_and_missing)
    assert status == TriStateStatus.FAIL


def test_ast_any_combinator_tri_state_logic():
    """
    Verify 'any' combinator semantics:
    - Any PASS -> PASS
    - All FAIL -> FAIL
    - Otherwise (no PASS, at least one UNKNOWN) -> UNKNOWN
    """
    ast = {
        "any": [
            {"field": "age", "operator": "greater_than_or_equal", "value": 70},
            {"field": "is_secc_deprived_family", "operator": "equals", "value": True},
        ]
    }

    # One satisfies alternative -> PASS (even if other is unknown)
    profile_pass = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        date_of_birth=date(1950, 1, 1),  # age > 70
        profile_data={},  # is_secc_deprived_family missing
    )
    status, leaves = evaluate_ast(ast, profile_pass)
    assert status == TriStateStatus.PASS

    # Both fail -> FAIL
    profile_fail = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        date_of_birth=date(1990, 1, 1),  # age ~36
        profile_data={"is_secc_deprived_family": False},
    )
    status, leaves = evaluate_ast(ast, profile_fail)
    assert status == TriStateStatus.FAIL

    # Both missing -> UNKNOWN
    profile_unknown = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        date_of_birth=None,
        profile_data={},
    )
    status, leaves = evaluate_ast(ast, profile_unknown)
    assert status == TriStateStatus.UNKNOWN


def test_ast_nested_combinators():
    """Verify nested combinations: all: [any: [c1, c2], c3]."""
    ast = {
        "all": [
            {
                "any": [
                    {"field": "is_sc", "operator": "equals", "value": True},
                    {"field": "is_st", "operator": "equals", "value": True},
                ]
            },
            {"field": "annual_income", "operator": "less_than_or_equal", "value": 250000},
        ]
    }

    # c1=True (any satisfies), income=200000 (c3 satisfies) -> PASS
    p_pass = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"is_sc": True, "annual_income": 200000},
    )
    status, _ = evaluate_ast(ast, p_pass)
    assert status == TriStateStatus.PASS

    # c1=False, c2=False (any fails) -> FAIL regardless of income
    p_fail = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"is_sc": False, "is_st": False, "annual_income": 200000},
    )
    status, _ = evaluate_ast(ast, p_fail)
    assert status == TriStateStatus.FAIL


def test_next_question_localization():
    """Verify question generation in English and Hindi for missing fields."""
    q_farmer = get_next_question("is_landholding_farmer", preferred_language="hi")
    assert "कृषि योग्य भूमि" in q_farmer.question_hi
    assert "agricultural land" in q_farmer.question
    assert q_farmer.field_type == "boolean"

    q_age = get_next_question("age", preferred_language="en")
    assert "What is your current age" in q_age.question
    assert q_age.field_type == "number"


# ── Scheme-Level Integration Evaluation Tests ───────────────────────────────

def _create_mock_scheme(
    scheme_code: str,
    name: str,
    criteria: dict,
    is_authoritative: bool = True,
    is_provisional: bool = False,
) -> Scheme:
    """Helper to instantiate mock Scheme and SchemeRuleVersion."""
    s_id = uuid.uuid4()
    scheme = Scheme(
        id=s_id,
        scheme_code=scheme_code,
        name=name,
        description=f"Description for {name}",
        ministry="Ministry of Example",
        category="agriculture",
        geographic_scope="central",
        target_beneficiaries=["farmers"],
        benefits="Sample financial benefit",
        source_url="https://example.gov.in/guidelines.pdf",
        scheme_status="active",
        last_retrieved_at=datetime.now(timezone.utc),
        last_verified_at=datetime.now(timezone.utc),
        source_evidence=[],
    )
    criteria_copy = dict(criteria)
    criteria_copy["is_authoritative"] = is_authoritative
    criteria_copy["is_provisional"] = is_provisional

    rule_ver = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=s_id,
        version=1,
        is_active=True,
        effective_from=datetime.now(timezone.utc),
        eligibility_criteria=criteria_copy,
        source_url="https://example.gov.in/guidelines.pdf",
    )
    scheme.rule_versions = [rule_ver]
    return scheme


def test_evaluate_pm_kisan_scenarios():
    """
    Test PM-KISAN evaluation against verified criteria:
    all: [is_landholding_farmer==True, is_institutional_landholder==False, is_income_tax_payer==False]
    """
    criteria = {
        "is_authoritative": True,
        "is_provisional": False,
        "limitations": "Core statutory eligibility conditions verified from Operational Guidelines.",
        "all": [
            {"field": "is_landholding_farmer", "operator": "equals", "value": True},
            {"field": "is_institutional_landholder", "operator": "equals", "value": False},
            {"field": "is_income_tax_payer", "operator": "equals", "value": False},
        ],
    }
    scheme = _create_mock_scheme("PM-KISAN", "PM Kisan Samman Nidhi", criteria)

    # Scenario 1: Fully Eligible Farmer
    eligible_profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={
            "is_landholding_farmer": True,
            "is_institutional_landholder": False,
            "is_income_tax_payer": False,
        },
    )
    res = evaluate_scheme_eligibility(scheme, eligible_profile)
    assert res.overall_status == TriStateStatus.PASS
    assert res.result == EligibilityResultStatus.ELIGIBLE
    assert res.eligible is True
    assert len(res.matched_conditions) == 3
    assert len(res.failed_conditions) == 0
    assert len(res.unknown_conditions) == 0
    assert res.is_authoritative is True

    # Scenario 2: Income Tax Payer Excluded
    taxpayer_profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={
            "is_landholding_farmer": True,
            "is_institutional_landholder": False,
            "is_income_tax_payer": True,
        },
    )
    res_tax = evaluate_scheme_eligibility(scheme, taxpayer_profile)
    assert res_tax.overall_status == TriStateStatus.FAIL
    assert res_tax.result == EligibilityResultStatus.NOT_ELIGIBLE
    assert res_tax.eligible is False
    assert len(res_tax.failed_conditions) == 1
    assert res_tax.failed_conditions[0].field == "is_income_tax_payer"

    # Scenario 3: Missing landholder information -> UNKNOWN with next question
    incomplete_profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"is_income_tax_payer": False},
    )
    res_unk = evaluate_scheme_eligibility(scheme, incomplete_profile)
    assert res_unk.overall_status == TriStateStatus.UNKNOWN
    assert res_unk.result == EligibilityResultStatus.POTENTIALLY_ELIGIBLE
    assert res_unk.eligible is None
    assert "is_landholding_farmer" in res_unk.missing_fields
    assert len(res_unk.next_questions) >= 1
    assert res_unk.next_questions[0].field == "is_landholding_farmer"


def test_all_seven_canonical_schemes_evaluation():
    """Verify that all 7 canonical seed schemes in backend/data/schemes evaluate accurately."""
    import json
    from pathlib import Path

    schemes_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
    seed_files = list(schemes_dir.glob("*.json"))
    assert len(seed_files) == 7

    for f in seed_files:
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        scheme_code = data["scheme_code"]
        criteria = data.get("eligibility_criteria")
        if not criteria:
            continue

        mock_scheme = _create_mock_scheme(
            scheme_code=scheme_code,
            name=data["name"],
            criteria=criteria,
            is_authoritative=criteria.get("is_authoritative", True),
            is_provisional=criteria.get("is_provisional", False),
        )

        # 1. Blank profile should produce UNKNOWN with next questions
        blank_profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
        res_blank = evaluate_scheme_eligibility(mock_scheme, blank_profile)
        assert res_blank.overall_status == TriStateStatus.UNKNOWN
        assert len(res_blank.missing_fields) > 0
        assert len(res_blank.next_questions) == len(res_blank.missing_fields)

        # 2. Scheme-specific PASS and FAIL validations
        if scheme_code == "AB-PMJAY":
            # Senior 70+ satisfies ANY branch immediately -> PASS
            senior_profile = UserProfile(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                date_of_birth=date(1950, 1, 1),
            )
            res_senior = evaluate_scheme_eligibility(mock_scheme, senior_profile)
            assert res_senior.overall_status == TriStateStatus.PASS
            assert res_senior.eligible is True

        elif scheme_code == "PM-SVANIDHI":
            # Urban vendor with LoR -> PASS
            vendor_profile = UserProfile(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                profile_data={"is_street_vendor": True, "has_vending_certificate_or_lor": True},
            )
            res_vendor = evaluate_scheme_eligibility(mock_scheme, vendor_profile)
            assert res_vendor.overall_status == TriStateStatus.PASS

            # Non-vendor -> FAIL
            non_vendor = UserProfile(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                profile_data={"is_street_vendor": False, "has_vending_certificate_or_lor": False},
            )
            res_non = evaluate_scheme_eligibility(mock_scheme, non_vendor)
            assert res_non.overall_status == TriStateStatus.FAIL

        elif scheme_code == "PMAY-U":
            # Pucca house owner -> FAIL
            homeowner = UserProfile(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                profile_data={"owns_pucca_house_in_india": True, "is_urban_resident": True},
            )
            res_home = evaluate_scheme_eligibility(mock_scheme, homeowner)
            assert res_home.overall_status == TriStateStatus.FAIL

        elif scheme_code == "PMUY":
            # Male applicant -> FAIL
            male_applicant = UserProfile(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                gender="male",
                date_of_birth=date(1995, 1, 1),
                profile_data={"has_existing_lpg_connection": False},
            )
            res_male = evaluate_scheme_eligibility(mock_scheme, male_applicant)
            assert res_male.overall_status == TriStateStatus.FAIL


def test_evaluate_scheme_without_rule_version():
    """Verify evaluation returns UNKNOWN with non-authoritative flag when no active rules exist."""
    scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="NO-RULES",
        name="Scheme Without Rules",
        description="No rules attached",
        ministry="Ministry of Tests",
        category="health",
        geographic_scope="central",
        target_beneficiaries=["all"],
        benefits="Test benefits",
        source_url="https://test.gov.in",
        scheme_status="active",
        last_retrieved_at=datetime.now(timezone.utc),
        source_evidence=[],
    )
    scheme.rule_versions = []  # No rule version

    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    res = evaluate_scheme_eligibility(scheme, profile)
    assert res.overall_status == TriStateStatus.UNKNOWN
    assert res.result == EligibilityResultStatus.INSUFFICIENT_INFORMATION
    assert res.eligible is None
    assert res.is_authoritative is False
    assert res.is_provisional is True
    assert "No structured eligibility criteria AST" in res.limitations

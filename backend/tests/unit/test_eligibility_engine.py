"""
Unit tests for Deterministic Tri-State Eligibility Engine and safe operators.
Tests all operators, strict boolean equality, AST combinators (all/any), boundary conditions,
missing fields, criteria completeness, independent authority enforcement, and next-question generation.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import pytest

from app.eligibility.operators import (
    evaluate_operator,
    parse_strict_bool,
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


# ── Operator Unit Tests & Blocker A Strict Boolean Tests ─────────────────────

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


def test_strict_boolean_operator_validation():
    """
    Blocker A: Verify strict boolean handling.
    - Matches explicit allowed string representations: true/false, 1/0, yes/no.
    - Rejects invalid strings with ValueError (does not silently convert to False).
    - Rejects empty strings, arbitrary integers, and incompatible types.
    - Ensures not_equals enforces identical strict comparison semantics.
    """
    # 1. Allowed representations
    assert evaluate_operator("equals", "true", True) is True
    assert evaluate_operator("equals", "TRUE  ", True) is True
    assert evaluate_operator("equals", "1", True) is True
    assert evaluate_operator("equals", "yes", True) is True

    assert evaluate_operator("equals", "false", False) is True
    assert evaluate_operator("equals", "  FALSE", False) is True
    assert evaluate_operator("equals", "0", False) is True
    assert evaluate_operator("equals", "no", False) is True

    # 2. Strict rejection of invalid strings
    with pytest.raises(ValueError, match="Invalid boolean string value: 'invalid-value'"):
        evaluate_operator("equals", "invalid-value", False)

    with pytest.raises(ValueError, match="Invalid boolean string value: 'maybe'"):
        evaluate_operator("equals", "maybe", True)

    with pytest.raises(ValueError, match="Invalid boolean string value: ''"):
        evaluate_operator("equals", "", False)

    # 3. Numeric values must not be implicitly interpreted as booleans
    with pytest.raises(ValueError, match="Cannot interpret value of type 'int' as a boolean"):
        evaluate_operator("equals", 1, True)

    with pytest.raises(ValueError, match="Cannot interpret value of type 'int' as a boolean"):
        evaluate_operator("equals", 0, False)

    with pytest.raises(ValueError, match="Cannot interpret value of type 'int' as a boolean"):
        evaluate_operator("equals", 2, True)

    # 4. not_equals preserves strict boolean semantics
    assert evaluate_operator("not_equals", "true", False) is True
    assert evaluate_operator("not_equals", "false", True) is True
    with pytest.raises(ValueError, match="Invalid boolean string value: 'invalid-value'"):
        evaluate_operator("not_equals", "invalid-value", False)


def test_strict_exists_operator():
    """
    Verify op_exists treats None, empty strings, and whitespace-only strings as nonexistent,
    while preserving strict validation of the expected boolean.
    """
    # 1. Nonexistent values: None, empty string, whitespace-only string
    for nonexistent_val in [None, "", "   ", "\t\r\n  ", " \n "]:
        assert evaluate_operator("exists", nonexistent_val, True) is False
        assert evaluate_operator("exists", nonexistent_val, False) is True
        assert evaluate_operator("exists", nonexistent_val, "true") is False
        assert evaluate_operator("exists", nonexistent_val, "false") is True
        assert evaluate_operator("exists", nonexistent_val, "1") is False
        assert evaluate_operator("exists", nonexistent_val, "0") is True

    # 2. Existent values: non-empty strings, numbers (including 0), booleans (including False)
    for existent_val in ["valid_data", " a ", 0, 100, False, True, ["item"]]:
        assert evaluate_operator("exists", existent_val, True) is True
        assert evaluate_operator("exists", existent_val, False) is False
        assert evaluate_operator("exists", existent_val, "true") is True
        assert evaluate_operator("exists", existent_val, "false") is False

    # 3. Strict validation of expected boolean
    with pytest.raises(ValueError, match="Invalid boolean string value: 'not-a-bool'"):
        evaluate_operator("exists", "data", "not-a-bool")

    with pytest.raises(ValueError, match="Invalid boolean string value: 'not-a-bool'"):
        evaluate_operator("exists", "", "not-a-bool")

    with pytest.raises(ValueError, match="Cannot interpret value of type 'int' as a boolean"):
        evaluate_operator("exists", "data", 1)

    with pytest.raises(ValueError, match="Cannot interpret value of type 'int' as a boolean"):
        evaluate_operator("exists", "", 0)

    # 4. Leaf condition node evaluation with whitespace/empty string
    empty_cond_true = {"field": "vending_cert", "operator": "exists", "value": True}
    res_empty_true = evaluate_condition_node(
        empty_cond_true,
        None,
        override_data={"vending_cert": "   "},
    )
    assert res_empty_true.status == TriStateStatus.FAIL
    assert res_empty_true.passed is False
    assert "existence is False" in res_empty_true.explanation

    empty_cond_false = {"field": "vending_cert", "operator": "exists", "value": False}
    res_empty_false = evaluate_condition_node(
        empty_cond_false,
        None,
        override_data={"vending_cert": ""},
    )
    assert res_empty_false.status == TriStateStatus.PASS
    assert res_empty_false.passed is True
    assert "existence is False" in res_empty_false.explanation


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


def test_unknown_residence_type_returns_unknown():
    """Secondary Fix: Unknown residence_type must not imply anything; returns UNKNOWN."""
    profile_unknown_residence = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        residence_type="coastal_zone",  # Invalid / unknown
    )
    val_u, pres_u = extract_profile_field("is_urban_resident", profile_unknown_residence)
    assert pres_u is False
    assert val_u is None

    val_r, pres_r = extract_profile_field("is_rural_resident", profile_unknown_residence)
    assert pres_r is False
    assert val_r is None


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
        date_of_birth=date(1950, 1, 1),
        profile_data={},
    )
    status, leaves = evaluate_ast(ast, profile_pass)
    assert status == TriStateStatus.PASS

    # Both fail -> FAIL
    profile_fail = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        date_of_birth=date(1990, 1, 1),
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


def test_empty_or_malformed_combinators_rejected():
    """Secondary Fix: Reject malformed or empty combinators with a controlled ValueError."""
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4())

    with pytest.raises(ValueError, match="Combinator 'all' must be a non-empty list"):
        evaluate_ast({"all": []}, profile)

    with pytest.raises(ValueError, match="Combinator 'any' must be a non-empty list"):
        evaluate_ast({"any": []}, profile)

    with pytest.raises(ValueError, match="Combinator 'all' must be a non-empty list"):
        evaluate_ast({"all": "invalid_children"}, profile)

    with pytest.raises(ValueError, match="AST node must be a dictionary"):
        evaluate_ast("not_a_dict", profile)


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


# ── Scheme-Level Evaluation & Blocker B / C Regression Tests ────────────────

def _create_mock_scheme(
    scheme_code: str,
    name: str,
    criteria: dict,
    is_authoritative: Optional[bool] = None,
    is_provisional: Optional[bool] = None,
    scheme_status: str = "active",
    effective_from: Optional[date] = None,
    effective_to: Optional[date] = None,
) -> Scheme:
    """Helper to instantiate mock Scheme and SchemeRuleVersion with verified evidence."""
    s_id = uuid.uuid4()
    evidence = [
        {
            "claim": "operational_status",
            "source_type": "guideline",
            "source_url": "https://example.gov.in/guidelines.pdf",
            "issuing_authority": "Ministry of Example",
            "retrieved_at": "2026-11-10T10:00:00Z",
            "citation": "Clause 1",
            "verification_status": "verified",
            "verified_at": "2026-11-10T12:00:00Z",
        }
    ] if scheme_status == "active" else []

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
        scheme_status=scheme_status,
        last_retrieved_at=datetime.now(timezone.utc),
        last_verified_at=datetime.now(timezone.utc) if scheme_status == "active" else None,
        source_evidence=evidence,
    )
    criteria_copy = dict(criteria)
    if is_authoritative is not None:
        criteria_copy["is_authoritative"] = is_authoritative
    elif "is_authoritative" not in criteria_copy:
        criteria_copy["is_authoritative"] = True

    if is_provisional is not None:
        criteria_copy["is_provisional"] = is_provisional
    elif "is_provisional" not in criteria_copy:
        criteria_copy["is_provisional"] = False

    rule_ver = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=s_id,
        version=1,
        is_active=True,
        effective_from=effective_from or date.today(),
        effective_to=effective_to,
        eligibility_criteria=criteria_copy,
        source_url="https://example.gov.in/guidelines.pdf",
    )
    scheme.rule_versions = [rule_ver]
    return scheme


def test_blocker_b_incomplete_criteria_all_conditions_pass_returns_unknown():
    """
    Blocker B: When all represented conditions pass but criteria_complete=False:
    - Must return UNKNOWN (indeterminate decision).
    - Must return eligible=None (never definitive eligible=True).
    - Preserves matched_conditions.
    - Result is 'potentially_eligible'.
    - Explanation clearly highlights incomplete criteria.
    """
    criteria = {
        "is_authoritative": True,
        "is_provisional": False,
        "criteria_complete": False,  # Incomplete model
        "limitations": "Detailed exclusion categories not fully modelled.",
        "all": [
            {"field": "is_landholding_farmer", "operator": "equals", "value": True},
            {"field": "is_institutional_landholder", "operator": "equals", "value": False},
        ],
    }
    scheme = _create_mock_scheme("PM-KISAN", "PM Kisan Samman Nidhi", criteria)

    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={
            "is_landholding_farmer": True,
            "is_institutional_landholder": False,
        },
    )
    res = evaluate_scheme_eligibility(scheme, profile)

    assert res.overall_status == TriStateStatus.UNKNOWN
    assert res.result == EligibilityResultStatus.POTENTIALLY_ELIGIBLE
    assert res.eligible is None
    assert res.criteria_complete is False
    assert len(res.matched_conditions) == 2
    assert len(res.failed_conditions) == 0
    assert "not fully modelled in the catalogue" in res.explanation


def test_blocker_b_incomplete_criteria_with_exclusion_returns_fail():
    """
    Blocker B: Known mandatory exclusion still establishes FAIL regardless
    of criteria completeness.
    """
    criteria = {
        "is_authoritative": True,
        "is_provisional": False,
        "criteria_complete": False,  # Incomplete
        "all": [
            {"field": "is_landholding_farmer", "operator": "equals", "value": True},
            {"field": "is_income_tax_payer", "operator": "equals", "value": False},
        ],
    }
    scheme = _create_mock_scheme("PM-KISAN", "PM Kisan Samman Nidhi", criteria)

    # Taxpayer fails mandatory condition
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={"is_landholding_farmer": True, "is_income_tax_payer": True},
    )
    res = evaluate_scheme_eligibility(scheme, profile)

    assert res.overall_status == TriStateStatus.FAIL
    assert res.result == EligibilityResultStatus.NOT_ELIGIBLE
    assert res.eligible is False
    assert len(res.failed_conditions) == 1
    assert res.failed_conditions[0].field == "is_income_tax_payer"


def test_blocker_b_missing_completeness_metadata_defaults_to_incomplete():
    """
    Blocker B: Missing completeness metadata defaults to False, not complete.
    """
    criteria = {
        "is_authoritative": True,
        "is_provisional": False,
        # 'criteria_complete' omitted
        "all": [
            {"field": "is_farmer", "operator": "equals", "value": True},
        ],
    }
    scheme = _create_mock_scheme("TEST-SCHEME", "Test Scheme", criteria)
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), profile_data={"is_farmer": True})

    res = evaluate_scheme_eligibility(scheme, profile)
    assert res.criteria_complete is False
    assert res.overall_status == TriStateStatus.UNKNOWN
    assert res.eligible is None


def test_blocker_b_complete_criteria_returns_eligible():
    """
    Blocker B: A scheme with criteria_complete=True returns definitive eligible=True
    when all conditions pass.
    """
    criteria = {
        "is_authoritative": True,
        "is_provisional": False,
        "criteria_complete": True,  # Explicitly complete
        "all": [
            {"field": "is_landholding_farmer", "operator": "equals", "value": True},
            {"field": "is_institutional_landholder", "operator": "equals", "value": False},
            {"field": "is_income_tax_payer", "operator": "equals", "value": False},
        ],
    }
    scheme = _create_mock_scheme("PM-KISAN", "PM Kisan Samman Nidhi", criteria)
    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        profile_data={
            "is_landholding_farmer": True,
            "is_institutional_landholder": False,
            "is_income_tax_payer": False,
        },
    )
    res = evaluate_scheme_eligibility(scheme, profile)

    assert res.overall_status == TriStateStatus.PASS
    assert res.result == EligibilityResultStatus.ELIGIBLE
    assert res.eligible is True
    assert res.criteria_complete is True


def test_blocker_c_pending_scheme_cannot_become_authoritative():
    """
    Blocker C: A pending_verification scheme must always return is_authoritative=False,
    even if its AST explicitly claims is_authoritative=True.
    """
    criteria = {
        "is_authoritative": True,  # AST erroneously claims authoritative
        "is_provisional": False,
        "criteria_complete": True,
        "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
    }
    # Scheme is pending_verification
    scheme = _create_mock_scheme(
        "PMUY",
        "PM Ujjwala Yojana",
        criteria,
        scheme_status="pending_verification",
    )
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), date_of_birth=date(1995, 1, 1))

    res = evaluate_scheme_eligibility(scheme, profile)
    # Authority cannot be elevated by AST
    assert res.is_authoritative is False
    assert res.is_provisional is True


def test_metadata_strict_boolean_type_safety():
    """
    Verify criteria_complete and is_authoritative are validated strictly using type(v) is bool.
    - String "false" as metadata must evaluate to False (never True via bool()).
    - Malformed metadata ("true", 1, 0, None, lists, dicts) must default to False.
    - Malformed is_authoritative must never elevate authority.
    """
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), date_of_birth=date(1995, 1, 1))

    # 1. "false" string as criteria_complete metadata
    criteria_false_str = {
        "is_authoritative": True,
        "is_provisional": False,
        "criteria_complete": "false",  # String "false"
        "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
    }
    scheme = _create_mock_scheme("SCHEME-1", "Scheme 1", criteria_false_str, scheme_status="active")

    res = evaluate_scheme_eligibility(scheme, profile)
    # Must strictly be False, NOT True via bool("false")
    assert res.criteria_complete is False
    assert res.overall_status == TriStateStatus.UNKNOWN
    assert res.result == EligibilityResultStatus.POTENTIALLY_ELIGIBLE
    assert res.eligible is None

    # 2. Malformed criteria_complete values must all default to False
    malformed_criteria_complete_values = ["true", "True", "1", 1, 0, None, ["true"], {"complete": True}]
    for bad_val in malformed_criteria_complete_values:
        crit = {
            "is_authoritative": True,
            "is_provisional": False,
            "criteria_complete": bad_val,
            "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
        }
        sch = _create_mock_scheme("SCHEME-BAD", "Scheme Bad", crit, scheme_status="active")
        r = evaluate_scheme_eligibility(sch, profile)
        assert r.criteria_complete is False, f"Expected False for {bad_val!r}, got {r.criteria_complete}"
        assert r.eligible is None

    # 3. "false" string as is_authoritative metadata
    criteria_auth_false_str = {
        "is_authoritative": "false",  # String "false"
        "is_provisional": False,
        "criteria_complete": True,
        "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
    }
    sch_auth = _create_mock_scheme("SCHEME-AUTH", "Scheme Auth", criteria_auth_false_str, scheme_status="active")
    r_auth = evaluate_scheme_eligibility(sch_auth, profile)
    assert r_auth.is_authoritative is False

    # 4. Malformed is_authoritative values must never elevate authority
    malformed_auth_values = ["true", "True", "1", "yes", 1, 0, None, ["true"], {"auth": True}]
    for bad_auth in malformed_auth_values:
        crit = {
            "is_authoritative": bad_auth,
            "is_provisional": False,
            "criteria_complete": True,
            "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
        }
        sch_bad_auth = _create_mock_scheme("SCHEME-BAD-AUTH", "Scheme Bad Auth", crit, scheme_status="active")
        r_bad_auth = evaluate_scheme_eligibility(sch_bad_auth, profile)
        assert r_bad_auth.is_authoritative is False, f"Expected False for bad is_authoritative {bad_auth!r}, got {r_bad_auth.is_authoritative}"

    # 5. Genuine booleans work as expected
    crit_valid = {
        "is_authoritative": True,
        "is_provisional": False,
        "criteria_complete": True,
        "all": [{"field": "age", "operator": "greater_than_or_equal", "value": 18}],
    }
    sch_valid = _create_mock_scheme("SCHEME-VALID", "Scheme Valid", crit_valid, scheme_status="active")
    r_valid = evaluate_scheme_eligibility(sch_valid, profile)
    assert r_valid.is_authoritative is True
    assert r_valid.criteria_complete is True
    assert r_valid.eligible is True


def test_rule_version_effective_dates_filtering():
    """
    Secondary Fix: Confirm active rule selection respects effective_from and effective_to.
    """
    today = date.today()
    criteria = {
        "criteria_complete": True,
        "all": [{"field": "age", "operator": "greater_than", "value": 18}],
    }

    # 1. Rule starting tomorrow (future) must not be selected
    scheme_future = _create_mock_scheme(
        "FUTURE-SCHEME",
        "Future Scheme",
        criteria,
        effective_from=today + timedelta(days=1),
    )
    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4(), date_of_birth=date(1990, 1, 1))
    res_future = evaluate_scheme_eligibility(scheme_future, profile)
    assert res_future.overall_status == TriStateStatus.UNKNOWN
    assert "no active rules are defined" in res_future.explanation

    # 2. Rule expired yesterday must not be selected
    scheme_expired = _create_mock_scheme(
        "EXPIRED-SCHEME",
        "Expired Scheme",
        criteria,
        effective_from=today - timedelta(days=30),
        effective_to=today - timedelta(days=1),
    )
    res_expired = evaluate_scheme_eligibility(scheme_expired, profile)
    assert res_expired.overall_status == TriStateStatus.UNKNOWN
    assert "no active rules are defined" in res_expired.explanation


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
    scheme.rule_versions = []

    profile = UserProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    res = evaluate_scheme_eligibility(scheme, profile)
    assert res.overall_status == TriStateStatus.UNKNOWN
    assert res.result == EligibilityResultStatus.INSUFFICIENT_INFORMATION
    assert res.eligible is None
    assert res.is_authoritative is False
    assert res.is_provisional is True
    assert "No structured eligibility criteria AST" in res.limitations

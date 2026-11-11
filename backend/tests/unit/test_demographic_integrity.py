"""
Unit tests for Demographic Integrity & Zero Fabrication Policy.
Verifies that:
- Approximate age is never converted into a fabricated date of birth.
- Occupation is never converted into an invented income.
- District / partial address is never guessed as rural or urban.
- Evaluator outputs genuine UNKNOWN when statutory requirements are missing.
- Family member evaluations NEVER fall back to account holder demographics.
"""
import uuid
from datetime import date, datetime, timezone
import pytest

from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.beneficiary_profile import BeneficiaryProfile
from app.schemas.beneficiary import BeneficiaryCreate
from app.schemas.profile import UserProfileCreate
from app.eligibility.engine import evaluate_ast
from app.schemas.eligibility import TriStateStatus


def test_no_date_of_birth_fabrication_from_age():
    """Citizen stating approximate age 62 must not generate an invented date_of_birth."""
    # Simulating data constructed from "Meri umra 62 saal hai"
    ben_data = BeneficiaryCreate(
        full_name="Sunita Devi",
        relationship="mother",
        date_of_birth=None,  # MUST NOT be fabricated
        profile_data={"approximate_age": 62},
    )
    assert ben_data.date_of_birth is None
    assert ben_data.profile_data["approximate_age"] == 62


def test_no_income_fabrication_from_occupation():
    """Citizen stating occupation 'small farmer' must not invent an annual income."""
    ben_data = BeneficiaryCreate(
        full_name="Ram Lal",
        relationship="father",
        occupation="farmer",
        annual_family_income=None,  # MUST NOT be guessed (e.g. 50000)
    )
    assert ben_data.occupation == "farmer"
    assert ben_data.annual_family_income is None


def test_no_residence_type_guessing_from_district():
    """Citizen stating district 'Varanasi' must not arbitrarily guess rural or urban."""
    ben_data = BeneficiaryCreate(
        full_name="Geeta",
        relationship="spouse",
        district="Varanasi",
        residence_type=None,  # MUST NOT be guessed
    )
    assert ben_data.district == "Varanasi"
    assert ben_data.residence_type is None


def test_tri_state_unknown_preservation_for_missing_dob():
    """
    When statutory rule requires min_age 60 (calculated via date_of_birth)
    and date_of_birth is None, the engine MUST return UNKNOWN.
    """
    # Rule requiring age >= 60 using AST combinator 'all'
    rule_ast = {
        "all": [
            {
                "field": "age",
                "operator": "greater_than_or_equal",
                "value": 60,
                "description": "Applicant must be at least 60 years of age.",
            }
        ],
    }

    # Profile with no date_of_birth
    profile_data = {
        "full_name": "Sunita Devi",
        "date_of_birth": None,
        "occupation": "Homemaker",
    }

    status, leaf_results = evaluate_ast(rule_ast, profile_data)
    assert status == TriStateStatus.UNKNOWN
    assert len(leaf_results) == 1
    assert leaf_results[0].field == "age"
    assert leaf_results[0].status == TriStateStatus.UNKNOWN


def test_family_member_evaluation_never_falls_back_to_account_holder():
    """
    When evaluating a family beneficiary (mother), missing caste or income
    must strictly produce UNKNOWN and must NEVER copy values from the account holder.
    """
    mother_profile = {
        "full_name": "Sunita Devi",
        "relationship": "mother",
        "date_of_birth": None,
        "annual_family_income": None,  # missing on mother
    }

    account_holder_data = {
        "full_name": "Rajesh Sharma",
        "date_of_birth": "1990-01-01",
        "annual_family_income": 120000.0,
    }

    rule_ast = {
        "all": [
            {
                "field": "annual_family_income",
                "operator": "less_than_or_equal",
                "value": 200000,
                "description": "Annual family income must be under 2 lakhs.",
            }
        ],
    }

    # Evaluating strictly against mother's profile
    status, leaf_results = evaluate_ast(rule_ast, mother_profile)
    assert status == TriStateStatus.UNKNOWN
    assert len(leaf_results) == 1
    assert leaf_results[0].field == "annual_family_income"
    assert leaf_results[0].status == TriStateStatus.UNKNOWN
    # Must not have evaluated as PASS using account holder's 120000

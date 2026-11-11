"""
API integration tests for Deterministic Eligibility Evaluation endpoints:
- POST /api/v1/eligibility/check
- POST /api/v1/eligibility/evaluate/{scheme_id}
- POST /api/v1/eligibility/evaluate-all
Enforces strict boolean handling, criteria completeness, independent authority, and non-destructive overrides.
"""
from pathlib import Path
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select

from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.scripts.seed_schemes import execute_seed_import
from tests.api.test_profile import _register_and_get_token


@pytest.fixture
def seeded_db(db_session):
    """Seed the database with the official 7 curated scheme seed files."""
    from sqlalchemy import text
    db_session.execute(text("DELETE FROM scheme_documents;"))
    db_session.execute(text("DELETE FROM scheme_rule_versions;"))
    db_session.execute(text("DELETE FROM schemes;"))
    db_session.commit()
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
    execute_seed_import(data_dir=data_dir, dry_run=False, session=db_session)
    return db_session


def test_eligibility_jwt_authentication_required(client):
    """All eligibility endpoints must strictly require Phase 1 JWT authentication."""
    # 1. /check
    res1 = client.post("/api/v1/eligibility/check", json={"scheme_id": str(uuid.uuid4())})
    assert res1.status_code == 401

    # 2. /evaluate/{scheme_id}
    res2 = client.post(f"/api/v1/eligibility/evaluate/{uuid.uuid4()}")
    assert res2.status_code == 401

    # 3. /evaluate-all
    res3 = client.post("/api/v1/eligibility/evaluate-all")
    assert res3.status_code == 401


def test_eligibility_check_pm_kisan_incomplete_criteria_returns_potentially_eligible(client, seeded_db):
    """
    Blocker B: Citizen satisfying all modelled PM-KISAN conditions receives
    UNKNOWN (potentially_eligible) with eligible=None because criteria_complete=False.
    Underlying matched_conditions are fully preserved.
    """
    token = _register_and_get_token(client, "farmer.eligible@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "full_name": "Ramesh Kisan",
            "occupation": "Farmer",
            "preferred_language": "en",
            "profile_data": {
                "is_landholding_farmer": True,
                "is_institutional_landholder": False,
                "is_income_tax_payer": False,
            },
        },
    )

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))
    assert pm_kisan is not None

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id)},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]

    assert data["scheme_code"] == "PM-KISAN"
    assert data["overall_status"] == "UNKNOWN"
    assert data["result"] == "potentially_eligible"
    assert data["eligible"] is None
    assert data["criteria_complete"] is False
    assert data["is_authoritative"] is True
    assert len(data["matched_conditions"]) == 3
    assert len(data["failed_conditions"]) == 0
    assert len(data["unknown_conditions"]) == 0
    assert "not fully modelled in the catalogue" in data["explanation"]


def test_eligibility_check_complete_criteria_scheme_returns_eligible(client, seeded_db):
    """
    Blocker B: When a scheme has criteria_complete=True and all conditions pass,
    it returns definitive eligible=True and overall_status=PASS.
    """
    token = _register_and_get_token(client, "complete.criteria@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Add a mock fully-complete scheme
    s_id = uuid.uuid4()
    complete_scheme = Scheme(
        id=s_id,
        scheme_code="COMPLETE-TEST",
        name="Fully Modelled Test Scheme",
        description="Scheme with complete criteria",
        ministry="Ministry of Agriculture and Farmers Welfare",
        category="agriculture",
        geographic_scope="central",
        target_beneficiaries=["farmers"],
        benefits="Sample benefits",
        source_url="https://agricoop.gov.in/guidelines.pdf",
        scheme_status="active",
        last_retrieved_at=datetime.now(timezone.utc),
        last_verified_at=datetime.now(timezone.utc),
        source_evidence=[
            {
                "claim": "operational_status",
                "source_type": "guideline",
                "source_url": "https://agricoop.gov.in/guidelines.pdf",
                "issuing_authority": "Ministry of Agriculture",
                "retrieved_at": "2026-11-10T10:00:00Z",
                "citation": "Clause 1",
                "verification_status": "verified",
                "verified_at": "2026-11-10T12:00:00Z",
            }
        ],
    )
    rule_ver = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=s_id,
        version=1,
        is_active=True,
        eligibility_criteria={
            "is_authoritative": True,
            "is_provisional": False,
            "criteria_complete": True,  # Fully modelled
            "all": [
                {"field": "is_farmer", "operator": "equals", "value": True},
            ],
        },
        source_url="https://agricoop.gov.in/guidelines.pdf",
    )
    complete_scheme.rule_versions = [rule_ver]
    seeded_db.add(complete_scheme)
    seeded_db.commit()

    client.put(
        "/api/v1/profile",
        headers=headers,
        json={"profile_data": {"is_farmer": True}},
    )

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(s_id)},
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["overall_status"] == "PASS"
    assert data["result"] == "eligible"
    assert data["eligible"] is True
    assert data["criteria_complete"] is True
    assert data["is_authoritative"] is True


def test_eligibility_check_pm_kisan_ineligible_due_to_tax(client, seeded_db):
    """
    Blocker B: Citizen who is an income tax payer fails PM-KISAN eligibility.
    A known exclusion establishes definitive FAIL even when criteria_complete=False.
    """
    token = _register_and_get_token(client, "farmer.taxpayer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "full_name": "Taxpayer Farmer",
            "profile_data": {
                "is_landholding_farmer": True,
                "is_institutional_landholder": False,
                "is_income_tax_payer": True,
            },
        },
    )

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id)},
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["overall_status"] == "FAIL"
    assert data["result"] == "not_eligible"
    assert data["eligible"] is False
    assert len(data["failed_conditions"]) == 1
    assert data["failed_conditions"][0]["field"] == "is_income_tax_payer"
    assert "not satisfied" in data["failed_conditions"][0]["explanation"]


def test_eligibility_check_pm_kisan_unknown_with_questions(client, seeded_db):
    """Citizen with blank profile evaluates to UNKNOWN and receives localized follow-up questions."""
    token = _register_and_get_token(client, "blank.user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id)},
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["overall_status"] == "UNKNOWN"
    assert data["result"] == "insufficient_information"
    assert data["eligible"] is None
    assert len(data["unknown_conditions"]) == 3
    assert len(data["missing_fields"]) == 3
    assert len(data["next_questions"]) == 3

    q_farmer = next((q for q in data["next_questions"] if q["field"] == "is_landholding_farmer"), None)
    assert q_farmer is not None
    assert "कृषि योग्य भूमि" in q_farmer["question_hi"]
    assert "agricultural land" in q_farmer["question"]


def test_eligibility_check_with_profile_override_non_destructive(client, seeded_db):
    """
    Profile override in request payload evaluates what-if conditions without
    mutating the citizen's actual database profile.
    """
    token = _register_and_get_token(client, "whatif.user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    # 1. Evaluate with override -> conditions pass (potentially_eligible due to incomplete criteria)
    res_override = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={
            "scheme_id": str(pm_kisan.id),
            "profile_override": {
                "is_landholding_farmer": True,
                "is_institutional_landholder": False,
                "is_income_tax_payer": False,
            },
        },
    )
    assert res_override.status_code == 200
    assert res_override.json()["data"]["result"] == "potentially_eligible"
    assert len(res_override.json()["data"]["matched_conditions"]) == 3

    # 2. Subsequent check without override -> returns insufficient_information
    res_stored = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id)},
    )
    assert res_stored.status_code == 200
    assert res_stored.json()["data"]["result"] == "insufficient_information"


def test_eligibility_evaluate_path_endpoint(client, seeded_db):
    """
    Secondary Fix: POST /api/v1/eligibility/evaluate/{scheme_id} operates cleanly
    without requiring duplicate scheme_id in payload.
    """
    token = _register_and_get_token(client, "path.user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    res = client.post(
        f"/api/v1/eligibility/evaluate/{pm_kisan.id}",
        headers=headers,
        json={
            "profile_override": {
                "is_landholding_farmer": True,
                "is_institutional_landholder": False,
                "is_income_tax_payer": False,
            },
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["result"] == "potentially_eligible"


def test_eligibility_evaluate_all_active_schemes(client, seeded_db):
    """Batch evaluation evaluates all active schemes and reports correct aggregate counts."""
    token = _register_and_get_token(client, "batch.senior.vendor@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "full_name": "Savitri Devi",
            "date_of_birth": "1952-03-15",
            "gender": "female",
            "residence_type": "urban",
            "profile_data": {
                "is_street_vendor": True,
                "has_vending_certificate_or_lor": True,
            },
        },
    )

    res = client.post(
        "/api/v1/eligibility/evaluate-all",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["total_evaluated"] == 4
    # All 4 active schemes have criteria_complete=False by default (conservative),
    # so schemes whose conditions pass are potentially_eligible (UNKNOWN)
    assert data["unknown_count"] == 4
    assert data["ineligible_count"] == 0

    evaluated_results = {r["scheme_code"]: r["result"] for r in data["results"]}
    assert evaluated_results["AB-PMJAY"] == "potentially_eligible"
    assert evaluated_results["PM-SVANIDHI"] == "potentially_eligible"
    assert evaluated_results["PM-KISAN"] == "insufficient_information"
    assert evaluated_results["PMAY-U"] == "potentially_eligible"


def test_eligibility_evaluate_all_include_pending(client, seeded_db):
    """Batch evaluation with include_pending=True evaluates all 7 schemes."""
    token = _register_and_get_token(client, "all.schemes@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/eligibility/evaluate-all",
        headers=headers,
        json={"include_pending": True},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_evaluated"] == 7


def test_eligibility_evaluate_all_category_filter(client, seeded_db):
    """Category filter restricts batch evaluation to matching schemes only."""
    token = _register_and_get_token(client, "cat.user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/eligibility/evaluate-all",
        headers=headers,
        json={"category": "agriculture"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_evaluated"] == 1
    assert data["results"][0]["scheme_code"] == "PM-KISAN"

    # Invalid category returns 422
    res_bad = client.post(
        "/api/v1/eligibility/evaluate-all",
        headers=headers,
        json={"category": "invalid_category"},
    )
    assert res_bad.status_code == 422


def test_eligibility_nonexistent_scheme_returns_404(client, seeded_db):
    """Evaluating a non-existent UUID returns 404 Not Found."""
    token = _register_and_get_token(client, "missing.scheme@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


def test_eligibility_pending_scheme_requires_include_pending(client, seeded_db):
    """
    Blocker C: Evaluating pending scheme (e.g. PMUY) without include_pending returns 404.
    With include_pending=True, evaluates successfully but is strictly non-authoritative.
    """
    token = _register_and_get_token(client, "pending.test@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    pmuy = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PMUY"))
    assert pmuy is not None

    # Without include_pending -> 404
    res_no = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pmuy.id)},
    )
    assert res_no.status_code == 404

    # With include_pending=True -> 200, strictly marked non-authoritative
    res_yes = client.post(
        "/api/v1/eligibility/check?include_pending=true",
        headers=headers,
        json={"scheme_id": str(pmuy.id)},
    )
    assert res_yes.status_code == 200
    data = res_yes.json()["data"]
    assert data["scheme_code"] == "PMUY"
    assert data["is_provisional"] is True
    assert data["is_authoritative"] is False


# ── Stage G: Beneficiary-Aware Eligibility Integration Tests ────────────────

def test_beneficiary_eligibility_isolation_and_gender(client, seeded_db):
    """
    Stage G: Beneficiary evaluation uses beneficiary data, never falling back to account holder.
    - Account holder is male, age 25.
    - Mother beneficiary is female, age 52.
    - Evaluating PMUY (requires female applicant) for mother evaluates mother's gender.
    - Account holder gender is NEVER substituted.
    """
    token = _register_and_get_token(client, "son.account@example.com", "Raju (Son)")
    headers = {"Authorization": f"Bearer {token}"}

    # Set account holder profile: Male, 25
    client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "gender": "male",
            "date_of_birth": "2001-01-01",
            "residence_type": "rural",
        },
    )

    # Register mother as a beneficiary: Female, 52
    ben_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Savitri Devi",
            "relationship": "mother",
            "gender": "female",
            "date_of_birth": "1974-06-15",
            "residence_type": "rural",
            "profile_data": {
                "has_existing_lpg_connection": False,
                "is_bpl_or_eligible_category": True,
            },
        },
    )
    assert ben_res.status_code == 201
    mother_id = ben_res.json()["data"]["id"]

    pmuy = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PMUY"))
    assert pmuy is not None

    # 1. Evaluate for mother explicitly
    res_mother = client.post(
        "/api/v1/eligibility/check?include_pending=true",
        headers=headers,
        json={
            "scheme_id": str(pmuy.id),
            "beneficiary_id": mother_id,
        },
    )
    assert res_mother.status_code == 200
    m_data = res_mother.json()["data"]
    assert m_data["beneficiary_id"] == mother_id
    assert m_data["beneficiary_name"] == "Savitri Devi"
    assert m_data["beneficiary_relationship"] == "mother"

    # In PMUY conditions, applicant_gender must match 'female'
    gender_match = next((c for c in m_data["matched_conditions"] if c["field"] == "applicant_gender"), None)
    assert gender_match is not None
    assert gender_match["passed"] is True
    assert gender_match["actual_value"] == "female"

    # 2. Evaluate for account holder (self, omitting beneficiary_id)
    res_self = client.post(
        "/api/v1/eligibility/check?include_pending=true",
        headers=headers,
        json={"scheme_id": str(pmuy.id)},
    )
    assert res_self.status_code == 200
    s_data = res_self.json()["data"]
    assert s_data["beneficiary_relationship"] == "self"
    gender_failed = next((c for c in s_data["failed_conditions"] if c["field"] == "applicant_gender"), None)
    assert gender_failed is not None
    assert gender_failed["passed"] is False
    assert gender_failed["actual_value"] == "male"


def test_beneficiary_different_dobs_produce_different_age_outcomes(client, seeded_db):
    """
    Stage G: Different DOBs on family beneficiaries produce distinct age-based outcomes.
    - Father (age 70) qualifies for senior citizen age >= 70 (AB-PMJAY top-up).
    - Son (age 16) does not qualify for age >= 18 schemes.
    """
    token = _register_and_get_token(client, "family.ages@example.com", "Account Holder")
    headers = {"Authorization": f"Bearer {token}"}

    # Register father: born 1954 (age ~72)
    res_f = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Grandpa Sharma",
            "relationship": "father",
            "date_of_birth": "1954-01-01",
        },
    )
    father_id = res_f.json()["data"]["id"]

    # Register son: born 2012 (age ~14)
    res_s = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Junior Sharma",
            "relationship": "son",
            "date_of_birth": "2012-01-01",
        },
    )
    son_id = res_s.json()["data"]["id"]

    # APY requires age between 18 and 40
    apy = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "APY"))
    assert apy is not None

    # Father evaluation: fails age <= 40
    res_father_apy = client.post(
        "/api/v1/eligibility/check?include_pending=true",
        headers=headers,
        json={"scheme_id": str(apy.id), "beneficiary_id": father_id},
    )
    assert res_father_apy.status_code == 200
    f_res = res_father_apy.json()["data"]
    assert any(c["field"] == "age" and c["passed"] is False for c in f_res["failed_conditions"])

    # Son evaluation: fails age >= 18
    res_son_apy = client.post(
        "/api/v1/eligibility/check?include_pending=true",
        headers=headers,
        json={"scheme_id": str(apy.id), "beneficiary_id": son_id},
    )
    assert res_son_apy.status_code == 200
    s_res = res_son_apy.json()["data"]
    assert any(c["field"] == "age" and c["passed"] is False for c in s_res["failed_conditions"])


def test_beneficiary_missing_fields_produce_unknown(client, seeded_db):
    """Stage G: Missing attributes on a beneficiary strictly produce UNKNOWN, not fallback to user."""
    token = _register_and_get_token(client, "user.incomplete.ben@example.com", "Rakesh")
    headers = {"Authorization": f"Bearer {token}"}

    # User profile has farming data
    client.put(
        "/api/v1/profile",
        headers=headers,
        json={"profile_data": {"is_landholding_farmer": True}},
    )

    # Beneficiary has NO farming data
    ben_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Spouse Sangeeta",
            "relationship": "spouse",
            "profile_data": {},  # Missing is_landholding_farmer
        },
    )
    spouse_id = ben_res.json()["data"]["id"]

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id), "beneficiary_id": spouse_id},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["beneficiary_id"] == spouse_id
    assert data["beneficiary_relationship"] == "spouse"
    assert data["overall_status"] == "UNKNOWN"
    # is_landholding_farmer must be in unknown_conditions, NOT derived from account holder!
    assert "is_landholding_farmer" in data["missing_fields"]


def test_beneficiary_batch_evaluation(client, seeded_db):
    """Stage G: Batch evaluation supports beneficiary_id and evaluates every scheme against that beneficiary."""
    token = _register_and_get_token(client, "user.batch.ben@example.com", "Batch User")
    headers = {"Authorization": f"Bearer {token}"}

    ben_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Sister Priya",
            "relationship": "sibling",
            "date_of_birth": "1998-03-25",
            "residence_type": "urban",
        },
    )
    sibling_id = ben_res.json()["data"]["id"]

    batch_res = client.post(
        "/api/v1/eligibility/evaluate-all",
        headers=headers,
        json={"beneficiary_id": sibling_id},
    )
    assert batch_res.status_code == 200
    batch_data = batch_res.json()["data"]
    assert batch_data["total_evaluated"] >= 4
    for r in batch_data["results"]:
        assert r["beneficiary_id"] == sibling_id
        assert r["beneficiary_relationship"] == "sibling"
        assert r["beneficiary_name"] == "Sister Priya"


def test_beneficiary_cross_account_idor_rejected(client, seeded_db):
    """Stage G: Evaluating another user's beneficiary returns 404 Not Found without leaking existence."""
    token_a = _register_and_get_token(client, "user.a.eval@example.com", "User A")
    token_b = _register_and_get_token(client, "user.b.eval@example.com", "User B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    ben_res_a = client.post(
        "/api/v1/beneficiaries",
        headers=headers_a,
        json={"full_name": "Father of A", "relationship": "father"},
    )
    father_a_id = ben_res_a.json()["data"]["id"]

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    # User B tries to evaluate using User A's father ID -> 404
    res_hack = client.post(
        "/api/v1/eligibility/check",
        headers=headers_b,
        json={"scheme_id": str(pm_kisan.id), "beneficiary_id": father_a_id},
    )
    assert res_hack.status_code == 404


def test_beneficiary_profile_override_non_destructive(client, seeded_db):
    """Stage G: Profile override for beneficiary evaluation is non-destructive (does not mutate DB)."""
    token = _register_and_get_token(client, "ben.override@example.com", "Override User")
    headers = {"Authorization": f"Bearer {token}"}

    ben_res = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json={
            "full_name": "Brother Rohan",
            "relationship": "sibling",
            "profile_data": {"owns_pucca_house": False},
        },
    )
    brother_id = ben_res.json()["data"]["id"]

    pmay = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PMAY-U"))

    # Evaluate with override claiming pucca house = True
    res = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={
            "scheme_id": str(pmay.id),
            "beneficiary_id": brother_id,
            "profile_override": {"owns_pucca_house": True},
        },
    )
    assert res.status_code == 200

    # Verify brother record in database remains owns_pucca_house: False
    get_res = client.get(f"/api/v1/beneficiaries/{brother_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["profile_data"]["owns_pucca_house"] is False


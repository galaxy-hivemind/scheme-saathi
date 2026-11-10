"""
API integration tests for Deterministic Eligibility Evaluation endpoints:
- POST /api/v1/eligibility/check
- POST /api/v1/eligibility/evaluate/{scheme_id}
- POST /api/v1/eligibility/evaluate-all
"""
from pathlib import Path
import uuid
import pytest
from sqlalchemy import select

from app.models.scheme import Scheme
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


def test_eligibility_check_pm_kisan_eligible(client, seeded_db):
    """Citizen satisfying all PM-KISAN statutory criteria evaluates to PASS (eligible)."""
    token = _register_and_get_token(client, "farmer.eligible@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Update profile with eligible farmer attributes
    client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "full_name": "Ramesh Kisan",
            "occupation": "Farmer",
            "profile_data": {
                "is_landholding_farmer": True,
                "is_institutional_landholder": False,
                "is_income_tax_payer": False,
            },
        },
    )

    # Fetch PM-KISAN scheme ID
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
    assert data["overall_status"] == "PASS"
    assert data["result"] == "eligible"
    assert data["eligible"] is True
    assert data["is_authoritative"] is True
    assert len(data["matched_conditions"]) == 3
    assert len(data["failed_conditions"]) == 0
    assert len(data["unknown_conditions"]) == 0
    assert len(data["missing_fields"]) == 0


def test_eligibility_check_pm_kisan_ineligible_due_to_tax(client, seeded_db):
    """Citizen who is an income tax payer fails PM-KISAN eligibility with detailed explanation."""
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

    # Check that localized Hindi question is provided for farmer
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

    # 1. Evaluate with override -> PASS
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
    assert res_override.json()["data"]["overall_status"] == "PASS"

    # 2. Subsequent check without override -> remains UNKNOWN
    res_stored = client.post(
        "/api/v1/eligibility/check",
        headers=headers,
        json={"scheme_id": str(pm_kisan.id)},
    )
    assert res_stored.status_code == 200
    assert res_stored.json()["data"]["overall_status"] == "UNKNOWN"


def test_eligibility_evaluate_path_endpoint(client, seeded_db):
    """POST /api/v1/eligibility/evaluate/{scheme_id} operates identically to /check."""
    token = _register_and_get_token(client, "path.user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    pm_kisan = seeded_db.scalar(select(Scheme).where(Scheme.scheme_code == "PM-KISAN"))

    res = client.post(
        f"/api/v1/eligibility/evaluate/{pm_kisan.id}",
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
    assert res.status_code == 200
    assert res.json()["data"]["overall_status"] == "PASS"


def test_eligibility_evaluate_all_active_schemes(client, seeded_db):
    """Batch evaluation evaluates all active schemes and reports correct aggregate counts."""
    token = _register_and_get_token(client, "batch.senior.vendor@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Senior urban vendor with LoR:
    # - AB-PMJAY: age >= 70 -> PASS
    # - PM-SVANIDHI: street vendor with LoR -> PASS
    # - PM-KISAN: land info missing -> UNKNOWN
    # - PMAY-U: pucca house info missing -> UNKNOWN
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
    assert data["eligible_count"] == 2
    assert data["unknown_count"] == 2
    assert data["ineligible_count"] == 0

    evaluated_codes = {r["scheme_code"]: r["overall_status"] for r in data["results"]}
    assert evaluated_codes["AB-PMJAY"] == "PASS"
    assert evaluated_codes["PM-SVANIDHI"] == "PASS"
    assert evaluated_codes["PM-KISAN"] == "UNKNOWN"
    assert evaluated_codes["PMAY-U"] == "UNKNOWN"


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
    """Evaluating pending scheme (e.g. PMUY) without include_pending returns 404."""
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

    # With include_pending=True -> 200, marked provisional
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

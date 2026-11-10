"""
API integration tests for Government Scheme Catalogue endpoints:
- GET /api/v1/schemes (search, category filter, visibility, deterministic pagination, FTS stop-word & punctuation bypass)
- GET /api/v1/schemes/{scheme_id} (active vs pending visibility, active document requirements, exclusion of rule JSON, 404/422 handling)
"""
from pathlib import Path
import uuid
import pytest

from app.scripts.seed_schemes import execute_seed_import
from tests.api.test_profile import _register_and_get_token


@pytest.fixture
def seeded_db(db_session):
    """Seed the database with the official 7 curated scheme seed files."""
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "schemes"
    execute_seed_import(data_dir=data_dir, dry_run=False, session=db_session)
    return db_session


def test_jwt_authentication_required(client):
    """Unauthenticated access to list or detail endpoints returns 401 Unauthorized."""
    # List endpoint
    res = client.get("/api/v1/schemes")
    assert res.status_code == 401

    # Detail endpoint
    res = client.get(f"/api/v1/schemes/{uuid.uuid4()}")
    assert res.status_code == 401


def test_list_schemes_active_only_by_default(client, seeded_db):
    """Default list returns only the 4 active schemes (PM-KISAN, PMAY-U, AB-PMJAY, PM-SVANIDHI)."""
    token = _register_and_get_token(client, "scheme.user1@example.com")
    res = client.get(
        "/api/v1/schemes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]

    # Exactly 4 active schemes
    assert data["total"] == 4
    codes = {item["scheme_code"] for item in data["items"]}
    assert codes == {"PM-KISAN", "PMAY-U", "AB-PMJAY", "PM-SVANIDHI"}

    for item in data["items"]:
        assert item["scheme_status"] == "active"


def test_list_schemes_include_pending(client, seeded_db):
    """include_pending=true returns both active and pending_verification schemes (all 7)."""
    token = _register_and_get_token(client, "scheme.user2@example.com")
    res = client.get(
        "/api/v1/schemes?include_pending=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["total"] == 7
    codes = {item["scheme_code"] for item in data["items"]}
    assert codes == {"PM-KISAN", "PMAY-U", "AB-PMJAY", "PM-SVANIDHI", "PMUY", "APY", "PMKVY"}


def test_list_schemes_lightweight_summary(client, seeded_db):
    """List endpoint items contain only summary fields; omit description, benefits, and evidence."""
    token = _register_and_get_token(client, "scheme.user3@example.com")
    res = client.get(
        "/api/v1/schemes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) > 0

    first_item = items[0]
    expected_fields = {"id", "scheme_code", "name", "short_title", "ministry", "category", "geographic_scope", "scheme_status"}
    assert set(first_item.keys()) == expected_fields

    # Omitted fields:
    assert "description" not in first_item
    assert "benefits" not in first_item
    assert "target_beneficiaries" not in first_item
    assert "source_evidence" not in first_item
    assert "official_url" not in first_item


def test_list_schemes_category_filter(client, seeded_db):
    """Category filter returns only schemes matching canonical category."""
    token = _register_and_get_token(client, "scheme.user4@example.com")

    # Agriculture -> PM-KISAN
    res = client.get(
        "/api/v1/schemes?category=agriculture",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["scheme_code"] == "PM-KISAN"

    # Invalid category -> 422
    res_invalid = client.get(
        "/api/v1/schemes?category=invalid_cat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_invalid.status_code == 422


def test_list_schemes_search_whitespace_only(client, seeded_db):
    """Whitespace-only search query ('   ') bypasses FTS filter and returns all active schemes."""
    token = _register_and_get_token(client, "scheme.user5@example.com")
    res = client.get(
        "/api/v1/schemes?q=%20%20%20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 4  # Unfiltered active schemes


def test_list_schemes_search_punctuation_only(client, seeded_db):
    """Punctuation-only search query ('???---') bypasses FTS filter and returns all active schemes."""
    token = _register_and_get_token(client, "scheme.user6@example.com")
    res = client.get(
        "/api/v1/schemes?q=%3F%3F%3F---",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 4  # Unfiltered active schemes


def test_list_schemes_search_stop_word_only(client, seeded_db):
    """Stop-word only query ('the and') produces 0 lexemes in PostgreSQL and bypasses FTS filter."""
    token = _register_and_get_token(client, "scheme.user7@example.com")
    res = client.get(
        "/api/v1/schemes?q=the%20and",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 4  # Unfiltered active schemes


def test_list_schemes_search_mixed_punctuation_and_words(client, seeded_db):
    """Mixed punctuation query ('PM-KISAN!') extracts searchable lexemes and matches PM-KISAN."""
    token = _register_and_get_token(client, "scheme.user8@example.com")
    res = client.get(
        "/api/v1/schemes?q=PM-KISAN!",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["scheme_code"] == "PM-KISAN"


def test_list_schemes_search_field_coverage(client, seeded_db):
    """Matches keywords across different indexed fields: ministry, benefits, beneficiaries."""
    token = _register_and_get_token(client, "scheme.user9@example.com")

    # Match in ministry: 'Health' -> AB-PMJAY
    r1 = client.get("/api/v1/schemes?q=Health", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200
    codes1 = {item["scheme_code"] for item in r1.json()["data"]["items"]}
    assert "AB-PMJAY" in codes1

    # Match in benefits: 'hospitalisation' -> AB-PMJAY
    r2 = client.get("/api/v1/schemes?q=hospitalisation", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    codes2 = {item["scheme_code"] for item in r2.json()["data"]["items"]}
    assert "AB-PMJAY" in codes2

    # Match in target_beneficiaries: 'vendors' -> PM-SVANIDHI
    r3 = client.get("/api/v1/schemes?q=vendors", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    codes3 = {item["scheme_code"] for item in r3.json()["data"]["items"]}
    assert "PM-SVANIDHI" in codes3


def test_list_schemes_deterministic_sorting(client, seeded_db):
    """Results are stably ordered by (Scheme.name ASC, Scheme.id ASC)."""
    token = _register_and_get_token(client, "scheme.user10@example.com")
    res = client.get("/api/v1/schemes?include_pending=true&limit=50", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()["data"]["items"]

    names = [item["name"] for item in items]
    assert names == sorted(names)


def test_detail_scheme_active_success(client, seeded_db):
    """Detail endpoint returns full metadata, active documents, and source evidence for active scheme."""
    token = _register_and_get_token(client, "scheme.user11@example.com")

    # Fetch PM-KISAN id from list
    list_res = client.get("/api/v1/schemes?q=PM-KISAN", headers={"Authorization": f"Bearer {token}"})
    scheme_id = list_res.json()["data"]["items"][0]["id"]

    res = client.get(f"/api/v1/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["scheme_code"] == "PM-KISAN"
    assert data["scheme_status"] == "active"
    assert data["benefits"] is not None
    assert data["description"] is not None
    assert len(data["source_evidence"]) == 6
    assert len(data["required_documents"]) >= 2

    # Verify document types
    doc_types = {d["document_type"] for d in data["required_documents"]}
    assert "aadhaar" in doc_types


def test_detail_scheme_excludes_rule_json(client, seeded_db):
    """Detail endpoint strictly excludes internal machine-readable eligibility rule JSON."""
    token = _register_and_get_token(client, "scheme.user12@example.com")
    list_res = client.get("/api/v1/schemes?q=PM-KISAN", headers={"Authorization": f"Bearer {token}"})
    scheme_id = list_res.json()["data"]["items"][0]["id"]

    res = client.get(f"/api/v1/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()["data"]

    assert "eligibility_criteria" not in data
    assert "eligibility_rules" not in data
    assert "rules" not in data


def test_detail_scheme_pending_visibility(client, seeded_db):
    """Pending scheme returns 404 by default; returns 200 only with include_pending=true."""
    token = _register_and_get_token(client, "scheme.user13@example.com")

    # Get PMUY id from list with include_pending=true
    list_res = client.get("/api/v1/schemes?include_pending=true&category=women_welfare", headers={"Authorization": f"Bearer {token}"})
    pmuy_id = list_res.json()["data"]["items"][0]["id"]

    # Without include_pending -> 404 Not Found
    res_hidden = client.get(f"/api/v1/schemes/{pmuy_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_hidden.status_code == 404
    assert res_hidden.json()["detail"] == "Scheme not found"

    # With include_pending=true -> 200 OK
    res_visible = client.get(f"/api/v1/schemes/{pmuy_id}?include_pending=true", headers={"Authorization": f"Bearer {token}"})
    assert res_visible.status_code == 200
    data = res_visible.json()["data"]
    assert data["scheme_code"] == "PMUY"
    assert data["scheme_status"] == "pending_verification"
    assert data["last_verified_at"] is None


def test_detail_scheme_invalid_uuid_returns_422(client):
    """Non-UUID path parameter returns 422 Unprocessable Entity."""
    token = _register_and_get_token(client, "scheme.user14@example.com")
    res = client.get("/api/v1/schemes/invalid-not-a-uuid", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422

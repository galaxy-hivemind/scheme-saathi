"""
Integration tests for Seed Schemes Importer CLI and dry-run semantics.
"""
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
from sqlalchemy import select, event
from sqlalchemy.orm import Session

from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.scheme_document import SchemeDocument
from app.scripts.seed_schemes import execute_seed_import, load_and_prevalidate_seed_files


@pytest.fixture
def temp_seed_dir(tmp_path):
    """Creates a temporary seed directory with 1 valid active scheme."""
    now = datetime.now(timezone.utc)
    seed = {
        "scheme_code": "TEST-PMK",
        "name": "Test Kisan Scheme",
        "short_title": "Test Kisan",
        "description": "Test description of sufficient length for validation",
        "ministry": "Ministry of Agriculture and Farmers Welfare",
        "department": "Agriculture Division",
        "category": "agriculture",
        "geographic_scope": "central",
        "target_beneficiaries": ["Small Farmers"],
        "benefits": "Rs 6000 per year via DBT",
        "official_url": "https://pmkisan.gov.in/",
        "application_url": "https://pmkisan.gov.in/register",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "scheme_status": "active",
        "last_retrieved_at": now.isoformat(),
        "last_verified_at": now.isoformat(),
        "source_evidence": [
            {
                "claim": "name_and_ministry",
                "statement": "Administered by MoA&FW",
                "source_url": "https://pmkisan.gov.in/guidelines.pdf",
                "source_type": "guideline",
                "issuing_authority": "MoA&FW",
                "publication_date": "2024-01-01",
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "Clause 1",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
            {
                "claim": "category_and_scope",
                "statement": "Central sector agriculture scheme",
                "source_url": "https://pmkisan.gov.in/guidelines.pdf",
                "source_type": "guideline",
                "issuing_authority": "MoA&FW",
                "publication_date": "2024-01-01",
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "Clause 2",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
            {
                "claim": "target_beneficiaries",
                "statement": "Landholding farmers",
                "source_url": "https://pmkisan.gov.in/guidelines.pdf",
                "source_type": "guideline",
                "issuing_authority": "MoA&FW",
                "publication_date": "2024-01-01",
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "Clause 3",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
            {
                "claim": "benefits",
                "statement": "Rs 6000 per year",
                "source_url": "https://pmkisan.gov.in/guidelines.pdf",
                "source_type": "guideline",
                "issuing_authority": "MoA&FW",
                "publication_date": "2024-01-01",
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "Clause 4",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
            {
                "claim": "official_and_application_urls",
                "statement": "Portal hosted on pmkisan.gov.in",
                "source_url": "https://pmkisan.gov.in/",
                "source_type": "government_portal",
                "issuing_authority": "MoA&FW",
                "publication_date": None,
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "Portal Homepage",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
            {
                "claim": "operational_status",
                "statement": "Latest installment released on 30 October 2026",
                "source_url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2330414",
                "source_type": "pib_release",
                "issuing_authority": "PIB",
                "publication_date": "2026-10-30",
                "retrieved_at": (now - timedelta(hours=1)).isoformat(),
                "citation": "PIB PRID 2330414",
                "verification_status": "verified",
                "verified_at": now.isoformat(),
            },
        ],
        "eligibility_criteria": {"field": "is_farmer", "operator": "equals", "value": True},
        "required_documents": [
            {
                "document_type": "aadhaar",
                "title": "Aadhaar Card",
                "description": "UIDAI Aadhaar Card",
                "is_mandatory": True,
            },
            {
                "document_type": "land_records",
                "title": "Land Ownership Records",
                "description": "Khatauni/Patta",
                "is_mandatory": True,
            },
        ],
    }

    file_path = tmp_path / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    return tmp_path, seed


def test_prevalidation_failure_zero_db_connection(tmp_path):
    """Malformed or invalid seed file must raise ValueError before touching DB."""
    bad_file = tmp_path / "bad-scheme.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json")

    with pytest.raises(ValueError, match="Failed to read/parse JSON"):
        load_and_prevalidate_seed_files(tmp_path)


def test_dry_run_zero_dml_sql_listener(db_session, temp_seed_dir):
    """Instruments engine listener during --dry-run; asserts zero DML statements executed."""
    temp_dir, _ = temp_seed_dir
    engine = db_session.get_bind()

    executed_statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        executed_statements.append(statement.strip().upper())

    # Attach event listener
    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    try:
        summary = execute_seed_import(
            data_dir=temp_dir,
            dry_run=True,
            session=db_session,
        )
        assert summary["added"] == 1

        # Check all executed statements
        dml_keywords = ["INSERT ", "UPDATE ", "DELETE ", "CREATE ", "DROP ", "ALTER "]
        for stmt in executed_statements:
            for kw in dml_keywords:
                assert not stmt.startswith(kw), f"DML statement detected during dry-run: {stmt}"

    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_importer_idempotency(db_session, temp_seed_dir):
    """Running seed twice produces 0 new records and 0 updates on the second run."""
    temp_dir, _ = temp_seed_dir

    # Run 1: initial insert
    s1 = execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)
    assert s1["added"] == 1

    # Run 2: second run must be purely idempotent
    s2 = execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)
    assert s2["added"] == 0
    assert s2["updated"] == 0
    assert s2["skipped"] == 0
    assert s2["rule_versions_added"] == 0


def test_override_protection_skips_entire_aggregate(db_session, temp_seed_dir):
    """Conflicting verified scheme without --allow-override-verified skips entire aggregate."""
    temp_dir, seed = temp_seed_dir

    # Initial import
    execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)

    # Modify seed file (change benefit and add a document)
    seed["benefits"] = "Rs 10,000 per year"
    seed["required_documents"].append({
        "document_type": "ration_card",
        "title": "Ration Card",
        "is_mandatory": False,
    })

    file_path = temp_dir / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    # Run import WITHOUT --allow-override-verified
    summary = execute_seed_import(
        data_dir=temp_dir,
        dry_run=False,
        allow_override_verified=False,
        session=db_session,
    )
    assert summary["skipped"] == 1
    assert summary["updated"] == 0

    # Verify DB was NOT updated
    db_scheme = db_session.scalar(select(Scheme).where(Scheme.scheme_code == "TEST-PMK"))
    assert db_scheme.benefits == "Rs 6000 per year via DBT"

    # Verify no new document was added
    docs = db_session.scalars(select(SchemeDocument).where(SchemeDocument.scheme_id == db_scheme.id)).all()
    assert len(docs) == 2  # Not 3


def test_override_with_fresh_evidence_updates(db_session, temp_seed_dir):
    """With --allow-override-verified and verified claims, updates fields and sets new last_verified_at."""
    temp_dir, seed = temp_seed_dir

    # Initial import
    execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)

    # Modify seed with fresh verified evidence
    new_verified_at = datetime.now(timezone.utc)
    seed["benefits"] = "Enhanced Rs 8,000 per year"
    seed["last_verified_at"] = new_verified_at.isoformat()
    for e in seed["source_evidence"]:
        e["verified_at"] = new_verified_at.isoformat()

    file_path = temp_dir / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    # Run import WITH --allow-override-verified
    summary = execute_seed_import(
        data_dir=temp_dir,
        dry_run=False,
        allow_override_verified=True,
        session=db_session,
    )
    assert summary["updated"] == 1
    assert summary["skipped"] == 0

    db_scheme = db_session.scalar(select(Scheme).where(Scheme.scheme_code == "TEST-PMK"))
    assert db_scheme.benefits == "Enhanced Rs 8,000 per year"
    assert db_scheme.scheme_status == "active"
    assert db_scheme.last_verified_at is not None


def test_override_with_incomplete_evidence_demotes_to_pending(db_session, temp_seed_dir):
    """With --allow-override-verified but unverified claims, updates fields and demotes to pending."""
    temp_dir, seed = temp_seed_dir

    # Initial import
    execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)

    # Modify seed: change benefits, mark operational_status outdated and status pending
    seed["benefits"] = "Unverified benefit change"
    seed["scheme_status"] = "pending_verification"
    seed["last_verified_at"] = None
    for e in seed["source_evidence"]:
        if e["claim"] == "operational_status":
            e["verification_status"] = "outdated"
            e["verified_at"] = None

    file_path = temp_dir / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    # Run import WITH --allow-override-verified
    summary = execute_seed_import(
        data_dir=temp_dir,
        dry_run=False,
        allow_override_verified=True,
        session=db_session,
    )
    assert summary["updated"] == 1
    assert summary["demoted_to_pending"] == 1

    db_scheme = db_session.scalar(select(Scheme).where(Scheme.scheme_code == "TEST-PMK"))
    assert db_scheme.benefits == "Unverified benefit change"
    assert db_scheme.scheme_status == "pending_verification"
    assert db_scheme.last_verified_at is None


def test_rule_version_append_and_close(db_session, temp_seed_dir):
    """Rule changes append version = version + 1 and close previous version."""
    temp_dir, seed = temp_seed_dir

    # Initial import
    execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)

    # Change eligibility criteria
    seed["eligibility_criteria"] = {"field": "is_farmer", "operator": "equals", "value": True, "land_acres": 2.0}
    file_path = temp_dir / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    summary = execute_seed_import(
        data_dir=temp_dir,
        dry_run=False,
        allow_override_verified=True,
        session=db_session,
    )
    assert summary["rule_versions_added"] == 1

    db_scheme = db_session.scalar(select(Scheme).where(Scheme.scheme_code == "TEST-PMK"))
    rule_versions = db_session.scalars(
        select(SchemeRuleVersion).where(SchemeRuleVersion.scheme_id == db_scheme.id).order_by(SchemeRuleVersion.version.asc())
    ).all()

    assert len(rule_versions) == 2
    # v1 is closed
    assert rule_versions[0].version == 1
    assert rule_versions[0].is_active is False
    assert rule_versions[0].effective_to is not None
    # v2 is active
    assert rule_versions[1].version == 2
    assert rule_versions[1].is_active is True
    assert rule_versions[1].effective_to is None


def test_omitted_document_soft_deactivation(db_session, temp_seed_dir):
    """Documents omitted in seed are marked is_active = False."""
    temp_dir, seed = temp_seed_dir

    # Initial import (has 2 docs: aadhaar, land_records)
    execute_seed_import(data_dir=temp_dir, dry_run=False, session=db_session)

    # Omit land_records from seed
    seed["required_documents"] = [seed["required_documents"][0]]  # Keep only aadhaar
    file_path = temp_dir / "test-scheme.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(seed, f)

    summary = execute_seed_import(
        data_dir=temp_dir,
        dry_run=False,
        allow_override_verified=True,
        session=db_session,
    )
    assert summary["documents_deactivated"] == 1

    db_scheme = db_session.scalar(select(Scheme).where(Scheme.scheme_code == "TEST-PMK"))
    docs = {d.document_type: d for d in db_session.scalars(select(SchemeDocument).where(SchemeDocument.scheme_id == db_scheme.id)).all()}

    assert docs["aadhaar"].is_active is True
    assert docs["land_records"].is_active is False  # Soft-deactivated!

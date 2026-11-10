"""
Integration tests for Scheme SQLAlchemy models, constraints, and foreign key RESTRICT rules against PostgreSQL.
"""
from datetime import date, datetime, timezone
import uuid
import pytest
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError

from app.models.scheme import Scheme
from app.models.scheme_rule_version import SchemeRuleVersion
from app.models.scheme_document import SchemeDocument


def _create_sample_scheme(db_session, code: str = "SAMPLE-01") -> Scheme:
    now = datetime.now(timezone.utc)
    scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code=code,
        name="Sample Welfare Scheme",
        short_title="Sample",
        description="A description of the sample scheme",
        ministry="Ministry of Agriculture and Farmers Welfare",
        category="agriculture",
        geographic_scope="central",
        target_beneficiaries=["Small Farmers"],
        benefits="Financial assistance",
        source_url="https://pmkisan.gov.in/guidelines.pdf",
        scheme_status="active",
        last_retrieved_at=now,
        last_verified_at=now,
    )
    db_session.add(scheme)
    db_session.commit()
    return scheme


def test_unique_scheme_code_constraint(db_session):
    """Enforces UNIQUE (scheme_code) constraint."""
    _create_sample_scheme(db_session, code="CODE-DUP")
    duplicate_scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="CODE-DUP",
        name="Duplicate Scheme",
        description="Another scheme",
        ministry="Ministry of Finance",
        category="social_security",
        geographic_scope="central",
        target_beneficiaries=["Citizens"],
        benefits="Benefit text",
        source_url="https://pfrda.org.in/",
        scheme_status="pending_verification",
        last_retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(duplicate_scheme)
    with pytest.raises(IntegrityError, match="uq_schemes_scheme_code"):
        db_session.commit()
    db_session.rollback()


def test_category_check_constraint(db_session):
    """Enforces CHECK constraint on canonical 12 categories."""
    invalid_scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="INVALID-CAT",
        name="Invalid Category Scheme",
        description="Description",
        ministry="Ministry",
        category="non_existent_category",
        geographic_scope="central",
        target_beneficiaries=["Citizens"],
        benefits="Benefit text",
        source_url="https://gov.in/",
        scheme_status="active",
        last_retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(invalid_scheme)
    with pytest.raises(IntegrityError, match="ck_schemes_category"):
        db_session.commit()
    db_session.rollback()


def test_geographic_scope_check_constraint(db_session):
    """Enforces CHECK constraint geographic_scope = 'central'."""
    invalid_scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="INVALID-SCOPE",
        name="State Scope Scheme",
        description="Description",
        ministry="Ministry",
        category="agriculture",
        geographic_scope="state_mh",  # Invalid!
        target_beneficiaries=["Citizens"],
        benefits="Benefit text",
        source_url="https://gov.in/",
        scheme_status="active",
        last_retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(invalid_scheme)
    with pytest.raises(IntegrityError, match="ck_schemes_geographic_scope"):
        db_session.commit()
    db_session.rollback()


def test_scheme_status_check_constraint(db_session):
    """Enforces CHECK constraint on scheme_status."""
    invalid_scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code="INVALID-STATUS",
        name="Invalid Status Scheme",
        description="Description",
        ministry="Ministry",
        category="agriculture",
        geographic_scope="central",
        target_beneficiaries=["Citizens"],
        benefits="Benefit text",
        source_url="https://gov.in/",
        scheme_status="unknown_status",
        last_retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(invalid_scheme)
    with pytest.raises(IntegrityError, match="ck_schemes_status"):
        db_session.commit()
    db_session.rollback()


def test_unique_rule_version_constraint(db_session):
    """Enforces UNIQUE (scheme_id, version) constraint."""
    scheme = _create_sample_scheme(db_session, code="RULE-VER-1")
    v1 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=1,
        is_active=False,
        eligibility_criteria={"field": "test"},
        source_url="https://pmkisan.gov.in/",
    )
    db_session.add(v1)
    db_session.commit()

    v1_dup = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=1,  # Duplicate version 1
        is_active=True,
        eligibility_criteria={"field": "test_different"},
        source_url="https://pmkisan.gov.in/",
    )
    db_session.add(v1_dup)
    with pytest.raises(IntegrityError, match="uq_scheme_rule_versions_scheme_version"):
        db_session.commit()
    db_session.rollback()


def test_single_active_rule_version_enforced(db_session):
    """Partial unique index blocks inserting two active rule versions for the same scheme."""
    scheme = _create_sample_scheme(db_session, code="ACTIVE-RULE-TEST")
    v1 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=1,
        is_active=True,  # Active
        eligibility_criteria={"field": "test1"},
        source_url="https://pmkisan.gov.in/",
    )
    db_session.add(v1)
    db_session.commit()

    v2 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=2,
        is_active=True,  # ALSO Active - must fail partial unique index!
        eligibility_criteria={"field": "test2"},
        source_url="https://pmkisan.gov.in/",
    )
    db_session.add(v2)
    with pytest.raises(IntegrityError, match="uq_scheme_rule_versions_active"):
        db_session.commit()
    db_session.rollback()


def test_foreign_key_restrict_on_delete(db_session):
    """Foreign key ON DELETE RESTRICT prevents deleting scheme if rules or documents exist."""
    scheme = _create_sample_scheme(db_session, code="RESTRICT-TEST")
    doc = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        document_type="aadhaar",
        title="Aadhaar Card",
        is_mandatory=True,
        is_active=True,
    )
    db_session.add(doc)
    db_session.commit()

    # Attempt to delete the parent scheme
    db_session.delete(scheme)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_document_type_constraint(db_session):
    """Enforces UNIQUE (scheme_id, document_type)."""
    scheme = _create_sample_scheme(db_session, code="DOC-DUP-TEST")
    doc1 = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        document_type="aadhaar",
        title="Aadhaar Card",
    )
    db_session.add(doc1)
    db_session.commit()

    doc2 = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        document_type="aadhaar",  # Duplicate document_type for same scheme
        title="Another Aadhaar",
    )
    db_session.add(doc2)
    with pytest.raises(IntegrityError, match="uq_scheme_documents_scheme_doc_type"):
        db_session.commit()
    db_session.rollback()


def test_multiple_inactive_rule_versions_allowed(db_session):
    """Partial unique index allows at most one active rule version; multiple inactive versions are allowed."""
    scheme = _create_sample_scheme(db_session, code="INACTIVE-RULES-TEST")

    v1 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=1,
        is_active=False,  # Inactive
        eligibility_criteria={"field": "test_old_1"},
        source_url="https://pmkisan.gov.in/",
    )
    v2 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=2,
        is_active=False,  # Also inactive
        eligibility_criteria={"field": "test_old_2"},
        source_url="https://pmkisan.gov.in/",
    )
    v3 = SchemeRuleVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version=3,
        is_active=True,  # The single active version
        eligibility_criteria={"field": "test_current"},
        source_url="https://pmkisan.gov.in/",
    )
    db_session.add_all([v1, v2, v3])
    db_session.commit()

    # Query all rule versions for this scheme
    versions = db_session.scalars(
        select(SchemeRuleVersion).where(SchemeRuleVersion.scheme_id == scheme.id).order_by(SchemeRuleVersion.version.asc())
    ).all()
    assert len(versions) == 3
    assert versions[0].is_active is False
    assert versions[1].is_active is False
    assert versions[2].is_active is True


def test_document_type_nonempty_check_constraint(db_session):
    """Enforces ck_scheme_documents_type_nonempty: document_type cannot be empty or whitespace."""
    # 1. Valid document_type succeeds
    scheme1 = _create_sample_scheme(db_session, code="DOC-TYPE-VALID")
    doc_valid = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme1.id,
        document_type="valid_doc",
        title="Valid Document",
    )
    db_session.add(doc_valid)
    db_session.commit()

    # 2. Empty string is rejected
    scheme2 = _create_sample_scheme(db_session, code="DOC-TYPE-EMPTY")
    doc_empty = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme2.id,
        document_type="",
        title="Empty Doc Type",
    )
    db_session.add(doc_empty)
    with pytest.raises(IntegrityError, match="ck_scheme_documents_type_nonempty"):
        db_session.commit()
    db_session.rollback()

    # 3. Whitespace-only string is rejected
    scheme3 = _create_sample_scheme(db_session, code="DOC-TYPE-WS")
    doc_whitespace = SchemeDocument(
        id=uuid.uuid4(),
        scheme_id=scheme3.id,
        document_type="   ",
        title="Whitespace Doc Type",
    )
    db_session.add(doc_whitespace)
    with pytest.raises(IntegrityError, match="ck_scheme_documents_type_nonempty"):
        db_session.commit()
    db_session.rollback()



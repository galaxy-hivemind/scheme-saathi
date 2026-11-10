"""
Unit tests for Scheme Pydantic schemas, evidence validation, and constraints.
Runs with zero database dependencies.
"""
from datetime import date, datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from app.schemas.scheme import (
    SchemeCategory,
    SchemeStatus,
    MaterialClaim,
    SourceType,
    VerificationStatus,
    SourceEvidenceEntry,
    SchemeSeedSchema,
    SchemeSeedDocument,
)


def test_canonical_12_categories():
    """Verify all 12 canonical categories are accepted and invalid ones are rejected."""
    expected_categories = {
        "agriculture",
        "education",
        "health",
        "housing",
        "employment",
        "women_welfare",
        "children_welfare",
        "senior_citizens",
        "disability",
        "financial_inclusion",
        "social_security",
        "skill_development",
    }
    actual_categories = {c.value for c in SchemeCategory}
    assert actual_categories == expected_categories

    for cat in expected_categories:
        assert SchemeCategory(cat) is not None

    with pytest.raises(ValueError):
        SchemeCategory("invalid_category")

    with pytest.raises(ValueError):
        SchemeCategory("women_child")  # Ensure obsolete name is rejected


def test_source_evidence_https_and_domain_allowlist():
    """Verify source URLs must be HTTPS and belong to approved government domains."""
    now = datetime.now(timezone.utc)
    base_data = {
        "claim": MaterialClaim.BENEFITS,
        "statement": "Valid benefit statement",
        "source_type": SourceType.GUIDELINE,
        "issuing_authority": "Ministry of Agriculture",
        "publication_date": date(2024, 1, 1),
        "retrieved_at": now,
        "citation": "Clause 1",
        "verification_status": VerificationStatus.UNVERIFIED,
        "verified_at": None,
    }

    # HTTP rejected
    with pytest.raises(ValidationError, match="HTTPS"):
        SourceEvidenceEntry.model_validate({**base_data, "source_url": "http://pmkisan.gov.in/guidelines.pdf"})

    # Non-government domain rejected
    with pytest.raises(ValidationError, match="domain allowlist"):
        SourceEvidenceEntry.model_validate({**base_data, "source_url": "https://evil.com/fake-scheme.pdf"})

    # Approved domains accepted
    valid_urls = [
        "https://pmkisan.gov.in/Documents/Guidelines.pdf",
        "https://subdomain.nic.in/portal",
        "https://www.pfrda.org.in/circular.pdf",
        "https://nha.gov.in/pmjay",
        "https://uidai.gov.in/aadhaar",
    ]
    for url in valid_urls:
        entry = SourceEvidenceEntry.model_validate({**base_data, "source_url": url})
        assert str(entry.source_url).startswith("https://")


def test_evidence_utc_zero_offset():
    """Verify timestamps must be timezone-aware UTC with zero offset and not in the future."""
    now = datetime.now(timezone.utc)
    base_data = {
        "claim": MaterialClaim.BENEFITS,
        "statement": "Valid benefit statement",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "source_type": SourceType.GUIDELINE,
        "issuing_authority": "Ministry of Agriculture",
        "citation": "Clause 1",
        "verification_status": VerificationStatus.UNVERIFIED,
    }

    # Naive datetime rejected
    naive_dt = datetime.now()
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        SourceEvidenceEntry.model_validate({**base_data, "retrieved_at": naive_dt})

    # Non-zero offset rejected (e.g. IST +05:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_dt = datetime.now(ist_tz)
    with pytest.raises(ValidationError, match="zero offset"):
        SourceEvidenceEntry.model_validate({**base_data, "retrieved_at": ist_dt})

    # Future datetime rejected
    future_dt = now + timedelta(days=2)
    with pytest.raises(ValidationError, match="future"):
        SourceEvidenceEntry.model_validate({**base_data, "retrieved_at": future_dt})


def test_evidence_publication_date_semantics():
    """Verify publication_date cannot be in the future relative to retrieved_at."""
    now = datetime.now(timezone.utc)
    base_data = {
        "claim": MaterialClaim.BENEFITS,
        "statement": "Valid benefit statement",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "source_type": SourceType.GUIDELINE,
        "issuing_authority": "Ministry of Agriculture",
        "retrieved_at": now,
        "citation": "Clause 1",
        "verification_status": VerificationStatus.UNVERIFIED,
    }

    # Future publication date relative to retrieval date rejected
    future_pub_date = now.date() + timedelta(days=5)
    with pytest.raises(ValidationError, match="publication_date cannot be in the future"):
        SourceEvidenceEntry.model_validate({**base_data, "publication_date": future_pub_date})

    # Past publication date accepted
    past_pub_date = now.date() - timedelta(days=100)
    entry = SourceEvidenceEntry.model_validate({**base_data, "publication_date": past_pub_date})
    assert entry.publication_date == past_pub_date


def test_evidence_verification_semantics():
    """Verify verified_at semantics against verification_status."""
    now = datetime.now(timezone.utc)
    base_data = {
        "claim": MaterialClaim.BENEFITS,
        "statement": "Valid benefit statement",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "source_type": SourceType.GUIDELINE,
        "issuing_authority": "Ministry of Agriculture",
        "retrieved_at": now - timedelta(hours=2),
        "citation": "Clause 1",
    }

    # Verified status requires verified_at
    with pytest.raises(ValidationError, match="verified_at is mandatory"):
        SourceEvidenceEntry.model_validate({**base_data, "verification_status": VerificationStatus.VERIFIED, "verified_at": None})

    # verified_at cannot precede retrieved_at
    with pytest.raises(ValidationError, match="verified_at cannot precede retrieved_at"):
        SourceEvidenceEntry.model_validate({
            **base_data,
            "verification_status": VerificationStatus.VERIFIED,
            "verified_at": now - timedelta(hours=5),  # 3 hours before retrieved_at!
        })

    # Unverified status must have null verified_at
    with pytest.raises(ValidationError, match="verified_at must be null"):
        SourceEvidenceEntry.model_validate({
            **base_data,
            "verification_status": VerificationStatus.UNVERIFIED,
            "verified_at": now,
        })

    # Outdated status must have null verified_at
    with pytest.raises(ValidationError, match="verified_at must be null"):
        SourceEvidenceEntry.model_validate({
            **base_data,
            "verification_status": VerificationStatus.OUTDATED,
            "verified_at": now,
        })


def test_active_scheme_standard_enforcement():
    """Verify SchemeSeedSchema rejects active status when required claims are missing or unverified."""
    now = datetime.now(timezone.utc)

    def make_evidence(claim: MaterialClaim, verified: bool = True) -> dict:
        return {
            "claim": claim,
            "statement": f"Valid statement for {claim.value}",
            "source_url": "https://pmkisan.gov.in/guidelines.pdf",
            "source_type": SourceType.GUIDELINE,
            "issuing_authority": "Ministry of Agriculture",
            "publication_date": date(2024, 1, 1),
            "retrieved_at": now - timedelta(hours=1),
            "citation": "Clause 1",
            "verification_status": VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED,
            "verified_at": now if verified else None,
        }

    all_claims = [
        make_evidence(MaterialClaim.NAME_AND_MINISTRY),
        make_evidence(MaterialClaim.CATEGORY_AND_SCOPE),
        make_evidence(MaterialClaim.TARGET_BENEFICIARIES),
        make_evidence(MaterialClaim.BENEFITS),
        make_evidence(MaterialClaim.OFFICIAL_AND_APPLICATION_URLS),
        make_evidence(MaterialClaim.OPERATIONAL_STATUS),
    ]

    base_scheme = {
        "scheme_code": "TEST-SCHEME",
        "name": "Test Scheme",
        "description": "Test description of sufficient length",
        "ministry": "Ministry of Agriculture",
        "category": SchemeCategory.AGRICULTURE,
        "geographic_scope": "central",
        "target_beneficiaries": ["Farmers"],
        "benefits": "Rs 6000 per year",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "last_retrieved_at": now,
    }

    # Valid active scheme
    valid_active = SchemeSeedSchema.model_validate({
        **base_scheme,
        "scheme_status": SchemeStatus.ACTIVE,
        "last_verified_at": now,
        "source_evidence": all_claims,
    })
    assert valid_active.scheme_status == SchemeStatus.ACTIVE

    # Active scheme missing a required claim
    with pytest.raises(ValidationError, match="must cover all required claims"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "scheme_status": SchemeStatus.ACTIVE,
            "last_verified_at": now,
            "source_evidence": all_claims[:-1],  # Drop operational_status
        })

    # Active scheme with an unverified claim
    unverified_claims = [all_claims[0], all_claims[1], all_claims[2], all_claims[3], all_claims[4], make_evidence(MaterialClaim.OPERATIONAL_STATUS, verified=False)]
    with pytest.raises(ValidationError, match="unverified claim"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "scheme_status": SchemeStatus.ACTIVE,
            "last_verified_at": now,
            "source_evidence": unverified_claims,
        })

    # Pending scheme must have null last_verified_at
    with pytest.raises(ValidationError, match="last_verified_at set to null"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "scheme_status": SchemeStatus.PENDING_VERIFICATION,
            "last_verified_at": now,
            "source_evidence": unverified_claims,
        })


def test_top_level_timestamp_validation_and_precedence():
    """Verify top-level timestamps: timezone-awareness, UTC zero-offset, future rejection, and precedence."""
    now_fixed = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)
    verified_fixed = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    def make_evidence(claim: MaterialClaim) -> Dict[str, Any]:
        return {
            "claim": claim.value,
            "statement": f"Statement for {claim.value}",
            "source_url": "https://pmkisan.gov.in/guidelines.pdf",
            "source_type": "guideline",
            "issuing_authority": "MoA&FW",
            "publication_date": "2024-01-01",
            "retrieved_at": now_fixed.isoformat(),
            "citation": "Official Circular",
            "verification_status": "verified",
            "verified_at": verified_fixed.isoformat(),
        }

    all_claims = [make_evidence(c) for c in MaterialClaim]

    base_scheme = {
        "scheme_code": "TEST-TIMESTAMP",
        "name": "Timestamp Test Scheme",
        "description": "Validating top-level timestamps with strict semantics",
        "ministry": "Ministry of Finance",
        "category": "social_security",
        "geographic_scope": "central",
        "target_beneficiaries": ["Citizens"],
        "benefits": "Rs 5000 pension",
        "source_url": "https://pmkisan.gov.in/guidelines.pdf",
        "scheme_status": "active",
        "source_evidence": all_claims,
    }

    # 1. Reject naive datetime for last_retrieved_at
    with pytest.raises(ValidationError, match="last_retrieved_at must be timezone-aware UTC with zero offset"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": datetime(2026, 11, 10, 10, 0),  # Naive
            "last_verified_at": verified_fixed,
        })

    # 2. Reject non-zero UTC offset for last_retrieved_at
    ist = timezone(timedelta(hours=5, minutes=30))
    with pytest.raises(ValidationError, match="last_retrieved_at must have zero UTC offset"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": datetime(2026, 11, 10, 15, 30, tzinfo=ist),
            "last_verified_at": verified_fixed,
        })

    # 3. Reject future last_retrieved_at
    future_time = datetime(2099, 1, 1, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="last_retrieved_at cannot be in the future"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": future_time,
            "last_verified_at": future_time,
        })

    # 4. Reject last_verified_at preceding last_retrieved_at
    with pytest.raises(ValidationError, match="last_verified_at cannot precede last_retrieved_at"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
            "last_verified_at": datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),  # Preceding
        })

    # 5. Reject last_verified_at preceding any verified evidence timestamp
    with pytest.raises(ValidationError, match="cannot precede verified evidence timestamp"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
            "last_verified_at": datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc),  # Evidence has 12:00
        })

    # 6. Reject future last_verified_at
    with pytest.raises(ValidationError, match="last_verified_at cannot be in the future"):
        SchemeSeedSchema.model_validate({
            **base_scheme,
            "last_retrieved_at": now_fixed,
            "last_verified_at": future_time,
        })



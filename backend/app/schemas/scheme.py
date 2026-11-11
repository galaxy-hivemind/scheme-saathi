"""
Pydantic schemas for Government Schemes, Source Evidence, and Catalogue APIs.
"""
from datetime import date, datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Set, Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ALLOWED_DOMAINS: Set[str] = {
    "gov.in",
    "nic.in",
    "pfrda.org.in",
    "nha.gov.in",
    "uidai.gov.in",
}


class SchemeCategory(str, Enum):
    AGRICULTURE = "agriculture"
    EDUCATION = "education"
    HEALTH = "health"
    HOUSING = "housing"
    EMPLOYMENT = "employment"
    WOMEN_WELFARE = "women_welfare"
    CHILDREN_WELFARE = "children_welfare"
    SENIOR_CITIZENS = "senior_citizens"
    DISABILITY = "disability"
    FINANCIAL_INCLUSION = "financial_inclusion"
    SOCIAL_SECURITY = "social_security"
    SKILL_DEVELOPMENT = "skill_development"


class SchemeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"


class MaterialClaim(str, Enum):
    NAME_AND_MINISTRY = "name_and_ministry"
    CATEGORY_AND_SCOPE = "category_and_scope"
    TARGET_BENEFICIARIES = "target_beneficiaries"
    BENEFITS = "benefits"
    OFFICIAL_AND_APPLICATION_URLS = "official_and_application_urls"
    OPERATIONAL_STATUS = "operational_status"


class SourceType(str, Enum):
    NOTIFICATION = "notification"
    GUIDELINE = "guideline"
    CIRCULAR = "circular"
    PIB_RELEASE = "pib_release"
    GAZETTE = "gazette"
    GOVERNMENT_PORTAL = "government_portal"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    OUTDATED = "outdated"


class SourceEvidenceEntry(BaseModel):
    claim: MaterialClaim
    statement: str = Field(..., min_length=5)
    source_url: HttpUrl
    source_type: SourceType
    issuing_authority: str = Field(..., min_length=2)
    publication_date: Optional[date] = None
    retrieved_at: datetime
    citation: str = Field(..., min_length=3)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_evidence(self) -> "SourceEvidenceEntry":
        now_utc = datetime.now(timezone.utc)

        # 1. Enforce HTTPS
        if self.source_url.scheme != "https":
            raise ValueError(f"Source URL must use HTTPS: {self.source_url}")

        # 2. Enforce Approved Government Domain
        host = self.source_url.host.lower() if self.source_url.host else ""
        domain_valid = any(
            host == allowed or host.endswith(f".{allowed}")
            for allowed in ALLOWED_DOMAINS
        )
        if not domain_valid:
            raise ValueError(f"Host '{host}' is not in approved government domain allowlist")

        # 3. Enforce Timezone-Aware UTC Timestamps with Zero Offset
        if self.retrieved_at.tzinfo != timezone.utc:
            raise ValueError("retrieved_at must be timezone-aware UTC with zero offset")
        if self.retrieved_at > now_utc:
            raise ValueError("retrieved_at cannot be in the future")

        # 4. Enforce Publication Date Semantics
        if self.publication_date and self.publication_date > self.retrieved_at.date():
            raise ValueError("publication_date cannot be in the future relative to retrieved_at")

        # 5. Enforce Verification Status Semantics
        if self.verification_status == VerificationStatus.VERIFIED:
            if self.verified_at is None:
                raise ValueError("verified_at is mandatory when verification_status is 'verified'")
            if self.verified_at.tzinfo != timezone.utc:
                raise ValueError("verified_at must be timezone-aware UTC with zero offset")
            if self.verified_at > now_utc:
                raise ValueError("verified_at cannot be in the future")
            if self.verified_at < self.retrieved_at:
                raise ValueError("verified_at cannot precede retrieved_at")
        else:
            if self.verified_at is not None:
                raise ValueError("verified_at must be null when verification_status is not 'verified'")

        return self


# Seed JSON validation schemas
class SchemeSeedDocument(BaseModel):
    document_type: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    is_mandatory: bool = True
    alternatives: Optional[List[str]] = None
    issuing_authority: Optional[str] = None
    guidance: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    last_verified_at: Optional[datetime] = None


class SchemeSeedSchema(BaseModel):
    scheme_code: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=255)
    short_title: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=10)
    ministry: str = Field(..., min_length=2, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    category: SchemeCategory
    geographic_scope: Literal["central"] = "central"
    target_beneficiaries: List[str] = Field(..., min_length=1)
    benefits: str = Field(..., min_length=5)
    official_url: Optional[HttpUrl] = None
    application_url: Optional[HttpUrl] = None
    source_url: HttpUrl
    scheme_status: SchemeStatus
    last_retrieved_at: datetime
    last_verified_at: Optional[datetime] = None
    source_evidence: List[SourceEvidenceEntry] = Field(..., min_length=1)
    eligibility_criteria: Optional[Dict[str, Any]] = None
    required_documents: List[SchemeSeedDocument] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_seed(self) -> "SchemeSeedSchema":
        now_utc = datetime.now(timezone.utc)

        # 1. Enforce timezone-aware UTC with zero offset for top-level last_retrieved_at
        if self.last_retrieved_at.tzinfo is None:
            raise ValueError("last_retrieved_at must be timezone-aware UTC with zero offset")
        if self.last_retrieved_at.utcoffset() != timedelta(0):
            raise ValueError("last_retrieved_at must have zero UTC offset")
        if self.last_retrieved_at > now_utc:
            raise ValueError("last_retrieved_at cannot be in the future")

        # 2. Enforce top-level last_verified_at semantics
        if self.last_verified_at is not None:
            if self.last_verified_at.tzinfo is None:
                raise ValueError("last_verified_at must be timezone-aware UTC with zero offset")
            if self.last_verified_at.utcoffset() != timedelta(0):
                raise ValueError("last_verified_at must have zero UTC offset")
            if self.last_verified_at > now_utc:
                raise ValueError("last_verified_at cannot be in the future")
            if self.last_verified_at < self.last_retrieved_at:
                raise ValueError("last_verified_at cannot precede last_retrieved_at")

            for evidence in self.source_evidence:
                if evidence.verification_status == VerificationStatus.VERIFIED and evidence.verified_at:
                    if self.last_verified_at < evidence.verified_at:
                        raise ValueError(
                            f"last_verified_at ({self.last_verified_at.isoformat()}) cannot precede "
                            f"verified evidence timestamp ({evidence.verified_at.isoformat()}) "
                            f"for claim '{evidence.claim.value}'"
                        )

        # 3. Enforce distinct material claims
        claims_seen = set()
        for evidence in self.source_evidence:
            if evidence.claim in claims_seen:
                raise ValueError(f"Duplicate evidence entry for claim: {evidence.claim}")
            claims_seen.add(evidence.claim)

        # 4. Enforce active scheme standard
        all_required_claims = {
            MaterialClaim.NAME_AND_MINISTRY,
            MaterialClaim.CATEGORY_AND_SCOPE,
            MaterialClaim.TARGET_BENEFICIARIES,
            MaterialClaim.BENEFITS,
            MaterialClaim.OFFICIAL_AND_APPLICATION_URLS,
            MaterialClaim.OPERATIONAL_STATUS,
        }

        if self.scheme_status == SchemeStatus.ACTIVE:
            missing_claims = all_required_claims - claims_seen
            if missing_claims:
                raise ValueError(f"Active scheme must cover all required claims. Missing: {missing_claims}")
            for evidence in self.source_evidence:
                if evidence.verification_status != VerificationStatus.VERIFIED:
                    raise ValueError(f"Active scheme has unverified claim: {evidence.claim}")
            if self.last_verified_at is None:
                raise ValueError("Active scheme must have a non-null last_verified_at timestamp")
        else:
            if self.last_verified_at is not None:
                raise ValueError("Pending or inactive scheme must have last_verified_at set to null")

        return self


# API Response Schemas
class SchemeSummaryResponse(BaseModel):
    id: uuid.UUID
    scheme_code: str
    name: str
    short_title: Optional[str] = None
    ministry: str
    category: str
    geographic_scope: str
    scheme_status: str

    model_config = ConfigDict(from_attributes=True)


class SchemeListResponse(BaseModel):
    items: List[SchemeSummaryResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class SchemeDocumentResponse(BaseModel):
    id: uuid.UUID
    document_type: str
    title: str
    description: Optional[str] = None
    is_mandatory: bool
    alternatives: Optional[List[str]] = None
    issuing_authority: Optional[str] = None
    guidance: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SchemeDetailResponse(BaseModel):
    id: uuid.UUID
    scheme_code: str
    name: str
    short_title: Optional[str] = None
    description: str
    ministry: str
    department: Optional[str] = None
    category: str
    geographic_scope: str
    target_beneficiaries: List[str]
    benefits: str
    official_url: Optional[str] = None
    application_url: Optional[str] = None
    source_url: str
    scheme_status: str
    last_retrieved_at: datetime
    last_verified_at: Optional[datetime] = None
    source_evidence: List[SourceEvidenceEntry]
    required_documents: List[SchemeDocumentResponse] = Field(default_factory=list)
    documents: List[SchemeDocumentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


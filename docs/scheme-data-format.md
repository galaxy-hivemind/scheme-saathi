# Scheme Saathi — Government Scheme Data Format

This document defines the canonical JSON format for government scheme seed files stored in `backend/data/schemes/`.

The single source of truth for schema validation is the Pydantic model `SchemeSeedSchema` defined in [`backend/app/schemas/scheme.py`](file:///Users/ayush_karmore_/SCHEME-SAATHI/backend/app/schemas/scheme.py).

---

## 1. File Naming Convention

```
backend/data/schemes/<scheme_slug>.json
```

Examples:
- `backend/data/schemes/pm-kisan.json`
- `backend/data/schemes/pmay-u.json`
- `backend/data/schemes/ab-pmjay.json`
- `backend/data/schemes/pm-svanidhi.json`
- `backend/data/schemes/pmuy.json`
- `backend/data/schemes/apy.json`
- `backend/data/schemes/pmkvy.json`

---

## 2. Canonical Scheme Schema Specification

### Top-Level Fields (`SchemeSeedSchema`)

| Field | Type | Required | Description |
|---|---|---|---|
| `scheme_code` | `str` (2-100 chars) | Yes | Uppercase unique identifier (e.g. `"PM-KISAN"`) |
| `name` | `str` (2-255 chars) | Yes | Official scheme title |
| `short_title` | `str` (max 100 chars) | No | Short name or acronym (e.g. `"PM-KISAN"`) |
| `description` | `str` (min 10 chars) | Yes | Detailed scheme description |
| `ministry` | `str` (2-255 chars) | Yes | Governing ministry |
| `department` | `str` (max 255 chars) | No | Governing department |
| `category` | `SchemeCategory` enum | Yes | One of the 12 canonical categories (see below) |
| `geographic_scope` | `"central"` | Yes | Fixed literal `"central"` |
| `target_beneficiaries` | `List[str]` | Yes | Beneficiary group identifiers (min 1) |
| `benefits` | `str` (min 5 chars) | Yes | Detailed financial or material benefits summary |
| `official_url` | `HttpUrl` | No | Official government portal URL |
| `application_url` | `HttpUrl` | No | Online registration / application portal URL |
| `source_url` | `HttpUrl` | Yes | Primary source URL (must use HTTPS on approved government domain) |
| `scheme_status` | `SchemeStatus` enum | Yes | `"active"`, `"inactive"`, or `"pending_verification"` |
| `last_retrieved_at` | ISO 8601 UTC `datetime` | Yes | Timestamp of official document retrieval (timezone-aware UTC, zero offset, not future) |
| `last_verified_at` | ISO 8601 UTC `datetime` | Conditional | Timestamp of human/editorial verification (required for `"active"`, must be `null` for `"pending_verification"` or `"inactive"`) |
| `source_evidence` | `List[SourceEvidenceEntry]` | Yes | List of claim-level evidence records (must cover all 6 material claims for `"active"`) |
| `eligibility_criteria` | `Optional[Dict[str, Any]]` | No | Evaluator AST dict containing `all`/`any` combinators, conditions, and provisional flags |
| `required_documents` | `List[SchemeSeedDocument]` | Yes | List of required citizen documents |

---

### Enums & Domain Constants

#### 1. Canonical Categories (`SchemeCategory`)
`"agriculture"`, `"education"`, `"health"`, `"housing"`, `"employment"`, `"women_welfare"`, `"children_welfare"`, `"senior_citizens"`, `"disability"`, `"financial_inclusion"`, `"social_security"`, `"skill_development"`.

#### 2. Scheme Status (`SchemeStatus`)
- `"active"`: Fully substantiated with verified 2026 evidence covering all 6 material claims; non-null `last_verified_at`.
- `"pending_verification"`: Incomplete or unverified evidence; `last_verified_at` must be `null`.
- `"inactive"`: Discontinued or superseded schemes; `last_verified_at` must be `null`.

#### 3. Material Claims (`MaterialClaim`)
Active schemes must substantiate all 6 required claims:
1. `"name_and_ministry"`
2. `"category_and_scope"`
3. `"target_beneficiaries"`
4. `"benefits"`
5. `"official_and_application_urls"`
6. `"operational_status"`

#### 4. Source Types (`SourceType`)
`"notification"`, `"guideline"`, `"circular"`, `"pib_release"`, `"gazette"`, `"government_portal"`.

#### 5. Verification Status (`VerificationStatus`)
`"verified"`, `"unverified"`, `"outdated"`.

#### 6. Approved Government Domains
Source URLs must be HTTPS endpoints hosted on:
`.gov.in`, `.nic.in`, `pfrda.org.in`, `nha.gov.in`, `uidai.gov.in`.

---

### Source Evidence Entry (`SourceEvidenceEntry`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `claim` | `MaterialClaim` | Yes | One of the 6 canonical material claim identifiers |
| `statement` | `str` (min 5 chars) | Yes | Factual assertion being supported |
| `source_url` | `HttpUrl` | Yes | HTTPS URL on approved government domain |
| `source_type` | `SourceType` | Yes | Type of government publication |
| `issuing_authority` | `str` (min 2 chars) | Yes | Name of government department or ministry |
| `publication_date` | `date` (`YYYY-MM-DD`) | No | Publication date of the document |
| `retrieved_at` | ISO 8601 UTC `datetime` | Yes | Timezone-aware UTC retrieval timestamp (zero offset) |
| `citation` | `str` (min 3 chars) | Yes | Exact paragraph, clause, or section citation |
| `verification_status` | `VerificationStatus` | Yes | Default: `"unverified"` |
| `verified_at` | ISO 8601 UTC `datetime` | Conditional | Required if `verification_status == "verified"`; must be `null` otherwise |

---

### Scheme Document Requirement (`SchemeSeedDocument`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `document_type` | `str` (2-50 chars) | Yes | Canonical document key (e.g. `"aadhaar"`, `"land_records"`) |
| `title` | `str` (2-255 chars) | Yes | Human-readable document name |
| `description` | `str` | No | Clarification of document purpose |
| `is_mandatory` | `bool` | Yes | Default: `true` |
| `alternatives` | `List[str]` | No | Permitted substitute documents |
| `issuing_authority` | `str` | No | Authority issuing the document |
| `guidance` | `str` | No | Procurement instructions for citizens |
| `source_url` | `HttpUrl` | No | Document verification guidelines URL |
| `last_verified_at` | ISO 8601 UTC `datetime` | No | Document verification timestamp |

---

## 3. Authoritative vs. Provisional Eligibility Rules

In Phase 2, eligibility criteria AST definitions are stored in `eligibility_criteria` (JSONB) on the `SchemeRuleVersion` model.

- **Authoritative Rules:** Only established when official guidelines or notifications define explicit statutory conditions. The dictionary specifies `"is_authoritative": true`, `"is_provisional": false`, and documents known limitations.
- **Provisional Rules:** When complete official operational criteria cannot be fully verified, the dictionary specifies `"is_authoritative": false`, `"is_provisional": true`, and documents the specific limitations.
- **Omission:** If criteria cannot be verified at all, `eligibility_criteria` is set to `null`, and no rule version is generated.

---

## 4. Complete Valid Seed Example (`pm-kisan.json`)

The following is a complete, valid seed file directly verified against `SchemeSeedSchema.model_validate()`:

```json
{
  "scheme_code": "PM-KISAN",
  "name": "Pradhan Mantri Kisan Samman Nidhi",
  "short_title": "PM-KISAN",
  "description": "A Central Sector Scheme to provide income support to all landholding farmer families across India to help them meet agricultural and domestic needs.",
  "ministry": "Ministry of Agriculture and Farmers Welfare",
  "department": "Department of Agriculture and Farmers Welfare",
  "category": "agriculture",
  "geographic_scope": "central",
  "target_beneficiaries": [
    "Small and marginal farmer families",
    "Landholding farmers"
  ],
  "benefits": "Financial benefit of Rs. 6,000 per year payable in three equal instalments of Rs. 2,000 every four months, credited directly into Aadhaar-seeded bank accounts through DBT.",
  "official_url": "https://pmkisan.gov.in/",
  "application_url": "https://pmkisan.gov.in/registrationform.aspx",
  "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
  "scheme_status": "active",
  "last_retrieved_at": "2026-11-10T10:00:00Z",
  "last_verified_at": "2026-11-10T12:00:00Z",
  "source_evidence": [
    {
      "claim": "name_and_ministry",
      "statement": "Administered by the Department of Agriculture and Farmers Welfare, Ministry of Agriculture and Farmers Welfare.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
      "source_type": "guideline",
      "issuing_authority": "Ministry of Agriculture and Farmers Welfare",
      "publication_date": "2024-02-01",
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "Chapter 1, Clause 1.1",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    },
    {
      "claim": "category_and_scope",
      "statement": "Central sector scheme covering all agricultural landholding families across India.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
      "source_type": "guideline",
      "issuing_authority": "Ministry of Agriculture and Farmers Welfare",
      "publication_date": "2024-02-01",
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "Chapter 1, Clause 1.2",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    },
    {
      "claim": "target_beneficiaries",
      "statement": "All landholding farmer families having cultivable landholding in their names.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
      "source_type": "guideline",
      "issuing_authority": "Ministry of Agriculture and Farmers Welfare",
      "publication_date": "2024-02-01",
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "Chapter 2, Clause 2.1",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    },
    {
      "claim": "benefits",
      "statement": "Rs. 6,000 per year transferred in three equal instalments of Rs. 2,000 via DBT into Aadhaar-seeded bank accounts.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
      "source_type": "guideline",
      "issuing_authority": "Ministry of Agriculture and Farmers Welfare",
      "publication_date": "2024-02-01",
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "Chapter 2, Clause 2.1",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    },
    {
      "claim": "official_and_application_urls",
      "statement": "Official portal and online self-registration for farmers hosted on pmkisan.gov.in.",
      "source_url": "https://pmkisan.gov.in/",
      "source_type": "government_portal",
      "issuing_authority": "Ministry of Agriculture and Farmers Welfare",
      "publication_date": null,
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "Homepage Farmers Corner",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    },
    {
      "claim": "operational_status",
      "statement": "24th installment released on 30 October 2026 from Banaskantha, Gujarat, disbursing over Rs. 18,690 crore to more than 9.34 crore farmer families.",
      "source_url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2330414",
      "source_type": "pib_release",
      "issuing_authority": "Press Information Bureau",
      "publication_date": "2026-10-30",
      "retrieved_at": "2026-11-10T10:00:00Z",
      "citation": "PIB Press Release PRID 2330414",
      "verification_status": "verified",
      "verified_at": "2026-11-10T12:00:00Z"
    }
  ],
  "eligibility_criteria": {
    "is_authoritative": true,
    "is_provisional": false,
    "limitations": "Core statutory eligibility conditions verified from Operational Guidelines; detailed exclusion categories (e.g. constitutional posts, institutional landholders) defined per guidelines.",
    "all": [
      {
        "field": "is_landholding_farmer",
        "operator": "equals",
        "value": true
      },
      {
        "field": "is_institutional_landholder",
        "operator": "equals",
        "value": false
      },
      {
        "field": "is_income_tax_payer",
        "operator": "equals",
        "value": false
      }
    ]
  },
  "required_documents": [
    {
      "document_type": "aadhaar",
      "title": "Aadhaar Card",
      "description": "UIDAI Aadhaar card for citizen identity and biometric e-KYC verification.",
      "is_mandatory": true,
      "alternatives": [],
      "issuing_authority": "UIDAI",
      "guidance": "Link Aadhaar with active bank account and verify mobile number for OTP.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf"
    },
    {
      "document_type": "land_records",
      "title": "Land Ownership Records (Khatauni/Patta)",
      "description": "Official land record extract demonstrating cultivable land title in beneficiary name.",
      "is_mandatory": true,
      "alternatives": ["Record of Rights (RoR)", "Mutation Extract"],
      "issuing_authority": "State Revenue Department",
      "guidance": "Obtain certified copy from state revenue Bhulekh portal or local Tehsildar.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf"
    },
    {
      "document_type": "bank_passbook",
      "title": "Bank Passbook or Account Details",
      "description": "Copy of bank passbook or cancelled cheque showing IFSC and NPCI-mapped account.",
      "is_mandatory": true,
      "alternatives": ["Bank Account Statement"],
      "issuing_authority": "Scheduled Commercial Bank / Post Office",
      "guidance": "Ensure account is Aadhaar-seeded via NPCI mapper for Direct Benefit Transfer.",
      "source_url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf"
    }
  ]
}
```

---

## 5. Seed Importer CLI Usage

The seed importer (`backend/app/scripts/seed_schemes.py`) synchronizes the JSON catalogue files into PostgreSQL:

```bash
python -m app.scripts.seed_schemes [--data-dir DIR] [--dry-run] [--allow-override-verified]
```

- `--dry-run`: Performs complete in-memory pre-validation and database comparison with **zero DML statements executed**.
- `--allow-override-verified`: Required to reconcile any verified/active scheme if differences are detected across its metadata, rules, or documents. Without this flag, conflicting verified schemes are skipped at the aggregate level.
- **Append-Only Rule Versions:** When incoming `eligibility_criteria` differs from the current active rule version, the previous version's `effective_to` timestamp is closed, and a new version incremented by 1 is appended.
- **Soft Document Deactivation:** Documents omitted from seed files are marked `is_active = FALSE` rather than deleted, preserving relational consistency with citizen application records.

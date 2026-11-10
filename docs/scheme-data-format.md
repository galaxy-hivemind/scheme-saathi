# Scheme Saathi — Government Scheme Data Format

This document defines the authoritative JSON format for government scheme seed files stored in `backend/data/schemes/`, along with claim-level evidence verification requirements and the CLI seed importer specification.

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

## 2. Seed JSON Schema Structure

Each scheme JSON file conforms to the Pydantic schema `SchemeSeedSchema` defined in `backend/app/schemas/scheme.py`:

```json
{
  "scheme_code": "PM-KISAN",
  "name": "Pradhan Mantri Kisan Samman Nidhi",
  "description": "Central sector scheme providing income support of Rs. 6,000 per year to all landholding farmer families.",
  "ministry": "Ministry of Agriculture and Farmers Welfare",
  "category": "agriculture",
  "benefits": "₹6,000 per year paid in three equal instalments of ₹2,000 directly into the bank accounts of eligible farmer families.",
  "target_beneficiaries": [
    "farmer_families",
    "small_farmers",
    "marginal_farmers"
  ],
  "geographic_scope": "central",
  "official_url": "https://pmkisan.gov.in/",
  "application_url": "https://pmkisan.gov.in/RegistrationFormNew.aspx",
  "source_url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2330414",
  "source_evidence": [
    {
      "claim": "scheme_existence",
      "source_type": "official_portal",
      "source_url": "https://pmkisan.gov.in/",
      "title": "PM Kisan Samman Nidhi Official Portal",
      "reference_number": null,
      "published_date": "2019-02-01",
      "retrieved_at": "2026-11-10T21:40:00Z",
      "verification_status": "verified",
      "verified_at": "2026-11-10T21:40:00Z",
      "verified_by": "editorial_team",
      "excerpt": "Under the Scheme, the entire financial liability towards transfer of benefit to eligible beneficiaries is borne by the Government of India."
    }
  ],
  "last_retrieved_at": "2026-11-10T21:40:00Z",
  "last_verified_at": "2026-11-10T21:40:00Z",
  "scheme_status": "active",

  "eligibility_rules": {
    "all": [
      {
        "field": "occupation",
        "operator": "in",
        "value": ["farmer", "agriculture"]
      },
      {
        "field": "land_holding_acres",
        "operator": "greater_than",
        "value": 0
      }
    ]
  },

  "required_documents": [
    {
      "document_type": "aadhaar",
      "is_mandatory": true,
      "guidance": "Aadhaar number seeded with bank account is mandatory for PM-KISAN DBT transfers.",
      "source_url": "https://pmkisan.gov.in/",
      "last_verified_at": "2026-11-10T21:40:00Z"
    }
  ]
}
```

---

## 3. Claim-Level Evidence Manifest (`source_evidence`)

To prevent hallucinations, unverified assertions, or stale administrative claims, every scheme includes a `source_evidence` array with atomic, verifiable entries:

### 3.1 Material Claims (`claim`)
Every `active` scheme must substantiate all 6 required material claims:
1. `scheme_existence` — Official inception, portal, or governing gazette notification.
2. `operational_status` — Confirmation of active operational status in the current fiscal year.
3. `benefit_structure` — Financial or material benefit amounts, frequencies, and disbursement mechanisms.
4. `eligibility_criteria` — Precise statutory conditions for qualifying beneficiaries.
5. `documentation_requirements` — Verifiable proof and document types required to apply.
6. `application_channel` — Official portal or physical points of registration.

### 3.2 Source Types (`source_type`)
Allowed values:
- `official_gazette` — Gazette of India notifications
- `ministry_notification` — Official circulars or notifications
- `operational_guidelines` — Standard operating procedures and published guidelines
- `official_portal` — Official `.gov.in` / `.nic.in` web applications
- `pib_release` — Press Information Bureau releases (`pib.gov.in`)
- `parliamentary_qa` — Lok Sabha / Rajya Sabha parliamentary Q&A (`sansad.in`)

### 3.3 Domain Allowlist & URL Rules
All source URLs must:
- Use `https://`.
- Come from trusted government domains: `.gov.in`, `.nic.in`, `pib.gov.in`, `sansad.in`, or `egazette.gov.in`.

### 3.4 Timestamp Integrity
- `published_date`: ISO date `YYYY-MM-DD` (cannot be in the future).
- `retrieved_at`: ISO 8601 UTC timestamp with explicit `Z` or `+00:00` offset (must be on or after `published_date`).
- `verified_at`: ISO 8601 UTC timestamp (only present when `verification_status == 'verified'`; must be on or after `retrieved_at`).

---

## 4. Active vs. Pending Verification Standards

### Active Status (`active`)
A scheme may only be marked `active` if:
1. All 6 material claims are substantiated in `source_evidence`.
2. Every evidence entry has `verification_status = "verified"` and non-null `verified_at`.
3. `last_verified_at` is populated and equals or exceeds the latest evidence `verified_at`.
4. Operational activity in 2026 is verified via official documentation.

### Pending Verification Status (`pending_verification`)
If any material claim cannot be independently confirmed with 2026 operational evidence, the scheme:
- Must have `scheme_status = "pending_verification"`.
- Must have `last_verified_at = null`.
- Is hidden from regular citizen search (`GET /api/v1/schemes`) unless requested via `?include_pending=true`.

---

## 5. Seed Importer CLI (`seed_schemes.py`)

The catalogue is populated using the administrative seed importer script:

```bash
python -m app.scripts.seed_schemes [--data-dir DIR] [--dry-run] [--allow-override-verified]
```

### Flags & Safety Guarantees:
- `--data-dir PATH`: Directory containing scheme JSON files (defaults to `backend/data/schemes`).
- `--dry-run`: Performs complete in-memory Pydantic validation and database comparisons, outputs a structured plan of proposed inserts and updates, and guarantees **zero database modifications** (verified via SQL DML listener).
- `--allow-override-verified`: By default, the importer refuses to silently overwrite existing schemes with `scheme_status = 'active'`. If a verified scheme differs, the importer reports a conflict and skips the entire aggregate. Passing `--allow-override-verified` permits controlled updates.
- **Append-Only Rule Versions:** When an incoming rule payload differs from the current active version, the existing active version's `effective_to` timestamp is closed, and a new version incremented by 1 is appended.
- **Soft Document Deactivation:** Documents present in the database but omitted from the seed file are marked `is_active = FALSE`, preserving foreign key references and application history.
- **Atomic Transaction:** Seeding executes in a single database transaction and rolls back cleanly on error.

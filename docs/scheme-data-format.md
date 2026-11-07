# Scheme Saathi — Government Scheme Data Format

This document defines the JSON format for scheme seed files stored in `backend/data/schemes/`.

---

## File naming convention

```
backend/data/schemes/<scheme_code>.json
```

Example: `backend/data/schemes/pm-kisan.json`

---

## Full scheme JSON schema

```json
{
  "scheme_code": "PM-KISAN",
  "name": "Pradhan Mantri Kisan Samman Nidhi",
  "description": "...",
  "ministry": "Ministry of Agriculture and Farmers Welfare",
  "category": "agriculture",
  "benefits": "Rs. 6000 per year in three instalments of Rs. 2000 each.",
  "target_beneficiaries": "Small and marginal farmer families.",
  "geographic_scope": "central",
  "official_url": "https://pmkisan.gov.in/",
  "application_url": "https://pmkisan.gov.in/registrationform.aspx",
  "source_url": "https://pmkisan.gov.in/",
  "last_retrieved_at": "2026-11-07",
  "last_verified_at": "2026-11-07",
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
        "operator": "less_than_or_equal",
        "value": 2
      }
    ]
  },

  "required_documents": [
    {
      "document_type": "aadhaar",
      "is_mandatory": true,
      "guidance": "Aadhaar card issued by UIDAI.",
      "source_url": "https://uidai.gov.in/"
    },
    {
      "document_type": "bank_passbook",
      "is_mandatory": true,
      "guidance": "Bank passbook or cancelled cheque for account verification."
    },
    {
      "document_type": "land_records",
      "is_mandatory": true,
      "guidance": "Land ownership document (Khatauni/Patta) from local revenue office."
    }
  ]
}
```

---

## Eligibility rule operators

| Operator | Meaning |
|---|---|
| `equals` | field == value |
| `not_equals` | field != value |
| `greater_than` | field > value |
| `greater_than_or_equal` | field >= value |
| `less_than` | field < value |
| `less_than_or_equal` | field <= value |
| `in` | field is one of [value list] |
| `not_in` | field is not in [value list] |
| `exists` | field is present and not null |

## Rule combinators

| Key | Meaning |
|---|---|
| `all` | All child conditions must pass (AND) |
| `any` | At least one child condition must pass (OR) |
| `not` | Condition must fail (NOT) |

---

## Scheme categories

Use these standard category strings:
- `agriculture`
- `education`
- `health`
- `housing`
- `employment`
- `women_welfare`
- `children_welfare`
- `senior_citizens`
- `disability`
- `financial_inclusion`
- `social_security`
- `skill_development`

---

## Important rules for scheme data

1. **Official sources only.** Use data from `myscheme.gov.in`, official ministry pages, or scheme portals.
2. **Never invent eligibility criteria.** Only encode rules you can verify from official sources.
3. **Source everything.** Every scheme file must have `source_url`, `last_retrieved_at`, and `last_verified_at`.
4. **Mark unverified data.** Use `scheme_status: "pending_verification"` until a team member has verified the content.
5. **Keep rule JSON simple.** Prefer flat `all` lists over deeply nested conditions.
6. **Illustrative data.** The PM-KISAN example above is illustrative only — verify all values before seeding.

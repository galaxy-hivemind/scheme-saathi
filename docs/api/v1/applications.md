# Application Drafts & Portal Handoff API Contract (v1)

## Overview

The Application Drafts module enables citizens to prepare welfare scheme applications in advance. It automatically snapshots verified demographics, links uploaded documents from the readiness checklist, evaluates rule-based eligibility, provides official government portal handoff instructions, and tracks external submission reference numbers.

### Security Architecture & Invariants

1. **Zero Automated Model Submissions:** Neither the AI model nor backend background tasks submit applications autonomously to external government portals. The citizen retains full agency.
2. **Snapshot Integrity (No Demographic Fabrication):** Staged drafts capture demographic values directly from `UserProfile` (for self) or `BeneficiaryProfile` (for family members). Unspecified attributes remain `None`; approximate age is never fabricated into an exact date of birth.
3. **State Machine Integrity:** Status transitions follow strict lifecycle gates:
   - `DRAFT`: Initial draft when one or more mandatory documents are missing.
   - `READY`: All mandatory scheme documents are attached and applicant is prepared for portal submission.
   - `SUBMITTED`: Citizen has submitted on the external portal and recorded their government acknowledgement reference number. Updates to submitted drafts are rejected with HTTP 422.
   - `ARCHIVED`: Closed or obsolete draft.
4. **Anti-IDOR Protection:** All draft retrieval, modification, submission recording, and deletion endpoints enforce ownership matching `user_id == current_user.id`.

---

## Endpoints

### 1. Create Application Draft
`POST /api/v1/applications/draft`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body (`ApplicationDraftCreate`):**
```json
{
  "scheme_id": "b3c2d1e0-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
  "beneficiary_id": null,
  "notes": "Preparing application for PM-KISAN 24th instalment"
}
```

**Response (`201 Created`):**
```json
{
  "success": true,
  "data": {
    "id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
    "user_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "beneficiary_id": null,
    "scheme_id": "b3c2d1e0-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
    "scheme_code": "PM-KISAN",
    "scheme_name": "PM Kisan Samman Nidhi",
    "target_name": "Ramesh Kumar",
    "status": "READY",
    "prefilled_data": {
      "applicant_type": "self",
      "relationship": "self",
      "full_name": "Ramesh Kumar",
      "date_of_birth": "1985-05-20",
      "gender": "male",
      "state": "Bihar",
      "district": "Patna",
      "residence_type": "rural",
      "occupation": "farmer",
      "annual_family_income": 80000.0,
      "profile_data": {
        "bpl_card": true
      },
      "eligibility_snapshot": {
        "status": "PASS",
        "result": "eligible",
        "rule_version": 1,
        "missing_fields": [],
        "reasons": ["All criteria met"]
      }
    },
    "attached_documents": [
      {
        "document_type": "aadhaar",
        "title": "Aadhaar Card",
        "citizen_document_id": "e4b3c2d1-7a8b-4c9d-8e1f-2a3b4c5d6e7f",
        "file_name": "aadhaar.pdf",
        "verification_status": "PENDING",
        "is_mandatory": true
      }
    ],
    "official_portal_url": "https://pmkisan.gov.in/registration",
    "notes": "Preparing application for PM-KISAN 24th instalment",
    "external_reference_number": null,
    "submitted_at": null,
    "created_at": "2026-11-11T10:15:00Z",
    "updated_at": "2026-11-11T10:15:00Z"
  },
  "message": "Application draft prepared successfully."
}
```

---

### 2. List Application Drafts
`GET /api/v1/applications`

**Headers:** `Authorization: Bearer <jwt>`

**Query Parameters:**
- `status`: (Optional) Filter by status (`DRAFT`, `READY`, `SUBMITTED`, `ARCHIVED`)
- `scheme_id`: (Optional) Filter by scheme UUID

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "items": [ ... ],
    "total": 1
  }
}
```

---

### 3. Get Application Draft Details
`GET /api/v1/applications/{draft_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):** Returns `ApplicationDraftResponse`.

---

### 4. Update Application Draft
`PUT /api/v1/applications/{draft_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body (`ApplicationDraftUpdate`):**
```json
{
  "notes": "Verified survey number with Patwari",
  "prefilled_data": {
    "khasra_number": "142/3"
  }
}
```

**Response (`200 OK`):** Returns updated `ApplicationDraftResponse`. Note: Rejects edits to `SUBMITTED` drafts with HTTP 422.

---

### 5. Record External Submission
`POST /api/v1/applications/{draft_id}/submit`

**Headers:** `Authorization: Bearer <jwt>`

**Request Body (`ApplicationDraftSubmitRequest`):**
```json
{
  "external_reference_number": "PMKISAN/2026/7891234",
  "notes": "Submitted successfully at CSC Centre"
}
```

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
    "status": "SUBMITTED",
    "external_reference_number": "PMKISAN/2026/7891234",
    "submitted_at": "2026-11-11T10:30:00Z",
    ...
  },
  "message": "External application submission recorded successfully."
}
```

---

### 6. Delete Application Draft
`DELETE /api/v1/applications/{draft_id}`

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "deleted": true,
    "draft_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c"
  },
  "message": "Application draft deleted successfully."
}
```

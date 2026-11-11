# Application Status Tracking & Timeline Audit API Contract (v1)

## Overview

The Application Tracking module provides citizens with transparent, real-time lifecycle tracking of their welfare scheme applications. It maintains an append-only, immutable audit trail (`application_status_history`) documenting every state change, external government portal acknowledgement reference number, and administrative action.

### Security Architecture & Invariants

1. **Immutable Audit Trail:** Once written, historical status records in `application_status_history` cannot be updated or deleted. Every state transition is recorded chronologically.
2. **Deterministic Lifecycle States:** Status transitions conform to validated canonical lifecycle statuses:
   - `DRAFT`: In-progress draft preparation.
   - `READY`: All mandatory scheme documents and demographics assembled.
   - `SUBMITTED`: Citizen submitted application to the government portal and logged official reference ID.
   - `IN_REVIEW`: Department officer or portal verification underway.
   - `APPROVED`: Statutory eligibility confirmed and approved for benefit.
   - `REJECTED`: Application rejected with official remarks or reason.
   - `DISBURSED`: Welfare funds or direct benefit transfer (DBT) completed.
   - `ARCHIVED`: Obsolete or superseded application.
3. **Audited Source Tracking:** Each transition records its exact origin:
   - `user_reported`: Citizen reported progress or portal status.
   - `official_integration`: Verified backend API integration.
   - `portal_sync`: Government portal synchronization hook.
   - `admin_action`: Verified administrative or nodal officer action.
4. **Anti-IDOR Protection:** All timeline queries and status transitions enforce strict tenant isolation (`user_id == current_user.id`). Cross-tenant access is rejected with HTTP 403.
5. **Automatic Citizen Alert Trigger:** Every status transition automatically triggers a real-time notification alert to the citizen.

---

## Endpoints

### 1. Get Application Timeline
`GET /api/v1/tracking/{application_id}/timeline`

Retrieve the full chronological status history and tracking timeline for an application draft.

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
```json
{
  "application_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
  "scheme_id": "b3c2d1e0-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
  "scheme_name": "PM Kisan Samman Nidhi",
  "scheme_code": "PM-KISAN",
  "applicant_type": "self",
  "target_name": "Ramesh Kumar",
  "current_status": "IN_REVIEW",
  "external_reference_number": "PMK/2026/778899",
  "official_portal_url": "https://pmkisan.gov.in",
  "submitted_at": "2026-11-11T12:00:00Z",
  "history": [
    {
      "id": "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b",
      "application_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
      "status": "SUBMITTED",
      "source_type": "user_reported",
      "source_reference": "PMK/2026/778899",
      "notes": "Citizen recorded external portal submission.",
      "created_at": "2026-11-11T12:00:00Z"
    },
    {
      "id": "f2a3b4c5-d6e7-4f8a-9b0c-1d2e3f4a5b6c",
      "application_id": "f5a4b3c2-1d0e-4f8a-9b7c-3d2e1f0a9b8c",
      "status": "IN_REVIEW",
      "source_type": "portal_sync",
      "source_reference": "PMK/2026/778899",
      "notes": "Government department portal verified reference; application under departmental review.",
      "created_at": "2026-11-11T14:30:00Z"
    }
  ],
  "created_at": "2026-11-11T10:00:00Z",
  "updated_at": "2026-11-11T14:30:00Z"
}
```

---

### 2. Record Status Transition
`POST /api/v1/tracking/{application_id}/status`

Update application status, append an immutable history entry, and notify the citizen.

**Headers:** `Authorization: Bearer <jwt>`

**Request Body (`StatusTransitionCreate`):**
```json
{
  "status": "IN_REVIEW",
  "source_type": "official_integration",
  "source_reference": "PMK/2026/778899",
  "notes": "Under field verification by Tehsildar"
}
```

**Response (`200 OK`):**
Returns the updated `ApplicationTimelineResponse`.

---

### 3. Synchronize Portal Status
`POST /api/v1/tracking/{application_id}/sync`

Query official government portal using the citizen's external reference number and update the tracking timeline.

**Headers:** `Authorization: Bearer <jwt>`

**Response (`200 OK`):**
Returns the refreshed `ApplicationTimelineResponse`.

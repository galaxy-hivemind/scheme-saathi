# Scheme Saathi — API Contracts

**Status:** Draft v0.1 — to be finalized jointly by backend and frontend developers.

All endpoints are prefixed with `/api/v1/`.

---

## Standard response envelope

### Success
```json
{
  "success": true,
  "data": { },
  "error": null,
  "request_id": "uuid-v4"
}
```

### Error
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description.",
    "details": [
      { "field": "annual_family_income", "message": "Must be a positive number." }
    ]
  },
  "request_id": "uuid-v4"
}
```

**HTTP status codes used:**
- `200 OK` — success
- `201 Created` — resource created
- `400 Bad Request` — malformed request
- `401 Unauthorized` — missing or invalid JWT
- `403 Forbidden` — authenticated but not authorized
- `404 Not Found` — resource does not exist
- `409 Conflict` — duplicate resource
- `422 Unprocessable Entity` — validation error
- `429 Too Many Requests` — rate limit exceeded
- `500 Internal Server Error` — unexpected server error

---

## Authentication

All endpoints except `/health` and `/auth/*` require a valid JWT Bearer access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

---

## Shared TypeScript / Pydantic types

### UserProfile
```typescript
interface UserProfile {
  id: string;                      // UUID
  user_id: string;                 // UUID (foreign key to auth user)
  full_name: string;
  date_of_birth?: string;          // ISO 8601 date: "YYYY-MM-DD"
  state?: string;
  district?: string;
  residence_type?: "rural" | "urban" | "semi_urban";
  occupation?: string;
  annual_family_income?: number;   // INR
  preferred_language: "hi" | "en"; // default "hi"
  profile_data?: Record<string, unknown>; // scheme-specific extra fields
  created_at: string;              // ISO 8601 datetime
  updated_at: string;
}
```

### BeneficiaryProfile
```typescript
interface BeneficiaryProfile {
  id: string;                      // UUID
  user_id: string;                 // UUID (foreign key to auth user)
  full_name: string;
  relationship: "self" | "spouse" | "father" | "mother" | "son" | "daughter" | "sibling" | "grandfather" | "grandmother" | "grandson" | "granddaughter" | "other_dependent";
  date_of_birth?: string;          // ISO 8601 date: "YYYY-MM-DD"
  gender?: "male" | "female" | "transgender" | "other";
  caste_category?: "general" | "obc" | "sc" | "st" | "pvtg";
  residence_type?: "rural" | "urban" | "semi_urban";
  occupation?: string;
  annual_income?: number;          // INR
  is_differently_abled?: boolean;
  disability_percentage?: number;
  marital_status?: "never_married" | "married" | "widowed" | "divorced" | "separated";
  profile_data?: Record<string, unknown>; // scheme-specific extra fields
  created_at: string;              // ISO 8601 datetime
  updated_at: string;
}
```

### Scheme
```typescript
interface Scheme {
  id: string;
  scheme_code: string;
  name: string;
  description: string;
  ministry: string;
  category: string;
  benefits: string;
  target_beneficiaries: string;
  geographic_scope: "central" | "state";
  official_url: string;
  application_url?: string;
  source_url: string;
  last_retrieved_at: string;
  last_verified_at: string;
  scheme_status: "active" | "inactive" | "pending_verification";
}
```

### EligibilityResult
```typescript
interface EligibilityResult {
  scheme_id: string;
  scheme_code: string;
  scheme_name: string;
  beneficiary_id?: string;
  beneficiary_name?: string;
  beneficiary_relationship?: string;
  overall_status: "PASS" | "FAIL" | "UNKNOWN";
  result: "eligible" | "not_eligible" | "potentially_eligible" | "insufficient_information";
  eligible: boolean | null;
  rule_version_id: string;
  rule_version: number;
  is_authoritative: boolean;
  is_provisional: boolean;
  limitations?: string;
  condition_results: EligibilityConditionResult[];
  matched_conditions: EligibilityConditionResult[];
  failed_conditions: EligibilityConditionResult[];
  unknown_conditions: EligibilityConditionResult[];
  missing_fields: string[];
  next_questions: EligibilityQuestion[];
  explanation: string;
  evaluated_at: string;
}
```

### EligibilityConditionResult
```typescript
interface EligibilityConditionResult {
  field: string;
  operator: string;
  expected_value: unknown;
  actual_value: unknown;
  passed: boolean | null;  // null = unknown (missing data)
  explanation: string;
}
```

### DocumentRequirement
```typescript
interface DocumentRequirement {
  id: string;
  scheme_id: string;
  document_type: string;
  is_mandatory: boolean;
  guidance?: string;
  source_url?: string;
  last_verified_at?: string;
}
```

### UserDocument
```typescript
interface UserDocument {
  id: string;
  user_id: string;
  document_type: string;
  upload_status: "pending" | "uploaded" | "failed";
  ocr_status?: "pending" | "processing" | "completed" | "failed" | "not_applicable";
  review_status?: "pending_review" | "accepted" | "rejected";
  created_at: string;
  updated_at: string;
}
```

### ApplicationDraft
```typescript
interface ApplicationDraft {
  id: string;
  user_id: string;
  scheme_id: string;
  form_data: Record<string, unknown>;
  lifecycle_state: "draft" | "validated" | "awaiting_confirmation" | "submitted" | "validation_failed" | "submission_failed" | "cancelled";
  validation_result?: ValidationResult;
  reference_number?: string;
  created_at: string;
  updated_at: string;
}
```

### ValidationResult
```typescript
interface ValidationResult {
  passed: boolean;
  errors: Array<{ field: string; message: string }>;
  warnings: Array<{ field: string; message: string }>;
}
```

### ApplicationStatus
```typescript
interface ApplicationStatus {
  application_id: string;
  status: string;
  source_type: "official_integration" | "user_reported" | "simulated_demo";
  source_reference?: string;
  notes?: string;
  recorded_at: string;
}
```

### ChatMessage
```typescript
interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  message_content: string;
  response_type?: "text" | "scheme_cards" | "eligibility_result" | "document_checklist" | "application_draft" | "confirmation_request" | "tracking_update";
  created_at: string;
}
```

### AgentResponse
```typescript
interface AgentResponse {
  conversation_id: string;
  message: string;
  response_type: ChatMessage["response_type"];
  data?: unknown;      // typed per response_type
  requires_action?: boolean;
  action_type?: "confirm_submission" | "upload_document" | "complete_profile";
}
```

### Notification
```typescript
interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  read_at?: string;
  created_at: string;
}
```

### APIError
```typescript
interface APIError {
  code: string;
  message: string;
  details: Array<{ field?: string; message: string }>;
}
```

---

## Endpoints

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health check |

---

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | None | Register new citizen account & create profile |
| POST | `/auth/login` | None | Authenticate with email/password & receive JWT |
| GET | `/auth/me` | JWT | Get current authenticated user identity |

**POST /auth/register** Request body:
```json
{
  "email": "citizen@example.com",
  "password": "SecurePassword123!",
  "full_name": "Ramesh Kumar",
  "preferred_language": "hi"
}
```

Response: `{ data: { "access_token": "...", "token_type": "bearer", "expires_in_seconds": 604800, "user_id": "...", "email": "..." } }`

**POST /auth/login** Request body:
```json
{
  "email": "citizen@example.com",
  "password": "SecurePassword123!"
}
```

Response: `{ data: { "access_token": "...", "token_type": "bearer", "expires_in_seconds": 604800, "user_id": "...", "email": "..." } }`

**GET /auth/me** → `{ data: { "id": "...", "email": "...", "is_active": true, "created_at": "..." } }`

---

### Profile

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/profile` | JWT | Get current user's profile |
| POST | `/profile` | JWT | Create or complete profile (safe update if exists) |
| PUT | `/profile` | JWT | Update profile fields progressively |
| POST | `/profile/consent` | JWT | Record explicit user consent (grant) |
| POST | `/profile/consent/revoke` | JWT | Explicitly revoke active consent |
| GET | `/profile/consent` | JWT | List audit trail of recorded consents for user |

**GET /profile** → `{ data: UserProfile }`

**POST /profile** Request body (creates or completes existing profile):
```json
{
  "full_name": "Ramesh Kumar",
  "preferred_language": "hi",
  "state": "Uttar Pradesh",
  "district": "Varanasi"
}
```

**POST /profile/consent** Request body:
```json
{
  "consent_type": "data_processing",
  "consent_status": "given"
}
```

**POST /profile/consent/revoke** Request body:
```json
{
  "consent_type": "data_processing"
}
```

---

### Beneficiaries

Implemented in Phase 3. Provides family-level beneficiary profile management under the authenticated citizen account. Enables eligibility evaluation and scheme discovery for both the primary citizen (`self`) and family members.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/beneficiaries` | JWT Bearer | List all beneficiaries for authenticated user (primary account holder `self` profile returned first) |
| POST | `/beneficiaries` | JWT Bearer | Create a new family beneficiary profile under authenticated user |
| GET | `/beneficiaries/{id}` | JWT Bearer | Retrieve a beneficiary profile (self or family member; IDOR-scoped) |
| PUT | `/beneficiaries/{id}` | JWT Bearer | Update a beneficiary profile (supports both self and family members) |
| DELETE | `/beneficiaries/{id}` | JWT Bearer | Delete a family beneficiary profile (deleting primary `self` profile is rejected with `400 Bad Request`) |

#### `GET /beneficiaries`

Returns the authenticated user's primary profile as the first element with synthetic `relationship: "self"`, followed by all registered family beneficiaries sorted by creation time.

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "user_id": "99999999-8888-7777-6666-555555555555",
      "full_name": "Ramesh Kumar",
      "relationship": "self",
      "date_of_birth": "1985-06-15",
      "gender": "male",
      "caste_category": "obc",
      "residence_type": "rural",
      "occupation": "Farmer",
      "annual_income": 45000,
      "is_differently_abled": false,
      "disability_percentage": null,
      "marital_status": "married",
      "profile_data": {
        "is_landholding_farmer": true
      },
      "created_at": "2026-11-10T10:00:00Z",
      "updated_at": "2026-11-10T10:00:00Z"
    },
    {
      "id": "22222222-3333-4444-5555-666666666666",
      "user_id": "99999999-8888-7777-6666-555555555555",
      "full_name": "Sunita Devi",
      "relationship": "mother",
      "date_of_birth": "1958-03-12",
      "gender": "female",
      "caste_category": "obc",
      "residence_type": "rural",
      "occupation": "Homemaker",
      "annual_income": 0,
      "is_differently_abled": false,
      "disability_percentage": null,
      "marital_status": "widowed",
      "profile_data": {
        "has_lpg_connection": false,
        "is_bpl_cardholder": true
      },
      "created_at": "2026-11-11T05:00:00Z",
      "updated_at": "2026-11-11T05:00:00Z"
    }
  ],
  "error": null,
  "request_id": "c1d2e3f4-a5b6-7c8d-9e0f-1a2b3c4d5e6f"
}
```

#### `POST /beneficiaries`

Creates a family beneficiary record. The `relationship` field must be one of the permitted family relationships (`spouse`, `father`, `mother`, `son`, `daughter`, `sibling`, `grandfather`, `grandmother`, `grandson`, `granddaughter`, `other_dependent`). Creating `relationship: "self"` via POST is rejected (the primary profile already serves as `self`). Any client-supplied `user_id` is ignored; the record is strictly associated with the authenticated user.

**Request Body (`BeneficiaryCreate`):**
```json
{
  "full_name": "Sunita Devi",
  "relationship": "mother",
  "date_of_birth": "1958-03-12",
  "gender": "female",
  "caste_category": "obc",
  "residence_type": "rural",
  "occupation": "Homemaker",
  "annual_income": 0,
  "marital_status": "widowed",
  "profile_data": {
    "has_lpg_connection": false,
    "is_bpl_cardholder": true
  }
}
```

**Success Response (`201 Created`):**
```json
{
  "success": true,
  "data": {
    "id": "22222222-3333-4444-5555-666666666666",
    "user_id": "99999999-8888-7777-6666-555555555555",
    "full_name": "Sunita Devi",
    "relationship": "mother",
    "date_of_birth": "1958-03-12",
    "gender": "female",
    "caste_category": "obc",
    "residence_type": "rural",
    "occupation": "Homemaker",
    "annual_income": 0,
    "is_differently_abled": false,
    "disability_percentage": null,
    "marital_status": "widowed",
    "profile_data": {
      "has_lpg_connection": false,
      "is_bpl_cardholder": true
    },
    "created_at": "2026-11-11T05:00:00Z",
    "updated_at": "2026-11-11T05:00:00Z"
  },
  "error": null,
  "request_id": "d2e3f4a5-b6c7-8d9e-0f1a-2b3c4d5e6f7a"
}
```

#### `GET /beneficiaries/{id}`

Retrieves a specific beneficiary profile. Supports both the primary profile ID (returns synthesized `relationship: "self"`) and family beneficiary IDs. Strict IDOR protection: requesting a beneficiary belonging to another user returns `404 Not Found` without disclosing existence.

#### `PUT /beneficiaries/{id}`

Progressively updates a beneficiary profile. If updating the primary `self` profile ID, updates the underlying `user_profiles` table. If updating a family beneficiary, updates `beneficiary_profiles`.

#### `DELETE /beneficiaries/{id}`

Deletes a family beneficiary record. Attempting to delete the primary account holder's profile (`self`) is rejected with `400 Bad Request` (`Cannot delete primary account holder self profile.`). IDOR-protected (`404 Not Found` on cross-tenant attempts).

---

### Schemes

Implemented in Phase 2. Provides authenticated citizen discovery and detail views over the authoritative scheme catalogue.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/schemes` | JWT Bearer | Search, filter, and paginate schemes (lightweight summaries) |
| GET | `/schemes/{scheme_id}` | JWT Bearer | Comprehensive scheme details with active documents and evidence |

#### `GET /schemes`

**Query Parameters:**
- `q` (string, optional): Full-text search string across scheme name, description, ministry, benefits, and target beneficiaries (PostgreSQL FTS English lexeme matching). Empty or punctuation-only strings are ignored cleanly.
- `category` (string, optional): Filter by one of the 12 canonical scheme categories (`agriculture`, `education`, `health`, `housing`, `employment`, `women_welfare`, `children_welfare`, `senior_citizens`, `disability`, `financial_inclusion`, `social_security`, `skill_development`). Invalid categories return HTTP `422`.
- `page` (integer, optional, default: `1`, minimum: `1`): Page number.
- `limit` (integer, optional, default: `20`, minimum: `1`, maximum: `50`): Results per page.
- `include_pending` (boolean, optional, default: `false`): By default, only schemes with `scheme_status = 'active'` are returned. Setting `true` also includes `pending_verification` schemes. Inactive schemes are always excluded.

**Sorting:** Deterministic ordering by `name ASC, id ASC`.

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "scheme_code": "PM-KISAN",
        "name": "Pradhan Mantri Kisan Samman Nidhi",
        "ministry": "Ministry of Agriculture and Farmers Welfare",
        "category": "agriculture",
        "benefits": "₹6,000 per year paid in three equal instalments of ₹2,000 directly into the bank accounts of eligible farmer families.",
        "target_beneficiaries": ["farmer_families", "small_farmers", "marginal_farmers"],
        "geographic_scope": "central",
        "official_url": "https://pmkisan.gov.in/",
        "application_url": "https://pmkisan.gov.in/RegistrationFormNew.aspx",
        "scheme_status": "active",
        "last_retrieved_at": "2026-11-10T21:40:00Z",
        "last_verified_at": "2026-11-10T21:40:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 20,
    "pages": 1
  },
  "error": null,
  "request_id": "c1f8a846-5b72-4d56-a991-8dc174825974"
}
```

#### `GET /schemes/{scheme_id}`

**Path Parameters:**
- `scheme_id` (UUID): The unique primary key identifier of the scheme. Malformed UUIDs return HTTP `422`.

**Visibility Rules:**
- Inactive schemes (`scheme_status = 'inactive'`) return HTTP `404 Not Found`.
- Schemes with `scheme_status = 'pending_verification'` return HTTP `404 Not Found` unless explicitly queried with `?include_pending=true`.
- Active schemes return HTTP `200 OK`.

**Security Note:** Internal eligibility rule JSON (`rules` AST) is deliberately excluded from the citizen detail endpoint to protect evaluator state and keep payloads lean.

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "scheme_code": "PM-KISAN",
    "name": "Pradhan Mantri Kisan Samman Nidhi",
    "description": "Central sector scheme providing income support of Rs. 6,000 per year to all landholding farmer families having cultivable landholding in their names.",
    "ministry": "Ministry of Agriculture and Farmers Welfare",
    "category": "agriculture",
    "benefits": "₹6,000 per year paid in three equal instalments of ₹2,000 directly into the bank accounts of eligible farmer families.",
    "target_beneficiaries": ["farmer_families", "small_farmers", "marginal_farmers"],
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
    "required_documents": [
      {
        "id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
        "document_type": "aadhaar",
        "is_mandatory": true,
        "guidance": "Aadhaar number seeded with bank account is mandatory for PM-KISAN DBT transfers.",
        "source_url": "https://pmkisan.gov.in/",
        "last_verified_at": "2026-11-10T21:40:00Z",
        "is_active": true
      }
    ],
    "created_at": "2026-11-10T21:45:00Z",
    "updated_at": "2026-11-10T21:45:00Z"
  },
  "error": null,
  "request_id": "893c524b-325b-42fa-9486-1df95e4ad0c7"
}
```

**Common Error Responses:**
- `401 Unauthorized`: Missing or expired Bearer token in `Authorization` header.
- `404 Not Found`: Scheme ID does not exist or is inactive / pending verification (when not allowed).
- `422 Unprocessable Entity`: Malformed UUID or invalid filter category.

---

### Eligibility

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/eligibility/check` | JWT | Check citizen eligibility for a scheme |
| POST | `/eligibility/evaluate/{scheme_id}` | JWT | RESTful endpoint to evaluate a specific scheme by UUID |
| POST | `/eligibility/evaluate-all` | JWT | Batch evaluate citizen eligibility across all available schemes |

#### `POST /eligibility/check`

**Query Parameters:**
- `include_pending` (boolean, optional, default `false`): When `true`, permits evaluation of schemes marked `pending_verification`.

**Request Body (`EligibilityCheckRequest`):**
```json
{
  "scheme_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "beneficiary_id": "22222222-3333-4444-5555-666666666666",
  "profile_override": {
    "is_landholding_farmer": true,
    "is_institutional_landholder": false,
    "is_income_tax_payer": false
  }
}
```
*Note: `beneficiary_id` is optional; if omitted, defaults to the authenticated primary account holder (`self`). `profile_override` is optional and enables what-if evaluation in conversational flows without mutating the citizen's or family member's persisted database profile.*

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "scheme_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "scheme_code": "PM-KISAN",
    "scheme_name": "Pradhan Mantri Kisan Samman Nidhi",
    "beneficiary_id": "22222222-3333-4444-5555-666666666666",
    "beneficiary_name": "Sunita Devi",
    "beneficiary_relationship": "mother",
    "overall_status": "PASS",
    "result": "eligible",
    "eligible": true,
    "rule_version_id": "e2d3c4b5-a6f7-8b9c-0d1e-2f3a4b5c6d7e",
    "rule_version": 1,
    "is_authoritative": true,
    "is_provisional": false,
    "limitations": "Core statutory eligibility conditions verified from Operational Guidelines.",
    "matched_conditions": [
      {
        "field": "is_landholding_farmer",
        "operator": "equals",
        "expected_value": true,
        "actual_value": true,
        "status": "PASS",
        "passed": true,
        "explanation": "Requirement satisfied: is_landholding_farmer (True) equals True."
      },
      {
        "field": "is_institutional_landholder",
        "operator": "equals",
        "expected_value": false,
        "actual_value": false,
        "status": "PASS",
        "passed": true,
        "explanation": "Requirement satisfied: is_institutional_landholder (False) equals False."
      },
      {
        "field": "is_income_tax_payer",
        "operator": "equals",
        "expected_value": false,
        "actual_value": false,
        "status": "PASS",
        "passed": true,
        "explanation": "Requirement satisfied: is_income_tax_payer (False) equals False."
      }
    ],
    "failed_conditions": [],
    "unknown_conditions": [],
    "condition_results": [
      {
        "field": "is_landholding_farmer",
        "operator": "equals",
        "expected_value": true,
        "actual_value": true,
        "status": "PASS",
        "passed": true,
        "explanation": "Requirement satisfied: is_landholding_farmer (True) equals True."
      }
    ],
    "missing_fields": [],
    "next_questions": [],
    "explanation": "Eligible! You satisfy all 3 evaluated eligibility criteria for Pradhan Mantri Kisan Samman Nidhi.",
    "evaluated_at": "2026-11-11T00:10:00Z"
  },
  "error": null,
  "request_id": "4e7f8a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b"
}
```

**UNKNOWN / Insufficient Information Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "scheme_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "scheme_code": "PM-KISAN",
    "scheme_name": "Pradhan Mantri Kisan Samman Nidhi",
    "beneficiary_id": "22222222-3333-4444-5555-666666666666",
    "beneficiary_name": "Sunita Devi",
    "beneficiary_relationship": "mother",
    "overall_status": "UNKNOWN",
    "result": "insufficient_information",
    "eligible": null,
    "rule_version_id": "e2d3c4b5-a6f7-8b9c-0d1e-2f3a4b5c6d7e",
    "rule_version": 1,
    "is_authoritative": true,
    "is_provisional": false,
    "limitations": "Core statutory eligibility conditions verified from Operational Guidelines.",
    "matched_conditions": [],
    "failed_conditions": [],
    "unknown_conditions": [
      {
        "field": "is_landholding_farmer",
        "operator": "equals",
        "expected_value": true,
        "actual_value": null,
        "status": "UNKNOWN",
        "passed": null,
        "explanation": "Information required: Field 'is_landholding_farmer' is missing from your profile."
      }
    ],
    "missing_fields": ["is_landholding_farmer"],
    "next_questions": [
      {
        "field": "is_landholding_farmer",
        "question": "Do you or your family own cultivable agricultural land?",
        "question_hi": "क्या आपके या आपके परिवार के नाम पर कृषि योग्य भूमि है?",
        "field_type": "boolean",
        "options": null
      }
    ],
    "explanation": "Insufficient information: 1 required profile attributes must be provided to determine eligibility for Pradhan Mantri Kisan Samman Nidhi.",
    "evaluated_at": "2026-11-11T00:10:00Z"
  },
  "error": null,
  "request_id": "5f8a9b2c-3d4e-5f6a-7b8c-9d0e1f2a3b4c"
}
```

#### `POST /eligibility/evaluate-all`

**Request Body (`BatchEligibilityCheckRequest`, optional):**
```json
{
  "beneficiary_id": "22222222-3333-4444-5555-666666666666",
  "include_pending": false,
  "category": "agriculture",
  "profile_override": null
}
```

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "total_evaluated": 4,
    "eligible_count": 2,
    "ineligible_count": 0,
    "unknown_count": 2,
    "results": [
      {
        "scheme_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "scheme_code": "AB-PMJAY",
        "scheme_name": "Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana",
        "beneficiary_id": "22222222-3333-4444-5555-666666666666",
        "beneficiary_name": "Sunita Devi",
        "beneficiary_relationship": "mother",
        "overall_status": "PASS",
        "result": "eligible",
        "eligible": true,
        "rule_version_id": "d1c2b3a4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "rule_version": 1,
        "is_authoritative": true,
        "is_provisional": false,
        "limitations": "Evaluates SECC 2011 deprivation criteria and age-based top-up coverage.",
        "condition_results": [
          {
            "field": "is_bpl_cardholder",
            "operator": "equals",
            "expected_value": true,
            "actual_value": true,
            "status": "PASS",
            "passed": true,
            "explanation": "Requirement satisfied: is_bpl_cardholder (True) equals True."
          }
        ],
        "matched_conditions": [
          {
            "field": "is_bpl_cardholder",
            "operator": "equals",
            "expected_value": true,
            "actual_value": true,
            "status": "PASS",
            "passed": true,
            "explanation": "Requirement satisfied: is_bpl_cardholder (True) equals True."
          }
        ],
        "failed_conditions": [],
        "unknown_conditions": [],
        "missing_fields": [],
        "next_questions": [],
        "explanation": "Eligible! You satisfy all evaluated eligibility criteria for Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana.",
        "evaluated_at": "2026-11-11T00:10:00Z"
      }
    ]
  },
  "error": null,
  "request_id": "6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d"
}
```

**Common Error Responses:**
- `401 Unauthorized`: Missing or invalid Bearer token in `Authorization` header.
- `404 Not Found`: Scheme ID does not exist, is inactive, or is pending verification (without `include_pending=true`).
- `422 Unprocessable Entity`: Malformed UUID or invalid category filter.

---

### Documents

See complete specification in [Documents API Contract (v1)](api/v1/documents.md).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/documents/upload` | JWT | Upload document file with magic byte sniffing, MIME validation, 10MB limit |
| GET | `/documents` | JWT | List citizen documents with optional `beneficiary_id` and `document_type` filters |
| GET | `/documents/checklist/{scheme_id}` | JWT | Generate readiness checklist with direct & alternative matching |
| GET | `/documents/{document_id}` | JWT | Retrieve document metadata with strict IDOR protection |
| GET | `/documents/{document_id}/download` | JWT | Secure streaming file download with tenant verification |
| DELETE | `/documents/{document_id}` | JWT | Delete document record and purge physical file |

---

### Applications

See complete specification in [Applications API Contract (v1)](api/v1/applications.md).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/applications/draft` | JWT | Create application draft packaging prefilled demographics & attached docs |
| GET | `/applications` | JWT | List citizen application drafts with optional `status` & `scheme_id` filters |
| GET | `/applications/{id}` | JWT | Retrieve application draft details and official portal handoff instructions |
| PUT | `/applications/{id}` | JWT | Update notes or demographic fields in unsubmitted draft |
| POST | `/applications/{id}/submit` | JWT | Record external portal submission with government acknowledgement reference # |
| DELETE | `/applications/{id}` | JWT | Delete application draft |

---

### Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/notifications` | JWT | List user notifications |
| PUT | `/notifications/{id}/read` | JWT | Mark notification as read |

---

### Agent / Conversational Intake

Implemented in Phase 3 / Increment 2. Provides AI-assisted multi-turn intake, read-only scheme discovery & eligibility evaluation, and independent action confirmation with zero-trust database write boundaries.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/agent/chat` | JWT | Send a message; receive conversational assistant response and optional staged pending action |
| POST | `/agent/actions/{id}/confirm` | JWT | Explicitly confirm and execute a staged pending action (row-locked, exact persisted payload) |
| POST | `/agent/actions/{id}/cancel` | JWT | Cancel a staged pending action |
| GET | `/agent/conversations` | JWT | List authenticated user's conversations (paginated) |
| GET | `/agent/conversations/{id}` | JWT | Retrieve full conversation with message history |

Detailed specification: see [`docs/api/v1/conversational_agent.md`](v1/conversational_agent.md).

---

## Error codes reference

| Code | Meaning |
|---|---|
| `VALIDATION_ERROR` | Request payload failed validation |
| `NOT_FOUND` | Resource does not exist |
| `UNAUTHORIZED` | Missing or invalid JWT |
| `FORBIDDEN` | Action not permitted for this user |
| `CONFLICT` | Duplicate resource or already executed/cancelled action |
| `GONE` | Action has expired (15-min TTL exceeded) |
| `ELIGIBILITY_ERROR` | Rule engine evaluation failure |
| `INTERNAL_ERROR` | Unexpected server error |
| `RATE_LIMITED` | Too many requests |

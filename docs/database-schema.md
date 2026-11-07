# Scheme Saathi — Database Schema

**Database:** PostgreSQL (via Supabase or local instance)
**ORM:** SQLAlchemy 2.0
**Migrations:** Alembic
**Primary keys:** UUID v4
**Phase 1 Status:** Implemented & Migrated (Revision: `d60b841ec91c`)

---

## Implemented in Phase 1

1. **`users`** — System user accounts and authentication state.
2. **`user_profiles`** — Citizen demographics, location, occupation, and financial attributes.
3. **`user_consents`** — Explicit immutable consent audit trail.

---

## Conventions

- All tables use `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- All tables have `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- Mutable tables also have `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- Foreign keys are always indexed.
- Soft-delete via `deleted_at` where appropriate.
- JSONB columns are used for schema-flexible data.

---

## Tables

### `users`
System user accounts for native authentication with email/password (bcrypt) and JWT.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | gen_random_uuid() |
| email | TEXT UNIQUE NOT NULL | Indexed, normalized lowercase |
| password_hash | TEXT NOT NULL | Salty bcrypt hash (12 rounds) |
| is_active | BOOLEAN NOT NULL DEFAULT true | Account status check |
| auth_provider_id | TEXT UNIQUE | Optional external UID for future identity providers |
| created_at | TIMESTAMPTZ | Automatic timestamp |
| updated_at | TIMESTAMPTZ | Automatic timestamp |

---

### `user_profiles`
Citizen profile data collected progressively.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | UNIQUE — one profile per user (CASCADE on delete) |
| full_name | TEXT | Citizen full name |
| date_of_birth | DATE | |
| gender | TEXT | Demographic classification |
| state | TEXT | Indian state name |
| district | TEXT | |
| residence_type | TEXT | 'rural', 'urban', or 'semi_urban' |
| occupation | TEXT | Occupation / trade |
| annual_family_income | NUMERIC(12,2) | INR |
| preferred_language | TEXT | 'hi' or 'en' — default 'hi' |
| profile_data | JSONB | Scheme-specific extra fields |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

### `user_consents`
Explicit immutable consent audit records — retained for regulatory compliance.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | FK with RESTRICT to protect audit history |
| consent_type | TEXT | e.g. 'data_processing', 'terms_of_service' |
| consent_status | TEXT | 'given' / 'revoked' |
| recorded_at | TIMESTAMPTZ | When consent was granted |
| revoked_at | TIMESTAMPTZ | NULL until revoked; populated upon revocation |
| revoked_at | TIMESTAMPTZ | NULL until revoked |

---

### `schemes`
Central-government scheme catalogue.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| scheme_code | TEXT UNIQUE NOT NULL | Short code e.g. 'PM-KISAN' |
| name | TEXT NOT NULL | Official scheme name |
| description | TEXT | |
| ministry | TEXT NOT NULL | Issuing ministry/department |
| category | TEXT NOT NULL | e.g. agriculture, education, health |
| benefits | TEXT | Description of benefits |
| target_beneficiaries | TEXT | Who qualifies |
| geographic_scope | TEXT | 'central' or state code |
| official_url | TEXT NOT NULL | Official government page |
| application_url | TEXT | Direct application URL |
| source_url | TEXT NOT NULL | URL used as data source |
| last_retrieved_at | TIMESTAMPTZ | When data was last fetched |
| last_verified_at | TIMESTAMPTZ | When a team member verified |
| scheme_status | TEXT | 'active' / 'inactive' / 'pending_verification' |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

### `scheme_rule_versions`
Versioned eligibility rules (JSONB). Never mutated; new version inserted for each change.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| scheme_id | UUID FK → schemes.id | |
| version | INTEGER NOT NULL | Increments per scheme |
| rules | JSONB NOT NULL | Rule tree (see eligibility spec) |
| source_url | TEXT | Official source for these rules |
| effective_from | TIMESTAMPTZ | When this version became active |
| effective_to | TIMESTAMPTZ | NULL = still active |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** `(scheme_id, version)`

---

### `scheme_documents`
Documents required per scheme.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| scheme_id | UUID FK → schemes.id | |
| document_type | TEXT NOT NULL | e.g. 'aadhaar', 'income_certificate' |
| is_mandatory | BOOLEAN NOT NULL DEFAULT true | |
| guidance | TEXT | How to obtain the document |
| source_url | TEXT | Verification source |
| last_verified_at | TIMESTAMPTZ | |

---

### `user_documents`
Citizen-uploaded documents.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| document_type | TEXT NOT NULL | |
| storage_path | TEXT | Path in Supabase Storage |
| upload_status | TEXT | 'pending' / 'uploaded' / 'failed' |
| ocr_status | TEXT | 'pending' / 'processing' / 'completed' / 'failed' / 'not_applicable' |
| extracted_data | JSONB | OCR output |
| review_status | TEXT | 'pending_review' / 'accepted' / 'rejected' |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

### `eligibility_checks`
Immutable record of every eligibility evaluation.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| scheme_id | UUID FK → schemes.id | |
| rule_version_id | UUID FK → scheme_rule_versions.id | |
| result | TEXT NOT NULL | 'eligible' / 'not_eligible' / 'potentially_eligible' / 'insufficient_information' |
| condition_results | JSONB | Per-condition pass/fail/unknown |
| missing_fields | JSONB | Fields needed but absent |
| evaluated_at | TIMESTAMPTZ NOT NULL | |

---

### `applications`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| scheme_id | UUID FK → schemes.id | |
| form_data | JSONB | Filled application form |
| lifecycle_state | TEXT NOT NULL | draft → validated → awaiting_confirmation → submitted |
| validation_result | JSONB | Last validation output |
| reference_number | TEXT | From official portal, if returned |
| submission_source | TEXT | 'official_integration' / 'portal_handoff' / 'simulated_demo' |
| confirmed_at | TIMESTAMPTZ | When user explicitly confirmed |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| submitted_at | TIMESTAMPTZ | |

---

### `application_documents`
Documents attached to an application.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| application_id | UUID FK → applications.id | |
| document_id | UUID FK → user_documents.id | |
| created_at | TIMESTAMPTZ | |

---

### `application_status_history`
Immutable status audit trail.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| application_id | UUID FK → applications.id | |
| status | TEXT NOT NULL | |
| source_type | TEXT NOT NULL | 'official_integration' / 'user_reported' / 'simulated_demo' |
| source_reference | TEXT | Reference ID from official system |
| notes | TEXT | |
| created_at | TIMESTAMPTZ NOT NULL | |

---

### `conversations`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| language | TEXT | 'hi' or 'en' |
| workflow_state | JSONB | Current agent workflow state |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

### `conversation_messages`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | UUID FK → conversations.id | |
| role | TEXT NOT NULL | 'user' / 'assistant' / 'tool' |
| message_content | TEXT NOT NULL | |
| response_type | TEXT | 'text' / 'scheme_cards' / 'eligibility_result' / etc. |
| tool_name | TEXT | If role = 'tool' |
| tool_result_reference | UUID | Reference to relevant record |
| created_at | TIMESTAMPTZ NOT NULL | |

---

### `followups`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| application_id | UUID FK → applications.id | |
| action | TEXT NOT NULL | What the citizen needs to do |
| due_at | TIMESTAMPTZ | |
| status | TEXT | 'pending' / 'completed' / 'dismissed' |
| created_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |

---

### `notifications`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| title | TEXT NOT NULL | |
| message | TEXT NOT NULL | |
| notification_type | TEXT | 'info' / 'action_required' / 'update' |
| read_at | TIMESTAMPTZ | NULL = unread |
| created_at | TIMESTAMPTZ NOT NULL | |

---

## Indexes

| Table | Column(s) | Type |
|---|---|---|
| user_profiles | user_id | UNIQUE |
| scheme_rule_versions | (scheme_id, version) | UNIQUE |
| scheme_rule_versions | scheme_id, effective_to | BTREE |
| eligibility_checks | user_id, scheme_id | BTREE |
| applications | user_id | BTREE |
| applications | lifecycle_state | BTREE |
| application_status_history | application_id | BTREE |
| conversation_messages | conversation_id | BTREE |
| notifications | user_id, read_at | BTREE |

---

## Authorization rules (enforced in application layer)

| Resource | Rule |
|---|---|
| user_profiles | User can only read/write own profile |
| user_documents | User can only read/write own documents |
| eligibility_checks | User can only read own checks |
| applications | User can only read/write own applications |
| conversations | User can only read/write own conversations |
| notifications | User can only read own notifications |
| schemes | Public read (all authenticated users) |
| scheme_documents | Public read (all authenticated users) |

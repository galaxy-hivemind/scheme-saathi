# Scheme Saathi — Database Schema

**Database:** PostgreSQL (via Supabase or local instance)
**ORM:** SQLAlchemy 2.0
**Migrations:** Alembic
**Primary keys:** UUID v4
**Phase 1 Status:** Implemented & Migrated (Head Revision: `bb1bf3e30acc`)

---

## Migration History

1. **`d60b841ec91c`** — Initial schema creation (`users`, `user_profiles`, `user_consents`).
2. **`bb1bf3e30acc`** — Alters `user_consents.user_id` foreign key from `CASCADE` to `RESTRICT` to enforce non-destructive consent audit retention.

---

## Test Database Isolation & Sentinel Trust Model

To prevent any possibility of destructive testing operations (`drop_all`, `create_all`, `drop schema`) impacting the production or application database, Scheme Saathi implements a **fail-closed verifiable trust model** (`backend/app/core/db_safety.py`):

### 1. In-Database Disposable Sentinel
Every disposable test database contains a dedicated sentinel table (`_scheme_saathi_db_sentinel`) initialized with:
- `marker_key`: `'scheme_saathi_test_isolation'`
- `purpose`: `'regular_test'` or `'migration_test'`
- `is_disposable`: `TRUE`
- `database_name`: Strictly verified against `current_database()`

If this record is missing, invalid, or marks `is_disposable = FALSE`, all destructive operations fail closed immediately.

### 2. Multi-Layer Anti-Application DB Protection
Regardless of environment variables, the system verifies that the target does not collide with `DATABASE_URL`:
- Normalizes URL schemes (`postgresql`, `postgresql+psycopg`, `postgresql+psycopg2`, `postgresql+asyncpg`, `postgres`).
- Resolves hostnames and IP addresses (`localhost`, `127.0.0.1`, `0.0.0.0`).
- Matches ports and database names.
- Compares live PostgreSQL catalog OIDs and cluster identifiers (`pg_database.oid`, `pg_control_system()`).
- Rejects application database targets even if a sentinel was artificially placed in them.

### 3. Independent Authorization Scopes
- `ALLOW_TEST_DB_RESET=1`: Authorizes regular test fixture setup/teardown on disposable test databases.
- `ALLOW_MIGRATION_TESTS=1`: Authorizes schema-isolated migration tests.
- Cross-role authorization is strictly rejected.

### 4. Centralized Destructive Execution Gateways
Destructive DDL calls cannot be called directly; they must route through verified gatekeeper functions:
- `safe_drop_all(engine, metadata, target_url, app_url, purpose)`
- `safe_create_all(engine, metadata, target_url, app_url, purpose)`
- `safe_create_schema(engine, schema_name, target_url, app_url, purpose)`
- `safe_drop_schema(engine, schema_name, target_url, app_url, purpose)` (strictly forbids dropping `public`, `pg_catalog`, or `information_schema`)

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

---

## Migration Testing and Schema Isolation

To safely test Alembic migrations without risking data loss or contaminating the public application schema, Scheme Saathi uses dedicated per-run PostgreSQL schemas (`migtest_<uuid>`) and strict environment safety guards.

### Safety Guards & Pre-flight Checks
1. **Explicit Opt-in:** Destructive migration lifecycle tests require the explicit environment variable:
   `ALLOW_MIGRATION_TESTS=1` (or `ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1`).
   Without this flag, destructive tests skip or reject execution to prevent inadvertent runs.
2. **Database Identity Verification:** The test runner resolves target host IPs and queries PostgreSQL's `SELECT current_database()` as well as catalog identity (`pg_control_system()`, `pg_database`). If the target matches the active application database (configured via `DATABASE_URL`), test execution is immediately halted with a `ValueError`.
3. **No Public Schema Drops:** The test runner **never** drops the `public` schema. All migration tables (`users`, `user_profiles`, `user_consents`, and `alembic_version`) are created inside an ephemeral schema unique to each test run.
4. **Reliable Teardown:** Schema teardown (`DROP SCHEMA <schema_name> CASCADE`) executes in guaranteed teardown blocks, preserving any underlying assertion exceptions.

### Running Migration Tests
```bash
# 1. Ensure test database is provisioned
createdb -h localhost -U postgres scheme_saathi_migration_test

# 2. Run migration test suite with explicit opt-in
ALLOW_MIGRATION_TESTS=1 \
MIGRATION_TEST_DB_URL=postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test \
pytest tests/integration/test_migrations.py -v
```

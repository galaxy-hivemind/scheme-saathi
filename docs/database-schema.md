# Scheme Saathi — Database Schema

**Database:** PostgreSQL (via Supabase or local instance)
**ORM:** SQLAlchemy 2.0
**Migrations:** Alembic
**Primary keys:** UUID v4
**Phase 1 Status:** Implemented & Migrated (Revision: `bb1bf3e30acc`)
**Phase 2 Status:** Implemented & Migrated (Head Revision: `e7b2c419fa01`)

---

## Migration History

1. **`d60b841ec91c`** — Initial schema creation (`users`, `user_profiles`, `user_consents`).
2. **`bb1bf3e30acc`** — Alters `user_consents.user_id` foreign key from `CASCADE` to `RESTRICT` to enforce non-destructive consent audit retention.
3. **`e7b2c419fa01`** — Schema creation for government scheme catalogue (`schemes`, `scheme_rule_versions`, `scheme_documents`), foreign keys with `ON DELETE RESTRICT`, check constraints, partial unique index for active rule versions, and PostgreSQL full-text search GIN index.

---

## Test Database Isolation & Sentinel Trust Model

To prevent any possibility of destructive testing operations (`drop_all`, `create_all`, `drop schema`) impacting the production or application database, Scheme Saathi implements a **fail-closed verifiable trust model** (`backend/app/core/db_safety.py`):

### 1. Dual Isolation Architecture
- **Testcontainers PostgreSQL (Preferred):** Dynamically spins up an ephemeral PostgreSQL 16 container on a random port, configures isolated credentials, runs tests, and destroys the container at the end of the session.
- **Dedicated Role-Isolated Databases (Fallback):** Runs against pre-provisioned disposable databases (`scheme_saathi_test` and `scheme_saathi_migration_test`) using a dedicated, permission-restricted role (`scheme_saathi_test_user`).

### 2. Privilege-Restricted Test Runtime Role (`scheme_saathi_test_user`)
- **Application Database Isolation Model:** Direct database privileges are explicitly revoked from `scheme_saathi_test_user` on `scheme_saathi` (`REVOKE ALL ON DATABASE scheme_saathi FROM scheme_saathi_test_user; REVOKE CONNECT ON DATABASE scheme_saathi FROM scheme_saathi_test_user;`). Because standard PostgreSQL retains `CONNECT` for `PUBLIC` by default (preserved to avoid impacting other roles and databases), `has_database_privilege(role, 'scheme_saathi', 'CONNECT')` evaluates to `True` via inheritance. Connection refusal is enforced at the database engine level via session-level configuration (`ALTER ROLE scheme_saathi_test_user IN DATABASE scheme_saathi SET session_preload_libraries = 'nonexistent_lib';`), which causes the PostgreSQL backend process to abort initialization with `FATAL` immediately upon authentication. In addition, gateway and target checks verify `current_database() != 'scheme_saathi'`. Execution of `pg_control_system()` is explicitly revoked from `PUBLIC` so cluster identifiers cannot be queried by unprivileged roles.
- **Read-Only Sentinel Access:** `GRANT SELECT ON _scheme_saathi_db_sentinel TO scheme_saathi_test_user; REVOKE ALL ON TABLE _scheme_saathi_db_sentinel FROM scheme_saathi_test_user; GRANT SELECT ON TABLE _scheme_saathi_db_sentinel TO scheme_saathi_test_user`.
- **No Self-Authorization:** Test fixtures **never** auto-provision or alter the sentinel. Missing sentinel causes immediate failure.
- **Rejection of Superusers/Administrators:** Fallback test fixtures strictly verify `current_user` against `scheme_saathi_test_user` and reject connections made by `postgres`, superusers, or administrator roles.

### 3. Multi-Layer Anti-Application DB Protection
Regardless of environment variables, the system verifies that the target does not collide with `DATABASE_URL`:
- **Unconditional Name Rejection:** If target's live `current_database()` matches `DATABASE_URL`'s connected database name, the target is rejected across all hostnames, ports, driver schemes, and proxy endpoints.
- **Fail-Closed on Unreachable App DB:** If `DATABASE_URL` cannot be reached during identity comparison, verification fails closed immediately.
- Normalizes URL schemes (`postgresql`, `postgresql+psycopg`, `postgresql+psycopg2`, `postgresql+asyncpg`, `postgres`).
- Resolves hostnames and IP addresses (`localhost`, `127.0.0.1`, `0.0.0.0`).
- Matches ports and database names.
- Compares live PostgreSQL catalog OIDs and cluster identifiers (`pg_database.oid`, `pg_control_system()`).

### 4. Independent Authorization Scopes
- `ALLOW_TEST_DB_RESET=1`: Authorizes regular test fixture setup/teardown on disposable test databases.
- `ALLOW_MIGRATION_TESTS=1`: Authorizes schema-isolated migration tests.
- Cross-role authorization is strictly rejected.
- Unit tests run completely free of database fixtures and opt-in requirements (`pytest tests/unit/`).

### 5. Centralized Destructive Execution Gateways & Live Catalog Revalidation
Under project test conventions, all application-controlled destructive test DDL must route through verified gatekeeper functions:
- `safe_drop_all(engine_or_conn, metadata, target_url, app_url, purpose, expected_role)`
- `safe_create_all(engine_or_conn, metadata, target_url, app_url, purpose, expected_role)`
- `safe_create_schema(engine_or_conn, schema_name, target_url, app_url, purpose, expected_role)`
- `safe_drop_schema(engine_or_conn, schema_name, target_url, app_url, purpose, expected_role)` (strictly forbids dropping `public`, `pg_catalog`, or `information_schema`)

> **Gateway Enforcement Scope:** The gateway functions verify target database identity, sentinel presence, opt-in authorization, role attributes, and transaction boundaries immediately before executing DDL. Direct raw SQL statements or unmanaged SQLAlchemy calls (such as `metadata.drop_all(bind=engine)`) that bypass these functions are not intercepted by the Python runtime; however, project conventions strictly mandate using the gateways, and PostgreSQL-level runtime role restrictions prevent destructive operations on the application database.

Every gateway operation:
1. Validates `expected_role` against the authoritative configured test runtime role (`TEST_DB_USER` or `scheme_saathi_test_user`), rejecting missing, `None`, empty, or unapproved roles before DDL.
2. Directly queries PostgreSQL system catalogs (`pg_roles`, `pg_auth_members`) on the exact live execution connection immediately prior to DDL, verifying `rolsuper = FALSE`, `rolcreatedb = FALSE`, `rolcreaterole = FALSE`, `rolcanlogin = TRUE`, `rolinherit = FALSE`, `rolreplication = FALSE`, `rolbypassrls = FALSE`, and zero memberships.
3. Preserves caller-owned active transactions and nested savepoints; gateway operations never commit unrelated caller DML.
4. Uses driver-verified SQL composition (`get_dbapi_sql_composer`) and validated PostgreSQL identifiers. Container instances generate cryptographically random credentials per instance with automatic teardown on failure.

---

## Implemented in Phase 1

1. **`users`** — System user accounts and authentication state.
2. **`user_profiles`** — Citizen demographics, location, occupation, and financial attributes.
3. **`user_consents`** — Explicit immutable consent audit trail.

---

## Implemented in Phase 2

1. **`schemes`** — Core government scheme metadata catalogue, full-text search index, source evidence manifest.
2. **`scheme_rule_versions`** — Append-only, versioned eligibility rule definitions with historical retention.
3. **`scheme_documents`** — Required documentation definitions with guidance and official sources per scheme.

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
Central-government welfare scheme catalogue. Implemented in Phase 2 with strict domain check constraints, non-redundant indexes, and PostgreSQL full-text search.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `gen_random_uuid()` |
| scheme_code | VARCHAR(64) UNIQUE NOT NULL | Short unique identifier, uppercase normalized (e.g. `PM-KISAN`) |
| name | VARCHAR(255) NOT NULL | Official scheme name |
| description | TEXT NOT NULL | Detailed description of the scheme |
| ministry | VARCHAR(255) NOT NULL | Responsible government ministry or department |
| category | VARCHAR(64) NOT NULL | One of 12 canonical categories (CHECK: `ck_schemes_category`) |
| benefits | TEXT NOT NULL | Description of financial or material benefits |
| target_beneficiaries | TEXT[] NOT NULL | Array of target beneficiary tags/identifiers |
| geographic_scope | VARCHAR(32) NOT NULL DEFAULT 'central' | CHECK: `ck_schemes_geographic_scope` (`geographic_scope = 'central'`) |
| official_url | TEXT NOT NULL | Official government portal URL |
| application_url | TEXT | Direct citizen application/registration URL (optional) |
| source_url | TEXT NOT NULL | Primary authoritative government source URL |
| source_evidence | JSONB NOT NULL DEFAULT '[]' | Complete claim-level evidence manifest (`SourceEvidenceEntry[]`) |
| last_retrieved_at | TIMESTAMPTZ NOT NULL | Timestamp when data was retrieved from government source |
| last_verified_at | TIMESTAMPTZ | Timestamp of human/editorial verification (required for `active`, NULL for `pending_verification`) |
| scheme_status | VARCHAR(32) NOT NULL DEFAULT 'pending_verification' | CHECK: `ck_schemes_status` (`'active'`, `'inactive'`, `'pending_verification'`) |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | Record update timestamp |

**Constraints & Indexes:**
- Unique Constraint: `uq_schemes_scheme_code` on `scheme_code`
- Check Constraint: `ck_schemes_category` restricting `category` to the 12 canonical values (`agriculture`, `education`, `health`, `housing`, `employment`, `women_welfare`, `children_welfare`, `senior_citizens`, `disability`, `financial_inclusion`, `social_security`, `skill_development`)
- Check Constraint: `ck_schemes_geographic_scope` (`geographic_scope = 'central'`)
- Check Constraint: `ck_schemes_status` (`scheme_status IN ('active', 'inactive', 'pending_verification')`)
- Composite Index: `idx_schemes_status_category` on `(scheme_status, category)`
- Index: `idx_schemes_name` on `name`
- PostgreSQL FTS GIN Index: `idx_schemes_fts` using `gin((to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(ministry, '') || ' ' || coalesce(benefits, '')) || array_to_tsvector(target_beneficiaries)))`

---

### `scheme_rule_versions`
Append-only eligibility rule versions (JSONB). In Phase 2, historical rule versions are immutable at the application layer; the only controlled lifecycle update closes `effective_to` when a newer version is activated.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `gen_random_uuid()` |
| scheme_id | UUID NOT NULL | Foreign key to `schemes.id` (`ON DELETE RESTRICT`) |
| version | INTEGER NOT NULL | Sequential version number per scheme (CHECK: `version >= 1`) |
| rules | JSONB NOT NULL | Evaluator-ready rule AST (combinators and field predicates) |
| source_url | TEXT | Official source establishing this rule version |
| is_active | BOOLEAN NOT NULL DEFAULT true | Whether this rule version is currently active |
| effective_from | TIMESTAMPTZ NOT NULL DEFAULT now() | Activation timestamp |
| effective_to | TIMESTAMPTZ | Expiration timestamp (NULL while active) |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | Record creation timestamp |

**Constraints & Indexes:**
- Foreign Key: `fk_scheme_rule_versions_scheme_id` referencing `schemes(id)` with `ON DELETE RESTRICT`
- Unique Constraint: `uq_scheme_rule_versions_scheme_version` on `(scheme_id, version)`
- Check Constraint: `ck_scheme_rule_versions_version_positive` (`version >= 1`)
- Partial Unique Index: `idx_rule_versions_active_unique` on `(scheme_id)` `WHERE is_active = TRUE` (enforces exactly one active rule version per scheme)

---

### `scheme_documents`
Required citizen documents per scheme. Document definitions are soft-deactivated (`is_active = FALSE`) rather than deleted when omitted during seed synchronization.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `gen_random_uuid()` |
| scheme_id | UUID NOT NULL | Foreign key to `schemes.id` (`ON DELETE RESTRICT`) |
| document_type | VARCHAR(64) NOT NULL | Canonical document identifier (e.g. `aadhaar`, `bank_passbook`, `land_records`) |
| is_mandatory | BOOLEAN NOT NULL DEFAULT true | Whether the document is strictly required |
| guidance | TEXT | Practical procurement instructions for citizens |
| source_url | TEXT | Official guidelines or portal source URL |
| last_verified_at | TIMESTAMPTZ | Verification timestamp |
| is_active | BOOLEAN NOT NULL DEFAULT true | Soft-deactivation status flag |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | Record update timestamp |

**Constraints & Indexes:**
- Foreign Key: `fk_scheme_documents_scheme_id` referencing `schemes(id)` with `ON DELETE RESTRICT`
- Unique Constraint: `uq_scheme_documents_scheme_doc_type` on `(scheme_id, document_type)`
- Check Constraint: `ck_scheme_documents_type_nonempty` (`char_length(trim(document_type)) > 0`)

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

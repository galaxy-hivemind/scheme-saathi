# Scheme Saathi — Backend PRD

This document is maintained by the backend developer.
See the full PRD in the team's shared document store for complete requirements.

For the living technical reference, see:
- [Architecture](architecture.md)
- [API Contracts](api-contracts.md)
- [Database Schema](database-schema.md)
- [Development Workflow](development-workflow.md)

---

## Phase 1 Implementation & Audit Status: COMPLETED

All Phase 1 requirements have been implemented, audited, verified, and regression tested:

1. **Database Foundation:**
   - SQLAlchemy 2.0 ORM engine, connection pooling with pre-ping, session dependency injection with per-request cleanup and rollback.
   - Declarative base with UUID v4 primary keys and timezone-aware timestamp mixins.
   - Strict environment configuration with production safety validators (rejecting debug mode, weak/placeholder secrets, and insecure JWT algorithms in production).

2. **Authentication & Security:**
   - Citizen registration (`POST /api/v1/auth/register`) with automatic profile provisioning.
   - Credentials verification (`POST /api/v1/auth/login`) with rate-safe bcrypt hashing (12 rounds) and safe handling of bcrypt's 72-byte limit.
   - Signed JWT access tokens with strict algorithm enforcement (`HS256`, `HS384`, `HS512`) and expiry verification.
   - Protected identity verification endpoint (`GET /api/v1/auth/me`).
   - Rejection of inactive or deactivated accounts.
   - Zero sensitive authentication data or password hashes in API responses or logs.

3. **User Profile:**
   - Profile automatically created upon citizen registration.
   - Protected profile retrieval (`GET /api/v1/profile`) with user ownership enforcement.
   - Idempotent profile completion (`POST /api/v1/profile`) preventing 409 conflicts.
   - Progressive partial updates (`PUT /api/v1/profile`) preserving existing values and merging scheme-specific JSONB `profile_data`.

4. **Consent Management:**
   - Explicit immutable consent audit trail (`user_consents` table).
   - Granting consent (`POST /api/v1/profile/consent`) and explicit revocation (`POST /api/v1/profile/consent/revoke`) recording accurate timestamps.
   - Foreign key constraint on `users.id` with `RESTRICT` to prevent accidental deletion of consent audit history.
   - Chronological audit trail listing (`GET /api/v1/profile/consent`).

5. **Alembic Migrations:**
   - Head revision `bb1bf3e30acc` verified: fresh upgrade, rollback, foreign key integrity, and isolated schema upgrades.

6. **Database Target Safety & Isolation:**
   - Dual-isolation architecture: ephemeral Testcontainers (preferred) and privilege-restricted dedicated fallback databases.
   - Mandatory live connection catalog revalidation (`pg_roles`, `pg_auth_members`) immediately before DDL.
   - Fail-closed execution gatekeepers (`safe_drop_all`, `safe_create_all`, `safe_create_schema`, `safe_drop_schema`) respecting caller transaction ownership.
   - Development rule: all application-controlled destructive test operations must use the verified gateways. Direct raw SQL / SQLAlchemy DDL bypassing gateways is not intercepted by the Python runtime, but is prohibited by test policy and blocked against the application DB by restricted runtime role privileges and session lockout.
   - Injection-immune SQL composition with runtime DBAPI verification and cryptographically random container passwords.

---

## Phase 2 Implementation & Audit Status: COMPLETED

All Phase 2 requirements for the Government Scheme Catalogue, Data Management, and Search API have been implemented, tested, and verified:

1. **Relational PostgreSQL Schema & Constraints (`backend/app/models/`):**
   - Three core tables: `schemes`, `scheme_rule_versions`, `scheme_documents`.
   - Domain check constraints enforcing the 12 canonical categories (`ck_schemes_category`), `geographic_scope = 'central'` (`ck_schemes_geographic_scope`), and valid statuses (`ck_schemes_status`).
   - Foreign key constraints with `ON DELETE RESTRICT` on both child tables to prevent accidental deletion of scheme rules or document definitions.
   - Non-redundant indexing with composite index `(scheme_status, category)` and a partial unique index `uq_scheme_rule_versions_active` enforcing at most one active rule version per scheme (permitting zero or multiple inactive versions).
   - High-performance PostgreSQL GIN full-text search index (`idx_schemes_fts`) indexing `name`, `description`, `ministry`, `benefits`, and `target_beneficiaries` (`array_to_tsvector`).
   - Alembic migration `e7b2c419fa01` fully reversible with isolated schema migration tests.

2. **Authoritative Seed Datasets (`backend/data/schemes/`):**
   - 7 central schemes curated with atomic claim-level `source_evidence` manifests.
   - 4 `active` schemes verified against official 2026 government documentation (PIB releases, CSMC meetings, portal guidelines):
     - `PM-KISAN`: 24th instalment released 30 October 2026 (PIB PRID 2330414).
     - `PMAY-U`: 10th CSMC meeting held 16 October 2026 sanctioning 1.93 lakh houses.
     - `AB-PMJAY`: Ayushman Vaya Vandana 70+ cover expanded 29 October 2026 (PIB PRID 2330009).
     - `PM-SVANIDHI`: Extended to 31 March 2030 with enhanced credit limits (PIB PRID 2161157, 2303797).
   - 3 `pending_verification` schemes awaiting verified 2026 evidence (`PMUY`, `APY`, `PMKVY`), with `last_verified_at = null`.

3. **Safe CLI Seed Importer (`backend/app/scripts/seed_schemes.py`):**
   - `--dry-run` mode provides a detailed proposed change manifest with **zero DML** executions (verified via SQL DML listener).
   - In-memory Pydantic validation before opening any database transactions.
   - Conflict detection skips entire aggregate records unless `--allow-override-verified` is explicitly supplied.
   - Append-only rule version incrementing and automatic closure of previous versions' `effective_to` timestamps.
   - Soft-deactivation (`is_active = FALSE`) of omitted documents to preserve relational integrity.

4. **Authenticated Search & Detail APIs (`backend/app/api/v1/schemes.py`):**
   - `GET /api/v1/schemes`: Lightweight summary list with PostgreSQL FTS search (`q`), category filtering (`category`), deterministic sorting (`name ASC, id ASC`), pagination (`page`, `limit`), and `include_pending` filter. Gracefully handles stop words and punctuation.
   - `GET /api/v1/schemes/{scheme_id}`: Comprehensive detail endpoint with active documents and source evidence. Inactive/hidden schemes return 404. Deliberately excludes internal rule JSON to protect evaluator AST state.
   - Both endpoints strictly protected by Phase 1 JWT authentication.

5. **Test Suite:**
   - 38 new tests covering unit schemas, model constraints, importer flags, API behavior, and migration cycles. 100% pass rate.

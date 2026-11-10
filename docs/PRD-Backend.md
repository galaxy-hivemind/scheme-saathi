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

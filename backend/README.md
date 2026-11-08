# Scheme Saathi — Backend

Python + FastAPI backend for the Scheme Saathi platform.

## Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your actual PostgreSQL connection string and secrets

# 4. Run database migrations
alembic upgrade head

# 5. Start development server
uvicorn app.main:app --reload --port 8000
```

## Database setup (PostgreSQL)

Scheme Saathi requires PostgreSQL 14+.

### Option A: Local Docker / Colima
```bash
docker run -d --name scheme-saathi-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=scheme_saathi \
  -p 5432:5432 \
  postgres:16-alpine
```

### Option B: Supabase PostgreSQL
Set `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Applying Migrations
```bash
# Apply all pending migrations to the latest revision
alembic upgrade head

# Revert the latest migration
alembic downgrade -1

# Create a new migration after model changes
alembic revision --autogenerate -m "describe changes"
```

## API documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health

## Running tests

The test suite runs against isolated PostgreSQL test databases (`scheme_saathi_test` and `scheme_saathi_migration_test`).

### Fail-Closed Database Isolation Trust Model

The Scheme Saathi test runner employs a strict **fail-closed trust model** (`app.core.db_safety`) that guarantees destructive database operations (dropping tables, recreating tables, dropping schemas) can **never** execute against the application database (`DATABASE_URL`) or an unverified database:

1. **In-Database Sentinel (`_scheme_saathi_db_sentinel`):**
   Disposable test databases must contain a dedicated sentinel table and marker record (`scheme_saathi_test_isolation`) with:
   - `purpose`: explicitly matching execution scope (`regular_test` vs `migration_test`).
   - `is_disposable`: `TRUE`.
   - `database_name`: strictly matching the live session's `current_database()`.
2. **Anti-Application Database Check:**
   Target URLs, resolved host IPs (normalizing loopback aliases `127.0.0.1`, `localhost`, `0.0.0.0`), port, database name, and PostgreSQL cluster OIDs are compared against `DATABASE_URL`. Any match is immediately rejected with `ValueError`. Even if a sentinel marker exists in the application database, the anti-app check strictly prevents destructive operations.
3. **Fail-Closed on Ambiguity:**
   If PostgreSQL catalog permissions restrict reading cluster identifiers or the target database cannot be reached, the system will **never** treat missing identity information as proof of isolation.
4. **Separate Authorization Scopes:**
   Authorization environment variables are independent and non-interchangeable:
   - `ALLOW_TEST_DB_RESET=1` authorizes regular test database resets.
   - `ALLOW_MIGRATION_TESTS=1` authorizes migration test schema creation/deletion.
5. **Centralized Execution Gateways:**
   All destructive DDL calls route through verified functions (`safe_drop_all`, `safe_create_all`, `safe_create_schema`, `safe_drop_schema`). Protected system schemas (`public`, `pg_catalog`, `information_schema`) can never be dropped.

### Provisioning Test Databases

Before running tests on a freshly created test database, provision its sentinel:

```bash
# Provision regular test database sentinel:
ALLOW_TEST_DB_RESET=1 python -m app.core.db_safety provision --purpose regular_test

# Provision migration test database sentinel:
ALLOW_MIGRATION_TESTS=1 python -m app.core.db_safety provision --purpose migration_test
```

### Regular Test Suite

Destructive test database setup and teardown (`drop_all` / `create_all`) requires explicit authorization:
```bash
ALLOW_TEST_DB_RESET=1 pytest tests/ -v
```
> **Safety Notice:** Running tests with `ALLOW_TEST_DB_RESET=1` operates only on the verified disposable test database (`TEST_DATABASE_URL`). If the opt-in is missing, tests fail closed with a `PermissionError`.

### Migration Tests (Schema Isolated)

Migration tests run against an ephemeral test schema inside `scheme_saathi_migration_test` and require independent opt-in (`ALLOW_MIGRATION_TESTS=1`):
```bash
ALLOW_MIGRATION_TESTS=1 \
MIGRATION_TEST_DB_URL=postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test \
pytest tests/integration/test_migrations.py -v
```

### Full Test Suite Run

To run all unit, integration, safety, and API tests:
```bash
ALLOW_TEST_DB_RESET=1 ALLOW_MIGRATION_TESTS=1 pytest tests/ -v
```

### Verification Failure Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `PermissionError: Destructive operation on regular test database rejected: explicit opt-in required` | Opt-in variable was not provided | Prepend `ALLOW_TEST_DB_RESET=1` to your test command. |
| `PermissionError: Destructive operation for migration_test rejected: explicit opt-in required` | Migration opt-in missing | Prepend `ALLOW_MIGRATION_TESTS=1` to your test command. |
| `ValueError: Unsafe target: Database '...' lacks the required in-database disposable sentinel record` | Test database was not provisioned with sentinel | Run `ALLOW_TEST_DB_RESET=1 python -m app.core.db_safety provision --purpose regular_test`. |
| `ValueError: Conflicting database identity: Target database has sentinel purpose 'migration_test', but current execution requires 'regular_test'` | Attempting to run regular tests on migration DB (or vice versa) | Ensure `TEST_DATABASE_URL` and `MIGRATION_TEST_DB_URL` point to their respective databases. |
| `ValueError: Unsafe target: Target URL points to the active application database` | Database target points to or resolves to `DATABASE_URL` | Set `TEST_DATABASE_URL` to a distinct disposable database (e.g. `scheme_saathi_test`). |

## Authentication & Profile Endpoints

All authenticated routes expect the JWT token in the `Authorization` header:
`Authorization: Bearer <access_token>`

### 1. Register
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "citizen@example.com",
    "password": "SecurePassword123!",
    "full_name": "Ramesh Kumar",
    "preferred_language": "hi"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "citizen@example.com",
    "password": "SecurePassword123!"
  }'
```

### 3. Current User Identity
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <token>"
```

### 4. Fetch Profile
```bash
curl -X GET http://localhost:8000/api/v1/profile \
  -H "Authorization: Bearer <token>"
```

### 5. Update Profile
```bash
curl -X PUT http://localhost:8000/api/v1/profile \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Uttar Pradesh",
    "district": "Varanasi",
    "occupation": "farmer",
    "annual_family_income": 120000.0,
    "residence_type": "rural"
  }'
```

### 6. Record Consent (Grant)
```bash
curl -X POST http://localhost:8000/api/v1/profile/consent \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "consent_type": "data_processing",
    "consent_status": "given"
  }'
```

### 7. Revoke Consent
```bash
curl -X POST http://localhost:8000/api/v1/profile/consent/revoke \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "consent_type": "data_processing"
  }'
```

### 8. List Consent History
```bash
curl -X GET http://localhost:8000/api/v1/profile/consent \
  -H "Authorization: Bearer <token>"
```

## Project structure

```
app/
├── main.py               # FastAPI application entry point
├── core/                 # Config, security (bcrypt & JWT), exceptions, logging
├── api/v1/               # Route handlers (auth, profile, health)
├── agents/               # Gemini orchestrator and tool registry (Phase 8)
├── tools/                # Agent-callable tool wrappers
├── services/             # Business logic (auth_service, profile_service)
├── eligibility/          # Deterministic rule engine (Phase 3)
├── models/               # SQLAlchemy ORM models (User, UserProfile, UserConsent)
├── schemas/              # Pydantic request/response schemas
├── database/             # DB session, engine, dependencies, base
└── jobs/                 # APScheduler background jobs

alembic/
└── versions/             # Database migration revisions

data/
└── schemes/              # Curated scheme JSON seed files (Phase 2)

tests/
├── unit/                 # Security & utility tests
├── integration/          # PostgreSQL database tests
└── api/                  # Auth, profile, health route tests
```

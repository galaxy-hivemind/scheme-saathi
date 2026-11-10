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

The test suite provides two independent, verified isolation strategies:
1. **Genuinely Isolated Testcontainers (Preferred):** Launches a fresh, ephemeral PostgreSQL container on a dynamic port, generates a cryptographically random runtime password, administratively provisions the restricted runtime role (`scheme_saathi_test_user`) with strict non-administrative attributes and zero memberships, executes all tests under that restricted role, and completely destroys the container upon session completion.
2. **Dedicated Role-Isolated PostgreSQL Test Databases (Fallback):** Runs against pre-provisioned databases (`scheme_saathi_test` and `scheme_saathi_migration_test`) using the dedicated, privilege-restricted runtime role (`scheme_saathi_test_user`). Both execution paths enforce mandatory runtime-role catalog verification immediately before any DDL.

### Pure Unit Tests (Zero Database Fixtures)

Unit tests (such as JWT token validation, bcrypt password hashing, and settings checks) are strictly decoupled from database fixtures. They run entirely in-memory and require **zero authorization flags or database connections**:
```bash
pytest tests/unit/ -v
```

### Strategy A: Testcontainers PostgreSQL (Containerized Integration & API Tests)

To run integration and API tests against an ephemeral, auto-destroyed PostgreSQL container (requires zero fallback database credentials):
```bash
USE_TESTCONTAINERS=1 ALLOW_TEST_DB_RESET=1 pytest tests/integration/test_database.py tests/api/ -v
```
> **Architecture Scope & Limitation:** The current Testcontainers fixture architecture in `conftest.py` provisions and manages disposable containers for the database integration and API test suite. Migration test suites (`test_migrations.py`) and safety guard suites (`test_db_safety.py`) specifically target and validate local fallback database role configurations and fail-closed schema isolation against pre-provisioned databases.

### Strategy B: Dedicated Test Databases with Restricted Role (Fallback)

When running against a local PostgreSQL instance, the test runner enforces strict database and role-level isolation:

1. **Dedicated Test Runtime Role (`scheme_saathi_test_user`):**
   - Direct database privileges on the application database (`scheme_saathi`) are completely revoked (`REVOKE ALL ON DATABASE scheme_saathi`).
   - In standard PostgreSQL, `PUBLIC` retains `CONNECT` privilege on databases by default, which means `has_database_privilege(role, 'scheme_saathi', 'CONNECT')` evaluates to `True` via inheritance (preserving general PostgreSQL functionality across unrelated roles and databases).
   - Application database isolation is enforced through defense-in-depth:
     a. Session startup is blocked at the database engine level via `ALTER ROLE scheme_saathi_test_user IN DATABASE scheme_saathi SET session_preload_libraries = 'nonexistent_lib'`, which causes the PostgreSQL server backend process to abort initialization (`FATAL`) immediately upon connection authentication.
     b. DDL gateway and target verification (`validate_database_target`, `verify_connection_isolation`) actively check `current_database() != 'scheme_saathi'` and fail closed if an application target is provided.
     c. Public execution of the physical cluster identifier (`pg_control_system()`) is explicitly revoked from `PUBLIC` so unprivileged roles cannot query cluster identifiers across databases.
   - Has only **SELECT-only** access on the in-database sentinel (`_scheme_saathi_db_sentinel`).
   - The test runner **cannot** insert, update, delete, or recreate the sentinel table (`permission denied`).
   - The test runner **never** auto-provisions sentinels; a missing sentinel causes immediate failure.
   - Requires explicit `TEST_DB_PASSWORD` configuration; default or placeholder passwords are strictly forbidden.

2. **One-Time Administrative Setup:**
   Run administrative provisioning using admin credentials (`postgres`):
   ```bash
   # 1. Configure restricted test runtime role (requires TEST_DB_PASSWORD):
   TEST_DB_PASSWORD="your_test_password" python -m app.core.db_safety setup-roles

   # 2. Provision regular test database sentinel:
   TEST_DB_PASSWORD="your_test_password" ALLOW_TEST_DB_RESET=1 python -m app.core.db_safety provision --purpose regular_test

   # 3. Provision migration test database sentinel:
   TEST_DB_PASSWORD="your_test_password" ALLOW_MIGRATION_TESTS=1 python -m app.core.db_safety provision --purpose migration_test
   ```

3. **Running Regular Test Suite:**
   ```bash
   TEST_DB_PASSWORD="your_test_password" ALLOW_TEST_DB_RESET=1 pytest tests/integration/test_database.py -v
   ```

4. **Running Schema-Isolated Migration Tests:**
   Migration tests run against dynamically generated ephemeral schemas (`migtest_<uuid>`) inside `scheme_saathi_migration_test` using the restricted role:
   ```bash
   TEST_DB_PASSWORD="your_test_password" ALLOW_MIGRATION_TESTS=1 pytest tests/integration/test_migrations.py -v
   ```

### Full Fallback Test Suite Run

To run all unit, integration, safety, migration, and API tests:
```bash
TEST_DB_PASSWORD="your_test_password" ALLOW_TEST_DB_RESET=1 ALLOW_MIGRATION_TESTS=1 pytest tests/ -v
```

### Fail-Closed Database Isolation Trust Model

The Scheme Saathi test runner employs a strict **fail-closed trust model** (`app.core.db_safety`) that guarantees destructive database operations (dropping tables, recreating tables, dropping schemas) can **never** execute against the application database (`DATABASE_URL`) or an unverified database:

1. **Unconditional Connected Database Name Check:**
   `current_database()` of the target is compared directly against `current_database()` of the application database. If they match, the target is **unconditionally rejected**, regardless of hostnames, ports, driver schemes, or proxy endpoints.
2. **Fail-Closed on Unreachable Application Database:**
   If the application database cannot be reached during verification, the system refuses destructive operations and fails closed with a `RuntimeError`.
3. **In-Database Sentinel Contract (`_scheme_saathi_db_sentinel`):**
   Disposable test databases must contain an administratively provisioned sentinel record with:
   - `purpose`: explicitly matching execution scope (`regular_test` vs `migration_test`).
   - `is_disposable`: `TRUE`.
   - `database_name`: strictly matching the live session's `current_database()`.
   Test fixtures never auto-provision or self-certify sentinels.
4. **Separate Authorization Scopes:**
   Authorization environment variables are independent and non-interchangeable:
   - `ALLOW_TEST_DB_RESET=1` authorizes regular test database resets.
   - `ALLOW_MIGRATION_TESTS=1` authorizes migration test schema creation/deletion.
5. **Centralized Execution Gateways & Bound DDL Connections:**
   All destructive DDL calls route through verified functions (`safe_drop_all`, `safe_create_all`, `safe_create_schema`, `safe_drop_schema`). The safety gate directly inspects the live SQLAlchemy connection (`verify_connection_isolation`) immediately prior to DDL and binds execution to that exact verified connection within an owned transaction scope or nested savepoint. Mismatched engines (e.g. administrative engines or engines targeting a different database) are rejected before DDL execution, leaving tables and schemas unchanged. Protected system schemas (`public`, `pg_catalog`, `information_schema`) can never be dropped.
6. **Mandatory Live Connection Catalog & Membership Verification:**
   Immediately prior to DDL execution, the gateway queries PostgreSQL system catalogs on the exact DDL execution connection to verify that the active role satisfies all security attributes: `rolsuper = FALSE`, `rolcreatedb = FALSE`, `rolcreaterole = FALSE`, `rolcanlogin = TRUE`, `rolinherit = FALSE`, `rolreplication = FALSE`, `rolbypassrls = FALSE`, and zero memberships in `pg_auth_members`. Any unexpected attribute, elevated membership, or query failure fails closed before DDL.
7. **Safe Testcontainers Provisioning & Driver Consistency:**
   When running under `USE_TESTCONTAINERS=1`, a fresh ephemeral container is initialized on a dynamic port using the verified `psycopg` (v3) driver and URL scheme (`postgresql+psycopg://`). A cryptographically random runtime password is generated per disposable instance (never logged or fixed). Role creation and permission grants are constructed using driver-verified SQL composition (`get_dbapi_sql_composer`) and validated identifiers. If container startup or provisioning fails, any active container is immediately stopped and state is cleaned up without leaving dangling resources or connections.

### Verification Failure Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `PermissionError: Destructive operation on regular test database rejected: explicit opt-in required` | Opt-in variable was not provided | Prepend `ALLOW_TEST_DB_RESET=1` to your test command. |
| `PermissionError: Destructive operation for migration_test rejected: explicit opt-in required` | Migration opt-in missing | Prepend `ALLOW_MIGRATION_TESTS=1` to your test command. |
| `ValueError: Unsafe target: Database '...' lacks the required in-database disposable sentinel record` | Test database was not provisioned with sentinel | Run administrative provisioning: `ALLOW_TEST_DB_RESET=1 python -m app.core.db_safety provision --purpose regular_test`. |
| `PermissionError: Connection mismatch: actual connection is using administrative/superuser role '...'` | An administrative engine was passed to a test DDL gateway | Ensure test fixtures and runners execute DDL using the configured restricted test runtime role (`scheme_saathi_test_user`). |
| `ValueError: Connection mismatch: actual connection is to database '...', but target URL specifies '...'` | Supplied engine connects to a different database than target | Align the execution engine with the verified target database URL. |
| `ValueError: Conflicting database identity: Target database has sentinel purpose 'migration_test', but current execution requires 'regular_test'` | Attempting to run regular tests on migration DB (or vice versa) | Ensure `TEST_DATABASE_URL` and `MIGRATION_TEST_DB_URL` point to their respective databases. |
| `ValueError: Unsafe target: Target URL points to the active application database` | Database target points to or resolves to `DATABASE_URL` | Set `TEST_DATABASE_URL` to a distinct disposable database (e.g. `scheme_saathi_test`) or use `USE_TESTCONTAINERS=1`. |

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

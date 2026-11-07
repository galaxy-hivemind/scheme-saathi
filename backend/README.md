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

The test suite runs against an isolated PostgreSQL test database (`scheme_saathi_test`):
```bash
pytest tests/ -v
```

### Migration Tests (Schema Isolated)

Migration tests run against an ephemeral test schema inside `scheme_saathi_migration_test` and require explicit opt-in:
```bash
ALLOW_MIGRATION_TESTS=1 \
MIGRATION_TEST_DB_URL=postgresql://postgres:postgres@localhost:5432/scheme_saathi_migration_test \
pytest tests/integration/test_migrations.py -v
```

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

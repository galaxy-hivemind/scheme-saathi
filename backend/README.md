# Scheme Saathi — Backend

Python + FastAPI backend for the Scheme Saathi platform.

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your actual values

# 4. Run database migrations (Phase 1 onwards)
# alembic upgrade head

# 5. Start development server
uvicorn app.main:app --reload --port 8000
```

## API documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health

## Running tests

```bash
pytest tests/ -v
```

## Project structure

```
app/
├── main.py               # FastAPI application entry point
├── core/                 # Config, security, exceptions, logging
├── api/v1/               # Route handlers (thin — logic lives in services)
├── agents/               # Gemini orchestrator and tool registry
├── tools/                # Agent-callable tool wrappers
├── services/             # Business logic
├── eligibility/          # Deterministic rule engine
├── models/               # SQLAlchemy ORM models
├── schemas/              # Pydantic request/response schemas
├── database/             # DB session and connection
└── jobs/                 # APScheduler background jobs

data/
└── schemes/              # Curated scheme JSON seed files

tests/
├── unit/
├── integration/
└── api/
```

## Key architectural decisions

- Route handlers are thin — all logic lives in services.
- Eligibility evaluation is **always** performed by the rule engine, never by the LLM.
- The LLM can read and explain eligibility results but cannot override them.
- Every consequential action (application submission) requires explicit user confirmation.
- All scheme data must include source URLs and verification dates.

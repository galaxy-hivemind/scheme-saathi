# Scheme Saathi 🇮🇳

**AI-powered government welfare scheme assistant for Indian citizens**

Scheme Saathi helps citizens discover relevant central-government welfare schemes, check their eligibility, prepare required documents, and track application progress — all through a natural, multilingual conversational interface.

---

## Project structure

```
scheme-saathi/
├── frontend/        # React + TypeScript (owned by frontend developer)
├── backend/         # Python + FastAPI (owned by backend developer)
├── docs/            # Shared architecture, API contracts, database schema
├── .gitignore
├── README.md
└── LICENSE
```

---

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # fill in your values
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in your values
npm run dev
```

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | System design and component responsibilities |
| [API Contracts](docs/api-contracts.md) | Shared endpoint definitions and schemas |
| [Database Schema](docs/database-schema.md) | Table definitions and relationships |
| [Development Workflow](docs/development-workflow.md) | Branching, commits, PRs, and integration |
| [Scheme Data Format](docs/scheme-data-format.md) | JSON schema for government schemes |

---

## Team

| Role | Responsibility |
|---|---|
| Backend developer | FastAPI, PostgreSQL, Gemini AI, eligibility engine |
| Frontend developer | React, TypeScript, UI/UX, Figma |

---

## Branch strategy

- `main` — stable integrated code
- `backend/phase-N-name` — backend feature branches
- `frontend/phase-N-name` — frontend feature branches

See [Development Workflow](docs/development-workflow.md) for full details.

---

## Tech stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (local instance or Supabase) |
| AI | Google Gemini with function/tool calling |
| Frontend | React, TypeScript, Vite |
| Auth | Native FastAPI (bcrypt password hashing + JWT access tokens) |
| Storage | Supabase Storage |
| Testing | Pytest (backend), Vitest (frontend) |

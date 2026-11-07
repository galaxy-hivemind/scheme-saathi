# Scheme Saathi — Development Workflow

## Branch strategy

```
main                              ← stable, integrated code
│
├── backend/phase-0-foundation    ← current
├── backend/phase-1-database
├── backend/phase-2-schemes
├── backend/phase-3-eligibility
├── backend/phase-4-documents
├── backend/phase-5-applications
├── backend/phase-6-submission
├── backend/phase-7-tracking
├── backend/phase-8-agent
│
├── frontend/phase-0-foundation
├── frontend/phase-1-onboarding
├── frontend/phase-2-chat
├── frontend/phase-3-schemes
├── frontend/phase-4-eligibility
├── frontend/phase-5-documents
├── frontend/phase-6-applications
└── frontend/phase-7-tracking
```

Create branches only when their phase begins. Never work directly on `main`.

---

## Daily workflow

### Starting a phase

```bash
# Always start from an up-to-date main
git checkout main
git pull origin main

# Create your feature branch
git checkout -b backend/phase-1-database
```

### During development

Commit small and often. Each commit should represent one logical change.

```bash
git add backend/           # never blindly add everything
git commit -m "feat(db): add users and user_profiles tables"
git push origin backend/phase-1-database
```

### Opening a Pull Request

1. Push your branch to GitHub.
2. Open a PR from your branch into `main`.
3. Write a clear description of what changed and why.
4. Tag your teammate for awareness on shared-contract changes.
5. Review the diff carefully — check for secrets, dead code, broken imports.
6. Run tests locally before requesting review.
7. Merge only when tests pass.

### After merge

```bash
git checkout main
git pull origin main

# If you're continuing work on the next phase
git checkout -b backend/phase-2-schemes
```

### Keeping feature branches up to date

```bash
git checkout backend/phase-1-database
git merge main
# resolve any conflicts, re-run tests
```

---

## Commit message conventions

Format: `type(scope): short description`

| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Setup, config, build tasks |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Code restructuring, no behaviour change |
| `style` | Formatting, no logic change |

**Examples:**
```
chore: initialize Scheme Saathi monorepo
feat(db): add eligibility_checks table and model
fix(eligibility): handle missing income field correctly
test(api): add health check endpoint tests
docs(api): update application lifecycle states
```

---

## Directory ownership

| Developer | Primary ownership |
|---|---|
| Backend | `backend/` |
| Frontend | `frontend/` |
| Both | `docs/`, root `README.md`, `docs/api-contracts.md` |

**Do not modify the other developer's implementation files.**
Coordinate via GitHub comments or direct communication before touching shared contracts.

---

## Environment setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # fill in real values
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # fill in real values
npm run dev
```

The frontend should connect to the backend through:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## Secrets and security rules

**Never commit:**
- `.env` files (only `.env.example`)
- API keys of any kind
- Supabase service role key
- Database passwords
- JWT secrets
- Private user documents

The `.gitignore` excludes `.env` and `.env.*`.
If you accidentally commit a secret, rotate it immediately and rewrite the git history with `git filter-branch` or `git filter-repo`.

---

## Integration between frontend and backend

1. Backend and frontend agree on API contracts **first** (see `docs/api-contracts.md`).
2. Frontend builds against mock responses matching the agreed shapes.
3. Backend implements the real endpoint.
4. Frontend replaces the mock with the real API call.
5. Both run integration tests together.

Do not silently fall back to mock data when the real API fails in production.

---

## Running tests

```bash
# Backend
cd backend
source .venv/bin/activate
pytest tests/ -v

# Frontend (once configured)
cd frontend
npm test
```

---

## Merge milestones

Both developers should merge small, working increments frequently.

| Milestone | Backend merges | Frontend merges |
|---|---|---|
| Phase 0 | Foundation + health API | React scaffold + design system |
| Phase 1 | DB + auth + profile APIs | Onboarding + profile screens |
| Phase 2 | Scheme catalogue + search | Scheme discovery screens |
| Phase 3 | Eligibility engine + API | Questionnaire + result screens |
| Phase 4 | Documents + OCR | Document upload screens |
| Phase 5 | Application draft + validate | Application form screens |
| Phase 6 | Submission workflow | Confirmation + status screens |
| Phase 7 | Tracking + notifications | Dashboard + timeline |
| Phase 8 | Gemini agent | Chat UI + structured cards |
| Phase 9 | Integration + tests | Integration + tests |

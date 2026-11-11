# Scheme Saathi — Deployment & Containerization Guide

This guide describes how to build, orchestrate, and deploy Scheme Saathi using Docker, Docker Compose, and cloud container environments.

---

## 1. Architecture Overview

Scheme Saathi is packaged into three orchestrated container services on a shared internal bridge network (`scheme-saathi-network`):

```
                       ┌────────────────────────┐
                       │      Browser / User    │
                       └───────────┬────────────┘
                                   │
                                   │ HTTP (Port 3000)
                                   ▼
             ┌──────────────────────────────────────────────┐
             │            scheme-saathi-frontend            │
             │           Nginx 1.27-Alpine Container        │
             │                                              │
             │  Static Assets (HTML/JS/CSS) ──► Port 80     │
             │  Reverse Proxy: /api/* ───────┐              │
             └───────────────────────────────┼──────────────┘
                                             │
                         Internal HTTP (8000)│
                                             ▼
             ┌──────────────────────────────────────────────┐
             │            scheme-saathi-backend             │
             │          Python 3.12-Slim Container          │
             │                                              │
             │  • FastAPI Application (Uvicorn)             │
             │  • Tesseract OCR Engine (Hindi + English)    │
             │  • Alembic Migrations & Auto-Seed Importer   │
             │  • Non-root runtime user (appuser:10001)     │
             └───────────────────────┬──────────────────────┘
                                     │
                 PostgreSQL Protocol │ (5432)
                                     ▼
             ┌──────────────────────────────────────────────┐
             │               scheme-saathi-db               │
             │          PostgreSQL 16-Alpine Container      │
             │                                              │
             │  • Persistent volume (scheme-saathi-pgdata)  │
             │  • Healthcheck: pg_isready                   │
             └──────────────────────────────────────────────┘
```

---

## 2. Quick Start with Docker Compose

### Prerequisites
- Docker Engine 24+ and Docker Compose v2+ (or Docker Desktop / Colima).
- Port 3000 (frontend), 8000 (backend), and 5432 (PostgreSQL) available on host.

### Starting the Platform
```bash
# 1. Clone the repository
git clone git@github.com:galaxy-hivemind/scheme-saathi.git
cd scheme-saathi

# 2. (Optional) Customize environment variables
cp .env.docker.example .env

# 3. Build images and start all containers in detached mode
docker-compose up -d --build

# 4. View status of orchestrated services
docker-compose ps
```

Once started:
- **Citizen Journey Web UI:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Interactive Swagger Docs:** [http://localhost:3000/docs](http://localhost:3000/docs) (or direct: [http://localhost:8000/docs](http://localhost:8000/docs))
- **Backend Health Check:** [http://localhost:3000/api/v1/health](http://localhost:3000/api/v1/health) (or direct: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health))

---

## 3. Container Services Detail

### 3.1 Database Service (`db`)
- **Image:** `postgres:16-alpine`
- **Volume:** `scheme-saathi-pgdata` maps to `/var/lib/postgresql/data` ensuring data survives container restarts.
- **Healthcheck:** `pg_isready -U postgres -d scheme_saathi` runs every 5 seconds. Dependent services wait until healthy.

### 3.2 Backend Service (`backend`)
- **Base Image:** `python:3.12-slim-bookworm`
- **System Binaries:** `tesseract-ocr`, `tesseract-ocr-hin` (Hindi dataset), `tesseract-ocr-eng`, `libpq5`, `curl`.
- **Security:** Runs as non-root user `appuser` (UID 10001, GID 10001).
- **Entrypoint Automation (`docker-entrypoint.sh`):**
  1. Polls database connection until PostgreSQL is ready to accept queries.
  2. Runs `alembic upgrade head` to apply all pending schema migrations.
  3. Executes `python -m app.scripts.seed_schemes --allow-override-verified` to ensure verified 2026 central schemes are indexed.
  4. Launches `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- **Healthcheck:** `curl -f http://localhost:8000/api/v1/health`.

### 3.3 Frontend Service (`frontend`)
- **Stage 1 (Builder):** `node:20-alpine` runs `npm ci && npm run build` with `VITE_API_BASE_URL=/api/v1`.
- **Stage 2 (Runtime):** `nginx:1.27-alpine` serves production bundle and proxies API requests.
- **Nginx Capabilities:**
  - Client-side SPA routing fallback (`try_files $uri $uri/ /index.html`).
  - Reverse proxy for `/api/` to `http://backend:8000/api/`, eliminating CORS in production.
  - Proxy for API documentation (`/docs`, `/redoc`, `/openapi.json`).
  - Gzip compression for static and API JSON payloads.
  - Standard security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`).

---

## 4. Operational Commands

### Viewing Logs
```bash
# Tail logs across all services
docker-compose logs -f

# Follow specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### Stopping and Cleaning Up
```bash
# Stop containers without losing database records
docker-compose down

# Stop containers and remove persistent database volume
docker-compose down -v
```

### Manual Schema Migration / Seeding inside Container
```bash
# Run migration manually
docker-compose exec backend alembic upgrade head

# Re-run scheme seed importer
docker-compose exec backend python -m app.scripts.seed_schemes --dry-run
```

---

## 5. Production Hardening Checklist

When deploying to production environments (AWS ECS, GCP Cloud Run, Railway, Kubernetes):
1. **Secrets:** Replace `SECRET_KEY` and `JWT_SECRET` with cryptographically random 32+ character keys (e.g. `openssl rand -hex 32`).
2. **CORS:** Restrict `ALLOWED_ORIGINS` in backend environment to exact production domain names.
3. **Database:** Use managed PostgreSQL (Supabase or AWS RDS) with SSL connection string (`sslmode=require`).
4. **AI Gateway:** Provide production `GEMINI_API_KEY` for Google Generative AI agent features.
5. **Storage:** Provide `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for encrypted citizen document vault storage.

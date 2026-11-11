#!/usr/bin/env bash
set -e

echo "==> [Scheme Saathi] Starting entrypoint initialization..."

# 1. Wait for database readiness if DATABASE_URL is configured
if [ -n "$DATABASE_URL" ]; then
  echo "==> [Scheme Saathi] Waiting for PostgreSQL database to accept connections..."
  python -c '
import sys
import time
import os
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
if not url or url.startswith("sqlite"):
    sys.exit(0)

max_retries = 30
for attempt in range(1, max_retries + 1):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"==> [Scheme Saathi] PostgreSQL connection verified on attempt {attempt}.")
        sys.exit(0)
    except Exception as exc:
        print(f"==> [Scheme Saathi] Waiting for database ({attempt}/{max_retries}): {exc}")
        time.sleep(1)

print("==> [Scheme Saathi] ERROR: Timed out waiting for database.")
sys.exit(1)
'
fi

# 2. Run Alembic schema migrations
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "==> [Scheme Saathi] Running Alembic schema migrations (alembic upgrade head)..."
  alembic upgrade head
  echo "==> [Scheme Saathi] Schema migrations applied successfully."
fi

# 3. Seed schemes catalogue if requested
if [ "${AUTO_SEED_SCHEMES:-true}" = "true" ]; then
  echo "==> [Scheme Saathi] Seeding authoritative government schemes data..."
  python -m app.scripts.seed_schemes --allow-override-verified || echo "==> [Scheme Saathi] Seed warning: seed script completed or skipped."
fi

echo "==> [Scheme Saathi] Initialization complete. Starting service..."
exec "$@"

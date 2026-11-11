# Scheme Saathi — Production Backend Dockerfile
# Python 3.12 + FastAPI + Tesseract OCR (Bilingual Hindi/English) + uv Package Manager

FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install runtime system packages and Tesseract OCR with Hindi and English language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-eng \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official binary for ultra-fast, deterministic package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create non-privileged user and application directory
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -d /home/appuser -s /bin/bash appuser

WORKDIR /app

# Install Python dependencies using uv directly into system Python environment
COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

# Copy application source code, Alembic migrations, configurations, and seed datasets
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY app /app/app
COPY data /app/data
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Ensure executable permissions and correct ownership
RUN chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appgroup /app /home/appuser

# Switch to non-root user
USER appuser

EXPOSE 8000

# Healthcheck monitoring the FastAPI health probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Two-target image:
#   target=api      → light API image (no crawl4ai, ~1.2 GB)
#   target=crawler  → adds crawl4ai for celery workers (~1.88 GB)
#
# Build via docker-compose using `target:` in each service definition.

FROM python:3.12-slim AS base

# System deps for psycopg2 and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install base Python dependencies (no crawl4ai / Playwright / scipy etc.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# ──────────────────────────────────────────────────────────────────────
# Target: api (light, for FastAPI server)
# ──────────────────────────────────────────────────────────────────────
FROM base AS api
# Run with 4 workers for production concurrency
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ──────────────────────────────────────────────────────────────────────
# Target: crawler (adds crawl4ai + heavy transitive deps — celery workers)
# ──────────────────────────────────────────────────────────────────────
FROM base AS crawler
COPY requirements-crawler.txt .
RUN pip install --no-cache-dir -r requirements-crawler.txt
# Install Chromium browser + its OS-level dependencies for Playwright.
# crawl4ai 0.8.x does NOT lazy-install browsers — it errors at run time if
# missing. Adds ~350 MB (chromium) + ~50 MB (fonts/libnss/libxkbcommon etc).
# Only chromium is installed (skip firefox/webkit to save space).
RUN apt-get update \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
CMD ["celery", "-A", "app.celery_app:celery", "worker", "--loglevel=info", "--concurrency=2"]

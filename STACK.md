# RAG SEO Engine — Technical Stack

Deep technical view of the codebase as of 2026-05-19. Pulled from `package.json`,
`requirements.txt`, `docker-compose.yml`, `backend/app/core/config.py`,
`backend/app/celery_app.py`, and the live source tree — not from memory.

---

## 1. High-Level Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │  Browser (admin dashboards, Spanish-first)  │
                    └───────────────────┬─────────────────────────┘
                                        │ HTTPS
                                        ▼
        ┌───────────────────────────────────────────────────────────┐
        │  Next.js 15 (standalone, port 3000)                       │
        │  - App Router, React 18, Zustand, Tailwind, Recharts      │
        │  - /api/* rewrite → BACKEND_URL                           │
        └───────────────────┬───────────────────────────────────────┘
                            │ /api/v1/...
                            ▼
        ┌───────────────────────────────────────────────────────────┐
        │  FastAPI (uvicorn, port 8000, 4 workers in prod)          │
        │  - 25+ routers under /api/v1                              │
        │  - Gzip → Metrics → CORS → SlowAPI rate limiter           │
        │  - Lifespan: init_db + background analytics sync          │
        └─┬─────────┬───────────────┬─────────────┬─────────────────┘
          │         │               │             │
          ▼         ▼               ▼             ▼
   ┌──────────┐ ┌────────┐ ┌────────────────┐ ┌─────────────┐
   │ Postgres │ │ Redis  │ │ Qdrant         │ │ External    │
   │ 15-alpine│ │ 7      │ │ v1.13.2        │ │ APIs        │
   │ :5432    │ │ :6379  │ │ :6333 / :6334  │ │ (see §10)   │
   └──────────┘ └───┬────┘ └────────────────┘ └─────────────┘
                   │
                   ▼
        ┌──────────────────────────────────────┐
        │  Celery (crawler image, +crawl4ai)   │
        │  - worker (concurrency=2)            │
        │  - beat (cron jobs, MX timezone)     │
        │  - flower (:5555, unauth UI)         │
        └──────────────────────────────────────┘
```

## 2. Frontend — Next.js 15

**Location:** `frontend/`
**Entry:** `frontend/app/layout.tsx`, `frontend/next.config.js`

### Dependencies (`frontend/package.json`)

| Package | Version | Role |
|---|---|---|
| `next` | ^15.5.16 | App Router, RSC, standalone build |
| `react` / `react-dom` | ^18.2.0 | UI runtime |
| `zustand` | ^4.5.0 | Client state (persisted via `zustand/middleware`) |
| `axios` | ^1.6.7 | HTTP client |
| `recharts` | ^3.7.0 | Charts (shadcn-style wrappers in `lib/chartConfigs.ts`) |
| `tailwindcss` | ^3.4.1 | Styling |
| `tailwind-merge` + `clsx` + `class-variance-authority` | — | shadcn-style class composition |
| `lucide-react` | ^0.575.0 | Icons |
| `papaparse` | ^5.5.3 | CSV parsing (GSC imports, inventory CSVs) |
| `typescript` | ^5 | Types (build errors ignored via `next.config.js`) |

### Build / runtime config

- `output: 'standalone'` — minimal node_modules in the Docker image.
- `typescript.ignoreBuildErrors: true` and `eslint.ignoreDuringBuilds: true`.
  Type-checking happens locally, not in CI gates.
- `NODE_OPTIONS=--max-old-space-size=4096` for dev/build/start — large pages
  pushed Node past default heap.
- `/api/:path*` rewrites to `BACKEND_URL` (default `http://localhost:8000`).
  In Docker Compose this is `http://backend:8000`.

### App Router layout

```
frontend/app/
├── layout.tsx              # Root, fonts (Montserrat + JetBrains Mono), Header
├── page.tsx                # Splash
├── (dashboard)/            # Route group
├── seo/
│   ├── dashboard/          # Priority Score + Optimization Queue
│   ├── intelligence/       # Real Impact score + Shopify snapshots
│   ├── articles/           # AEO article enrichment UI
│   ├── collections/        # Collection optimizer
│   └── unified-dashboard/
├── aeo/                    # AI visibility, orders, correlation ROI
│   ├── enrichment/
│   └── page.tsx
├── intelligence/
│   ├── opportunities/      # Creative Intelligence (demand-gap detectors)
│   ├── seo/
│   └── cro-technical/
├── solution-engine/        # Fault code → product recommendations
├── creative-intelligence/
├── inventory/
├── generate/[id]/          # Product content generation
├── chat/                   # AI chat
├── libraries/              # Knowledge libraries
├── supervisor/             # News supervisor agent dashboard
└── tier-sync/
```

### State

`frontend/app/store.ts` — single Zustand store with `persist` middleware.
Keeps a synced product list, selected product, generated content cache, and
`lastSynced` timestamp in localStorage so a dashboard reload doesn't refetch
5,000 SKUs.

### Styling

`frontend/tailwind.config.js` defines a custom design system:

- `v07.yellow` `#F7B500` (brand), `v07.bg`/`card`/`header` (dark palette).
- shadcn-style `chart.1`…`chart.5` HSL CSS vars for Recharts.
- Custom keyframes (`fadeIn`, `slideUp`, `diagonalReveal`, `glowPulse`).
- Industrial diagonal-line backgrounds via `repeating-linear-gradient`.

CSS rule from project memory: **never** use `!important`.

---

## 3. Backend — FastAPI

**Location:** `backend/`
**Entry:** `backend/app/main.py` (`app` object, lifespan, routers).

### Python runtime

- Python **3.12-slim** in Docker (`backend/Dockerfile`).
- Local venvs at project root (`venv/`) and `backend/.venv/`.
- `backend/pyproject.toml` declares `requires-python = ">=3.10"` and a Pyre
  config — used for type checking outside CI.

### Dependencies (`backend/requirements.txt` — API image)

| Package | Min version | Role |
|---|---|---|
| `fastapi` | 0.109.0 | Web framework |
| `uvicorn[standard]` | 0.27.0 | ASGI server |
| `sqlalchemy` | 2.0.25 | ORM |
| `psycopg2-binary` | 2.9.9 | Postgres driver |
| `aiosqlite` | 0.19.0 | Legacy SQLite (tests + fallback) |
| `redis` | 5.0.0 | Cache + Celery broker client |
| `qdrant-client` | 1.7.1 | Vector DB client |
| `pydantic` / `pydantic-settings` | 2.5+ / 2.1+ | Settings + schemas |
| `anthropic` | 0.18.0 | Claude SDK |
| `openai` | 1.12.0 | OpenAI / Grok-compatible clients |
| `celery[redis]` | 5.3.0 | Async task queue |
| `flower` | 2.0.0 | Celery monitoring UI |
| `slowapi` | 0.1.9 | Rate limiting |
| `ShopifyAPI` | 12.4.0 | Shopify Admin REST |
| `google-api-python-client` / `google-analytics-data` / `google-auth*` | — | GA4 + Search Console |
| `pypdf2` / `beautifulsoup4` / `openpyxl` | — | Document parsing, Excel export |
| `loguru` | 0.7.2 | Structured logging |
| `httpx` | 0.26.0 | Async HTTP |

### Crawler-only image (`requirements-crawler.txt`)

- `crawl4ai>=0.4.0` — pulls Playwright, patchright, scipy, numpy, litellm,
  nltk, shapely, alphashape. ~600 MB extra.
- Dockerfile crawler target also installs `chromium` via `playwright install
  --with-deps chromium` (~400 MB). Firefox/WebKit deliberately skipped.

### Middleware stack (`backend/app/main.py`)

Order matters — added outer-to-inner here means innermost runs first:

1. `MetricsMiddleware` (innermost) — records uncompressed payload size and a
   correlation `X-Request-ID`.
2. `GZipMiddleware` (`minimum_size=1000`) — compresses bodies above 1 kB.
3. `CORSMiddleware` — allows `localhost:3000`, `127.0.0.1:3000`,
   `frontend:3000`. Exposes `X-Request-ID` to the browser.
4. SlowAPI rate limiter + `RateLimitExceeded` exception handler.

### Lifespan

`@asynccontextmanager async def lifespan(app)`:

1. `init_db()` — creates tables + applies idempotent `ALTER TABLE` migrations
   (the auto-migrate fallback; see §5).
2. If `USE_CELERY=false`, spawns `_run_startup_sync()` as a background task:
   waits 5 s, checks if `Product.last_analytics_sync < 24 h`, otherwise syncs
   GA4 + GSC and Shopify sales data. This is the "no Celery, no problem"
   path for local dev.

### Routers (mounted under `/api/v1`)

`products`, `content`, `libraries`, `aeo`, `analytics`, `settings`,
`collection-optimizer`, `content-analyzer`, `product-visibility`,
`store-intelligence`, `seo-intelligence`, `seo-articles`, `solution-engine`,
`solution-engine-ai`, `products-ai`, `scrapers`, `tier-sync`, `tasks`,
`inventory`, `collections-ai`, `creative-intelligence`, `supervisor`,
`serp-sync`.

### Healthchecks

- `GET /` — project metadata.
- `GET /health` — probes Postgres (`SELECT 1`), Redis (if enabled), Qdrant
  (`GET /collections`).

---

## 4. Backend services map

`backend/app/services/`

| Service | Responsibility |
|---|---|
| `content_generator.py` | RAG product content generation |
| `dataforseo_service.py` | SERP, PAA, featured snippets |
| `google_api_service.py` | GA4 + Search Console |
| `collection_optimizer_service.py` | Collection SEO |
| `collection_cannibalization_guard.py` | Detect keyword conflicts between blog + collection |
| `collection_smart_recommendations.py` | Multi-agent collection recs |
| `collection_snapshot_service.py` | Trend snapshots for collections |
| `collection_intelligence_service.py` | Collection health reports |
| `ai_referral_tracker.py` | Attribute orders to AI sources (ChatGPT etc.) |
| `ai_visibility_service.py` | GEO visibility monitoring |
| `aeo/knowledge_graph.py` | Fault-code knowledge graph |
| `aeo/llms_txt_builder.py` | `/llms.txt` for AI crawlers |
| `aeo/schema_generator.py` | JSON-LD generation |
| `eeat_generator.py` | E-E-A-T authority signals |
| `blog_content_generator.py` | Blog content for fault codes |
| `article_enrichment_service.py` | TL;DR + FAQ + last_reviewed_at via PAA/GSC/Grok |
| `article_priority_score.py` / `priority_score.py` | CTR-curve-driven priority |
| `intelligence/intelligence_engine.py` | Store intelligence AI advisor |
| `intelligence/data_hub.py` | Unified data aggregation |
| `seo_intelligence/daily_collector.py` + `alert_service.py` | Daily harvest + alerts |
| `creative_intelligence_service.py` + `creative_intelligence_opportunities.py` | Demand-gap detectors |
| `solution_engine.py` / `solution_engine_ai.py` | Fault code → product recs |
| `supervisor/news_ingestor.py` + `daily_ingest.py` + `sources.py` | News supervisor agent |
| `qdrant_service.py` | Vector store ops |
| `product_embedding_service.py` | Embed product catalog into Qdrant |
| `redis_service.py` | Cache layer |
| `shopify_service.py` / `shopify_schema_service.py` | Shopify Admin REST + metafields |
| `multi_agent/orchestrator.py` + `agents.py` + `task_router.py` | Multi-agent task routing |
| `llm_service.py` + `llm_providers/*` | LLM abstraction (see §8) |
| `web_search_service.py` | Serper fallback when RAG returns < 3 chunks |
| `document_ingestion_service.py` | Crawl4AI → BS4 fallback for static pages |

---

## 5. Data layer

### Database

- **Postgres 15-alpine** in production/dev (`USE_POSTGRES=true`, see
  `docker-compose.yml`). Tuned via flags: `shared_buffers=256MB`,
  `effective_cache_size=512MB`, `max_connections=50`, `work_mem=2.5MB`,
  `random_page_cost=1.1`.
- **SQLite** legacy fallback (`rag_seo.db`) — still referenced in some
  tests; the `db_url` property in `config.py` switches based on `USE_POSTGRES`.
- Engine pool: `pool_pre_ping=True`, `pool_size=5`, `max_overflow=10`
  (`backend/app/db/session.py`).

### Models

`backend/app/models/`:

- `product.py` — central model. ~100 columns covering Shopify state, GA4
  metrics, GSC metrics, inventory intelligence (velocity, days-of-supply,
  dead-stock tier), anchor/co-purchase fields, computed priority score +
  `priority_components` JSON.
- `aeo_models.py`, `analysis_run.py`, `chat.py`,
  `collection_intelligence_models.py`, `collection_optimizer_models.py`,
  `creative_opportunity.py`, `inventory_models.py`, `library.py`,
  `seo_intelligence.py`, `solution_graph.py`, `store_intelligence.py`,
  `supervisor_models.py`.

### Migrations — dual strategy

1. **Alembic** (`backend/alembic/versions/`) — primary tool. 16 revisions
   covering: snapshot/shopify state, solution engine tables, store
   intelligence, creative opportunities, priority score, supervisor,
   collection optimizer (4 sequential + merge heads), product analytics.
2. **Idempotent `ALTER TABLE` fallback** in `init_db()` — runs at every
   startup, wrapped in try/except so already-applied columns get skipped.
   Adds inventory + collection-intelligence + AEO competitor columns that
   were added before formal Alembic revisions existed.

### Auto-sync at startup

If Celery is off, `_run_startup_sync()` pulls GA4 + GSC into `Product` rows
and re-pulls Shopify sales data into `sold_*` / `revenue_*` columns. Skipped
if `last_analytics_sync < 24 h`.

---

## 6. Vector layer — Qdrant + Embeddings

- **Qdrant** `v1.13.2`, ports 6333 (HTTP) / 6334 (gRPC), data in named volume
  `qdrant_data`. Default collection: `documents`.
- **Embeddings:**
  - Config default: `EMBEDDING_PROVIDER=openai`,
    `EMBEDDING_MODEL=text-embedding-3-small`.
  - Production runs Nomic-Embed-Text via Ollama (768 dims) — referenced in
    project memory; `EMBEDDING_PROVIDER=ollama` toggles it.
- **RAG knobs:** `RAG_CHUNK_SIZE=1000`, `RAG_CHUNK_OVERLAP=200`,
  `RAG_TOP_K=5`, `MAX_PROMPT_TOKENS=4000`.
- **Fallback:** if RAG returns < `WEB_SEARCH_MIN_RAG_CHUNKS` (default 3) and
  `WEB_SEARCH_FALLBACK=true`, `web_search_service` queries Serper.

---

## 7. Async layer — Celery + Redis

### Redis

- `redis:7-alpine`, port 6379, `maxmemory=256mb`, eviction `allkeys-lru`.
- Roles: Celery broker, Celery result backend, generic cache via
  `redis_service.py`.

### Celery (`backend/app/celery_app.py`)

- App name: `example-store`. Timezone: `America/Mexico_City`.
- Hard timeout 600 s, soft 540 s, prefetch 1, max tasks/child 50, result TTL
  1 h.
- Task modules: `sync_tasks`, `analytics_tasks`, `content_tasks`,
  `crawling_tasks`, `creative_intelligence_tasks`.

### Beat schedule (all times America/Mexico_City)

| Cron | Task | Why |
|---|---|---|
| 06:00 | `refresh_and_snapshot_analytics` | Pulls fresh GSC + GA4 into Product, recalcs SEO scores, persists daily snapshot — single source of fresh data for SEO Intelligence dashboard |
| 06:30 | `refresh_fault_codes_from_gsc` | Derives fault codes from GSC queries, keeps AEO knowledge graph synced to real demand |
| 06:45 | `sync_sales_data` | Incremental Shopify order sync |
| 07:00 | `seo_intelligence_collect` | GSC/GA4 keyword/page/cannibalization harvest |
| 07:30 | `detect_creative_opportunities` | Runs after morning GSC sync so it sees fresh data |
| 07:45 | `recompute_product_priority_scores` | Feeds `/seo/dashboard` Optimization Queue — must run before first dashboard load |
| Mon 03:00 | `derive_ctr_curve` | Re-derives position→CTR curve weekly |
| Mon 08:00 | `refresh_ai_visibility` | Weekly (daily would burn LLM budget without signal) |
| Sun 02:00 | `embed_product_catalog` | Weekly re-embed of Shopify catalog into Qdrant |

All entries include `expires: 3600` (1 h) — drops missed runs if beat was
down longer.

### Containers

- `celery-worker` — concurrency=2, uses crawler image (Playwright available).
- `celery-beat` — schedule persisted to `/tmp` (named volume `celery_beat_data`).
- `celery-flower` — port 5555, `FLOWER_UNAUTHENTICATED_API=true` (dev only).

---

## 8. LLM provider abstraction

`backend/app/services/llm_providers/` exposes a `base.py` interface
implemented by:

- `anthropic.py` — Claude (default model `claude-sonnet-4-5-20250929`).
- `openai.py` — OpenAI (default `gpt-5`).
- `grok.py` + `grok420.py` — X.AI Grok (`grok-4.20-0309-reasoning`, multi-agent
  variant `grok-4.20-multi-agent-0309`).
- `kimi.py` — Moonshot Kimi (`kimi-k2.5`).
- `ollama.py` — local Ollama (`llama3.2:latest`, also serves Nomic embeddings).
- `perplexity.py` — Perplexity Sonar (web-search-augmented).

`LLM_PROVIDER` env var selects the default at boot. `SUPERVISOR_SUMMARIZE_MODEL`
(default `grok-4`) overrides the model for the supervisor's news summarization
so triage work doesn't pay reasoning latency.

`multi_agent/orchestrator.py` routes by task type via `task_router.py`.

---

## 9. External integrations

| Integration | Service file | Notes |
|---|---|---|
| **Shopify Admin** | `shopify_service.py` | Store set via `SHOPIFY_STORE` env, API version `2025-01`. Two-way product + metafield sync + 301-redirect backfill scripts in `backend/scripts/`. |
| **Google Analytics 4** | `google_api_service.py` | Property ID via `GOOGLE_GA4_PROPERTY_ID`; service-account creds via `GOOGLE_APPLICATION_CREDENTIALS` (gitignored). |
| **Google Search Console** | `google_api_service.py` | Site set via `GOOGLE_SEARCH_CONSOLE_SITE_URL`. |
| **DataForSEO** | `dataforseo_service.py` | SERP, PAA, featured snippets. Gated by `DATAFORSEO_MIN_IMPRESSIONS=50` floor + `DATAFORSEO_SCRAPE_COMPETITORS` sub-toggle (the expensive Playwright path). Standard-endpoint mode (`DATAFORSEO_USE_STANDARD`) trades 30-60 s latency for 10× cost reduction. |
| **SerpAPI** | `dataforseo_service.py` (provider switch) | Free-tier fallback (`SERP_PROVIDER=serpapi`, 100 SERPs/month, no card). Same response shape as DataForSEO. |
| **Serper** | `web_search_service.py` | RAG fallback when fewer than 3 chunks. |
| **Grok API** | `llm_providers/grok.py`, `grok420.py` | Deep product analysis (SEO/AEO/GEO scores). |
| **Crawl4AI** | `document_ingestion_service.py` | Playwright-backed crawler in crawler image only. Falls back to `httpx + BeautifulSoup` on ImportError. |
| **Anthropic / OpenAI / Kimi / MiniMax / Mistral / Perplexity** | `llm_providers/*` | Config in `config.py`; any can be the default via `LLM_PROVIDER`. |

---

## 10. Containerization (`docker-compose.yml`)

Six services + 3 named volumes (`postgres_data`, `qdrant_data`,
`celery_beat_data`).

| Service | Image | Port | Depends on | Healthcheck |
|---|---|---|---|---|
| `postgres` | `postgres:15-alpine` | 5432 | — | `pg_isready` |
| `redis` | `redis:7-alpine` | 6379 | — | `redis-cli ping` |
| `qdrant` | `qdrant/qdrant:v1.13.2` | 6333/6334 | — | TCP probe |
| `backend` | `rag-seo-backend:latest` (target=api) | 8000 | postgres + redis + qdrant healthy | `curl /health` |
| `frontend` | built from `frontend/Dockerfile` | 3000 | backend healthy | `wget /` |
| `celery-worker` | `rag-seo-crawler:latest` (target=crawler) | — | postgres + redis | — |
| `celery-beat` | crawler image | — | postgres + redis + celery-worker | — |
| `celery-flower` | crawler image | 5555 | redis | — |

**Dockerfile is multi-stage two-target** (`backend/Dockerfile`):

- `base` (python:3.12-slim + libpq + gcc + `requirements.txt`).
- `api` target: 4-worker uvicorn (~1.2 GB).
- `crawler` target: extends base + `crawl4ai` + Chromium via Playwright
  (~1.88 GB). Used by all three Celery containers because they may scrape.

Compose overrides exist for dev (`docker-compose.dev.yml`),
production (`docker-compose.prod.yml`), and ad-hoc overrides
(`docker-compose.override.yml`).

---

## 11. Observability & Security

### Observability

- `MetricsMiddleware` (`backend/app/core/metrics.py`) — request/response
  metrics, generates correlation `X-Request-ID`.
- Prometheus exporter (productization foundation, commit `9affda9`).
- `loguru` structured logs. Log level by environment:
  development=DEBUG, staging=INFO, production=WARNING.

### Rate limiting

- `slowapi` instance in `backend/app/core/rate_limiter.py`, attached as
  `app.state.limiter` with `RateLimitExceeded` handler.

### Secrets

- `backend/.env` (gitignored) — DataForSEO, Grok, Shopify, Google creds.
- Google SA JSON mounted read-only into backend + celery containers from
  `./credentials/google-sa.json` (gitignored). Set `GOOGLE_SA_KEY_PATH` in `.env` to override.

### Caches

- Redis cache TTL by environment: dev=60 s, staging=300 s, prod=600 s.

---

## 12. Repo layout

```
RAG SEO ENGINE/
├── backend/                         # FastAPI app
│   ├── app/
│   │   ├── api/v1/endpoints/        # 25+ routers
│   │   ├── core/                    # config, logging, metrics, rate_limiter
│   │   ├── db/session.py            # SQLAlchemy engine + init_db auto-migrate
│   │   ├── models/                  # SQLAlchemy models
│   │   ├── schemas/                 # Pydantic
│   │   ├── services/                # 50+ service modules (see §4)
│   │   ├── tasks/                   # Celery tasks
│   │   ├── jobs/                    # Scheduled jobs
│   │   ├── celery_app.py            # Celery + beat schedule
│   │   ├── main.py                  # FastAPI app + lifespan + routers
│   │   └── scheduler.py
│   ├── alembic/                     # Migrations (16 revisions)
│   ├── scripts/                     # 301-redirect backfill etc.
│   ├── tests/
│   ├── Dockerfile                   # multi-stage: api + crawler
│   ├── requirements.txt             # API image deps
│   └── requirements-crawler.txt     # +crawl4ai/Playwright
├── frontend/                        # Next.js 15 dashboards
│   ├── app/                         # App Router pages
│   ├── components/                  # Shared components
│   ├── lib/                         # api.ts, chartConfigs.ts, parsers, utils
│   ├── store/                       # Zustand
│   ├── hooks/
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── package.json
├── docker-compose.yml               # Base compose
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── docker-compose.override.yml
```

---

## 13. Configuration matrix

`backend/app/core/config.py` is the single source of truth for feature flags.
Most important toggles:

| Setting | Default | Effect when on |
|---|---|---|
| `ENVIRONMENT` | `development` | Drives log level, cache TTL, uvicorn worker count |
| `USE_POSTGRES` | `false` | Switches `db_url` from SQLite to Postgres |
| `USE_REDIS` | `false` | Enables Redis cache + health probe |
| `USE_CELERY` | `false` | Skips startup-sync background task (lets beat own it) |
| `USE_DATAFORSEO` | `false` | Master DataForSEO toggle (SERP + keyword volumes) |
| `DATAFORSEO_SCRAPE_COMPETITORS` | `false` | Enables Playwright competitor scraping (the expensive path) |
| `DATAFORSEO_USE_STANDARD` | `false` | Async task endpoint ($0.06/1k) vs live ($0.60/1k) |
| `SERP_PROVIDER` | `dataforseo` | Or `serpapi` (free tier) |
| `WEB_SEARCH_FALLBACK` | `true` | Serper falls in when RAG returns < 3 chunks |
| `MULTI_AGENT_ENABLED` | `false` | Routes via `multi_agent/orchestrator.py` |
| `LLM_PROVIDER` | `ollama` | Default LLM (one of ollama/openai/anthropic/grok/minimax/kimi/mistral/perplexity) |
| `EMBEDDING_PROVIDER` | `openai` | Or `ollama` (Nomic) |

Effective uvicorn worker count: dev=1, staging=2, prod=4
(`settings.effective_workers`).

---

## 14. Local dev quickstart

```powershell
# 1. Start data plane
docker compose up -d postgres redis qdrant

# 2. Backend (in a venv)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend rewrites `/api/*` to
`http://localhost:8000`. Backend `/health` reports per-component status.

To run the full stack including Celery + Flower:

```powershell
docker compose up -d
```

Flower UI on `http://localhost:5555`.

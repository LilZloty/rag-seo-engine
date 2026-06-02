import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from sqlalchemy import text as import_text
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.metrics import MetricsMiddleware, metrics
from app.db.session import init_db, SessionLocal
from app.api.v1.endpoints import products, content, libraries, aeo_endpoints, analytics_endpoints, settings_endpoints, collection_optimizer_endpoints, content_analyzer, product_visibility_endpoints, store_intelligence, seo_intelligence_endpoints, seo_articles_endpoints, solution_engine, solution_engine_ai, products_ai, scraper_endpoints, tier_sync_endpoints, tasks, inventory_endpoints, creative_intelligence_endpoints, supervisor, serp_sync, sucursales_endpoints


async def _run_startup_sync():
    """Run analytics + sales sync in background on startup (when Celery is disabled)."""
    # Wait a few seconds for the app to fully start
    await asyncio.sleep(5)

    from datetime import datetime, timedelta, timezone
    from app.models.product import Product
    from sqlalchemy import func

    db = SessionLocal()
    try:
        # Check if any product has a recent sync (< 24h)
        last_sync = db.query(func.max(Product.last_analytics_sync)).scalar()
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

        # Normalize last_sync to offset-aware if needed
        if last_sync and last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)

        if last_sync and last_sync > stale_threshold:
            hours_ago = (datetime.now(timezone.utc) - last_sync).total_seconds() / 3600
            print(f"[STARTUP SYNC] Analytics data is fresh ({hours_ago:.1f}h old) — skipping sync")
            return

        hours_str = "never" if not last_sync else f"{(datetime.now(timezone.utc) - last_sync).total_seconds() / 3600:.1f}h ago"
        print(f"[STARTUP SYNC] Analytics data is stale (last sync: {hours_str}) — running background sync...")

        # 1. Sync GA4 + GSC data to products
        try:
            from app.services.product_service import ProductService
            service = ProductService(db)
            result = await service.sync_product_analytics()
            print(f"[STARTUP SYNC] Analytics sync done: {result.get('updated', 0)} products updated")
        except Exception as e:
            print(f"[STARTUP SYNC] Analytics sync failed (non-fatal): {e}")

        # 2. Sync Shopify sales data
        try:
            from app.services.shopify_service import ShopifyService
            shopify = ShopifyService()
            sales_data = shopify.get_product_sales_all_periods()
            updated = 0
            for product_shopify_id, periods in sales_data.items():
                product = db.query(Product).filter(Product.shopify_id == str(product_shopify_id)).first()
                if product:
                    product.total_sold = periods['90d']['total_sold']
                    product.total_revenue = periods['90d']['total_revenue']
                    product.sold_30d = periods['30d']['total_sold']
                    product.revenue_30d = periods['30d']['total_revenue']
                    product.sold_90d = periods['90d']['total_sold']
                    product.revenue_90d = periods['90d']['total_revenue']
                    product.sold_365d = periods['365d']['total_sold']
                    product.revenue_365d = periods['365d']['total_revenue']
                    product.sold_all_time = periods['all_time']['total_sold']
                    product.revenue_all_time = periods['all_time']['total_revenue']
                    updated += 1
            db.commit()
            print(f"[STARTUP SYNC] Sales sync done: {updated} products updated")
        except Exception as e:
            print(f"[STARTUP SYNC] Sales sync failed (non-fatal): {e}")

    except Exception as e:
        print(f"[STARTUP SYNC] Unexpected error: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, run background sync if data is stale."""
    init_db()
    print("[OK] Database initialized")

    # Run analytics sync in background (non-blocking) when Celery is disabled
    if not settings.USE_CELERY:
        asyncio.create_task(_run_startup_sync())

    yield
    print("[BYE] Shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Example Store SEO Content Generation Engine with RAG-powered Knowledge Libraries",
    lifespan=lifespan
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Metrics middleware — innermost so it records uncompressed payload sizes
app.add_middleware(MetricsMiddleware)

# Gzip after metrics, before CORS: compressed body, CORS headers applied
# to final response. 1000-byte floor avoids compressing trivially small payloads.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # let browsers read the correlation ID
)

# API Routes
app.include_router(products.router, prefix=settings.API_V1_STR, tags=["products"])
app.include_router(content.router, prefix=settings.API_V1_STR, tags=["content"])
app.include_router(libraries.router, prefix=settings.API_V1_STR, tags=["libraries"])
app.include_router(aeo_endpoints.router, prefix=f"{settings.API_V1_STR}/aeo", tags=["aeo"])
app.include_router(analytics_endpoints.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(settings_endpoints.router, prefix=f"{settings.API_V1_STR}/settings", tags=["settings"])
app.include_router(collection_optimizer_endpoints.router, prefix=f"{settings.API_V1_STR}/optimizer", tags=["collection-optimizer"])
app.include_router(content_analyzer.router, prefix=f"{settings.API_V1_STR}", tags=["content-analyzer"])
app.include_router(product_visibility_endpoints.router, prefix=f"{settings.API_V1_STR}", tags=["product-visibility"])
app.include_router(store_intelligence.router, prefix=f"{settings.API_V1_STR}", tags=["store-intelligence"])
app.include_router(seo_intelligence_endpoints.router, prefix=f"{settings.API_V1_STR}", tags=["seo-intelligence"])
app.include_router(seo_articles_endpoints.router, prefix=f"{settings.API_V1_STR}", tags=["seo-articles"])
app.include_router(solution_engine.router, prefix=f"{settings.API_V1_STR}", tags=["solution-engine"])
app.include_router(solution_engine_ai.router, prefix=f"{settings.API_V1_STR}", tags=["solution-engine-ai"])
app.include_router(products_ai.router, prefix=f"{settings.API_V1_STR}", tags=["products-ai"])
app.include_router(scraper_endpoints.router, prefix=settings.API_V1_STR, tags=["scrapers"])
app.include_router(tier_sync_endpoints.router, prefix=settings.API_V1_STR, tags=["tier-sync"])
app.include_router(tasks.router, prefix=settings.API_V1_STR, tags=["tasks"])
app.include_router(inventory_endpoints.router, prefix=settings.API_V1_STR, tags=["inventory"])

from app.api.v1.endpoints import collections_ai
app.include_router(collections_ai.router, prefix=f"{settings.API_V1_STR}", tags=["collections-ai"])
app.include_router(creative_intelligence_endpoints.router, prefix=f"{settings.API_V1_STR}", tags=["creative-intelligence"])
app.include_router(supervisor.router, prefix=f"{settings.API_V1_STR}", tags=["supervisor"])
app.include_router(serp_sync.router, prefix=f"{settings.API_V1_STR}/serp", tags=["serp-sync"])
app.include_router(sucursales_endpoints.router, prefix=f"{settings.API_V1_STR}", tags=["sucursales"])



@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "database": "postgresql"
    }


@app.get("/health")
async def health():
    """Enhanced health check — probes each dependency."""
    components = {}

    # Database
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        db.execute(import_text("SELECT 1"))
        db.close()
        components["database"] = {"status": "healthy", "type": "postgresql"}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # Redis
    if settings.USE_REDIS:
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            components["redis"] = {"status": "healthy"}
        except Exception as e:
            components["redis"] = {"status": "unhealthy", "error": str(e)}
    else:
        components["redis"] = {"status": "disabled"}

    # Qdrant
    try:
        import httpx
        resp = httpx.get(f"{settings.QDRANT_URL}/collections", timeout=3)
        components["qdrant"] = {"status": "healthy" if resp.status_code == 200 else "degraded"}
    except Exception:
        components["qdrant"] = {"status": "unreachable"}

    # Celery
    if settings.USE_CELERY:
        try:
            from app.celery_app import celery
            inspect = celery.control.inspect(timeout=2)
            active = inspect.ping()
            workers = len(active) if active else 0
            components["celery"] = {"status": "healthy" if workers > 0 else "no_workers", "workers": workers}
        except Exception as e:
            components["celery"] = {"status": "unhealthy", "error": str(e)}
    else:
        components["celery"] = {"status": "disabled"}

    overall = "healthy" if all(
        c.get("status") in ("healthy", "disabled") for c in components.values()
    ) else "degraded"

    return {
        "status": overall,
        "components": components,
        "llm": settings.DEFAULT_LLM,
    }


@app.get(f"{settings.API_V1_STR}/metrics")
async def get_metrics():
    """Request metrics: counts, latencies, error rates, cache hit rates."""
    return metrics.get_summary()


@app.get(f"{settings.API_V1_STR}/metrics/prometheus", response_class=PlainTextResponse)
async def get_metrics_prometheus():
    """Prometheus text-exposition-format metrics for scraping."""
    return metrics.get_prometheus()


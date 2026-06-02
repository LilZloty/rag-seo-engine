from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Register all SQLAlchemy models so mappers resolve cross-model relationships
import app.models  # noqa: F401

celery = Celery(
    "example-store",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Mexico_City",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,       # 10 min hard timeout
    task_soft_time_limit=540,  # 9 min soft timeout
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    result_expires=3600,
)

celery.conf.update(
    include=[
        "app.tasks.sync_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.content_tasks",
        "app.tasks.crawling_tasks",
        "app.tasks.creative_intelligence_tasks",
    ]
)

# ============================================================================
# CELERY BEAT SCHEDULE
# ============================================================================
# Runs in the celery-beat container (see docker-compose.yml).
# All times are America/Mexico_City (set above).
#
# Pipeline:
#   06:00 → Pull fresh GSC + GA4 data into Product fields, recalc SEO scores,
#            then persist a daily snapshot. This is the single source of fresh
#            data that the SEO Intelligence dashboard depends on.
#   06:45 → Sync Shopify orders incrementally (cheap, only fetches new orders)
#   07:00 → SEO Intelligence keyword/page/cannibalization harvest (GSC + GA4)
# ============================================================================
celery.conf.beat_schedule = {
    "refresh-and-snapshot-analytics-daily": {
        "task": "refresh_and_snapshot_analytics",
        "schedule": crontab(hour=6, minute=0),
        "options": {"expires": 3600},  # If beat is down >1h, drop the missed run
    },
    # Fault codes derived from GSC queries — keeps the AEO knowledge graph
    # synced to real search demand instead of a stale hardcoded list.
    # Runs 30 min after the product analytics sync so GSC quota isn't hit twice.
    "refresh-fault-codes-from-gsc-daily": {
        "task": "refresh_fault_codes_from_gsc",
        "schedule": crontab(hour=6, minute=30),
        "options": {"expires": 3600},
    },
    "incremental-order-sync-daily": {
        "task": "sync_sales_data",
        "schedule": crontab(hour=6, minute=45),
        "options": {"expires": 3600},
    },
    "seo-intelligence-collect-daily": {
        "task": "seo_intelligence_collect",
        "schedule": crontab(hour=7, minute=0),
        "options": {"expires": 3600},
    },
    # AI visibility: run once a week on Monday morning. Daily runs would burn
    # LLM budget without adding signal — transmission SERP-style landscape
    # changes slowly. Weekly gives a clean week-over-week trend.
    "refresh-ai-visibility-weekly": {
        "task": "refresh_ai_visibility",
        "schedule": crontab(hour=8, minute=0, day_of_week="monday"),
        "options": {"expires": 3600 * 6},  # 6h grace if beat is down
    },
    # Creative opportunity detection: runs after morning GSC sync (07:00) so it
    # operates on fresh keyword + impression data. Persists results via
    # signal_hash upserts; human status decisions survive across runs.
    "detect-creative-opportunities-daily": {
        "task": "detect_creative_opportunities",
        "schedule": crontab(hour=7, minute=30),
        "options": {"expires": 3600},
    },
    # Product catalog re-embed: weekly is plenty — new products picked up
    # on Sunday night so Monday's opportunities detector sees them.
    "embed-product-catalog-weekly": {
        "task": "embed_product_catalog",
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
        "options": {"expires": 3600 * 6},
    },
    # Position→CTR curve derivation: weekly is enough — impressions-weighted
    # buckets don't shift much over 7 days. Runs early Monday so the working
    # week starts with a freshly-derived curve driving priority scores.
    "derive-ctr-curve-weekly": {
        "task": "derive_ctr_curve",
        "schedule": crontab(hour=3, minute=0, day_of_week="monday"),
        "options": {"expires": 3600 * 6},
    },
    # Priority score recompute: nightly at 07:45 — after the 06:00 analytics
    # refresh + snapshot, after 07:30 creative opportunities, before users
    # arrive in the morning. This is what feeds the /seo/dashboard Optimization
    # Queue, so it has to run before the first dashboard load of the day.
    "recompute-priority-scores-daily": {
        "task": "recompute_product_priority_scores",
        "schedule": crontab(hour=7, minute=45),
        "options": {"expires": 3600},
    },
}

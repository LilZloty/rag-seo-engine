"""
Supervisor Agent API Endpoints

Phase 0+1: news ingestion + read API.
- POST /supervisor/news/ingest  — fetch + summarize new items (cron trigger)
- GET  /supervisor/news         — paginated feed of summarized items
- GET  /supervisor/runs         — recent supervisor runs (observability)
- GET  /supervisor/health       — quick check that the substrate is wired up
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.supervisor_models import NewsItem, SupervisorRun, SupervisorProposal
from app.services.supervisor.news_ingestor import ingest_news
from app.services.supervisor.sources import get_sources
from app.services.supervisor.tools import metrics_reader, aeo_reader, content_sampler

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


# ────────────────────────────────────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────────────────────────────────────

class NewsItemOut(BaseModel):
    id: int
    source: str
    title: str
    url: str
    summary_bullets: List[str] = []
    tag: Optional[str] = None
    relevance: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NewsFeedResponse(BaseModel):
    items: List[NewsItemOut]
    total: int
    page: int
    page_size: int
    by_tag: dict


class IngestResponse(BaseModel):
    run_id: int
    new_items: int
    summarized: int
    per_source_added: dict
    fetch_errors: List[str]
    duration_seconds: float


class RunOut(BaseModel):
    id: int
    mode: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary: Optional[str] = None
    artifacts: Optional[dict] = None
    cost_usd: Optional[float] = 0.0
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0

    class Config:
        from_attributes = True


class HealthOut(BaseModel):
    status: str
    sources_count: int
    news_items_count: int
    summarized_count: int
    last_ingest_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    summarizer_provider: str
    summarizer_configured: bool


# ────────────────────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────────────────────

@router.post("/news/ingest", response_model=IngestResponse)
async def trigger_news_ingest(
    background: bool = Query(False, description="If true, return 202 immediately and run in background"),
    summarize: bool = Query(True, description="If false, only fetch + dedup; skip LLM summarization"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Trigger news ingestion. Designed to be hit by a daily cron (9am Mexico time).

    By default runs synchronously and returns the full report. Set background=true
    to fire-and-forget (useful when the caller is a cron that doesn't care about
    the response).
    """
    if background:
        # Re-open a session inside the background task — the request-scoped
        # session in `db` would be closed by the time the task runs.
        from app.db.session import SessionLocal

        async def _run():
            bg_db = SessionLocal()
            try:
                await ingest_news(bg_db, summarize=summarize)
            finally:
                bg_db.close()

        if background_tasks is not None:
            background_tasks.add_task(_run)
        return IngestResponse(
            run_id=0, new_items=0, summarized=0,
            per_source_added={}, fetch_errors=[], duration_seconds=0.0,
        )

    try:
        result = await ingest_news(db, summarize=summarize)
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")


@router.get("/news", response_model=NewsFeedResponse)
def get_news_feed(
    tag: Optional[str] = Query(None, description="Filter by tag: algo|aeo|geo|tooling|policy|market|other"),
    relevance: Optional[str] = Query(None, description="Filter by relevance: high|medium|low|skip"),
    days: int = Query(14, ge=1, le=90, description="How many days back to include"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Paginated news feed. Defaults to last 14 days, all tags, all relevance levels
    (including skip — UI can hide them). The /supervisor page should default to
    `relevance != skip`.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_q = db.query(NewsItem).filter(
        # Use fetched_at as the floor — published_at is nullable for some feeds
        (NewsItem.fetched_at >= since)
    )
    if tag:
        base_q = base_q.filter(NewsItem.tag == tag)
    if relevance:
        base_q = base_q.filter(NewsItem.relevance == relevance)

    total = base_q.count()

    rows = (
        base_q.order_by(desc(NewsItem.published_at), desc(NewsItem.fetched_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Group counts by tag (across the whole filtered window — no relevance filter,
    # so the UI can show "12 algo / 4 aeo / 1 tooling" even when filtering)
    tag_counts_q = (
        db.query(NewsItem.tag, func.count(NewsItem.id))
        .filter(NewsItem.fetched_at >= since)
        .filter(NewsItem.relevance.in_(("high", "medium", "low")))  # exclude skip in tag chart
        .group_by(NewsItem.tag)
        .all()
    )
    by_tag = {(t or "untagged"): c for t, c in tag_counts_q}

    return NewsFeedResponse(
        items=[NewsItemOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        by_tag=by_tag,
    )


@router.get("/runs", response_model=List[RunOut])
def get_recent_runs(
    mode: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(SupervisorRun)
    if mode:
        q = q.filter(SupervisorRun.mode == mode)
    rows = q.order_by(desc(SupervisorRun.started_at)).limit(limit).all()
    return [RunOut.model_validate(r) for r in rows]


@router.get("/health", response_model=HealthOut)
def get_supervisor_health(db: Session = Depends(get_db)):
    """Quick check of the supervisor substrate — useful for the operator and for monitoring."""
    sources = get_sources()
    news_count = db.query(func.count(NewsItem.id)).scalar() or 0
    summarized_count = db.query(func.count(NewsItem.id)).filter(NewsItem.summarized_at.isnot(None)).scalar() or 0

    last_run = (
        db.query(SupervisorRun)
        .filter(SupervisorRun.mode == "news_ingest")
        .order_by(desc(SupervisorRun.started_at))
        .first()
    )

    status = "ok"
    if not settings.XAI_API_KEY:
        status = "degraded"
    elif last_run and last_run.status == "error":
        status = "degraded"

    return HealthOut(
        status=status,
        sources_count=len(sources),
        news_items_count=news_count,
        summarized_count=summarized_count,
        last_ingest_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
        summarizer_provider="grok",
        summarizer_configured=bool(settings.XAI_API_KEY),
    )


# ────────────────────────────────────────────────────────────────────────────
# Tool endpoints — Phase 2 read tools, exposed as REST so the supervisor agent
# (Phase 3) can call them via tool use, and so the operator can debug them.
# ────────────────────────────────────────────────────────────────────────────

@router.get("/tools/metrics")
def tool_metrics(
    days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
):
    """Combined GSC delta + GA4 totals for the supervisor's reasoning loop."""
    return metrics_reader.read_metrics_overview(days=days, baseline_days=baseline_days)


@router.get("/tools/metrics/gsc")
def tool_metrics_gsc(
    days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=180),
    top_movers: int = Query(10, ge=1, le=50),
):
    """GSC-only — totals + top moving queries between current and baseline windows."""
    return metrics_reader.read_gsc_metrics(days=days, baseline_days=baseline_days, top_movers=top_movers)


@router.get("/tools/metrics/ga4")
def tool_metrics_ga4(days: int = Query(7, ge=1, le=90)):
    """GA4-only — sessions, conversions, revenue, top pages."""
    return metrics_reader.read_ga4_traffic(days=days)


@router.get("/tools/aeo")
def tool_aeo(
    days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
):
    """Combined brand + product AEO visibility view."""
    return aeo_reader.read_aeo_overview(db, days=days, baseline_days=baseline_days)


@router.get("/tools/aeo/brand")
def tool_aeo_brand(
    days: int = Query(7, ge=1, le=90),
    baseline_days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
):
    """Brand-level visibility (AI engines): scores, deltas, top competitors cited."""
    return aeo_reader.read_brand_visibility(db, days=days, baseline_days=baseline_days)


@router.get("/tools/aeo/products")
def tool_aeo_products(
    days: int = Query(14, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Per-product visibility — top winners and losers in AI citation rate."""
    return aeo_reader.read_product_visibility(db, days=days, limit=limit)


@router.get("/tools/content-samples")
def tool_content_samples(
    days: int = Query(7, ge=1, le=60),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Recent Grok content generations — drift detection, sample-grading."""
    return content_sampler.sample_recent_generations(db, limit=limit, days=days)

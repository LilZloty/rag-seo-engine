"""
SEO Articles Endpoints
======================
Powers the `/seo/articles` dashboard — the blog-article counterpart to
`/seo/dashboard` (which covers products + collections).

What it returns:
- Per-article GSC metrics (clicks, impressions, CTR, position)
- Per-article GA4 metrics (sessions, engagement time, bounce, conversions)
- AEO enrichment status (TL;DR, FAQs count, last reviewed)
- A computed priority_score (0-100) ranking optimization opportunity
- On-demand top queries with CTR-gap analysis for an expanded row

Article metrics are aggregated by `article_metrics_service.fetch_article_metrics()`,
which is cached at the service layer for 10 minutes. Priority is computed
inline in this endpoint because articles aren't stored in Postgres (they
live in Shopify) and the CTR curve cache makes the math cheap.

Routes:
  GET /api/v1/seo/articles                       — list + priority
  GET /api/v1/seo/articles/optimization-queue    — top-N by priority (slim)
  GET /api/v1/seo/articles/{article_id}/queries  — GSC top queries for one article
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.article_metrics_service import fetch_article_metrics
from app.services.article_priority_score import compute_article_priority
from app.services.google_api_service import GoogleApiService
from app.services.seo_opportunity import get_ctr_curve, _ctr_for_position

logger = logging.getLogger("seo_articles_endpoints")
router = APIRouter(prefix="/seo/articles", tags=["SEO Articles"])


def _enrich_with_priority(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach `priority_score` and `priority_components` to each article."""
    curve = get_ctr_curve()
    enriched: List[Dict[str, Any]] = []
    for a in articles:
        result = compute_article_priority(a, curve=curve)
        enriched.append({
            **a,
            "priority_score": result.score,
            "priority_components": result.components,
        })
    return enriched


@router.get("")
def list_seo_articles(
    blogs_first: int = Query(10, ge=1, le=50),
    articles_per_blog: int = Query(100, ge=1, le=250),
    min_score: float = Query(0.0, ge=0.0, le=100.0, description="Filter articles below this priority score"),
    sort: str = Query("priority", description="Sort: priority | impressions | sessions | position | aeo_score"),
    limit: Optional[int] = Query(None, ge=1, le=500),
):
    """List every blog article with full SEO + AEO metrics + priority score.

    Sort options:
      - `priority`     (default) — composite optimization opportunity
      - `impressions`  — highest GSC impressions first (visibility)
      - `sessions`     — highest GA4 sessions first (traffic)
      - `position`     — best GSC position first (already ranking well)
      - `aeo_score`    — highest AEO score first (most enriched)
    """
    try:
        articles = fetch_article_metrics(
            blogs_first=blogs_first,
            articles_per_blog=articles_per_blog,
        )
    except Exception as e:
        logger.error(f"fetch_article_metrics failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch article metrics: {str(e)}"
        )

    enriched = _enrich_with_priority(articles)

    if min_score > 0:
        enriched = [a for a in enriched if a["priority_score"] >= min_score]

    if sort == "impressions":
        enriched.sort(key=lambda a: a["gsc"]["impressions"] or 0, reverse=True)
    elif sort == "sessions":
        enriched.sort(key=lambda a: a["ga4"]["sessions"] or 0, reverse=True)
    elif sort == "position":
        # Lower position = better. Treat 0/None as worst (999).
        enriched.sort(key=lambda a: a["gsc"]["position"] if a["gsc"]["position"] else 999.0)
    elif sort == "aeo_score":
        enriched.sort(key=lambda a: a["aeo_score"], reverse=True)
    else:
        enriched.sort(key=lambda a: a["priority_score"], reverse=True)

    if limit:
        enriched = enriched[:limit]

    # Roll up totals for the header
    total_impressions = sum(a["gsc"]["impressions"] or 0 for a in enriched)
    total_clicks = sum(a["gsc"]["clicks"] or 0 for a in enriched)
    total_sessions = sum(a["ga4"]["sessions"] or 0 for a in enriched)
    total_projected_clicks = sum(
        a["priority_components"]["projected_clicks"]["value"] for a in enriched
    )
    needs_enrichment = sum(
        1 for a in enriched if not a["enrichment"]["fully_enriched"]
    )
    avg_position = (
        round(
            sum(a["gsc"]["position"] for a in enriched if a["gsc"]["position"])
            / max(1, sum(1 for a in enriched if a["gsc"]["position"])),
            2,
        )
        if enriched
        else 0.0
    )

    return {
        "count": len(enriched),
        "sort": sort,
        "totals": {
            "impressions_30d": total_impressions,
            "clicks_30d": total_clicks,
            "sessions_30d": total_sessions,
            "projected_clicks_potential": round(total_projected_clicks, 1),
            "needs_enrichment": needs_enrichment,
            "avg_position": avg_position,
        },
        "articles": enriched,
    }


@router.get("/optimization-queue")
def article_optimization_queue(
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.0, ge=0.0, le=100.0),
):
    """Top-N articles ranked by priority_score — the article equivalent of
    `/seo-intelligence/optimization-queue` for products.

    Slimmed payload: same as `list_seo_articles` but only the top N and only
    the fields the queue card needs (no body, no extra GA4 detail).
    """
    try:
        articles = fetch_article_metrics()
    except Exception as e:
        logger.error(f"fetch_article_metrics failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch article metrics: {str(e)}"
        )

    enriched = _enrich_with_priority(articles)
    enriched = [a for a in enriched if a["priority_score"] >= min_score]
    enriched.sort(key=lambda a: a["priority_score"], reverse=True)
    enriched = enriched[:limit]

    return {
        "limit": limit,
        "min_score": min_score,
        "count": len(enriched),
        "articles": [
            {
                "article_id": a["article_id"],
                "title": a["title"],
                "handle": a["handle"],
                "blog_handle": a["blog_handle"],
                "url": a["url"],
                "priority_score": a["priority_score"],
                "priority_components": a["priority_components"],
                "gsc": a["gsc"],
                "ga4": a["ga4"],
                "enrichment": a["enrichment"],
                "aeo_score": a["aeo_score"],
                "fault_codes": a["fault_codes"],
            }
            for a in enriched
        ],
    }


@router.get("/{article_id}/queries")
def get_article_top_queries(
    article_id: str,
    days: int = Query(90, ge=7, le=365),
    limit: int = Query(20, ge=1, le=50),
):
    """GSC top queries for one article, with CTR-gap vs the curve.

    Used by the dashboard's expand-row drawer: shows which queries drive
    impressions/clicks, the actual CTR, the expected CTR at that position,
    and the click headroom from closing the gap.

    `article_id` is the Shopify article ID (numeric or GID). We use it to
    look up the article's URL path via the cached article metrics — that
    avoids needing the URL passed in by the caller.
    """
    try:
        articles = fetch_article_metrics()
    except Exception as e:
        logger.error(f"fetch_article_metrics failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch article metrics: {str(e)}"
        )

    target = None
    for a in articles:
        if str(a["article_id"]) == str(article_id):
            target = a
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

    url_path = target["url"]
    google = GoogleApiService()
    try:
        queries = google.get_search_console_queries_for_url(
            url_path, days=days, limit=limit
        ) or []
    except Exception as e:
        logger.warning(f"GSC queries fetch failed for {url_path}: {e}")
        queries = []

    curve = get_ctr_curve()
    enriched_queries = []
    for q in queries:
        position = float(q.get("position") or 0.0)
        impressions = int(q.get("impressions") or 0)
        clicks = int(q.get("clicks") or 0)
        actual_ctr = (clicks / impressions) if impressions > 0 else 0.0
        expected_ctr = _ctr_for_position(position, curve)
        ctr_gap = round(actual_ctr - expected_ctr, 4) if expected_ctr > 0 else None
        potential_clicks = (
            max(0, int(impressions * (expected_ctr - actual_ctr)))
            if expected_ctr > actual_ctr
            else 0
        )
        enriched_queries.append({
            "query": q.get("query"),
            "position": round(position, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(actual_ctr, 4),
            "expected_ctr": round(expected_ctr, 4),
            "ctr_gap": ctr_gap,
            "is_underperforming": ctr_gap is not None and ctr_gap < -0.005,
            "potential_extra_clicks": potential_clicks,
        })

    enriched_queries.sort(key=lambda q: q["potential_extra_clicks"], reverse=True)

    return {
        "article_id": article_id,
        "article_title": target["title"],
        "url": url_path,
        "days": days,
        "count": len(enriched_queries),
        "queries": enriched_queries,
    }

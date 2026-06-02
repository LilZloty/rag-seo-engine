"""
Phase 3.2 — PAA + GSC enrichment for product JSON-LD.

Two enrichments, both reading from already-cached upstream services:

  1. PAA → FAQPage.mainEntity (merge, not replace)
     Real People-Also-Ask questions from Google Mexico SERP. Joins existing
     Grok-generated FAQs in the same FAQPage. Dedup is normalized-text exact
     match (lowercase + strip punctuation) — fuzzy match would be nicer but
     adds a dep; revisit if exact-match misses too many duplicates.

  2. GSC top queries → store_aeo.top_search_queries
     Actual queries that brought traffic to this product's URL, ordered by
     clicks. Not FAQs (they're search terms, not questions) — emitted as
     read-only metadata. Future: could become schema.org PotentialAction/
     SearchAction if a value materializes.

Both upstream services cache aggressively (DataForSEO 90d, GSC 30min via
Redis), so calling these on every /generate-schema is cheap for warm
products. Cold-start cost: ~$0.03 in DataForSEO calls per new product, one
time, then 90 days of cache.

Graceful failure throughout — if either service errors (no GSC auth, no
DataForSEO creds, network), return empty and let the schema compose without
the enrichment instead of failing the whole generation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger("product_paa_gsc")


class PAAQuestion(BaseModel):
    q: str = Field(..., min_length=5, max_length=300)
    a: str = Field(..., min_length=5, max_length=600)
    source: str = Field(default="paa")
    source_keyword: Optional[str] = None


class TopSearchQuery(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    clicks: int = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    position: float = Field(default=0.0)


def _normalize_question(text: str) -> str:
    """Lowercase + strip punctuation/extra whitespace for dedup comparison."""
    if not text:
        return ""
    norm = text.lower().strip()
    norm = re.sub(r"[¿?¡!.,;:()\[\]\"'`]", "", norm)
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


async def enrich_with_paa_questions(
    product,
    db: Session,
    existing_questions: Optional[List[str]] = None,
    max_questions: int = 5,
) -> List[PAAQuestion]:
    """Fetch PAA questions for this product's keywords, deduped vs existing FAQs.

    Pulls top GSC queries first (real search demand) so DataForSEO sees the
    keywords that actually matter for THIS product, not just title tokens.
    Both upstream calls are cache-hot for repeat generations.
    """
    if not getattr(product, "title", None):
        return []

    existing_norm = {_normalize_question(q) for q in (existing_questions or []) if q}

    handle = (getattr(product, "handle", "") or "").strip()
    gsc_queries: List[Dict[str, Any]] = []
    if handle:
        try:
            from app.services.google_api_service import GoogleApiService
            gsc = GoogleApiService()
            # get_product_gsc_queries is SYNC despite living next to async methods;
            # @cached decorator wraps the sync impl. No await.
            # 90-day window: transmission parts have slow SEO velocity; 30d returned
            # 5 rows vs 24 at 90d for a product with 1485 total impressions (audit
            # 2026-05-20). Most of the gap is GSC's per-query privacy threshold,
            # not something we can recover.
            gsc_queries = gsc.get_product_gsc_queries(handle, days=90, limit=30) or []
        except Exception as e:
            logger.info(f"[PAA] GSC queries unavailable for {handle}: {e}")
            gsc_queries = []

    try:
        from app.services.dataforseo_service import DataForSEOService
        dfs = DataForSEOService()
        serp = await dfs.get_serp_data_for_product(
            product_title=product.title,
            gsc_queries=gsc_queries,
            db=db,
            max_keywords=3,
        )
    except Exception as e:
        logger.info(f"[PAA] DataForSEO unavailable for {product.title!r}: {e}")
        return []

    paa_raw = (serp or {}).get("all_paa") or []
    results: List[PAAQuestion] = []
    seen_norms: set = set(existing_norm)

    for entry in paa_raw:
        if not isinstance(entry, dict):
            continue
        q = (entry.get("question") or "").strip()
        a = (entry.get("answer_snippet") or entry.get("answer") or "").strip()
        if not q or not a or len(q) < 5 or len(a) < 5:
            continue
        norm = _normalize_question(q)
        if norm in seen_norms:
            continue
        try:
            results.append(PAAQuestion(
                q=q,
                a=a,
                source="paa",
                source_keyword=entry.get("source_keyword"),
            ))
            seen_norms.add(norm)
        except Exception:
            continue
        if len(results) >= max_questions:
            break

    return results


async def get_top_search_queries(
    product,
    max_queries: int = 8,
    min_impressions: int = 3,
) -> List[TopSearchQuery]:
    """Top GSC queries this product's URL ranks for, sorted by clicks then impressions.

    `min_impressions` filters out 1-2 impression noise queries with no clicks —
    those are usually scrapers or single-human accidents. Set conservatively
    after the 2026-05-20 audit: real product queries cluster at 3-15 impressions
    over 90 days; threshold of 50 dropped everything for a 1485-impression product.

    `days=90` window: transmission parts have slow SEO velocity. 30-day window
    returned 1/5th the queries (5 vs 24 for the same product).
    """
    handle = (getattr(product, "handle", "") or "").strip()
    if not handle:
        return []
    try:
        from app.services.google_api_service import GoogleApiService
        gsc = GoogleApiService()
        rows = gsc.get_product_gsc_queries(handle, days=90, limit=50) or []
    except Exception as e:
        logger.info(f"[GSC] queries unavailable for {handle}: {e}")
        return []

    filtered: List[TopSearchQuery] = []
    for r in (rows or []):
        impressions = int(r.get("impressions") or 0)
        clicks = int(r.get("clicks") or 0)
        if impressions < min_impressions and clicks == 0:
            continue
        q = (r.get("query") or "").strip()
        if not q:
            continue
        try:
            filtered.append(TopSearchQuery(
                query=q,
                clicks=clicks,
                impressions=impressions,
                position=float(r.get("position") or 0.0),
            ))
        except Exception:
            continue

    filtered.sort(key=lambda x: (-x.clicks, -x.impressions))
    return filtered[:max_queries]


def paa_to_faq_entities(paa: List[PAAQuestion]) -> List[Dict[str, Any]]:
    """Convert PAA questions to schema.org Question entities for FAQPage.mainEntity."""
    return [
        {
            "@type": "Question",
            "name": q.q,
            "acceptedAnswer": {"@type": "Answer", "text": q.a},
        }
        for q in paa
    ]


def top_queries_to_compact_dicts(queries: List[TopSearchQuery]) -> List[Dict[str, Any]]:
    """Compact list for store_aeo.top_search_queries — frontend reads this."""
    return [
        {
            "query": q.query,
            "clicks": q.clicks,
            "impressions": q.impressions,
            "position": round(q.position, 1) if q.position else 0,
        }
        for q in queries
    ]

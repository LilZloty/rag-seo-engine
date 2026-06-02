"""
Article Metrics Service

Aggregates per-article performance + AEO-readiness data for the
`/aeo/enrichment` dashboard. One call returns the full table row payload.

Sources:
- Shopify Admin GraphQL → article list + three enrichment metafields (single
  batched call; ~one API request total instead of N+1)
- GSC blog pages (one cached call, mapped by URL)
- GA4 engagement (one cached call, mapped by URL)
- OBD-II fault-code regex over title + tags (no extra API calls)

AEO Score (0-100) — opinionated composite:
  +30  has tldr_summary metafield
  +30  has faqs metafield with >=3 items
  +10  last_reviewed_at set within the last 365 days
  +10  fault codes detected (entity-rich)
  +15  GSC avg position <= 20 (visible in SERP)
  + 5  word_count >= 500 (approximated from summary length × 4 here)
Total: 100.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.core.config import settings
from app.services.redis_service import cached
from app.services.shopify_service import shopify_service
from app.services.google_api_service import GoogleApiService
from app.services.article_enrichment_service import FAULT_CODE_PATTERN

logger = logging.getLogger("article_metrics_service")

_METRICS_CACHE_TTL = 600  # 10 minutes — heavy aggregate; refresh isn't urgent

ARTICLES_GRAPHQL_QUERY = """
query GetArticlesWithEnrichmentMetafields($blogsFirst: Int!, $articlesFirst: Int!) {
  blogs(first: $blogsFirst) {
    edges {
      node {
        id
        handle
        articles(first: $articlesFirst) {
          edges {
            node {
              id
              title
              handle
              tags
              publishedAt
              summary
              tldrSummary: metafield(namespace: "custom", key: "article_metafields_tldr_summary") { value }
              faqs: metafield(namespace: "custom", key: "article_metafields_faqs") { value }
              lastReviewedAt: metafield(namespace: "custom", key: "article_metafields_last_reviewed_at") { value }
            }
          }
        }
      }
    }
  }
}
"""


def _extract_id(gid: str) -> str:
    """gid://shopify/Article/123456 → '123456'."""
    if not gid:
        return ""
    return gid.rsplit("/", 1)[-1]


def _parse_int_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _faqs_count(raw_value: Optional[str]) -> int:
    if not raw_value:
        return 0
    try:
        data = json.loads(raw_value)
        if isinstance(data, list):
            return len([f for f in data if (f.get("q") or f.get("question"))])
    except json.JSONDecodeError:
        return 0
    return 0


def _detect_fault_codes(text: str, limit: int = 5) -> List[str]:
    if not text:
        return []
    seen: List[str] = []
    for m in FAULT_CODE_PATTERN.finditer(text):
        code = m.group(1).upper()
        if code not in seen:
            seen.append(code)
            if len(seen) >= limit:
                break
    return seen


def _compute_score(
    has_tldr: bool,
    faqs_count: int,
    last_reviewed_iso: Optional[str],
    fault_codes: List[str],
    gsc_position: Optional[float],
    word_count: int,
) -> int:
    score = 0
    if has_tldr:
        score += 30
    if faqs_count >= 3:
        score += 30
    if last_reviewed_iso:
        reviewed_dt = None
        try:
            reviewed_dt = datetime.fromisoformat(last_reviewed_iso[:10])
        except Exception:
            pass
        if reviewed_dt:
            age_days = (datetime.now() - reviewed_dt).days
            if age_days <= 365:
                score += 10
    if fault_codes:
        score += 10
    if gsc_position is not None and gsc_position <= 20:
        score += 15
    if word_count >= 500:
        score += 5
    return min(score, 100)


@cached(ttl=_METRICS_CACHE_TTL)
def fetch_article_metrics(blogs_first: int = 10, articles_per_blog: int = 100) -> List[Dict[str, Any]]:
    """
    Returns a list of article dicts with metafield status, GSC + GA4 metrics,
    fault codes detected, and computed AEO score. Cached at the service level
    (Redis, 10min) so the dashboard is snappy.
    """
    shopify_service._ensure_initialized()
    site_url = (settings.GOOGLE_SEARCH_CONSOLE_SITE_URL or "").rstrip("/")

    graphql_resp = shopify_service._graphql_request(
        ARTICLES_GRAPHQL_QUERY,
        {"blogsFirst": blogs_first, "articlesFirst": articles_per_blog},
    )

    blog_edges = (
        graphql_resp.get("data", {})
        .get("blogs", {})
        .get("edges", [])
    )

    google = GoogleApiService()
    try:
        gsc_pages = google.get_search_console_blog_data(days=30) or []
    except Exception as e:
        logger.warning(f"[metrics] GSC blog data failed: {e}")
        gsc_pages = []
    try:
        ga_pages = google.get_ga4_engagement_data(days=30) or []
    except Exception as e:
        logger.warning(f"[metrics] GA4 engagement data failed: {e}")
        ga_pages = []

    # Build URL → metrics maps (path-suffix match for resilience to subdomains)
    gsc_by_path: Dict[str, Dict[str, Any]] = {}
    for row in gsc_pages:
        page_url = row.get("page", "")
        path = page_url.split("//", 1)[-1].split("/", 1)
        path = "/" + path[1] if len(path) > 1 else page_url
        gsc_by_path[path] = row

    ga_by_path: Dict[str, Dict[str, Any]] = {p.get("page_path", ""): p for p in ga_pages}

    articles: List[Dict[str, Any]] = []
    for blog_edge in blog_edges:
        blog = blog_edge.get("node", {})
        blog_handle = blog.get("handle", "")
        for art_edge in blog.get("articles", {}).get("edges", []):
            n = art_edge.get("node", {})
            article_id = _extract_id(n.get("id", ""))
            handle = n.get("handle", "")
            title = n.get("title", "")
            summary = n.get("summary", "") or ""
            tags = n.get("tags", []) or []
            path = f"/blogs/{blog_handle}/{handle}"

            tldr_value = (n.get("tldrSummary") or {}).get("value")
            faqs_value = (n.get("faqs") or {}).get("value")
            last_reviewed_value = (n.get("lastReviewedAt") or {}).get("value")

            has_tldr = bool(tldr_value and tldr_value.strip())
            faqs_count = _faqs_count(faqs_value)

            # Fault-code detection over title + tags + summary (no body fetch here)
            detection_text = f"{title} {' '.join(tags)} {summary}"
            fault_codes = _detect_fault_codes(detection_text)

            gsc = gsc_by_path.get(path) or {}
            ga = ga_by_path.get(path) or {}

            # Approximate word count from summary if no body — used as a soft signal
            word_count = len((summary or "").split()) * 4

            score = _compute_score(
                has_tldr=has_tldr,
                faqs_count=faqs_count,
                last_reviewed_iso=last_reviewed_value,
                fault_codes=fault_codes,
                gsc_position=gsc.get("position"),
                word_count=word_count,
            )

            articles.append({
                "article_id": int(article_id) if article_id.isdigit() else article_id,
                "title": title,
                "handle": handle,
                "blog_handle": blog_handle,
                "url": path,
                "tags": tags,
                "published_at": n.get("publishedAt"),
                "enrichment": {
                    "has_tldr": has_tldr,
                    "faqs_count": faqs_count,
                    "last_reviewed_at": last_reviewed_value,
                    "fully_enriched": has_tldr and faqs_count >= 3,
                },
                "gsc": {
                    "clicks": gsc.get("clicks", 0),
                    "impressions": gsc.get("impressions", 0),
                    "ctr": gsc.get("ctr"),
                    "position": gsc.get("position"),
                },
                "ga4": {
                    "sessions": ga.get("sessions", 0),
                    "active_users": ga.get("active_users", 0),
                    "avg_duration": ga.get("avg_duration"),
                    "bounce_rate": ga.get("bounce_rate"),
                    "conversions": ga.get("conversions", 0),
                },
                "fault_codes": fault_codes,
                "aeo_score": score,
            })

    # Sort: lowest score first (these need attention most)
    articles.sort(key=lambda a: (a["aeo_score"], -(a["gsc"]["impressions"] or 0)))
    return articles

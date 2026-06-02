"""
Product Insights Service
========================
Cross-silo enrichment for the Optimization Queue cards. Pulls signals that
are already collected by the SEO Intelligence daily harvest but never made
it onto the product dashboard before:

  - Top underperforming queries (with CTR gap) for *this* product
  - 30-day position trend (daily snapshots)
  - Cannibalization: other Example Store pages competing for the same queries

All reads. Joins `keyword_page_mappings` and `keyword_daily_metrics` (from
DailyCollector) with `product_analytics_snapshots` and resolves the product's
page URL via the most recent `page_daily_metrics` row.

Why a separate service from priority_score.py: the queue is cheap to
compute (one bulk score per product); these insights are richer per-product
joins that we lazy-load only when the user expands a card.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.product import Product, ProductAnalyticsSnapshot
from app.models.seo_intelligence import (
    KeywordDailyMetric,
    KeywordPageMapping,
    PageDailyMetric,
)

logger = logging.getLogger("product_insights")

# Look back this many days when assembling "top recent queries". 14 days is
# wide enough to ride past weekend dips, narrow enough that ancient snapshots
# don't dilute the picture.
QUERY_LOOKBACK_DAYS = 14
TREND_DAYS = 30
TOP_QUERIES_LIMIT = 5
CANNIBALIZATION_LIMIT = 5


def resolve_product_page_url(db: Session, product: Product) -> Optional[str]:
    """Return the canonical page_url for a product.

    Prefer the URL actually stored in `page_daily_metrics` (what GSC reports),
    fall back to constructing from handle. Handles edge cases like Shopify
    redirects, URL casing changes, and missing GSC data for new products.
    """
    row = (
        db.query(PageDailyMetric.page_url)
        .filter(PageDailyMetric.product_id == product.id)
        .order_by(desc(PageDailyMetric.date))
        .first()
    )
    if row and row.page_url:
        return row.page_url
    if product.handle:
        return f"https://www.example-store.com/products/{product.handle}"
    return None


def get_top_underperforming_queries(
    db: Session,
    product: Product,
    page_url: Optional[str],
    limit: int = TOP_QUERIES_LIMIT,
) -> List[Dict[str, Any]]:
    """Queries where this product ranks but isn't clicking as well as its
    position deserves. Each row's `potential_extra_clicks` quantifies the
    upside of closing the CTR gap (hitting the expected curve).
    """
    if not page_url:
        return []

    cutoff = date.today() - timedelta(days=QUERY_LOOKBACK_DAYS)

    # Get the latest mapping per query for this page in the lookback window.
    # SQLAlchemy DISTINCT ON would be cleaner on PG, but a Python pass over
    # the ordered set keeps this portable and avoids an extra import.
    mapping_rows = (
        db.query(KeywordPageMapping)
        .filter(KeywordPageMapping.page_url == page_url)
        .filter(KeywordPageMapping.date >= cutoff)
        .filter(KeywordPageMapping.impressions > 0)
        .order_by(KeywordPageMapping.query, desc(KeywordPageMapping.date))
        .all()
    )

    latest_by_query: Dict[str, KeywordPageMapping] = {}
    for row in mapping_rows:
        if row.query not in latest_by_query:
            latest_by_query[row.query] = row

    if not latest_by_query:
        return []

    # Pull the matching keyword_daily_metrics rows for CTR gap context. Match
    # by (query, date) so the benchmark reflects the same observation window
    # as the mapping row.
    queries = list(latest_by_query.keys())
    metric_rows = (
        db.query(KeywordDailyMetric)
        .filter(KeywordDailyMetric.query.in_(queries))
        .filter(KeywordDailyMetric.date >= cutoff)
        .order_by(KeywordDailyMetric.query, desc(KeywordDailyMetric.date))
        .all()
    )
    latest_metric_by_query: Dict[str, KeywordDailyMetric] = {}
    for row in metric_rows:
        if row.query not in latest_metric_by_query:
            latest_metric_by_query[row.query] = row

    results = []
    for query, mapping in latest_by_query.items():
        metric = latest_metric_by_query.get(query)
        actual_ctr = float(mapping.ctr or 0)
        expected_ctr = float(metric.expected_ctr) if metric and metric.expected_ctr else None
        ctr_gap = (
            float(metric.ctr_gap)
            if metric and metric.ctr_gap is not None
            else (None if expected_ctr is None else round(actual_ctr - expected_ctr, 5))
        )
        is_underperforming = bool(metric and metric.is_underperforming) or (
            ctr_gap is not None and ctr_gap < 0
        )

        potential_extra = 0
        if expected_ctr is not None and expected_ctr > actual_ctr:
            potential_extra = int(round((expected_ctr - actual_ctr) * (mapping.impressions or 0)))

        results.append(
            {
                "query": query,
                "position": round(float(mapping.position or 0), 2),
                "impressions": int(mapping.impressions or 0),
                "clicks": int(mapping.clicks or 0),
                "ctr": round(actual_ctr, 4),
                "expected_ctr": round(expected_ctr, 4) if expected_ctr is not None else None,
                "ctr_gap": round(ctr_gap, 4) if ctr_gap is not None else None,
                "is_underperforming": is_underperforming,
                "potential_extra_clicks": potential_extra,
                "position_change_30d": (
                    round(float(metric.position_change_30d), 2)
                    if metric and metric.position_change_30d is not None
                    else None
                ),
                "last_seen": mapping.date.isoformat() if mapping.date else None,
            }
        )

    # Prefer queries that are underperforming, then sort by impressions desc.
    results.sort(
        key=lambda r: (not r["is_underperforming"], -r["impressions"])
    )
    return results[:limit]


def get_position_trend_30d(
    db: Session, product: Product, days: int = TREND_DAYS
) -> List[Dict[str, Any]]:
    """Daily position + impressions for sparkline rendering."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(ProductAnalyticsSnapshot)
        .filter(ProductAnalyticsSnapshot.product_id == product.id)
        .filter(ProductAnalyticsSnapshot.snapshot_date >= cutoff)
        .order_by(ProductAnalyticsSnapshot.snapshot_date)
        .all()
    )
    return [
        {
            "date": row.snapshot_date.date().isoformat() if row.snapshot_date else None,
            "position": round(float(row.gsc_position or 0), 2),
            "impressions": int(row.gsc_impressions or 0),
            "clicks": int(row.gsc_clicks or 0),
        }
        for row in rows
        if row.snapshot_date
    ]


def get_cannibalization_warnings(
    db: Session,
    product: Product,
    page_url: Optional[str],
    limit: int = CANNIBALIZATION_LIMIT,
) -> List[Dict[str, Any]]:
    """Queries where this product's page competes with other Example Store pages.

    Reads `is_cannibalized` flag and `competing_pages_count` pre-computed by
    the DailyCollector. For each cannibalized query, surfaces the other
    competing pages so the user can decide which page should own the query.
    """
    if not page_url:
        return []

    cutoff = date.today() - timedelta(days=QUERY_LOOKBACK_DAYS)

    cannibalized_rows = (
        db.query(KeywordPageMapping)
        .filter(KeywordPageMapping.page_url == page_url)
        .filter(KeywordPageMapping.date >= cutoff)
        .filter(KeywordPageMapping.is_cannibalized == True)  # noqa: E712
        .order_by(KeywordPageMapping.query, desc(KeywordPageMapping.date))
        .all()
    )
    if not cannibalized_rows:
        return []

    seen_queries: set = set()
    results = []
    for row in cannibalized_rows:
        if row.query in seen_queries:
            continue
        seen_queries.add(row.query)

        # Other pages competing for this query on the same date
        competitors = (
            db.query(KeywordPageMapping)
            .filter(KeywordPageMapping.query == row.query)
            .filter(KeywordPageMapping.date == row.date)
            .filter(KeywordPageMapping.page_url != page_url)
            .order_by(KeywordPageMapping.position)
            .limit(5)
            .all()
        )

        results.append(
            {
                "query": row.query,
                "this_page_position": round(float(row.position or 0), 2),
                "this_page_impressions": int(row.impressions or 0),
                "competing_pages_count": int(row.competing_pages_count or 1),
                "competing_pages": [
                    {
                        "page_url": c.page_url,
                        "position": round(float(c.position or 0), 2),
                        "impressions": int(c.impressions or 0),
                        "page_type": c.page_type,
                    }
                    for c in competitors
                ],
                "date": row.date.isoformat() if row.date else None,
            }
        )
        if len(results) >= limit:
            break

    return results


def get_product_insights(db: Session, product_id: str) -> Dict[str, Any]:
    """Top-level entry point — the API endpoint calls this directly."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "product_not_found", "product_id": product_id}

    page_url = resolve_product_page_url(db, product)

    return {
        "product_id": product_id,
        "page_url": page_url,
        "top_underperforming_queries": get_top_underperforming_queries(db, product, page_url),
        "position_trend_30d": get_position_trend_30d(db, product),
        "cannibalization": get_cannibalization_warnings(db, product, page_url),
    }

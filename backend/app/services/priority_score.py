"""
Priority Score Service
======================
Composite 0-100 score that ranks products by "should I optimize this one
this week?" Combines opportunity sizing (from seo_opportunity.py) with
trend, fixability, data confidence, and an effort penalty.

Formula (weights sum to 1.00 of positive contribution, minus an effort penalty):
    priority = 0.35 × projected_clicks_norm   (real CTR-curve-based opportunity)
             + 0.20 × revenue_potential_norm  (clicks × RPS or default conv × AOV)
             + 0.15 × trend_urgency           (position got worse over 30 days)
             + 0.15 × fixability              (has images, in stock, convertible, has content)
             + 0.10 × confidence              (data freshness + sample size)
             - 0.05 × effort_estimate         (more missing pieces = more work)

Each component normalizes to 0-100 with concrete caps documented inline.
Final score clamped to [0, 100].

Bulk recompute path: `compute_priority_scores_bulk(db)` runs nightly in
`recompute_product_priority_scores`. Per-product path: `compute_priority_score(...)`
takes a product + pre-fetched context (curve + 30-day-ago position lookup).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.product import Product, ProductAnalyticsSnapshot
from app.services.seo_opportunity import (
    get_ctr_curve,
    projected_click_gain,
    revenue_potential,
    default_target_position,
)

logger = logging.getLogger("priority_score")

# Component weights — exposed so a future calibration can tweak without
# rewriting the formula.
W_CLICKS = 0.35
W_REVENUE = 0.20
W_TREND = 0.15
W_FIXABILITY = 0.15
W_CONFIDENCE = 0.10
W_EFFORT = 0.05  # subtracted

# Normalization caps. A product hitting the cap gets 100 on that component;
# anything beyond the cap doesn't get extra credit. Caps tuned for Example Store's
# niche (4,600 products, 2,400 with GSC data, MXN AOV ~$800).
CAP_PROJECTED_CLICKS = 1000.0  # ~max realistic monthly gain for a top product
CAP_REVENUE_MXN = 30000.0
CAP_TREND_POSITIONS = 20.0  # losing 20+ ranks in 30d = 100% urgency
TREND_LOOKBACK_DAYS = 30


@dataclass
class PriorityResult:
    score: float
    components: Dict[str, Any]


def _norm(value: float, cap: float) -> float:
    """Linear-then-clip normalize to 0-100."""
    if value <= 0 or cap <= 0:
        return 0.0
    return round(min(100.0, (value / cap) * 100.0), 2)


def _fixability(product: Product) -> Tuple[float, Dict[str, bool]]:
    """How confident am I that fixing this will move the needle?

    Four equal-weighted checks (25 pts each):
      - has_images: any optimization is wasted on a product with 0 images
      - in_stock: don't burn hours optimizing an OOS SKU this week
      - convertible: sold_365d > 0 OR ga4_sessions >= 50 — proves real demand
      - has_baseline_content: description_length >= 100 OR seo_score >= 30
    """
    has_images = (product.image_count or 0) > 0
    in_stock = product.inventory_status != "out_of_stock"
    convertible = (product.sold_365d or 0) > 0 or (product.ga4_sessions or 0) >= 50
    has_baseline_content = (
        (product.description_length or 0) >= 100
        or (product.seo_score or 0) >= 30
    )
    flags = {
        "has_images": has_images,
        "in_stock": in_stock,
        "convertible": convertible,
        "has_baseline_content": has_baseline_content,
    }
    score = sum(25.0 for v in flags.values() if v)
    return score, flags


def _confidence(product: Product) -> Tuple[float, Dict[str, Any]]:
    """How much do I trust the signal? 50/50 between GSC and GA4 having usable data.

    Above 30 GSC impressions matches the CTR-curve min-samples threshold —
    below that the rank/CTR data is just noise.
    """
    gsc_ok = (product.gsc_impressions or 0) >= 30
    ga4_ok = (product.ga4_sessions or 0) >= 10
    details = {
        "gsc_impressions": int(product.gsc_impressions or 0),
        "ga4_sessions": int(product.ga4_sessions or 0),
        "gsc_above_threshold": gsc_ok,
        "ga4_above_threshold": ga4_ok,
    }
    score = (50.0 if gsc_ok else 0.0) + (50.0 if ga4_ok else 0.0)
    return score, details


def _effort(product: Product) -> Tuple[float, Dict[str, Any]]:
    """Rule-based effort estimate. Higher = more work to optimize.

    The dashboard subtracts this at 5% weight — a small nudge that breaks
    ties in favor of quick wins, not a dominant signal.
    """
    effort = 0.0
    drivers = []
    if (product.image_count or 0) == 0:
        effort += 50  # sourcing/creating images is the biggest single chunk
        drivers.append("missing_images")
    if (product.description_length or 0) < 100:
        effort += 30
        drivers.append("missing_description")
    if (product.seo_score or 0) < 40:
        effort += 20
        drivers.append("low_seo_score")
    score = min(100.0, effort)
    return score, {"score": score, "drivers": drivers}


def _trend_urgency(
    current_position: float, position_30d_ago: Optional[float]
) -> Tuple[float, Dict[str, Any]]:
    """Position got worse → urgency goes up. Stable or improving → 0.

    Capped at CAP_TREND_POSITIONS positions of decline (a 20-rank drop is
    catastrophic; anything beyond shouldn't get extra weight).
    """
    if not current_position or not position_30d_ago:
        return 0.0, {"delta": None, "has_baseline": False}
    delta = current_position - position_30d_ago  # positive = worse
    details = {
        "current_position": round(float(current_position), 2),
        "position_30d_ago": round(float(position_30d_ago), 2),
        "delta": round(delta, 2),
        "has_baseline": True,
    }
    if delta <= 0:
        return 0.0, details
    score = _norm(delta, CAP_TREND_POSITIONS)
    return score, details


def compute_priority_score(
    product: Product,
    curve: Optional[Dict[int, float]] = None,
    position_30d_ago: Optional[float] = None,
) -> PriorityResult:
    """Compute a single product's priority score + component breakdown.

    `curve` and `position_30d_ago` are passed in so a bulk loop doesn't pay
    Redis + DB round-trips per product.
    """
    c = curve if curve is not None else get_ctr_curve()
    current_pos = float(product.gsc_position or 0.0)
    impressions = int(product.gsc_impressions or 0)

    target_pos = default_target_position(current_pos)
    proj_clicks = projected_click_gain(impressions, current_pos, target_pos, curve=c)

    # Prefer revenue-per-session if the product has historical GA4 revenue + sessions.
    rps = None
    if (product.ga4_sessions or 0) > 0 and (product.ga4_revenue or 0) > 0:
        rps = float(product.ga4_revenue) / float(product.ga4_sessions)
    revenue = revenue_potential(proj_clicks, rps=rps)

    clicks_norm = _norm(proj_clicks, CAP_PROJECTED_CLICKS)
    revenue_norm = _norm(revenue, CAP_REVENUE_MXN)
    trend_score, trend_meta = _trend_urgency(current_pos, position_30d_ago)
    fix_score, fix_flags = _fixability(product)
    conf_score, conf_meta = _confidence(product)
    effort_score, effort_meta = _effort(product)

    score = (
        W_CLICKS * clicks_norm
        + W_REVENUE * revenue_norm
        + W_TREND * trend_score
        + W_FIXABILITY * fix_score
        + W_CONFIDENCE * conf_score
        - W_EFFORT * effort_score
    )
    score = max(0.0, min(100.0, round(score, 2)))

    components = {
        "score": score,
        "weights": {
            "clicks": W_CLICKS,
            "revenue": W_REVENUE,
            "trend": W_TREND,
            "fixability": W_FIXABILITY,
            "confidence": W_CONFIDENCE,
            "effort": -W_EFFORT,
        },
        "projected_clicks": {
            "value": proj_clicks,
            "normalized": clicks_norm,
            "current_position": current_pos,
            "target_position": target_pos,
            "impressions": impressions,
        },
        "revenue_potential": {
            "value": revenue,
            "normalized": revenue_norm,
            "used_rps": rps is not None,
            "rps": round(rps, 2) if rps else None,
        },
        "trend_urgency": {
            "value": trend_score,
            **trend_meta,
        },
        "fixability": {
            "value": fix_score,
            **fix_flags,
        },
        "confidence": {
            "value": conf_score,
            **conf_meta,
        },
        "effort_estimate": effort_meta,
    }
    return PriorityResult(score=score, components=components)


def _fetch_position_30d_lookup(db: Session) -> Dict[str, float]:
    """For each product, find the most recent snapshot at or before T-30 days.

    Returns {product_id: gsc_position}. Products with no snapshot in that
    window get omitted (callers treat as "no baseline").
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=TREND_LOOKBACK_DAYS)
    # One snapshot per product, the latest <= cutoff. We do this in Python after
    # ordering — simpler than DISTINCT ON when there's no Postgres-specific
    # SQLAlchemy dialect import already in this file.
    rows = (
        db.query(
            ProductAnalyticsSnapshot.product_id,
            ProductAnalyticsSnapshot.gsc_position,
            ProductAnalyticsSnapshot.snapshot_date,
        )
        .filter(ProductAnalyticsSnapshot.snapshot_date <= cutoff)
        .order_by(
            ProductAnalyticsSnapshot.product_id,
            desc(ProductAnalyticsSnapshot.snapshot_date),
        )
        .all()
    )
    lookup: Dict[str, float] = {}
    for row in rows:
        if row.product_id in lookup:
            continue  # already grabbed the most recent
        if row.gsc_position and row.gsc_position > 0:
            lookup[row.product_id] = float(row.gsc_position)
    return lookup


def compute_priority_scores_bulk(db: Session) -> Dict[str, Any]:
    """Recompute priority_score for every product and bulk-update the DB.

    Returns a summary suitable for Celery task output.
    """
    curve = get_ctr_curve()
    position_lookup = _fetch_position_30d_lookup(db)
    now = datetime.now(timezone.utc)

    products: Iterable[Product] = db.query(Product).all()
    updates = []
    score_buckets = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    top_score = 0.0
    total = 0

    for p in products:
        total += 1
        pos_30d = position_lookup.get(p.id)
        result = compute_priority_score(p, curve=curve, position_30d_ago=pos_30d)
        updates.append(
            {
                "id": p.id,
                "priority_score": result.score,
                "priority_components": result.components,
                "priority_computed_at": now,
            }
        )
        if result.score >= 75:
            score_buckets["75-100"] += 1
        elif result.score >= 50:
            score_buckets["50-75"] += 1
        elif result.score >= 25:
            score_buckets["25-50"] += 1
        else:
            score_buckets["0-25"] += 1
        if result.score > top_score:
            top_score = result.score

    # Chunked bulk update — keeps memory + statement size sane.
    CHUNK = 500
    for i in range(0, len(updates), CHUNK):
        db.bulk_update_mappings(Product, updates[i : i + CHUNK])
    db.commit()

    logger.info(
        "Priority scores recomputed: %d products, top=%s, distribution=%s",
        total,
        top_score,
        score_buckets,
    )
    return {
        "total_products": total,
        "top_score": top_score,
        "score_distribution": score_buckets,
        "products_with_30d_baseline": len(position_lookup),
        "computed_at": now.isoformat(),
    }

"""
SEO Opportunity Sizing
======================
Position-based CTR curve derivation + projected click-gain math.

Replaces the `revenue × 0.25` heuristic that previously powered the SEO
dashboard's "estimated impact". A real CTR-per-position curve lets us
project actual click gains from rank improvements.

The curve is derived weekly from Example Store's own GSC history
(Product.gsc_position / gsc_clicks / gsc_impressions). Buckets with
fewer than `min_samples` products fall back to a published industry curve
so positions we haven't ranked in yet still get a sensible estimate.

Why impressions-weighted (sum_clicks / sum_impressions) rather than a
simple average of per-product gsc_ctr: a product with 1,000 impressions
has 100x more signal than one with 10. Equal-weighting them lets a single
high-CTR low-impression outlier distort the bucket.

Public surface:
  - derive_ctr_curve(db)              build the curve from DB
  - build_and_cache_ctr_curve(db)     derive + cache in Redis (task entry point)
  - get_ctr_curve()                   cached read (industry fallback if cold)
  - get_ctr_curve_with_meta()         cached payload with sample counts
  - projected_click_gain(...)         expected click delta for a rank move
  - revenue_potential(...)            expected MXN value of those clicks
  - default_target_position(...)      sensible target rank for a given current rank
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.redis_service import cache

logger = logging.getLogger("seo_opportunity")

CTR_CURVE_CACHE_KEY = "seo:ctr_curve:v1"
CTR_CURVE_TTL_SECONDS = 7 * 24 * 60 * 60
MIN_SAMPLES_PER_BUCKET = 30
MAX_POSITION = 30

# Published AWR-style curve. Used as fallback for buckets where our own data
# is sparse (positions we rarely rank in). Numbers are realistic for niche
# e-commerce; transmission queries skew slightly lower at top positions
# because users compare 2-3 results before buying, but the order of magnitude
# is correct.
INDUSTRY_CTR_CURVE: Dict[int, float] = {
    1: 0.2820, 2: 0.1559, 3: 0.1100, 4: 0.0807, 5: 0.0613,
    6: 0.0490, 7: 0.0427, 8: 0.0353, 9: 0.0316, 10: 0.0299,
    11: 0.0214, 12: 0.0181, 13: 0.0162, 14: 0.0148, 15: 0.0134,
    16: 0.0121, 17: 0.0109, 18: 0.0099, 19: 0.0093, 20: 0.0086,
    21: 0.0070, 22: 0.0060, 23: 0.0052, 24: 0.0045, 25: 0.0040,
    26: 0.0035, 27: 0.0030, 28: 0.0025, 29: 0.0020, 30: 0.0015,
}

DEFAULT_CONV_RATE = 0.02
DEFAULT_AOV_MXN = 800.0


def derive_ctr_curve(
    db: Session, min_samples: int = MIN_SAMPLES_PER_BUCKET
) -> Dict[str, Any]:
    """Aggregate avg CTR per position bucket from Product.gsc_* fields.

    Returns a payload containing:
      - curve: dict[int, float]      position 1..MAX_POSITION → CTR (0-1 float)
      - sample_counts: dict[int, int]  products per bucket
      - fallback_positions: list[int]  buckets that fell back to industry curve
      - derived_from_count: int        total products contributing real signal
      - derived_at: ISO-8601 string
      - min_samples_threshold: int
    """
    rows = (
        db.query(
            sql_func.floor(Product.gsc_position).label("bucket"),
            sql_func.sum(Product.gsc_impressions).label("total_impressions"),
            sql_func.sum(Product.gsc_clicks).label("total_clicks"),
            sql_func.count(Product.id).label("sample_count"),
        )
        .filter(Product.gsc_position > 0)
        .filter(Product.gsc_position <= MAX_POSITION)
        .filter(Product.gsc_impressions > 0)
        .group_by(sql_func.floor(Product.gsc_position))
        .all()
    )

    derived: Dict[int, float] = {}
    sample_counts: Dict[int, int] = {}
    derived_from_count = 0
    for row in rows:
        pos = int(row.bucket)
        if pos < 1 or pos > MAX_POSITION:
            continue
        impressions = int(row.total_impressions or 0)
        clicks = int(row.total_clicks or 0)
        count = int(row.sample_count or 0)
        sample_counts[pos] = count
        if count >= min_samples and impressions > 0:
            derived[pos] = round(clicks / impressions, 5)
            derived_from_count += count

    curve: Dict[int, float] = {}
    fallback_positions = []
    for pos in range(1, MAX_POSITION + 1):
        if pos in derived:
            curve[pos] = derived[pos]
        else:
            curve[pos] = INDUSTRY_CTR_CURVE.get(pos, 0.0)
            fallback_positions.append(pos)

    return {
        "curve": curve,
        "sample_counts": sample_counts,
        "fallback_positions": fallback_positions,
        "derived_from_count": derived_from_count,
        "derived_at": datetime.now(timezone.utc).isoformat(),
        "min_samples_threshold": min_samples,
        "source": "derived" if derived else "industry_fallback_only",
    }


def build_and_cache_ctr_curve(db: Session) -> Dict[str, Any]:
    """Derive, cache for `CTR_CURVE_TTL_SECONDS`, and return the payload."""
    payload = derive_ctr_curve(db)
    cache.set(CTR_CURVE_CACHE_KEY, payload, ttl=CTR_CURVE_TTL_SECONDS)
    logger.info(
        "CTR curve derived: %d real buckets, %d fallback buckets, %d products sampled",
        MAX_POSITION - len(payload["fallback_positions"]),
        len(payload["fallback_positions"]),
        payload["derived_from_count"],
    )
    return payload


def get_ctr_curve() -> Dict[int, float]:
    """Return the cached position→CTR mapping.

    Cold cache → industry curve copy (lets the rest of the pipeline keep
    working before the first weekly derivation runs).
    """
    cached_payload = cache.get(CTR_CURVE_CACHE_KEY)
    if isinstance(cached_payload, dict) and "curve" in cached_payload:
        # JSON round-trip in Redis turns int keys into strings — restore.
        return {int(k): float(v) for k, v in cached_payload["curve"].items()}
    return INDUSTRY_CTR_CURVE.copy()


def get_ctr_curve_with_meta() -> Dict[str, Any]:
    """Return the full cached payload (curve + sample counts + metadata)."""
    cached_payload = cache.get(CTR_CURVE_CACHE_KEY)
    if isinstance(cached_payload, dict) and "curve" in cached_payload:
        cached_payload["curve"] = {
            int(k): float(v) for k, v in cached_payload["curve"].items()
        }
        return cached_payload
    return {
        "curve": INDUSTRY_CTR_CURVE.copy(),
        "sample_counts": {},
        "fallback_positions": list(INDUSTRY_CTR_CURVE.keys()),
        "derived_from_count": 0,
        "derived_at": None,
        "min_samples_threshold": MIN_SAMPLES_PER_BUCKET,
        "source": "industry_fallback_only",
    }


def _ctr_for_position(position: float, curve: Dict[int, float]) -> float:
    """Look up CTR for a continuous position by floor-bucketing."""
    if position <= 0:
        return 0.0
    bucket = max(1, int(position))
    if bucket > MAX_POSITION:
        return 0.0
    return curve.get(bucket, 0.0)


def projected_click_gain(
    impressions: int,
    current_pos: float,
    target_pos: float = 5.0,
    curve: Optional[Dict[int, float]] = None,
) -> float:
    """Expected click gain from moving a product from current_pos to target_pos.

    Returns 0 when:
      - impressions <= 0 (no demand signal)
      - current_pos <= 0 (no GSC data for this product)
      - target_pos >= current_pos (no improvement)
    """
    if impressions <= 0 or current_pos <= 0:
        return 0.0
    if target_pos >= current_pos:
        return 0.0

    c = curve if curve is not None else get_ctr_curve()
    current_ctr = _ctr_for_position(current_pos, c)
    target_ctr = _ctr_for_position(target_pos, c)
    gain = impressions * (target_ctr - current_ctr)
    return max(0.0, round(gain, 1))


def revenue_potential(
    projected_clicks: float,
    rps: Optional[float] = None,
    conv_rate: Optional[float] = None,
    aov: Optional[float] = None,
) -> float:
    """Expected MXN revenue from `projected_clicks`.

    Prefers revenue-per-session (most accurate when the product already has
    traffic). Falls back to conv_rate × AOV with niche defaults.
    """
    if projected_clicks <= 0:
        return 0.0
    if rps and rps > 0:
        return round(projected_clicks * rps, 2)
    cr = conv_rate if conv_rate and conv_rate > 0 else DEFAULT_CONV_RATE
    av = aov if aov and aov > 0 else DEFAULT_AOV_MXN
    return round(projected_clicks * cr * av, 2)


def default_target_position(current_pos: float) -> int:
    """Suggest a realistic target rank for a given current rank.

    Page 2 (11-20)        → position 5  (move onto page 1)
    Page 1 bottom (6-10)  → position 3
    Page 1 top (2-5)      → position 1
    Position 1            → already there
    Position 21+          → position 10 (push onto page 1 at all)
    """
    if current_pos <= 1:
        return 1
    if current_pos <= 5:
        return 1
    if current_pos <= 10:
        return 3
    if current_pos <= 20:
        return 5
    return 10

"""
Article Priority Score Service
==============================
Composite 0-100 score that ranks blog articles by "should I optimize this one
this week?" Mirrors the product priority_score.py formula but adapted for
articles, which have no direct revenue and live in Shopify (not our DB).

Why a separate formula:
- Articles don't have revenue → can't weight by MXN value.
- Articles don't have per-day position snapshots → no trend urgency component.
- Articles DO have AEO enrichment metafields (TL;DR + FAQs) — when those are
  missing, that's a concrete optimization lever the product formula doesn't have.

Formula (positive weights sum to 1.00, minus an effort penalty):
    priority = 0.40 × projected_clicks_norm    (CTR-curve based; rank gain → click gain)
             + 0.20 × enrichment_gap           (100 - aeo_score; inverse of completeness)
             + 0.15 × engagement_quality       (long time-on-page + low bounce + conversions)
             + 0.15 × traffic_potential        (raw GA4 sessions, scaled)
             + 0.10 × confidence               (GSC impressions + GA4 sessions thresholds)
             - 0.05 × effort_estimate          (missing tags / fault codes / body)

Each component normalizes to 0-100. Final score clamped to [0, 100].

This is computed on-the-fly in the `/api/v1/seo/articles` endpoint — articles
aren't stored in our Postgres DB (they live in Shopify), and the underlying
`article_metrics_service.fetch_article_metrics()` already caches the heavy
Shopify + GSC + GA4 aggregation for 10 minutes.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.seo_opportunity import (
    get_ctr_curve,
    projected_click_gain,
    default_target_position,
)

# Component weights — exposed so a future calibration can tweak without
# rewriting the formula. Match the spirit of priority_score.py but with the
# article-specific signals.
W_CLICKS = 0.40
W_ENRICHMENT = 0.20
W_ENGAGEMENT = 0.15
W_TRAFFIC = 0.15
W_CONFIDENCE = 0.10
W_EFFORT = 0.05  # subtracted

# Normalization caps. Tuned for Example Store's blog volume: most articles get
# 50-500 monthly impressions, top performers occasionally reach 5k. A
# top-tier article in pos 5 with 5,000 impressions would gain ~150 clicks
# by moving to pos 1, so 200 is a realistic ceiling.
CAP_PROJECTED_CLICKS = 200.0
CAP_GA4_SESSIONS = 1000.0  # one article hitting 1k sessions/month = saturated


@dataclass
class ArticlePriorityResult:
    score: float
    components: Dict[str, Any]
    projected_clicks: float
    target_position: int


def _norm(value: float, cap: float) -> float:
    if value <= 0 or cap <= 0:
        return 0.0
    return round(min(100.0, (value / cap) * 100.0), 2)


def _engagement_quality(ga4: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """How well does this article actually engage users when they arrive?

    Three equal-weight signals (33pt each, capped at 100):
      - duration_ok: avg_duration >= 60s (user actually read it)
      - bounce_ok: bounce_rate <= 0.65 (didn't immediately leave)
      - converts: at least one purchase/lead attributed (rare for articles, big signal)

    Missing data = signal off (don't penalize, just don't credit).
    """
    avg_duration = ga4.get("avg_duration") or 0.0
    bounce_rate = ga4.get("bounce_rate")
    conversions = int(ga4.get("conversions") or 0)

    duration_ok = avg_duration >= 60
    bounce_ok = bounce_rate is not None and bounce_rate <= 0.65
    converts = conversions > 0

    score = 0.0
    if duration_ok:
        score += 33.3
    if bounce_ok:
        score += 33.3
    if converts:
        score += 33.4

    return round(score, 1), {
        "avg_duration_s": round(float(avg_duration), 1),
        "bounce_rate": round(float(bounce_rate), 3) if bounce_rate is not None else None,
        "conversions": conversions,
        "duration_ok": duration_ok,
        "bounce_ok": bounce_ok,
        "converts": converts,
    }


def _confidence(gsc: Dict[str, Any], ga4: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """50/50 between GSC and GA4 having enough samples to trust.

    Same thresholds as the product formula: 30 GSC impressions matches the
    CTR-curve min-samples, 10 GA4 sessions is the minimum for engagement
    signals to be more than noise.
    """
    gsc_impr = int(gsc.get("impressions") or 0)
    ga4_sess = int(ga4.get("sessions") or 0)
    gsc_ok = gsc_impr >= 30
    ga4_ok = ga4_sess >= 10
    score = (50.0 if gsc_ok else 0.0) + (50.0 if ga4_ok else 0.0)
    return score, {
        "gsc_impressions": gsc_impr,
        "ga4_sessions": ga4_sess,
        "gsc_above_threshold": gsc_ok,
        "ga4_above_threshold": ga4_ok,
    }


def _effort(article: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """How much work is required to optimize this article? Higher = more work.

    Drivers (additive, capped at 100):
      - no_tldr: writing a TL;DR is the cheapest, biggest unlock
      - few_faqs: <3 FAQs means we need to generate them (the article enrichment
        endpoint handles this; effort is real)
      - no_tags: article hasn't been categorized, harder to surface keyword
      - no_fault_codes: niche-irrelevant article OR very generic; can't reuse
        knowledge graph facts during enrichment
    """
    enr = article.get("enrichment") or {}
    has_tldr = bool(enr.get("has_tldr"))
    faqs_count = int(enr.get("faqs_count") or 0)
    tags = article.get("tags") or []
    fault_codes = article.get("fault_codes") or []

    drivers = []
    effort = 0.0
    if not has_tldr:
        effort += 35
        drivers.append("missing_tldr")
    if faqs_count < 3:
        effort += 30
        drivers.append("missing_faqs")
    if not tags:
        effort += 20
        drivers.append("no_tags")
    if not fault_codes:
        effort += 15
        drivers.append("no_fault_codes")

    score = min(100.0, effort)
    return score, {"score": score, "drivers": drivers}


def compute_article_priority(
    article: Dict[str, Any],
    curve: Optional[Dict[int, float]] = None,
) -> ArticlePriorityResult:
    """Compute an article's priority score from its metrics dict.

    `article` is the shape returned by `article_metrics_service.fetch_article_metrics`:
    has `gsc`, `ga4`, `enrichment`, `aeo_score`, `fault_codes`, `tags`.
    """
    c = curve if curve is not None else get_ctr_curve()

    gsc = article.get("gsc") or {}
    ga4 = article.get("ga4") or {}
    enrichment = article.get("enrichment") or {}
    aeo_score = float(article.get("aeo_score") or 0.0)

    impressions = int(gsc.get("impressions") or 0)
    current_pos = float(gsc.get("position") or 0.0)
    target_pos = default_target_position(current_pos) if current_pos > 0 else 0
    proj_clicks = projected_click_gain(impressions, current_pos, target_pos, curve=c) if current_pos > 0 else 0.0

    clicks_norm = _norm(proj_clicks, CAP_PROJECTED_CLICKS)
    enrichment_gap = round(max(0.0, 100.0 - aeo_score), 1)
    engagement_score, eng_meta = _engagement_quality(ga4)
    traffic_norm = _norm(float(ga4.get("sessions") or 0), CAP_GA4_SESSIONS)
    confidence_score, conf_meta = _confidence(gsc, ga4)
    effort_score, effort_meta = _effort(article)

    score = (
        W_CLICKS * clicks_norm
        + W_ENRICHMENT * enrichment_gap
        + W_ENGAGEMENT * engagement_score
        + W_TRAFFIC * traffic_norm
        + W_CONFIDENCE * confidence_score
        - W_EFFORT * effort_score
    )
    score = max(0.0, min(100.0, round(score, 2)))

    components = {
        "score": score,
        "weights": {
            "clicks": W_CLICKS,
            "enrichment": W_ENRICHMENT,
            "engagement": W_ENGAGEMENT,
            "traffic": W_TRAFFIC,
            "confidence": W_CONFIDENCE,
            "effort": -W_EFFORT,
        },
        "projected_clicks": {
            "value": proj_clicks,
            "normalized": clicks_norm,
            "current_position": round(current_pos, 2),
            "target_position": target_pos,
            "impressions": impressions,
        },
        "enrichment_gap": {
            "value": enrichment_gap,
            "aeo_score": aeo_score,
            "has_tldr": bool(enrichment.get("has_tldr")),
            "faqs_count": int(enrichment.get("faqs_count") or 0),
            "fully_enriched": bool(enrichment.get("fully_enriched")),
        },
        "engagement_quality": {
            "value": engagement_score,
            **eng_meta,
        },
        "traffic_potential": {
            "value": traffic_norm,
            "ga4_sessions": int(ga4.get("sessions") or 0),
        },
        "confidence": {
            "value": confidence_score,
            **conf_meta,
        },
        "effort_estimate": effort_meta,
    }

    return ArticlePriorityResult(
        score=score,
        components=components,
        projected_clicks=proj_clicks,
        target_position=target_pos,
    )

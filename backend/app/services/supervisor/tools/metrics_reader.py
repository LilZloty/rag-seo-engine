"""
Metrics reader — wraps GoogleApiService for GSC + GA4 deltas.

Returns compact JSON the supervisor can reason over:
- 7-day vs 30-day deltas on impressions/clicks/position
- Top movers (queries that gained/lost the most impressions)
- Page-level winners and losers

Falls back gracefully when GSC / GA4 credentials are missing — returns
an empty `data` block with `available: false` so the agent knows what's
actually queryable rather than confabulating.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.services.google_api_service import GoogleApiService

logger = get_logger(__name__)


def _agg(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregate GSC rows into totals + averages."""
    if not rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0, "queries": 0}
    total_clicks = sum(r.get("clicks", 0) or 0 for r in rows)
    total_impr = sum(r.get("impressions", 0) or 0 for r in rows)
    # Weighted avg CTR/position by impressions (matches GSC's own aggregation)
    if total_impr > 0:
        avg_pos = sum((r.get("position", 0) or 0) * (r.get("impressions", 0) or 0) for r in rows) / total_impr
        avg_ctr = total_clicks / total_impr
    else:
        avg_pos = 0.0
        avg_ctr = 0.0
    return {
        "clicks": int(total_clicks),
        "impressions": int(total_impr),
        "ctr": round(avg_ctr, 4),
        "position": round(avg_pos, 2),
        "queries": len(rows),
    }


def _delta(curr: Dict[str, float], prev: Dict[str, float]) -> Dict[str, Any]:
    """Compare current period totals against a baseline period."""
    def pct(a: float, b: float) -> Optional[float]:
        if b == 0:
            return None
        return round(((a - b) / b) * 100, 1)

    return {
        "impressions_pct": pct(curr["impressions"], prev["impressions"]),
        "clicks_pct": pct(curr["clicks"], prev["clicks"]),
        "ctr_delta": round(curr["ctr"] - prev["ctr"], 4),
        "position_delta": round(curr["position"] - prev["position"], 2),  # negative = better
    }


def _movers(curr_rows: List[Dict[str, Any]], prev_rows: List[Dict[str, Any]], limit: int) -> Dict[str, List[Dict[str, Any]]]:
    """Find the queries that moved most by impressions between the two windows."""
    prev_map = {r["query"]: r for r in prev_rows}
    movers: List[Tuple[str, int, Dict[str, Any], Dict[str, Any]]] = []
    for r in curr_rows:
        q = r["query"]
        prev = prev_map.get(q)
        prev_impr = (prev or {}).get("impressions", 0)
        delta = (r.get("impressions", 0) or 0) - (prev_impr or 0)
        movers.append((q, delta, r, prev or {}))

    movers.sort(key=lambda x: x[1])  # most negative first
    losers = [
        {
            "query": q,
            "impressions_now": r.get("impressions", 0),
            "impressions_prev": (prev or {}).get("impressions", 0),
            "delta": d,
            "position_now": round(r.get("position", 0) or 0, 1),
            "position_prev": round((prev or {}).get("position", 0) or 0, 1),
        }
        for q, d, r, prev in movers[:limit] if d < 0
    ]
    winners = [
        {
            "query": q,
            "impressions_now": r.get("impressions", 0),
            "impressions_prev": (prev or {}).get("impressions", 0),
            "delta": d,
            "position_now": round(r.get("position", 0) or 0, 1),
            "position_prev": round((prev or {}).get("position", 0) or 0, 1),
        }
        for q, d, r, prev in reversed(movers[-limit:]) if d > 0
    ]
    return {"winners": winners, "losers": losers}


def read_gsc_metrics(days: int = 7, baseline_days: int = 30, top_movers: int = 10) -> Dict[str, Any]:
    """
    Pull GSC totals for the current `days` window and a `baseline_days`
    comparison window, plus top moving queries.

    Returns shape:
    {
      "available": true,
      "site_url": "https://...",
      "windows": {"current_days": 7, "baseline_days": 30},
      "current": {"clicks": ..., "impressions": ..., ...},
      "baseline": {...},
      "delta": {...},
      "movers": {"winners": [...], "losers": [...]},
      "summary": "compact prose for the LLM"
    }
    """
    google = GoogleApiService()
    if not google.credentials or not google.site_url:
        return {
            "available": False,
            "reason": "GSC credentials or site URL missing",
            "data": None,
        }

    curr_rows = google.get_search_console_data(days=days) or []
    prev_rows = google.get_search_console_data(days=baseline_days) or []

    curr = _agg(curr_rows)
    prev = _agg(prev_rows)
    delta = _delta(curr, prev)
    movers = _movers(curr_rows, prev_rows, top_movers)

    summary_parts = []
    if delta.get("impressions_pct") is not None:
        summary_parts.append(f"impressions {curr['impressions']:,} ({delta['impressions_pct']:+.1f}% vs {baseline_days}d)")
    if delta.get("clicks_pct") is not None:
        summary_parts.append(f"clicks {curr['clicks']:,} ({delta['clicks_pct']:+.1f}%)")
    if curr["position"]:
        direction = "improved" if delta["position_delta"] < 0 else "worsened"
        summary_parts.append(f"avg position {curr['position']} ({direction} {abs(delta['position_delta']):.2f})")

    summary = f"GSC last {days}d: " + ", ".join(summary_parts) if summary_parts else "GSC: no data"
    if movers["losers"]:
        top_loser = movers["losers"][0]
        summary += f". Biggest loser: '{top_loser['query']}' ({top_loser['delta']:+,} impressions)"
    if movers["winners"]:
        top_winner = movers["winners"][0]
        summary += f". Biggest winner: '{top_winner['query']}' ({top_winner['delta']:+,} impressions)"

    return {
        "available": True,
        "site_url": google.site_url,
        "windows": {"current_days": days, "baseline_days": baseline_days},
        "current": curr,
        "baseline": prev,
        "delta": delta,
        "movers": movers,
        "summary": summary,
    }


def read_ga4_traffic(days: int = 7) -> Dict[str, Any]:
    """
    Pull GA4 page-level engagement for the last `days`. Returns total sessions,
    revenue, and top landing pages by sessions.

    GA4 doesn't have a clean delta primitive without a second query, so this
    intentionally returns absolute numbers + the top pages. The supervisor
    can ask for a baseline window if needed.
    """
    google = GoogleApiService()
    if not google.credentials or not google.property_id:
        return {
            "available": False,
            "reason": "GA4 credentials or property ID missing",
            "data": None,
        }

    rows = google.get_ga4_engagement_data(days=days) or []
    if not rows:
        return {"available": True, "windows": {"days": days}, "totals": {}, "top_pages": [], "summary": "GA4: no rows returned"}

    total_sessions = sum(r.get("sessions", 0) or 0 for r in rows)
    total_users = sum(r.get("active_users", 0) or 0 for r in rows)
    total_revenue = sum(r.get("revenue", 0) or 0 for r in rows)
    total_conversions = sum(r.get("conversions", 0) or 0 for r in rows)

    top = sorted(rows, key=lambda r: r.get("sessions", 0) or 0, reverse=True)[:10]
    top_pages = [
        {
            "page": r.get("page_path"),
            "sessions": int(r.get("sessions", 0) or 0),
            "active_users": int(r.get("active_users", 0) or 0),
            "conversions": int(r.get("conversions", 0) or 0),
            "revenue": round(r.get("revenue", 0) or 0, 2),
            "bounce_rate": round(r.get("bounce_rate", 0) or 0, 3),
        }
        for r in top
    ]

    summary = (
        f"GA4 last {days}d: {total_sessions:,} sessions, {total_users:,} users, "
        f"{total_conversions:,} conversions, ${total_revenue:,.0f} revenue"
    )

    return {
        "available": True,
        "windows": {"days": days},
        "totals": {
            "sessions": int(total_sessions),
            "active_users": int(total_users),
            "conversions": int(total_conversions),
            "revenue": round(total_revenue, 2),
        },
        "top_pages": top_pages,
        "summary": summary,
    }


def read_metrics_overview(days: int = 7, baseline_days: int = 30) -> Dict[str, Any]:
    """
    One-shot combined view the supervisor can request when scanning health.
    Includes GSC delta + GA4 totals + a top-line prose summary that joins both.
    """
    gsc = read_gsc_metrics(days=days, baseline_days=baseline_days, top_movers=5)
    ga4 = read_ga4_traffic(days=days)

    parts = []
    if gsc.get("available"):
        parts.append(gsc["summary"])
    else:
        parts.append(f"GSC unavailable ({gsc.get('reason')})")
    if ga4.get("available"):
        parts.append(ga4["summary"])
    else:
        parts.append(f"GA4 unavailable ({ga4.get('reason')})")

    return {
        "windows": {"current_days": days, "baseline_days": baseline_days},
        "gsc": gsc,
        "ga4": ga4,
        "summary": " | ".join(parts),
    }

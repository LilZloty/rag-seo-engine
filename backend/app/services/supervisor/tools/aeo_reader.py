"""
AEO visibility reader — wraps VisibilitySnapshot + ProductVisibilitySnapshot.

The supervisor uses this to answer "is Example Store still being cited by AI engines,
and which products are gaining/losing visibility?"

We read from snapshots, NOT from the live LLM check pipeline. Live checks are
expensive and run on a separate cadence — the supervisor's job is to read what's
already been computed and reason over it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.aeo_models import (
    VisibilitySnapshot, ProductVisibilitySnapshot, AIVisibilityResult,
)

logger = get_logger(__name__)


def _avg(rows: List[VisibilitySnapshot], field: str) -> Optional[float]:
    vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def read_brand_visibility(db: Session, days: int = 7, baseline_days: int = 30) -> Dict[str, Any]:
    """
    Brand-level visibility summary across all AI engines.

    Reads VisibilitySnapshot rows (one per day) and produces:
    - Recent average scores (visibility, citation, share-of-voice)
    - Delta vs baseline window
    - Top competitor names appearing in citations
    """
    now = datetime.now(timezone.utc)
    curr_floor = now - timedelta(days=days)
    base_floor = now - timedelta(days=baseline_days)

    curr_rows = (
        db.query(VisibilitySnapshot)
        .filter(VisibilitySnapshot.snapshot_date >= curr_floor)
        .order_by(desc(VisibilitySnapshot.snapshot_date))
        .all()
    )
    base_rows = (
        db.query(VisibilitySnapshot)
        .filter(
            VisibilitySnapshot.snapshot_date >= base_floor,
            VisibilitySnapshot.snapshot_date < curr_floor,
        )
        .all()
    )

    if not curr_rows and not base_rows:
        return {
            "available": False,
            "reason": "No visibility snapshots in DB — has the AEO check run yet?",
            "data": None,
        }

    curr = {
        "visibility_score": _avg(curr_rows, "visibility_score"),
        "citation_score": _avg(curr_rows, "citation_score"),
        "share_of_voice": _avg(curr_rows, "share_of_voice"),
        "snapshots": len(curr_rows),
    }
    baseline = {
        "visibility_score": _avg(base_rows, "visibility_score"),
        "citation_score": _avg(base_rows, "citation_score"),
        "share_of_voice": _avg(base_rows, "share_of_voice"),
        "snapshots": len(base_rows),
    }

    def delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return round(a - b, 2)

    delta_vis = delta(curr["visibility_score"], baseline["visibility_score"])
    delta_cit = delta(curr["citation_score"], baseline["citation_score"])
    delta_sov = delta(curr["share_of_voice"], baseline["share_of_voice"])

    # Aggregate competitor breakdown across the current window
    competitors: Dict[str, int] = {}
    for r in curr_rows:
        cb = r.competitor_breakdown or {}
        if isinstance(cb, dict):
            for name, count in cb.items():
                competitors[name] = competitors.get(name, 0) + int(count or 0)
    top_competitors = sorted(competitors.items(), key=lambda x: x[1], reverse=True)[:5]

    parts = []
    if curr["visibility_score"] is not None:
        d = f" ({delta_vis:+.1f} vs {baseline_days}d)" if delta_vis is not None else ""
        parts.append(f"visibility {curr['visibility_score']:.1f}{d}")
    if curr["citation_score"] is not None:
        d = f" ({delta_cit:+.1f})" if delta_cit is not None else ""
        parts.append(f"citation {curr['citation_score']:.1f}{d}")
    if curr["share_of_voice"] is not None:
        d = f" ({delta_sov:+.1f})" if delta_sov is not None else ""
        parts.append(f"share-of-voice {curr['share_of_voice']:.1f}{d}")
    summary = f"AEO last {days}d: " + ", ".join(parts) if parts else "AEO: no data"
    if top_competitors:
        comp_str = ", ".join(f"{n} ({c})" for n, c in top_competitors[:3])
        summary += f". Top competitors cited: {comp_str}"

    return {
        "available": True,
        "windows": {"current_days": days, "baseline_days": baseline_days},
        "current": curr,
        "baseline": baseline,
        "delta": {"visibility": delta_vis, "citation": delta_cit, "share_of_voice": delta_sov},
        "top_competitors": [{"name": n, "mentions": c} for n, c in top_competitors],
        "summary": summary,
    }


def read_product_visibility(db: Session, days: int = 14, limit: int = 10) -> Dict[str, Any]:
    """
    Product-level visibility — top winners and losers in AI citation rate over `days`.

    Strategy: for each product, take the most recent snapshot in the window and
    compare its score to the most recent snapshot before the window.
    """
    now = datetime.now(timezone.utc)
    floor = now - timedelta(days=days)

    # Most recent snapshot per product within the window
    subq = (
        db.query(
            ProductVisibilitySnapshot.product_id.label("pid"),
            func.max(ProductVisibilitySnapshot.snapshot_date).label("max_date"),
        )
        .filter(ProductVisibilitySnapshot.snapshot_date >= floor)
        .group_by(ProductVisibilitySnapshot.product_id)
        .subquery()
    )
    curr = (
        db.query(ProductVisibilitySnapshot)
        .join(
            subq,
            (ProductVisibilitySnapshot.product_id == subq.c.pid)
            & (ProductVisibilitySnapshot.snapshot_date == subq.c.max_date),
        )
        .all()
    )

    if not curr:
        return {
            "available": False,
            "reason": f"No product visibility snapshots in last {days} days",
            "data": None,
        }

    # For each product, find the most recent prior snapshot OUTSIDE the window
    items = []
    for s in curr:
        prior = (
            db.query(ProductVisibilitySnapshot)
            .filter(
                ProductVisibilitySnapshot.product_id == s.product_id,
                ProductVisibilitySnapshot.snapshot_date < floor,
            )
            .order_by(desc(ProductVisibilitySnapshot.snapshot_date))
            .first()
        )
        prior_score = prior.visibility_score if prior else None
        delta = None
        if prior_score is not None and s.visibility_score is not None:
            delta = round(s.visibility_score - prior_score, 2)
        items.append({
            "product_id": s.product_id,
            "score": round(s.visibility_score or 0, 2),
            "level": s.visibility_level,
            "score_prior": round(prior_score, 2) if prior_score is not None else None,
            "delta": delta,
            "scores_by_llm": s.scores_by_llm or {},
            "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else None,
        })

    items_with_delta = [i for i in items if i["delta"] is not None]
    winners = sorted(items_with_delta, key=lambda x: x["delta"], reverse=True)[:limit]
    losers = sorted(items_with_delta, key=lambda x: x["delta"])[:limit]
    losers = [i for i in losers if i["delta"] < 0]
    winners = [i for i in winners if i["delta"] > 0]

    summary_parts = [f"{len(items)} products tracked over {days}d"]
    if winners:
        summary_parts.append(f"top winner +{winners[0]['delta']} ({winners[0]['product_id']})")
    if losers:
        summary_parts.append(f"top loser {losers[0]['delta']} ({losers[0]['product_id']})")

    return {
        "available": True,
        "windows": {"days": days},
        "products_tracked": len(items),
        "winners": winners,
        "losers": losers,
        "summary": ". ".join(summary_parts),
    }


def read_aeo_overview(db: Session, days: int = 7, baseline_days: int = 30) -> Dict[str, Any]:
    """One-shot combined AEO health view for the supervisor."""
    brand = read_brand_visibility(db, days=days, baseline_days=baseline_days)
    products = read_product_visibility(db, days=days * 2, limit=5)

    parts = []
    if brand.get("available"):
        parts.append(brand["summary"])
    else:
        parts.append(f"brand AEO unavailable ({brand.get('reason')})")
    if products.get("available"):
        parts.append(products["summary"])
    else:
        parts.append(f"product AEO unavailable ({products.get('reason')})")

    return {
        "windows": {"current_days": days, "baseline_days": baseline_days},
        "brand": brand,
        "products": products,
        "summary": " | ".join(parts),
    }

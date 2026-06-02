"""
Content sampler — pulls recent Grok content generations for the supervisor to
sample-grade.

The supervisor's job is *not* to grade every generation (the rubric inside
content_generator already does that). It's to spot drift: did the recent
batch start ignoring product data again (Mar 7 incident pattern)? Are titles
suddenly generic? Is the LLM_used field churning between models?

Returns enough signal for the supervisor to ask follow-up questions without
loading huge HTML payloads.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.library import GenerationHistory
from app.models.product import Product

logger = get_logger(__name__)


def _truncate(s: Optional[str], n: int = 240) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"


def sample_recent_generations(db: Session, limit: int = 20, days: int = 7) -> Dict[str, Any]:
    """
    Pull the last N content generations and return enough signal for the
    supervisor to detect drift without loading multi-KB HTML bodies.

    Each item includes the generated H1, meta title, meta description (lengths
    matter for SEO), the model used, and a short snippet of the body so the
    supervisor can sample-read a few rather than reading them all.

    The aggregated view exposes:
    - model usage distribution (catches silent model fallbacks)
    - description-length distribution (catches "too short / placeholder" drift)
    - a heuristic "looks generic" flag (description doesn't mention any product
      identifier — the Mar 7 issue)
    """
    floor = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(GenerationHistory)
        .filter(GenerationHistory.generated_at >= floor)
        .order_by(desc(GenerationHistory.generated_at))
        .limit(limit)
        .all()
    )

    if not rows:
        return {
            "available": True,
            "windows": {"days": days, "limit": limit},
            "samples": [],
            "stats": {},
            "summary": f"No generations in last {days} days",
        }

    # Quick lookup for product titles (so the supervisor can see what was generated for what)
    product_ids = [r.product_id for r in rows if r.product_id]
    product_map: Dict[str, Product] = {}
    if product_ids:
        for p in db.query(Product).filter(Product.id.in_(product_ids)).all():
            product_map[p.id] = p

    samples: List[Dict[str, Any]] = []
    looks_generic_count = 0
    for r in rows:
        product = product_map.get(r.product_id) if r.product_id else None
        product_sku = (product.sku or "") if product else ""
        product_handle = (product.handle or "") if product else ""

        body = r.description_html or ""
        body_lower = body.lower()
        # "Generic" = description doesn't mention any product identifier.
        # Imperfect but cheap signal that something like the Mar 7 regen happened.
        looks_generic = bool(body) and not any(
            ident and ident.lower() in body_lower
            for ident in (product_sku, product_handle)
            if ident and len(ident) > 2
        )
        if looks_generic:
            looks_generic_count += 1

        samples.append({
            "id": r.id,
            "product_id": r.product_id,
            "product_title": product.title if product else None,
            "product_sku": product_sku or None,
            "h1_title": r.h1_title,
            "meta_title": r.meta_title,
            "meta_title_len": len(r.meta_title or ""),
            "meta_description": r.meta_description,
            "meta_description_len": len(r.meta_description or ""),
            "url_handle": r.url_handle,
            "body_snippet": _truncate(body, 240),
            "body_length": len(body),
            "llm_used": r.llm_used,
            "tokens_in": r.llm_tokens_input,
            "tokens_out": r.llm_tokens_output,
            "generation_time_ms": r.generation_time_ms,
            "status": r.status,
            "looks_generic": looks_generic,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        })

    # Aggregations
    model_dist: Dict[str, int] = {}
    for s in samples:
        m = s.get("llm_used") or "unknown"
        model_dist[m] = model_dist.get(m, 0) + 1

    metalens = [s["meta_description_len"] for s in samples if s["meta_description_len"]]
    avg_meta = round(sum(metalens) / len(metalens), 1) if metalens else 0
    short_meta = sum(1 for L in metalens if L < 70)  # GSC-undesirable
    long_meta = sum(1 for L in metalens if L > 165)  # truncated by Google

    summary = (
        f"{len(samples)} generations in last {days}d "
        f"({looks_generic_count} look generic, {short_meta} short metas, {long_meta} too-long metas, "
        f"avg meta {avg_meta} chars). Models used: " + ", ".join(f"{m}×{c}" for m, c in model_dist.items())
    )

    return {
        "available": True,
        "windows": {"days": days, "limit": limit},
        "samples": samples,
        "stats": {
            "count": len(samples),
            "looks_generic_count": looks_generic_count,
            "short_meta_count": short_meta,
            "long_meta_count": long_meta,
            "avg_meta_description_len": avg_meta,
            "model_distribution": model_dist,
        },
        "summary": summary,
    }

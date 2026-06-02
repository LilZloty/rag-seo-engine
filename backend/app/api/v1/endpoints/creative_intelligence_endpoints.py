from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.rate_limiter import RATE_ANALYSIS, RATE_GENERAL, limiter
from app.db.session import get_db
from app.models.creative_opportunity import CreativeOpportunity

router = APIRouter()


# ============================================================================
# Existing creative report endpoints
# ============================================================================

@router.get("/creative-intelligence")
@limiter.limit(RATE_ANALYSIS)
async def get_creative_report(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Full creative intelligence report: products grouped by vehicle brand
    with sales, search, and traffic data for ad creative planning.
    """
    from app.services.creative_intelligence_service import CreativeIntelligenceService
    service = CreativeIntelligenceService(db)
    return service.get_creative_report()


@router.get("/creative-intelligence/brand/{brand_name}")
@limiter.limit(RATE_ANALYSIS)
async def get_brand_detail(
    request: Request,
    brand_name: str,
    db: Session = Depends(get_db),
):
    """Detailed creative data for a specific vehicle brand."""
    from app.services.creative_intelligence_service import CreativeIntelligenceService
    service = CreativeIntelligenceService(db)
    result = service.get_brand_detail(brand_name)
    if not result:
        return {"error": f"Brand '{brand_name}' not found", "available_brands": []}
    return result


@router.get("/creative-intelligence/transmissions")
@limiter.limit(RATE_ANALYSIS)
async def get_transmission_report(
    request: Request,
    db: Session = Depends(get_db),
):
    """Transmission-level breakdown for granular ad targeting."""
    from app.services.creative_intelligence_service import CreativeIntelligenceService
    service = CreativeIntelligenceService(db)
    return service.get_transmission_report()


@router.get("/creative-intelligence/export", response_class=PlainTextResponse)
@limiter.limit(RATE_ANALYSIS)
async def export_csv(
    request: Request,
    db: Session = Depends(get_db),
):
    """Export creative intelligence data as CSV."""
    from app.services.creative_intelligence_service import CreativeIntelligenceService
    service = CreativeIntelligenceService(db)
    csv_content = service.export_csv()
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=creative_intelligence.csv"}
    )


# ============================================================================
# Opportunity endpoints
# ============================================================================

OpportunityType = Literal[
    "transmission_demand_gap",
    "query_demand_gap",
    "latent_inventory",
    "marketing_gap",
]

OpportunityStatus = Literal["open", "investigating", "in_progress", "resolved", "dismissed"]

OpportunityPriority = Literal["high", "medium", "low"]


class OpportunityResponse(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    opportunity_type: str
    priority: str
    target_type: str
    target_transmission_code: Optional[str] = None
    target_vehicle_brand: Optional[str] = None
    target_product_id: Optional[str] = None
    target_query: Optional[str] = None
    signal_data: dict = Field(default_factory=dict)
    opportunity_score: float
    estimated_monthly_sessions: Optional[int] = None
    estimated_monthly_revenue: Optional[float] = None
    title: str
    description: Optional[str] = None
    recommended_action: Optional[str] = None
    action_steps: List[str] = Field(default_factory=list)
    status: str
    notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OpportunityListResponse(BaseModel):
    total: int
    counts_by_type: dict
    counts_by_priority: dict
    counts_by_status: dict
    opportunities: List[OpportunityResponse]


class OpportunityUpdate(BaseModel):
    status: Optional[OpportunityStatus] = None
    notes: Optional[str] = None


class RefreshResponse(BaseModel):
    transmission_demand_gap: int
    query_demand_gap: int
    latent_inventory: int
    marketing_gap: int
    total: int


@router.get("/creative-intelligence/opportunities", response_model=OpportunityListResponse)
@limiter.limit(RATE_GENERAL)
async def list_opportunities(
    request: Request,
    opportunity_type: Optional[OpportunityType] = Query(None),
    priority: Optional[OpportunityPriority] = Query(None),
    status: Optional[OpportunityStatus] = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List creative opportunities sorted by score desc.

    Defaults to status='open' so resolved/dismissed items don't clutter the
    dashboard. Pass status=None (or any string) to include all states.
    """
    q = db.query(CreativeOpportunity)

    if opportunity_type:
        q = q.filter(CreativeOpportunity.opportunity_type == opportunity_type)
    if priority:
        q = q.filter(CreativeOpportunity.priority == priority)
    if status:
        q = q.filter(CreativeOpportunity.status == status)

    total = q.count()
    rows = (
        q.order_by(desc(CreativeOpportunity.opportunity_score))
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Aggregate counts independent of paging — handy for tab badges in the UI.
    counts_q = db.query(CreativeOpportunity)
    if status:
        counts_q = counts_q.filter(CreativeOpportunity.status == status)

    all_for_counts = counts_q.all()
    by_type: dict = {}
    by_priority: dict = {}
    by_status: dict = {}
    for r in all_for_counts:
        by_type[r.opportunity_type] = by_type.get(r.opportunity_type, 0) + 1
        by_priority[r.priority] = by_priority.get(r.priority, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1

    return OpportunityListResponse(
        total=total,
        counts_by_type=by_type,
        counts_by_priority=by_priority,
        counts_by_status=by_status,
        opportunities=[OpportunityResponse.model_validate(r) for r in rows],
    )


@router.get("/creative-intelligence/opportunities/{opportunity_id}", response_model=OpportunityResponse)
@limiter.limit(RATE_GENERAL)
async def get_opportunity(
    request: Request,
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    row = (
        db.query(CreativeOpportunity)
        .filter(CreativeOpportunity.id == opportunity_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return OpportunityResponse.model_validate(row)


@router.patch("/creative-intelligence/opportunities/{opportunity_id}", response_model=OpportunityResponse)
@limiter.limit(RATE_GENERAL)
async def update_opportunity(
    request: Request,
    opportunity_id: str,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
):
    """Update opportunity status or notes. Used by the dashboard buttons."""
    row = (
        db.query(CreativeOpportunity)
        .filter(CreativeOpportunity.id == opportunity_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    now = datetime.now(timezone.utc)

    if payload.status is not None:
        row.status = payload.status
        if payload.status == "resolved":
            row.resolved_at = now
        elif payload.status == "dismissed":
            row.dismissed_at = now
    if payload.notes is not None:
        row.notes = payload.notes

    db.commit()
    db.refresh(row)
    return OpportunityResponse.model_validate(row)


@router.post("/creative-intelligence/opportunities/refresh", response_model=RefreshResponse)
@limiter.limit(RATE_ANALYSIS)
async def refresh_opportunities(
    request: Request,
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    """Trigger a fresh detection run. Synchronous — takes ~30-90s.

    The daily Celery task runs the same logic, this endpoint is for
    on-demand refresh from the dashboard.
    """
    from app.services.creative_intelligence_opportunities import (
        get_creative_opportunity_detector,
    )

    detector = get_creative_opportunity_detector(db)
    result = await detector.detect_all(days=days, persist=True)

    return RefreshResponse(
        transmission_demand_gap=len(result["transmission_demand_gap"]),
        query_demand_gap=len(result["query_demand_gap"]),
        latent_inventory=len(result["latent_inventory"]),
        marketing_gap=len(result["marketing_gap"]),
        total=sum(len(v) for v in result.values()),
    )


@router.post("/creative-intelligence/embed-catalog")
@limiter.limit(RATE_ANALYSIS)
async def embed_catalog(
    request: Request,
    db: Session = Depends(get_db),
):
    """Bulk-embed all products into the Qdrant product catalog collection.

    Prerequisite for the `query_demand_gap` detector. Idempotent — re-running
    upserts on product.id. Long-running: ~5-15 min for 5,000 products at
    concurrency=5.
    """
    from app.services.product_embedding_service import product_embedding_service

    result = await product_embedding_service.embed_all_products(db)
    return {
        "status": "completed",
        "total": result["total"],
        "embedded": result["embedded"],
        "skipped": result["skipped"],
    }


class GeneratedCopyResponse(BaseModel):
    meta_title: str
    meta_description: str
    rationale: str
    generated_at: datetime
    provider: Optional[str] = None


@router.post(
    "/creative-intelligence/opportunities/{opportunity_id}/generate-copy",
    response_model=GeneratedCopyResponse,
)
@limiter.limit(RATE_ANALYSIS)
async def generate_opportunity_copy(
    request: Request,
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    """Generate a suggested meta title + description for an opportunity.

    Only applicable to marketing_gap and latent_inventory (both target a
    specific product). Calls the existing LLM pipeline with a focused
    prompt and stashes the result in signal_data._generated_copy so it
    survives subsequent detection re-runs.
    """
    import json as _json
    from app.models.product import Product
    from app.services.llm_service import LLMService

    row = (
        db.query(CreativeOpportunity)
        .filter(CreativeOpportunity.id == opportunity_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    if row.opportunity_type not in ("marketing_gap", "latent_inventory"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Copy generation only supported for marketing_gap and "
                f"latent_inventory (got {row.opportunity_type})."
            ),
        )

    if not row.target_product_id:
        raise HTTPException(status_code=400, detail="Opportunity has no target product.")

    product = (
        db.query(Product)
        .filter(Product.id == row.target_product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Target product not found.")

    signal = row.signal_data or {}
    top_queries = signal.get("matched_queries", []) if row.opportunity_type == "marketing_gap" else []

    angle = (
        "El producto recibe impresiones en Google pero el CTR es muy bajo. "
        "El meta title + description actual no convierte la visibilidad en clicks."
        if row.opportunity_type == "marketing_gap"
        else "El producto tiene ventas históricas pero no aparece en búsqueda. "
             "El meta title + description debe capturar la demanda orgánica que actualmente se pierde."
    )

    system_prompt = (
        "Eres un experto en SEO técnico y copywriting para Example Store, tienda mexicana "
        "de partes de transmisión (Shopify, mercado MX). Tu tarea es reescribir el "
        "meta title y meta description de un producto para maximizar CTR en Google.\n\n"
        "Reglas estrictas:\n"
        "- Idioma: español mexicano natural, claro y directo.\n"
        "- meta_title: máximo 70 caracteres, incluir keyword principal + diferenciador.\n"
        "- meta_description: máximo 160 caracteres, incluir CTA + envío/garantía si aplica.\n"
        "- NO incluir marcas registradas de terceros como si fueran nuestras.\n"
        "- Si el producto tiene un código de transmisión (4L60E, DQ200, etc.), inclúyelo.\n"
        "- rationale: 1-2 oraciones explicando por qué la nueva versión debería performar mejor.\n\n"
        "Responde EXCLUSIVAMENTE con JSON válido en este formato (sin markdown, sin texto extra):\n"
        '{\n'
        '  "meta_title": "...",\n'
        '  "meta_description": "...",\n'
        '  "rationale": "..."\n'
        '}'
    )

    product_info = {
        "title": product.title,
        "handle": product.handle,
        "transmission_code": product.transmission_code,
        "product_type": product.product_type,
        "vendor": product.vendor,
        "price_mxn": product.price,
        "current_description": (product.current_description_html or "")[:500],
        "gsc_impressions": product.gsc_impressions or 0,
        "gsc_clicks": product.gsc_clicks or 0,
        "gsc_ctr": float(product.gsc_ctr or 0),
        "gsc_position": float(product.gsc_position or 0),
        "sold_30d": product.sold_30d or 0,
        "sold_all_time": product.sold_all_time or 0,
        "opportunity_angle": angle,
        "top_search_queries": top_queries[:5],
    }

    llm = LLMService()
    response = await llm.generate_content(
        product_info=product_info,
        context=[],
        system_prompt=system_prompt,
    )

    # Response shape varies by provider: usually {"content": "<json string>", ...}
    content = response.get("content", response) if isinstance(response, dict) else response
    parsed: Optional[dict] = None
    if isinstance(content, dict):
        parsed = content
    elif isinstance(content, str):
        try:
            parsed = _json.loads(content)
        except _json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    parsed = _json.loads(content[start:end])
                except _json.JSONDecodeError:
                    parsed = None

    if not parsed or "meta_title" not in parsed:
        raise HTTPException(
            status_code=502,
            detail=f"LLM response did not include valid JSON copy. Got: {str(content)[:200]}",
        )

    generated_at = datetime.now(timezone.utc)
    generated_copy = {
        "meta_title": parsed["meta_title"],
        "meta_description": parsed.get("meta_description", ""),
        "rationale": parsed.get("rationale", ""),
        "generated_at": generated_at.isoformat(),
        "provider": response.get("provider") if isinstance(response, dict) else None,
    }

    # Stash into signal_data._generated_copy. The persist() upsert preserves
    # underscore-prefixed keys, so this survives the next detection cycle.
    signal_data = dict(row.signal_data or {})
    signal_data["_generated_copy"] = generated_copy
    row.signal_data = signal_data
    db.commit()

    return GeneratedCopyResponse(**generated_copy)

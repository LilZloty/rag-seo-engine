"""
Product AI Visibility API Endpoints

SEMrush-style AI visibility tracking for individual products.
Provides endpoints for checking visibility, viewing scores,
and analyzing trends across LLM platforms.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date

from app.db.session import get_db
from app.services.product_ai_visibility_service import product_ai_visibility_service
from app.models.product import Product
from app.models.aeo_models import ProductVisibilityResult, ProductVisibilitySnapshot

router = APIRouter(prefix="/product-visibility", tags=["Product AI Visibility"])


# ============ Pydantic Schemas ============

class VisibilityCheckRequest(BaseModel):
    """Request to trigger a visibility check."""
    providers: List[str] = Field(default=["grok"], description="LLM providers to check")
    max_prompts: int = Field(default=5, ge=1, le=10, description="Maximum prompts to generate")
    custom_prompts: Optional[List[str]] = Field(default=None, description="Custom prompts to use instead of auto-generated")


class VisibilityScoreBreakdown(BaseModel):
    """Breakdown of visibility score components."""
    mention_score: float
    position_score: float
    citation_score: float
    competitor_score: float


class VisibilityStats(BaseModel):
    """Raw statistics from visibility checks."""
    total_checks: int
    mentions: int
    first_positions: int
    url_citations: int
    competitor_appearances: int


class ProductVisibilityScore(BaseModel):
    """Complete visibility score for a product."""
    score: float = Field(ge=0, le=100, description="Overall visibility score (0-100)")
    level: str = Field(description="Visibility level: low, medium, high")
    breakdown: VisibilityScoreBreakdown
    by_llm: dict = Field(description="Score breakdown by LLM provider")
    stats: VisibilityStats


class VisibilityCheckResponse(BaseModel):
    """Response after running a visibility check."""
    product_id: int
    checks_performed: int
    score: ProductVisibilityScore
    results: List[dict] = Field(description="Individual check results")


class VisibilityTrendPoint(BaseModel):
    """Single point in visibility trend."""
    date: str
    score: float
    level: str
    by_llm: dict
    mentions: int
    first_positions: int
    competitor_share: float


class VisibilityTrendResponse(BaseModel):
    """Historical visibility trend data."""
    product_id: int
    period_days: int
    trend: List[VisibilityTrendPoint]
    current_score: Optional[float]
    change_7d: Optional[float]
    change_30d: Optional[float]


class LLMComparisonResponse(BaseModel):
    """Comparison of visibility across LLM providers."""
    product_id: int
    period_days: int
    by_provider: dict


class ProductVisibilityOverview(BaseModel):
    """Overview of a product's AI visibility."""
    product_id: int
    product_title: str
    product_sku: Optional[str]
    current_score: Optional[float]
    current_level: Optional[str]
    last_checked: Optional[datetime]
    by_llm: Optional[dict]
    change_7d: Optional[float]
    top_competitors: Optional[List[dict]]


# ============ API Endpoints ============

@router.get("/{product_id}", response_model=ProductVisibilityOverview)
async def get_product_visibility(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current AI visibility overview for a product.
    
    Returns the most recent visibility score and metrics.
    Like SEMrush's "AI Visibility Score" card.
    """
    # Get product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Get latest snapshot
    snapshot = db.query(ProductVisibilitySnapshot).filter(
        ProductVisibilitySnapshot.product_id == product_id
    ).order_by(ProductVisibilitySnapshot.snapshot_date.desc()).first()
    
    # Get last check time
    last_check = db.query(ProductVisibilityResult).filter(
        ProductVisibilityResult.product_id == product_id
    ).order_by(ProductVisibilityResult.checked_at.desc()).first()
    
    return ProductVisibilityOverview(
        product_id=product_id,
        product_title=product.title or "",
        product_sku=product.sku,
        current_score=snapshot.visibility_score if snapshot else None,
        current_level=snapshot.visibility_level if snapshot else None,
        last_checked=last_check.checked_at if last_check else None,
        by_llm=snapshot.scores_by_llm if snapshot else None,
        change_7d=snapshot.score_change_7d if snapshot else None,
        top_competitors=snapshot.top_competitors if snapshot else None
    )


@router.post("/{product_id}/check", response_model=VisibilityCheckResponse)
async def check_product_visibility(
    product_id: int,
    request: VisibilityCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Trigger a visibility check for a product.
    
    Queries specified LLM providers with auto-generated or custom prompts
    to determine if the product is being recommended by AI assistants.
    
    This is the core action - like SEMrush's "Check Visibility" button.
    """
    # Get product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Prepare prompts
    prompts = None
    if request.custom_prompts:
        prompts = [
            {"prompt_text": p, "prompt_type": "custom"}
            for p in request.custom_prompts
        ]
    else:
        prompts = product_ai_visibility_service.generate_product_prompts(
            product=product,
            db=db,
            max_prompts=request.max_prompts
        )
    
    # Run visibility checks
    results = await product_ai_visibility_service.check_product_visibility(
        db=db,
        product_id=product_id,
        provider_names=request.providers,
        prompts=prompts
    )
    
    # Calculate score
    score_data = product_ai_visibility_service.calculate_visibility_score(results)
    
    # Create snapshot
    product_ai_visibility_service.create_product_snapshot(
        db=db,
        product_id=product_id
    )
    
    # Format results for response
    result_dicts = [
        {
            "prompt": r.prompt_text,
            "prompt_type": r.prompt_type,
            "provider": r.llm_provider,
            "was_mentioned": r.was_mentioned,
            "position": r.position_in_response,
            "context": r.mention_context,
            "brand_mentioned": r.brand_mentioned,
            "url_cited": r.brand_url_cited,
            "competitors": r.competitors_mentioned or [],
            "sentiment": r.sentiment,
            "error": r.error
        }
        for r in results
    ]
    
    return VisibilityCheckResponse(
        product_id=product_id,
        checks_performed=len(results),
        score=ProductVisibilityScore(
            score=score_data["score"],
            level=score_data["level"],
            breakdown=VisibilityScoreBreakdown(**score_data["breakdown"]),
            by_llm=score_data["by_llm"],
            stats=VisibilityStats(**score_data["stats"])
        ),
        results=result_dicts
    )


@router.get("/{product_id}/trend", response_model=VisibilityTrendResponse)
async def get_product_visibility_trend(
    product_id: int,
    days: int = Query(default=30, ge=7, le=90, description="Number of days to include"),
    db: Session = Depends(get_db)
):
    """
    Get historical visibility trend for charting.
    
    Returns daily visibility scores for the specified period.
    Ideal for rendering line charts like SEMrush's trend graphs.
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Get trend data
    trend = product_ai_visibility_service.get_product_visibility_trend(
        db=db,
        product_id=product_id,
        days=days
    )
    
    # Get latest snapshot for current stats
    latest = db.query(ProductVisibilitySnapshot).filter(
        ProductVisibilitySnapshot.product_id == product_id
    ).order_by(ProductVisibilitySnapshot.snapshot_date.desc()).first()
    
    return VisibilityTrendResponse(
        product_id=product_id,
        period_days=days,
        trend=[VisibilityTrendPoint(**t) for t in trend],
        current_score=latest.visibility_score if latest else None,
        change_7d=latest.score_change_7d if latest else None,
        change_30d=latest.score_change_30d if latest else None
    )


@router.get("/{product_id}/compare", response_model=LLMComparisonResponse)
async def get_llm_comparison(
    product_id: int,
    days: int = Query(default=7, ge=1, le=30, description="Days to include in comparison"),
    db: Session = Depends(get_db)
):
    """
    Get visibility comparison across LLM providers.
    
    Shows how the product performs on different AI platforms
    (Grok, ChatGPT, Perplexity, etc.).
    """
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    comparison = product_ai_visibility_service.get_multi_llm_comparison(
        db=db,
        product_id=product_id,
        days=days
    )
    
    return LLMComparisonResponse(**comparison)


@router.get("/{product_id}/prompts")
async def get_product_prompts(
    product_id: int,
    max_prompts: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    Preview the prompts that would be generated for a product.
    
    Useful for understanding what queries will be sent to LLMs
    before running a full visibility check.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    prompts = product_ai_visibility_service.generate_product_prompts(
        product=product,
        db=db,
        max_prompts=max_prompts
    )
    
    return {
        "product_id": product_id,
        "product_title": product.title,
        "prompts": prompts
    }


@router.get("/")
async def list_products_visibility(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="score", regex="^(score|last_checked|change_7d)$"),
    level: Optional[str] = Query(default=None, regex="^(low|medium|high)$"),
    db: Session = Depends(get_db)
):
    """
    List products with their visibility scores.
    
    Supports filtering by visibility level and sorting.
    Great for a dashboard overview showing all tracked products.
    """
    from sqlalchemy import desc, asc
    
    # Base query - join products with their latest snapshots
    query = db.query(
        Product,
        ProductVisibilitySnapshot
    ).outerjoin(
        ProductVisibilitySnapshot,
        Product.id == ProductVisibilitySnapshot.product_id
    )
    
    # Filter by level if specified
    if level:
        query = query.filter(ProductVisibilitySnapshot.visibility_level == level)
    
    # Sort
    if sort_by == "score":
        query = query.order_by(desc(ProductVisibilitySnapshot.visibility_score))
    elif sort_by == "last_checked":
        query = query.order_by(desc(ProductVisibilitySnapshot.created_at))
    elif sort_by == "change_7d":
        query = query.order_by(desc(ProductVisibilitySnapshot.score_change_7d))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    results = query.offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "product_id": p.id,
                "title": p.title,
                "sku": p.sku,
                "score": s.visibility_score if s else None,
                "level": s.visibility_level if s else None,
                "change_7d": s.score_change_7d if s else None,
                "by_llm": s.scores_by_llm if s else None,
                "last_snapshot": s.snapshot_date.isoformat() if s else None
            }
            for p, s in results
        ]
    }


@router.get("/{product_id}/positions")
async def get_position_history(
    product_id: int,
    days: int = Query(default=30, ge=7, le=90, description="Number of days"),
    provider: Optional[str] = Query(default=None, description="Filter by provider"),
    db: Session = Depends(get_db)
):
    """
    Get position ranking history for a product.
    
    Tracks how the product's position in LLM recommendations has changed
    over time, similar to SEMrush's position tracking for organic search.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product_ai_visibility_service.get_position_history(
        db=db,
        product_id=product_id,
        days=days,
        provider_filter=provider
    )


@router.get("/{product_id}/gaps")
async def get_competitor_gap_analysis(
    product_id: int,
    days: int = Query(default=30, ge=7, le=90, description="Number of days"),
    db: Session = Depends(get_db)
):
    """
    Analyze competitor visibility gap.
    
    Shows which competitors are being mentioned more than your product
    and identifies opportunities where you should be visible but aren't.
    Returns:
    - Competitor visibility rates
    - Gap vs product
    - Competitive index (0-100)
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product_ai_visibility_service.get_competitor_gap_analysis(
        db=db,
        product_id=product_id,
        days=days
    )


@router.get("/{product_id}/recommendations")
async def get_optimization_recommendations(
    product_id: int,
    days: int = Query(default=30, ge=7, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get platform-specific recommendations for improving visibility.
    
    Analyzes performance across LLM providers and suggests optimizations
    tailored to each platform's behavior patterns (Grok, ChatGPT, Perplexity).
    
    Returns prioritized recommendations with:
    - Issue identification
    - Specific action steps
    - Expected impact
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product_ai_visibility_service.get_optimization_recommendations(
        db=db,
        product_id=product_id,
        days=days
    )


# ============ V2.0 ENHANCED ENDPOINTS ============

@router.get("/{product_id}/prompts-v2")
async def get_product_prompts_v2(
    product_id: int,
    max_prompts: int = Query(default=10, ge=1, le=20),
    include_gsc: bool = Query(default=True, description="Include GSC query-based prompts"),
    include_vehicles: bool = Query(default=True, description="Include vehicle-specific prompts"),
    include_fault_codes: bool = Query(default=True, description="Include fault code prompts"),
    include_competitive: bool = Query(default=True, description="Include competitive comparison prompts"),
    db: Session = Depends(get_db)
):
    """
    V2.0: Preview enhanced prompts generated from REAL data sources.
    
    Data sources:
    - GSC Queries: Actual search terms users use (highest value!)
    - Vehicle Fitments: Specific make/model/year from product data
    - Fault Codes: Based on transmission type
    - Competitor Context: Based on past AI visibility results
    
    Use this to understand what queries will be sent to LLMs
    before running a visibility check.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    prompts = product_ai_visibility_service.generate_product_prompts_v2(
        product=product,
        db=db,
        max_prompts=max_prompts,
        include_gsc_queries=include_gsc,
        include_vehicle_specific=include_vehicles,
        include_fault_codes=include_fault_codes,
        include_competitive=include_competitive
    )
    
    # Group by source for clarity
    by_source = {}
    for p in prompts:
        source = p.get("source", p.get("prompt_type", "unknown"))
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(p)
    
    return {
        "product_id": product_id,
        "product_title": product.title,
        "total_prompts": len(prompts),
        "prompts": prompts,
        "by_source": by_source,
        "sources_used": list(by_source.keys())
    }


@router.get("/{product_id}/recommendations-v2")
async def get_optimization_recommendations_v2(
    product_id: int,
    days: int = Query(default=30, ge=7, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    V2.0: Get DATA-DRIVEN, ACTIONABLE recommendations.
    
    Enhanced over V1 with:
    - Actual LLM response analysis (WHY competitors were mentioned)
    - Real revenue opportunity calculations using product conversion data
    - Specific content suggestions based on competitor context
    - Prompt effectiveness analysis (which prompts work best)
    
    Returns:
    - Competitor insights: What competitors said that you should match
    - Revenue opportunity: $ impact of improving visibility
    - Provider insights: Performance breakdown by LLM
    - Prompt effectiveness: Which query types perform best
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product_ai_visibility_service.get_optimization_recommendations_v2(
        db=db,
        product_id=product_id,
        days=days
    )


@router.get("/{product_id}/llm-comparison")
async def get_llm_response_comparison(
    product_id: int,
    days: int = Query(default=7, ge=1, le=30, description="Days to include"),
    prompt_text: Optional[str] = Query(default=None, description="Filter to specific prompt"),
    db: Session = Depends(get_db)
):
    """
    V2.0: Compare how different LLMs responded to the same prompts.
    
    Shows side-by-side analysis:
    - Which LLM mentioned your product
    - Which competitors each LLM mentioned  
    - What each LLM said about competitors (to identify content gaps)
    - Win/loss rate by provider
    
    Use this to understand WHY one LLM recommends you but another doesn't.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    return product_ai_visibility_service.get_llm_response_comparison(
        db=db,
        product_id=product_id,
        prompt_text=prompt_text,
        days=days
    )


@router.get("/{product_id}/revenue-opportunity")
async def get_revenue_opportunity(
    product_id: int,
    target_visibility: float = Query(default=70.0, ge=0, le=100, description="Target visibility score"),
    db: Session = Depends(get_db)
):
    """
    V2.0: Calculate actual $ revenue opportunity from improving visibility.
    
    Uses REAL product data:
    - Current conversion rate (from sales/sessions)
    - Average order value (product price)
    - Current traffic (GA4 sessions)
    - Current visibility score
    
    Returns estimated additional monthly revenue if visibility improves.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Get current visibility score
    from app.models.aeo_models import ProductVisibilitySnapshot
    snapshot = db.query(ProductVisibilitySnapshot).filter(
        ProductVisibilitySnapshot.product_id == product_id
    ).order_by(ProductVisibilitySnapshot.snapshot_date.desc()).first()
    
    current_score = snapshot.visibility_score if snapshot else 0
    
    return product_ai_visibility_service.calculate_revenue_opportunity(
        product=product,
        current_visibility_score=current_score,
        target_visibility_score=target_visibility
    )


@router.post("/{product_id}/check-v2")
async def check_product_visibility_v2(
    product_id: int,
    request: VisibilityCheckRequest,
    use_v2_prompts: bool = Query(default=True, description="Use V2 enhanced prompts"),
    db: Session = Depends(get_db)
):
    """
    V2.0: Trigger visibility check with ENHANCED prompts.
    
    Uses V2 prompt generation which includes:
    - GSC real queries (actual user searches)
    - Vehicle-specific prompts (from fitments data)
    - Fault code prompts (based on transmission type)
    - Competitive prompts (based on past competitor mentions)
    
    Falls back to V1 prompts if V2 data sources unavailable.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    
    # Generate prompts based on version
    if use_v2_prompts and not request.custom_prompts:
        prompts = product_ai_visibility_service.generate_product_prompts_v2(
            product=product,
            db=db,
            max_prompts=request.max_prompts
        )
    elif request.custom_prompts:
        prompts = [
            {"prompt_text": p, "prompt_type": "custom"}
            for p in request.custom_prompts
        ]
    else:
        prompts = product_ai_visibility_service.generate_product_prompts(
            product=product,
            db=db,
            max_prompts=request.max_prompts
        )
    
    # Run visibility checks
    results = await product_ai_visibility_service.check_product_visibility(
        db=db,
        product_id=product_id,
        provider_names=request.providers,
        prompts=prompts
    )
    
    # Calculate score
    score_data = product_ai_visibility_service.calculate_visibility_score(results)
    
    # Create snapshot
    product_ai_visibility_service.create_product_snapshot(
        db=db,
        product_id=product_id
    )
    
    # Format results
    result_dicts = [
        {
            "prompt": r.prompt_text,
            "prompt_type": r.prompt_type,
            "provider": r.llm_provider,
            "was_mentioned": r.was_mentioned,
            "position": r.position_in_response,
            "context": r.mention_context,
            "brand_mentioned": r.brand_mentioned,
            "url_cited": r.brand_url_cited,
            "competitors": r.competitors_mentioned or [],
            "sentiment": r.sentiment,
            "error": r.error
        }
        for r in results
    ]
    
    # Calculate revenue opportunity
    revenue_opp = product_ai_visibility_service.calculate_revenue_opportunity(
        product=product,
        current_visibility_score=score_data["score"],
        target_visibility_score=70.0
    )
    
    return {
        "product_id": product_id,
        "checks_performed": len(results),
        "prompts_used": len(prompts),
        "prompt_sources": list(set(p.get("source", p.get("prompt_type", "unknown")) for p in prompts)),
        "score": {
            "score": score_data["score"],
            "level": score_data["level"],
            "breakdown": score_data["breakdown"],
            "by_llm": score_data["by_llm"],
            "stats": score_data["stats"]
        },
        "revenue_opportunity": revenue_opp,
        "results": result_dicts
    }


"""
Products AI API Endpoints
=========================

Multi-agent powered endpoints for product analysis, smart recommendations,
and intelligent SEO/AEO/GEO optimization.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import logging
import json
from datetime import datetime

from app.db.session import get_db
from app.core.config import settings
from app.models.product import Product
from app.services.smart_recommendations import (
    SmartRecommendationsService,
    get_smart_recommendations_service,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationContext,
    RecommendationFilters,
    Recommendation,
    SmartRecommendationsResponse,
)
from app.services.llm_service import llm_service
from app.services.multi_agent import TaskRouter

logger = logging.getLogger("products_ai_api")

router = APIRouter(prefix="/products-ai", tags=["Products AI"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalysisDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ProductAnalysisRequest(BaseModel):
    product_id: str
    include_analysis: bool = True
    include_recommendations: bool = True
    multi_agent: bool = False
    analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD


class SEOBreakdown(BaseModel):
    technical: int = Field(default=0, ge=0, le=100)
    content: int = Field(default=0, ge=0, le=100)
    keywords: int = Field(default=0, ge=0, le=100)


class SEOAnalysis(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    breakdown: SEOBreakdown
    issues: List[str] = []
    opportunities: List[str] = []


class AEOAnalysis(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    voice_search_ready: bool = False
    faq_opportunities: List[str] = []


class GEOAnalysis(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    ai_visibility: Dict[str, int] = {}


class ProductAnalysisResponse(BaseModel):
    product_id: str
    product_title: str
    seo_analysis: SEOAnalysis
    aeo_analysis: AEOAnalysis
    geo_analysis: GEOAnalysis
    recommendations: List[Recommendation] = []
    _multi_agent: Optional[Dict[str, Any]] = None


class BatchAnalysisRequest(BaseModel):
    product_ids: List[str]
    multi_agent: bool = False
    include_recommendations: bool = False


class BatchAnalysisResponse(BaseModel):
    total_requested: int
    completed: int
    failed: int
    results: Dict[str, ProductAnalysisResponse]


# ============================================================================
# Multi-Agent Product Analysis Endpoints
# ============================================================================

@router.post("/product/{product_id}/analyze")
async def analyze_product_with_multi_agent(
    product_id: str,
    multi_agent: bool = Query(False, description="Enable multi-agent mode"),
    analysis_depth: AnalysisDepth = Query(AnalysisDepth.STANDARD, description="Analysis depth level"),
    db: Session = Depends(get_db)
):
    """
    Perform multi-agent analysis on a single product.
    
    This endpoint uses the 4-agent system (Harper, Benjamin, Lucas, Captain)
    to provide comprehensive SEO/AEO/GEO analysis with consensus scoring.
    
    Args:
        product_id: The product ID to analyze
        multi_agent: Enable multi-agent consensus mode (default: True)
        analysis_depth: Level of analysis depth (quick/standard/deep)
    
    Returns:
        ProductAnalysisResponse with SEO, AEO, GEO analysis and recommendations
    """
    # Get product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    # Build analysis prompt
    prompt = _build_analysis_prompt(product, analysis_depth)
    system_prompt = _get_analysis_system_prompt(analysis_depth)

    # Route to appropriate provider
    router_instance = TaskRouter()
    provider = router_instance.route("product_analysis", multi_agent)

    # Get SEO score from AI cache if available
    seo_score = None
    if product.ai_analysis_cache:
        seo_score = product.ai_analysis_cache.seo_score

    try:
        response = await llm_service.generate_content(
            product_info={
                "product_id": str(product_id),
                "title": product.title,
                "sku": product.sku,
                "seo_score": seo_score,
                "performance_score": product.performance_score,
                "description_length": product.description_length,
            },
            context=[],
            system_prompt=system_prompt,
            provider=provider,
        )

        # Parse response
        analysis = _parse_analysis_response(response, product)

        return analysis

    except Exception as e:
        logger.error(f"Multi-agent analysis failed for product {product_id}: {e}")
        # Return fallback analysis
        return _get_fallback_analysis(product)


@router.post("/recommendations/{product_id}", response_model=SmartRecommendationsResponse)
async def get_smart_recommendations(
    product_id: str,
    multi_agent: bool = Query(False, description="Enable multi-agent mode"),
    min_confidence: int = Query(60, ge=0, le=100, description="Minimum confidence filter"),
    categories: Optional[str] = Query(None, description="Comma-separated categories: seo,aeo,geo,conversion"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum recommendations"),
    sort_by: str = Query("impact", description="Sort by: impact, confidence, effort"),
    context: Optional[RecommendationContext] = Body(None),
    db: Session = Depends(get_db)
):
    """
    Get smart recommendations for a product using multi-agent consensus.
    
    Categories can include:
    - seo: Search engine optimization
    - aeo: Answer engine optimization (voice search, snippets)
    - geo: Generative engine optimization (AI visibility)
    - conversion: Conversion rate optimization
    
    Returns recommendations with confidence scores and implementation steps.
    """
    # Parse categories
    category_list = [RecommendationCategory.SEO, RecommendationCategory.AEO, 
                     RecommendationCategory.GEO, RecommendationCategory.CONVERSION]
    if categories:
        try:
            category_list = [RecommendationCategory(c.strip()) for c in categories.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category. Use: seo, aeo, geo, conversion")

    # Build filters
    filters = RecommendationFilters(
        min_confidence=min_confidence,
        categories=category_list,
        max_results=max_results,
        sort_by=sort_by
    )

    # Get recommendations
    service = get_smart_recommendations_service(db)
    
    try:
        result = await service.get_product_recommendations(
            product_id=product_id,
            context=context or RecommendationContext(),
            filters=filters,
            multi_agent=multi_agent
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get recommendations for {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/analyze", response_model=BatchAnalysisResponse)
async def batch_analyze_products(
    request: BatchAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze multiple products in batch with multi-agent.
    
    Note: For large batches, consider using background tasks.
    Maximum recommended batch size is 20 products.
    """
    if len(request.product_ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum batch size is 20 products")

    results = {}
    completed = 0
    failed = 0

    for product_id in request.product_ids:
        try:
            analysis = await analyze_product_with_multi_agent(
                product_id=product_id,
                multi_agent=request.multi_agent,
                analysis_depth=AnalysisDepth.STANDARD,
                db=db
            )
            results[product_id] = analysis
            completed += 1
        except Exception as e:
            logger.error(f"Batch analysis failed for {product_id}: {e}")
            results[product_id] = {"error": str(e)}
            failed += 1

    return BatchAnalysisResponse(
        total_requested=len(request.product_ids),
        completed=completed,
        failed=failed,
        results=results
    )


@router.post("/batch/recommendations")
async def batch_get_recommendations(
    product_ids: List[str] = Body(..., description="List of product IDs"),
    multi_agent: bool = Query(False, description="Enable multi-agent mode"),
    min_confidence: int = Query(60, ge=0, le=100),
    db: Session = Depends(get_db)
):
    """
    Get recommendations for multiple products in batch.
    
    Returns a dictionary of product_id -> recommendations.
    """
    if len(product_ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum batch size is 20 products")

    service = get_smart_recommendations_service(db)
    filters = RecommendationFilters(min_confidence=min_confidence)

    results = {}
    for product_id in product_ids:
        try:
            result = await service.get_product_recommendations(
                product_id=product_id,
                filters=filters,
                multi_agent=multi_agent
            )
            results[product_id] = result.model_dump()
        except Exception as e:
            logger.error(f"Batch recommendations failed for {product_id}: {e}")
            results[product_id] = {"error": str(e)}

    return {
        "total_requested": len(product_ids),
        "results": results
    }


# ============================================================================
# Quick Analysis Endpoints (Single-Agent for Speed)
# ============================================================================

@router.get("/product/{product_id}/quick-scan")
async def quick_scan_product(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Quick single-agent scan for immediate feedback.
    
    Uses single-agent Grok for faster response (not multi-agent consensus).
    Good for real-time UI feedback.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    # Use single-agent for speed
    router_instance = TaskRouter()
    provider = router_instance.route("product_content", multi_agent_enabled=False)

    try:
        response = await llm_service.generate_content(
            product_info={
                "product_id": str(product_id),
                "title": product.title,
                "seo_score": product.seo_score,
            },
            context=[],
            system_prompt=_get_quick_scan_prompt(),
            provider=provider,
        )

        return {
            "product_id": product_id,
            "quick_score": response.get("score", 70) if isinstance(response, dict) else 70,
            "top_issue": response.get("top_issue", "No issues found") if isinstance(response, dict) else "No issues found",
            "quick_win": response.get("quick_win", "Optimize meta title") if isinstance(response, dict) else "Optimize meta title",
            "analysis_type": "quick_scan"
        }

    except Exception as e:
        logger.error(f"Quick scan failed for {product_id}: {e}")
        return {
            "product_id": product_id,
            "quick_score": product.seo_score or 50,
            "top_issue": "Analysis unavailable",
            "quick_win": "Run full analysis for detailed recommendations",
            "analysis_type": "quick_scan_fallback"
        }


# ============================================================================
# AI-Powered Product Filtering & Discovery
# ============================================================================

@router.get("/discover-opportunities")
async def discover_opportunities(
    opportunity_type: str = Query("all", description="Filter by opportunity type"),
    min_impact: int = Query(500, description="Minimum estimated revenue impact ($)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    AI-powered opportunity discovery across ALL products.
    
    Analyzes patterns in Shopify, GA4, and Search Console data to identify:
    - High revenue products with low SEO scores
    - High traffic products with poor conversion
    - Page 2 ranking opportunities
    - Stale inventory with potential
    - Cross-sell/upsell opportunities
    
    Returns grouped opportunities with estimated impact.
    """
    products = db.query(Product).limit(500).all()
    
    opportunities = {
        "high_revenue_low_seo": [],
        "high_traffic_low_conversion": [],
        "page_two_opportunities": [],
        "high_impressions_low_ctr": [],
        "stale_high_inventory": [],
        "cross_sell_candidates": [],
    }
    
    total_potential_impact = 0
    
    for p in products:
        # High Revenue + Low SEO = Quick Win
        if (p.revenue_90d or 0) >= 5000 and (p.seo_score or 0) < 60:
            impact = int((p.revenue_90d or 0) * 0.25)  # 25% potential uplift
            opportunities["high_revenue_low_seo"].append({
                "product_id": str(p.id),
                "title": p.title or "",
                "sku": p.sku,
                "revenue_90d": p.revenue_90d or 0,
                "seo_score": p.seo_score or 0,
                "potential_impact": impact,
                "quick_fix": "Optimize meta title and description"
            })
            total_potential_impact += impact
        
        # High Traffic + Low Conversion
        if (p.ga4_sessions or 0) >= 100 and (p.ga4_bounce_rate or 0) > 70:
            impact = int((p.ga4_sessions or 0) * 2)  # $2 per session potential
            opportunities["high_traffic_low_conversion"].append({
                "product_id": str(p.id),
                "title": p.title or "",
                "sessions": p.ga4_sessions or 0,
                "bounce_rate": p.ga4_bounce_rate or 0,
                "potential_impact": impact,
                "quick_fix": "Improve page content and add trust signals"
            })
            total_potential_impact += impact
        
        # Page 2 Opportunities (position 11-20)
        if 11 <= (p.gsc_position or 100) <= 20:
            impact = int((p.gsc_impressions or 0) * 0.1)  # 10% click potential
            opportunities["page_two_opportunities"].append({
                "product_id": str(p.id),
                "title": p.title or "",
                "position": round(p.gsc_position or 0, 1),
                "impressions": p.gsc_impressions or 0,
                "potential_impact": impact,
                "quick_fix": "Add internal links and optimize title"
            })
            total_potential_impact += impact
        
        # High Impressions + Low CTR
        if (p.gsc_impressions or 0) >= 500 and (p.gsc_ctr or 0) < 2:
            impact = int((p.gsc_impressions or 0) * 0.05)  # 5% click improvement
            opportunities["high_impressions_low_ctr"].append({
                "product_id": str(p.id),
                "title": p.title or "",
                "impressions": p.gsc_impressions or 0,
                "ctr": round(p.gsc_ctr or 0, 2),
                "potential_impact": impact,
                "quick_fix": "Rewrite meta title for better CTR"
            })
            total_potential_impact += impact
        
        # Stale Inventory (no sales, high stock)
        if (p.sold_90d or 0) == 0 and (p.inventory_quantity or 0) >= 5:
            impact = int((p.inventory_quantity or 0) * 50)  # $50 per unit potential
            opportunities["stale_high_inventory"].append({
                "product_id": str(p.id),
                "title": p.title or "",
                "inventory": p.inventory_quantity or 0,
                "days_since_sale": "90+",
                "potential_impact": impact,
                "quick_fix": "Create promotion bundle or refresh content"
            })
            total_potential_impact += impact
    
    # Sort each category by impact
    for key in opportunities:
        opportunities[key].sort(key=lambda x: x.get("potential_impact", 0), reverse=True)
        opportunities[key] = opportunities[key][:limit]
    
    # Filter by opportunity_type if specified
    if opportunity_type != "all" and opportunity_type in opportunities:
        filtered = {opportunity_type: opportunities[opportunity_type]}
        filtered_total = sum(o.get("potential_impact", 0) for o in opportunities[opportunity_type])
    else:
        filtered = opportunities
        filtered_total = total_potential_impact
    
    return {
        "opportunities": filtered,
        "summary": {
            "total_products_analyzed": len(products),
            "total_opportunities_found": sum(len(v) for v in opportunities.values()),
            "total_potential_impact": filtered_total,
            "by_category": {
                "high_revenue_low_seo": len(opportunities["high_revenue_low_seo"]),
                "high_traffic_low_conversion": len(opportunities["high_traffic_low_conversion"]),
                "page_two_opportunities": len(opportunities["page_two_opportunities"]),
                "high_impressions_low_ctr": len(opportunities["high_impressions_low_ctr"]),
                "stale_high_inventory": len(opportunities["stale_high_inventory"]),
            }
        },
        "data_sources_used": ["shopify", "ga4", "search_console"],
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/smart-filters")
async def get_smart_filters(
    db: Session = Depends(get_db)
):
    """
    Get AI-suggested smart filters based on your product data.
    
    Returns filter configurations that would surface high-opportunity products.
    """
    products = db.query(Product).limit(500).all()
    
    # Analyze data to suggest filters
    filters = []
    
    # Calculate thresholds based on data distribution
    revenues = sorted([p.revenue_90d or 0 for p in products], reverse=True)
    sessions = sorted([p.ga4_sessions or 0 for p in products], reverse=True)
    
    if len(revenues) > 10:
        top_10_revenue = revenues[9]  # 10th highest
        filters.append({
            "id": "top-revenue-low-seo",
            "name": "Top Revenue, Low SEO",
            "description": "Products generating significant revenue with SEO scores below 60",
            "filter_config": {
                "revenue_90d_min": top_10_revenue,
                "seo_score_max": 60,
            },
            "estimated_count": len([p for p in products if (p.revenue_90d or 0) >= top_10_revenue and (p.seo_score or 0) < 60]),
            "potential_impact": "High",
            "icon": "💰"
        })
    
    if len(sessions) > 10:
        top_10_sessions = sessions[9]
        filters.append({
            "id": "high-traffic-high-bounce",
            "name": "High Traffic, High Bounce",
            "description": "Popular products losing visitors - conversion optimization needed",
            "filter_config": {
                "ga4_sessions_min": top_10_sessions,
                "ga4_bounce_rate_min": 70,
            },
            "estimated_count": len([p for p in products if (p.ga4_sessions or 0) >= top_10_sessions and (p.ga4_bounce_rate or 0) >= 70]),
            "potential_impact": "High",
            "icon": "📊"
        })
    
    # Page 2 opportunities
    page_2_count = len([p for p in products if 11 <= (p.gsc_position or 100) <= 20])
    if page_2_count > 0:
        filters.append({
            "id": "page-two-push",
            "name": "Page 2 → Page 1",
            "description": "Products on Google page 2 - one push away from visibility",
            "filter_config": {
                "gsc_position_min": 11,
                "gsc_position_max": 20,
            },
            "estimated_count": page_2_count,
            "potential_impact": "Medium",
            "icon": "🔍"
        })
    
    # No sales but has traffic
    traffic_no_sales = len([p for p in products if (p.ga4_sessions or 0) >= 50 and (p.sold_90d or 0) == 0])
    if traffic_no_sales > 0:
        filters.append({
            "id": "traffic-no-conversions",
            "name": "Traffic Without Conversions",
            "description": "Products getting visitors but not converting",
            "filter_config": {
                "ga4_sessions_min": 50,
                "sold_90d_max": 0,
            },
            "estimated_count": traffic_no_sales,
            "potential_impact": "High",
            "icon": "⚠️"
        })
    
    # Stale inventory
    stale_count = len([p for p in products if (p.sold_90d or 0) == 0 and (p.inventory_quantity or 0) >= 10])
    if stale_count > 0:
        filters.append({
            "id": "stale-inventory",
            "name": "Stale Inventory",
            "description": "Products with no recent sales but significant stock",
            "filter_config": {
                "sold_90d_max": 0,
                "inventory_quantity_min": 10,
            },
            "estimated_count": stale_count,
            "potential_impact": "Medium",
            "icon": "📦"
        })
    
    return {
        "smart_filters": filters,
        "total_filters": len(filters),
        "data_analyzed": len(products),
        "last_updated": datetime.utcnow().isoformat()
    }


@router.post("/batch-discover")
async def batch_discover_opportunities(
    multi_agent: bool = Query(False, description="Enable multi-agent mode"),
    db: Session = Depends(get_db)
):
    """
    Run multi-agent analysis to discover cross-product opportunities.
    
    This endpoint uses the 4-agent system to analyze patterns across
    all products and identify strategic opportunities.
    """
    products = db.query(Product).limit(50).all()  # Limit for performance
    
    # Build aggregate data for multi-agent analysis
    aggregate_data = {
        "total_products": len(products),
        "avg_seo_score": sum(p.seo_score or 0 for p in products) / len(products) if products else 0,
        "total_revenue_90d": sum(p.revenue_90d or 0 for p in products),
        "total_sessions": sum(p.ga4_sessions or 0 for p in products),
        "products_by_opportunity": {
            "high": len([p for p in products if p.opportunity_level == "high"]),
            "medium": len([p for p in products if p.opportunity_level == "medium"]),
            "low": len([p for p in products if p.opportunity_level == "low"]),
        },
        "seo_score_distribution": {
            "excellent": len([p for p in products if (p.seo_score or 0) >= 80]),
            "good": len([p for p in products if 60 <= (p.seo_score or 0) < 80]),
            "needs_work": len([p for p in products if 40 <= (p.seo_score or 0) < 60]),
            "critical": len([p for p in products if (p.seo_score or 0) < 40]),
        },
        "top_transmission_codes": _get_top_transmission_codes(products),
    }
    
    # Use multi-agent for strategic analysis
    router_instance = TaskRouter()
    provider = router_instance.route("recommendation_engine", multi_agent)
    
    system_prompt = """You are a strategic SEO/AEO/GEO consultant for Example Store, analyzing aggregate product data.

Based on the aggregate data provided, identify:
1. Strategic opportunities across product categories
2. Quick wins that would impact multiple products
3. Content gaps in the catalog
4. Cross-sell/upsell opportunities
5. Technical SEO improvements needed site-wide

Respond with JSON containing strategic recommendations."""

    prompt = f"""# AGGREGATE PRODUCT ANALYSIS

## Data Summary
```json
{json.dumps(aggregate_data, indent=2, ensure_ascii=False)}
```

## Task
Analyze this aggregate data and provide strategic recommendations that would improve performance across multiple products.

## Response Format
Return JSON:
{{
  "strategic_recommendations": [
    {{
      "type": "quick_win" | "strategic" | "technical",
      "title": "Recommendation title",
      "description": "Detailed description",
      "affected_products": 10,
      "estimated_impact": "$X-X/month",
      "implementation_effort": "low" | "medium" | "high",
      "priority": 1-10
    }}
  ],
  "content_gaps": ["gap1", "gap2"],
  "cross_sell_opportunities": [
    {{"product_a": "SKU1", "product_b": "SKU2", "reason": "reason"}}
  ],
  "technical_improvements": ["improvement1", "improvement2"],
  "_multi_agent": {{
    "mode": "simulated",
    "consensus_score": 85
  }}
}}"""

    try:
        response = await llm_service.generate_content(
            product_info=aggregate_data,
            context=[],
            system_prompt=system_prompt,
            provider=provider,
        )
        
        return {
            "aggregate_data": aggregate_data,
            "strategic_analysis": response,
            "analysis_type": "multi_agent_batch"
        }
    except Exception as e:
        logger.error(f"Batch discover failed: {e}")
        return {
            "aggregate_data": aggregate_data,
            "strategic_analysis": {"error": str(e)},
            "analysis_type": "fallback"
        }


def _get_top_transmission_codes(products: list) -> dict:
    """Get top transmission codes by revenue."""
    code_revenue = {}
    for p in products:
        code = p.transmission_code
        if code:
            code_revenue[code] = code_revenue.get(code, 0) + (p.revenue_90d or 0)
    
    # Sort by revenue and return top 5
    sorted_codes = sorted(code_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
    return dict(sorted_codes)


# ============================================================================
# Multi-Agent Status Endpoint
# ============================================================================

@router.get("/multi-agent/status")
async def get_products_multi_agent_status():
    """
    Get current multi-agent configuration for products AI module.
    """
    return {
        "multi_agent_enabled": settings.MULTI_AGENT_ENABLED,
        "mode": settings.XAI_GROK420_MODEL,
        "model": settings.XAI_GROK420_MODEL,
        "timeout": settings.MULTI_AGENT_TIMEOUT,
        "available_task_types": [
            "product_analysis",
            "recommendation_engine",
            "content_generation",
            "seo_optimization"
        ],
        "agents": ["harper", "benjamin", "lucas", "captain"]
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _build_analysis_prompt(product: Product, depth: AnalysisDepth) -> str:
    """Build the analysis prompt based on depth level."""
    import json

    product_data = {
        "id": str(product.id),
        "title": product.title,
        "sku": product.sku,
        "handle": product.handle,
        "seo_score": product.seo_score or 0,
        "description_length": product.description_length or 0,
        "image_count": product.image_count or 0,
        "total_sold": product.total_sold or 0,
        "ga4_sessions": product.ga4_sessions or 0,
        "gsc_impressions": product.gsc_impressions or 0,
        "gsc_clicks": product.gsc_clicks or 0,
        "gsc_position": float(product.gsc_position or 0),
        "transmission_code": product.transmission_code,
    }

    depth_instructions = {
        AnalysisDepth.QUICK: "Focus on top 3 issues only. Brief analysis.",
        AnalysisDepth.STANDARD: "Comprehensive analysis with all major categories.",
        AnalysisDepth.DEEP: "Exhaustive analysis with detailed recommendations and implementation steps."
    }

    return f"""# PRODUCT ANALYSIS TASK

## Product Data
```json
{json.dumps(product_data, indent=2, ensure_ascii=False)}
```

## Analysis Depth: {depth.value}
{depth_instructions[depth]}

## Task
Analyze this product for SEO, AEO, and GEO optimization opportunities.

Provide scores (0-100) and specific issues/opportunities for each category:

1. **SEO Analysis**
   - Technical score (meta tags, structure, schema)
   - Content score (length, keywords, relevance)
   - Keywords score (density, targeting, opportunities)
   - List critical issues
   - List improvement opportunities

2. **AEO Analysis** (Answer Engine Optimization)
   - Voice search readiness
   - FAQ opportunities
   - Featured snippet potential

3. **GEO Analysis** (Generative Engine Optimization)
   - AI visibility score for Grok, Perplexity, ChatGPT
   - Entity clarity
   - Context gaps

## Response Format
Return JSON with this structure:
{{
  "seo_analysis": {{
    "score": 75,
    "breakdown": {{
      "technical": 70,
      "content": 80,
      "keywords": 75
    }},
    "issues": ["Missing meta description", "No FAQ schema"],
    "opportunities": ["Add transmission code to title", "Create FAQ section"]
  }},
  "aeo_analysis": {{
    "score": 60,
    "voice_search_ready": false,
    "faq_opportunities": ["How to install this kit?", "What vehicles is it compatible with?"]
  }},
  "geo_analysis": {{
    "score": 55,
    "ai_visibility": {{
      "grok": 60,
      "perplexity": 50,
      "chatgpt": 55
    }}
  }}
}}

Respond ONLY with valid JSON."""


def _get_analysis_system_prompt(depth: AnalysisDepth) -> str:
    """Get system prompt based on analysis depth."""
    base_prompt = """You are an expert SEO/AEO/GEO analyst for Example Store, a transmission parts e-commerce company.

Analyze products and provide actionable insights for:
1. SEO - Search engine optimization (Google, Bing)
2. AEO - Answer engine optimization (voice search, featured snippets)
3. GEO - Generative engine optimization (AI citations, visibility in LLMs)

Rules:
- Be specific and actionable
- Provide quantified scores (0-100)
- Consider Mexican Spanish language context
- Focus on transmission-specific terminology
- Respond ONLY with valid JSON"""

    depth_additions = {
        AnalysisDepth.QUICK: "\n\nPrioritize speed. Focus on the most impactful issues only.",
        AnalysisDepth.STANDARD: "\n\nProvide balanced coverage of all categories.",
        AnalysisDepth.DEEP: "\n\nBe exhaustive. Include detailed implementation steps and estimated impact for each recommendation."
    }

    return base_prompt + depth_additions[depth]


def _get_quick_scan_prompt() -> str:
    """Get quick scan system prompt."""
    return """You are a quick SEO scanner. Analyze the product briefly and provide:
1. An overall score (0-100)
2. The top issue that needs immediate attention
3. One quick win that can be implemented immediately

Respond ONLY with JSON:
{
  "score": 75,
  "top_issue": "Missing meta description",
  "quick_win": "Add transmission code to title"
}"""


def _parse_analysis_response(response: Dict, product: Product) -> ProductAnalysisResponse:
    """Parse AI response into ProductAnalysisResponse."""
    try:
        content = response
        if isinstance(response, dict):
            if "content" in response:
                content = response["content"]
                if isinstance(content, str):
                    import json
                    try:
                        content = json.loads(content)
                    except:
                        # Find JSON in string
                        start = content.find("{")
                        end = content.rfind("}") + 1
                        if start >= 0 and end > start:
                            content = json.loads(content[start:end])

        seo_data = content.get("seo_analysis", {})
        aeo_data = content.get("aeo_analysis", {})
        geo_data = content.get("geo_analysis", {})

        return ProductAnalysisResponse(
            product_id=str(product.id),
            product_title=product.title or "",
            seo_analysis=SEOAnalysis(
                score=seo_data.get("score", product.seo_score or 50),
                breakdown=SEOBreakdown(**seo_data.get("breakdown", {})),
                issues=seo_data.get("issues", []),
                opportunities=seo_data.get("opportunities", [])
            ),
            aeo_analysis=AEOAnalysis(
                score=aeo_data.get("score", 50),
                voice_search_ready=aeo_data.get("voice_search_ready", False),
                faq_opportunities=aeo_data.get("faq_opportunities", [])
            ),
            geo_analysis=GEOAnalysis(
                score=geo_data.get("score", 50),
                ai_visibility=geo_data.get("ai_visibility", {})
            ),
            recommendations=[],
            _multi_agent=response.get("_multi_agent") if isinstance(response, dict) else None
        )

    except Exception as e:
        logger.error(f"Failed to parse analysis response: {e}")
        return _get_fallback_analysis(product)


def _get_fallback_analysis(product: Product) -> ProductAnalysisResponse:
    """Return fallback analysis when AI fails."""
    return ProductAnalysisResponse(
        product_id=str(product.id),
        product_title=product.title or "",
        seo_analysis=SEOAnalysis(
            score=product.seo_score or 50,
            breakdown=SEOBreakdown(
                technical=50,
                content=50,
                keywords=50
            ),
            issues=["AI analysis unavailable - showing basic score"],
            opportunities=["Run analysis again for detailed recommendations"]
        ),
        aeo_analysis=AEOAnalysis(
            score=50,
            voice_search_ready=False,
            faq_opportunities=[]
        ),
        geo_analysis=GEOAnalysis(
            score=50,
            ai_visibility={}
        ),
        recommendations=[],
        _multi_agent=None
    )

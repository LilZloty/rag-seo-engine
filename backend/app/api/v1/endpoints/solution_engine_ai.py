"""
Solution Engine AI API Endpoints
=================================

Async endpoints for AI-powered fault code analysis and content generation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
import logging

from app.db.session import get_db
from app.core.config import settings
from app.services.solution_engine_ai import SolutionEngineAI, get_solution_engine_ai
from app.services.blog_content_generator import BlogContentGenerator, get_blog_generator
from app.services.schema_generator import SchemaGenerator, get_schema_generator

logger = logging.getLogger("solution_engine_api")

router = APIRouter(prefix="/solution-engine/ai", tags=["Solution Engine AI"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class AIProductRecommendation(BaseModel):
    product_id: str
    sku: Optional[str]
    title: str
    rank: int
    match_score: int
    reasoning: str
    fix_probability: str
    url: Optional[str]


class AIFaultCodeAnalysisResponse(BaseModel):
    fault_code: str
    products: List[AIProductRecommendation]
    reasoning: str
    confidence: int
    alternative_approaches: List[str]
    ai_analyzed: bool


class BlogContentRequest(BaseModel):
    fault_code: str = Field(..., description="Fault code to generate content for")
    include_products: bool = True
    word_count: int = Field(1000, ge=500, le=2000)
    tone: str = Field("professional", description="professional, friendly, technical")


class BlogContentSection(BaseModel):
    heading: str
    content: str
    type: str  # intro, symptoms, causes, solution, products, cta


class BlogContentResponse(BaseModel):
    fault_code: str
    title: str
    meta_description: str
    sections: List[BlogContentSection]
    product_recommendations: List[dict]
    faq_schema: dict
    howto_schema: dict
    estimated_read_time: int
    target_keywords: List[str]


class SchemaGenerationRequest(BaseModel):
    content_type: str = Field(..., description="faq, howto, product, breadcrumb")
    fault_code: Optional[str] = None
    blog_content: Optional[str] = None
    products: Optional[List[str]] = None


class SchemaGenerationResponse(BaseModel):
    schema_type: str
    schema_json: dict
    html_script: str


class ContentBatchRequest(BaseModel):
    fault_codes: List[str]
    generate_blogs: bool = True
    generate_schemas: bool = True
    publish_to_shopify: bool = False


class ContentBatchResponse(BaseModel):
    total_requested: int
    completed: int
    failed: int
    results: List[dict]


# ============================================================================
# AI Analysis Endpoints
# ============================================================================

@router.post("/fault-code/{fault_code}/analyze")
async def analyze_fault_code_with_ai(
    fault_code: str,
    multi_agent: Optional[bool] = Query(None, description="Enable multi-agent mode"),
    db: Session = Depends(get_db)
):
    """
    Use Grok AI to analyze which products truly solve a fault code.

    Pass multi_agent=true to use the 4-agent consensus system (Grok 4.20),
    or multi_agent=false for standard single-agent Grok.
    Defaults to the MULTI_AGENT_ENABLED setting.
    """
    engine = get_solution_engine_ai(db)
    multi_agent_enabled = multi_agent if multi_agent is not None else settings.MULTI_AGENT_ENABLED

    try:
        result = await engine.analyze_fault_code_with_ai(
            fault_code, multi_agent_enabled=multi_agent_enabled
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"AI analysis failed for {fault_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smart-snippet/geo")
async def generate_geo_optimized_snippet(
    query: str = Query(..., description="Search query to optimize for"),
    multi_agent: Optional[bool] = Query(None, description="Enable multi-agent mode"),
    db: Session = Depends(get_db)
):
    """
    Generate GEO-optimized snippet for AI engine citations.

    Optimized for:
    - Grok citations
    - Perplexity references
    - ChatGPT knowledge
    """
    engine = get_solution_engine_ai(db)
    multi_agent_enabled = multi_agent if multi_agent is not None else settings.MULTI_AGENT_ENABLED

    try:
        snippet = await engine.generate_geo_snippet(query, multi_agent_enabled=multi_agent_enabled)
        return snippet
    except Exception as e:
        logger.error(f"GEO snippet generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blog/{blog_id}/analyze")
async def analyze_blog_content(
    blog_id: str,
    db: Session = Depends(get_db)
):
    """
    Analyze blog content and recommend products to feature.
    
    Uses AI to understand content context and find relevant products.
    """
    engine = get_solution_engine_ai(db)
    
    try:
        result = await engine.analyze_blog_content(blog_id)
        return result
    except Exception as e:
        logger.error(f"Blog analysis failed for {blog_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Content Generation Endpoints
# ============================================================================

@router.post("/content/generate-blog", response_model=BlogContentResponse)
async def generate_blog_content(
    request: BlogContentRequest,
    db: Session = Depends(get_db)
):
    """
    Generate complete AEO-optimized blog article for a fault code.
    
    Creates content with:
    - SEO-optimized title and meta description
    - Structured sections (symptoms, causes, solutions)
    - Embedded product recommendations
    - Schema.org FAQ and HowTo markup
    """
    generator = get_blog_generator(db)
    
    try:
        result = await generator.generate_fault_code_article(
            fault_code=request.fault_code,
            include_products=request.include_products,
            word_count=request.word_count,
            tone=request.tone
        )
        return result
    except Exception as e:
        logger.error(f"Blog generation failed for {request.fault_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content/generate-schema", response_model=SchemaGenerationResponse)
async def generate_schema(
    request: SchemaGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Schema.org structured data.
    
    Supports: FAQPage, HowTo, Product, BreadcrumbList
    """
    generator = get_schema_generator(db)
    
    try:
        result = await generator.generate_schema(
            content_type=request.content_type,
            fault_code=request.fault_code,
            blog_content=request.blog_content,
            product_ids=request.products
        )
        return result
    except Exception as e:
        logger.error(f"Schema generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Operations
# ============================================================================

@router.post("/batch/generate-content", response_model=ContentBatchResponse)
async def batch_generate_content(
    request: ContentBatchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate content for multiple fault codes in batch.
    
    Can run in background for large batches.
    """
    generator = get_blog_generator(db)
    
    results = []
    completed = 0
    failed = 0
    
    for fault_code in request.fault_codes:
        try:
            if request.generate_blogs:
                result = await generator.generate_fault_code_article(
                    fault_code=fault_code,
                    include_products=True
                )
                results.append({
                    "fault_code": fault_code,
                    "status": "success",
                    "blog_title": result.title
                })
                completed += 1
        except Exception as e:
            results.append({
                "fault_code": fault_code,
                "status": "failed",
                "error": str(e)
            })
            failed += 1
    
    return {
        "total_requested": len(request.fault_codes),
        "completed": completed,
        "failed": failed,
        "results": results
    }


# ============================================================================
# Collection Management Endpoints
# ============================================================================

@router.post("/collections/create-for-fault-code/{fault_code}")
async def create_collection_for_fault_code(
    fault_code: str,
    db: Session = Depends(get_db)
):
    """
    Create a Shopify collection for a fault code with matching products.
    
    Collection will be named: "Kits [Fault Code] - [Transmission Names]"
    """
    from app.services.collection_manager import CollectionManager, get_collection_manager
    
    manager = get_collection_manager(db)
    
    try:
        result = await manager.create_fault_code_collection(fault_code)
        return result
    except Exception as e:
        logger.error(f"Collection creation failed for {fault_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/fault-code/{fault_code}")
async def get_fault_code_collection_data(
    fault_code: str,
    db: Session = Depends(get_db)
):
    """
    Get collection data for a fault code (products, description, SEO data).
    """
    from app.services.collection_manager import CollectionManager, get_collection_manager
    
    manager = get_collection_manager(db)
    
    try:
        result = await manager.get_collection_data(fault_code)
        return result
    except Exception as e:
        logger.error(f"Failed to get collection data for {fault_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard/Stats Endpoints
# ============================================================================

@router.get("/dashboard/ai-stats")
async def get_ai_dashboard_stats(
    db: Session = Depends(get_db)
):
    """
    Get AI-powered Solution Engine statistics.
    """
    from app.models.solution_graph import (
        ProductRecommendationEngine, SmartSnippet, SolutionPath
    )
    from sqlalchemy import func
    
    try:
        # Count AI-generated recommendations
        ai_recs = db.query(ProductRecommendationEngine).filter(
            ProductRecommendationEngine.generated_by == "grok"
        ).count()
        
        # Count smart snippets
        snippets = db.query(SmartSnippet).count()
        
        # Count solution paths
        paths = db.query(SolutionPath).count()
        
        # Average confidence score
        avg_confidence = db.query(
            func.avg(ProductRecommendationEngine.confidence_score)
        ).filter(
            ProductRecommendationEngine.generated_by == "grok"
        ).scalar() or 0
        
        return {
            "ai_analyzed_fault_codes": ai_recs,
            "smart_snippets_generated": snippets,
            "solution_paths_created": paths,
            "average_ai_confidence": round(avg_confidence, 1),
            "fault_codes_ready_for_content": ai_recs  # Those with AI analysis
        }
    except Exception as e:
        logger.error(f"Failed to get AI stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Multi-Agent Status Endpoint
# ============================================================================

@router.get("/multi-agent/status")
async def get_multi_agent_status():
    """
    Get current multi-agent configuration and status.
    """
    from app.services.llm_providers.base import LLMProviderFactory

    grok420_registered = LLMProviderFactory.is_registered("grok420")
    grok420_status = {}
    if grok420_registered:
        try:
            provider = LLMProviderFactory.create("grok420")
            grok420_status = provider.get_status()
        except Exception as e:
            grok420_status = {"error": str(e)}

    return {
        "multi_agent_enabled": settings.MULTI_AGENT_ENABLED,
        "mode": settings.XAI_GROK420_MODE,
        "model": settings.XAI_GROK420_MODEL,
        "timeout": settings.MULTI_AGENT_TIMEOUT,
        "provider_registered": grok420_registered,
        "provider_status": grok420_status,
        "agents": ["harper", "benjamin", "lucas", "captain"],
    }

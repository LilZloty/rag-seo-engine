"""
AEO API Endpoints (Optimized Version)

REST API for Answer Engine Optimization features.
Per architecture doc: /api/v1/aeo/

Improvements:
- Chunks now include sample_products
- New endpoint for batch transmission_code update
- New endpoint for blog cache refresh
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.db.session import get_db
from app.services.aeo_service import aeo_service
from app.services.ai_visibility_service import ai_visibility_service
from app.schemas.aeo_schemas import (
    ProductChunkResponse,
    ChunkApprovalRequest,
    LLMSTxtPreviewResponse,
    LLMSTxtGenerateRequest,
    VehiclePartSchemaResponse,
    BlogArticleResponse,
    AEOConfigResponse,
    AEOConfigUpdateRequest,
    # AI Visibility schemas
    PromptPanelItemCreate,
    PromptPanelItemResponse,
    AIVisibilityResultResponse,
    VisibilitySnapshotResponse,
    VisibilityCheckRequest,
    VisibilityDashboardResponse,
    # Product Intelligence schemas
    ProductIntelligenceResponse,
)
from app.schemas.analytics_schemas import VisibilitySalesCorrelation

from app.models.aeo_models import AEOConfig, AEOEvent, VisibilitySnapshot
from pydantic import BaseModel


router = APIRouter()


# ============ llms.txt Endpoints ============

@router.get("/llms-txt", response_class=PlainTextResponse)
async def download_llms_txt(
    force_rebuild: bool = False,
    db: Session = Depends(get_db)
):
    """
    Download generated llms.txt file.
    
    Returns plain text markdown suitable for upload to Shopify.
    """
    content, _ = aeo_service.generate_llms_txt(db, force_rebuild=force_rebuild)
    return PlainTextResponse(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=llms.txt"}
    )


@router.get("/llms-txt/preview", response_model=LLMSTxtPreviewResponse)
async def preview_llms_txt(db: Session = Depends(get_db)):
    """
    Preview llms.txt with metadata including token estimate.
    """
    return aeo_service.get_llms_txt_preview(db)


@router.post("/rebuild")
async def rebuild_llms_txt(db: Session = Depends(get_db)):
    """
    Force rebuild llms.txt cache.
    """
    content, tokens = aeo_service.generate_llms_txt(db, force_rebuild=True)
    return {
        "status": "rebuilt",
        "token_estimate": tokens,
        "byte_size": len(content.encode('utf-8'))
    }


# ============ Chunk Management Endpoints ============

@router.get("/chunks", response_model=List[ProductChunkResponse])
async def list_chunks(
    include_samples: bool = Query(True, description="Include sample products in response"),
    db: Session = Depends(get_db)
):
    """
    List all product type chunks with approval status.
    
    Chunks are computed from products grouped by transmission_code field.
    Includes sample products when include_samples=true.
    """
    chunks = aeo_service.get_product_chunks(db, include_samples=include_samples)
    return chunks


@router.post("/chunks/{product_type}/approve")
async def approve_chunk(
    product_type: str,
    request: ChunkApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve or reject a product type chunk for llms.txt inclusion.
    """
    status = aeo_service.approve_chunk(
        db=db,
        product_type=product_type,
        approved=request.approved,
        approved_by=request.approved_by,
        notes=request.notes
    )
    
    return {
        "product_type": status.product_type,
        "approved": status.approved,
        "approved_at": status.approved_at,
        "message": f"Chunk {'approved' if status.approved else 'rejected'}"
    }


@router.post("/chunks/{product_type}/reject")
async def reject_chunk(
    product_type: str,
    notes: str = None,
    db: Session = Depends(get_db)
):
    """
    Reject a product type chunk (shortcut for approve with approved=False).
    """
    status = aeo_service.approve_chunk(
        db=db,
        product_type=product_type,
        approved=False,
        notes=notes
    )
    
    return {
        "product_type": status.product_type,
        "approved": False,
        "message": "Chunk rejected"
    }


# ============ Batch Update Endpoints ============

@router.post("/sync-transmission-codes")
async def sync_transmission_codes(db: Session = Depends(get_db)):
    """
    Batch update transmission_code field for all products.
    
    Uses configured patterns from TransmissionPattern table.
    Call this after Shopify product sync.
    """
    count = aeo_service.update_product_transmission_codes(db)
    return {
        "status": "completed",
        "products_updated": count,
        "message": f"Updated transmission_code for {count} products"
    }


@router.post("/refresh-blogs")
async def refresh_blog_cache(db: Session = Depends(get_db)):
    """
    Fetch blog articles from Shopify and update cache.
    """
    count = aeo_service.refresh_blog_cache(db)
    return {
        "status": "completed",
        "blogs_cached": count,
        "message": f"Cached {count} blog articles"
    }


# ============ Schema.org Endpoints ============

@router.get("/schema/product/{product_id}", response_model=VehiclePartSchemaResponse)
async def get_product_schema(
    product_id: str,
    db: Session = Depends(get_db)
):
    """
    Get VehiclePart JSON-LD schema for a specific product.
    """
    json_ld = aeo_service.generate_product_schema(db, product_id)
    
    if "error" in json_ld:
        raise HTTPException(status_code=404, detail=json_ld["error"])
    
    return {
        "product_id": product_id,
        "json_ld": json_ld,
        "validation_status": "valid"
    }


@router.get("/schema/bulk")
async def get_bulk_schemas(
    chunk_id: str = Query(None, description="Filter by transmission code (e.g., DQ200)"),
    db: Session = Depends(get_db)
):
    """
    Generate schemas for multiple products.
    
    Optionally filter by chunk_id (transmission type).
    """
    schemas = aeo_service.generate_bulk_schemas(db, chunk_id)
    
    return {
        "count": len(schemas),
        "schemas": schemas
    }


@router.get("/schema/metrics")
async def get_schema_metrics(db: Session = Depends(get_db)):
    """
    Get aggregate schema deployment metrics for the dashboard.
    """
    return aeo_service.get_schema_metrics(db)


# ============ Blog Endpoints ============

@router.get("/blogs", response_model=List[BlogArticleResponse])
async def list_blogs(db: Session = Depends(get_db)):
    """
    List blog articles available for llms.txt inclusion.
    
    Returns cached blogs. Use /refresh-blogs to update cache.
    """
    try:
        articles = aeo_service.get_blog_articles(db)
        return articles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch blogs: {str(e)}")


# ============ Patterns Endpoints ============

@router.get("/patterns")
async def list_patterns(db: Session = Depends(get_db)):
    """
    List all transmission patterns used for chunk extraction.
    """
    patterns = aeo_service.get_patterns(db)
    return {
        "count": len(patterns),
        "patterns": [
            {"code": code, "category": cat, "description": desc}
            for code, (cat, desc) in patterns.items()
        ]
    }


# ============ Config Endpoints ============

@router.get("/config", response_model=AEOConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    """
    Get current AEO configuration.
    """
    config = aeo_service.get_aeo_config(db)
    return {
        "llms_txt_version": config.llms_txt_version,
        "include_blogs": config.include_blogs,
        "include_collections": config.include_collections,
        "include_fault_codes": getattr(config, 'include_fault_codes', True),
        "max_products_per_category": int(config.max_products_per_category),
        "store_name": config.store_name,
        "store_description": config.store_description,
        "authority_statement": getattr(config, 'authority_statement', None)
    }


@router.patch("/config")
async def update_config(
    request: AEOConfigUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update AEO configuration.
    """
    config = aeo_service.get_aeo_config(db)
    
    if request.include_blogs is not None:
        config.include_blogs = request.include_blogs
    if request.include_collections is not None:
        config.include_collections = request.include_collections
    if request.max_products_per_category is not None:
        config.max_products_per_category = str(request.max_products_per_category)
    if request.store_name is not None:
        config.store_name = request.store_name
    if request.store_description is not None:
        config.store_description = request.store_description
    if hasattr(request, 'include_fault_codes') and request.include_fault_codes is not None:
        config.include_fault_codes = request.include_fault_codes
    if hasattr(request, 'authority_statement') and request.authority_statement is not None:
        config.authority_statement = request.authority_statement
    
    db.commit()
    
    return {"status": "updated", "config": config}


# ============ GEO Fault Code Endpoints ============

@router.get("/fault-codes")
async def list_fault_codes(
    priority_only: bool = Query(False, description="Only return priority fault codes from GA"),
    db: Session = Depends(get_db)
):
    """
    List all fault codes in the Knowledge Graph.
    
    Priority fault codes are those with highest traffic from Google Analytics.
    """
    fault_codes = aeo_service.get_fault_codes(db, priority_only=priority_only)
    return {
        "count": len(fault_codes),
        "fault_codes": [
            {
                "code": fc.code,
                "name": fc.name,
                "description": fc.description,
                "severity": fc.severity,
                "monthly_clicks": fc.monthly_clicks,
                "monthly_impressions": fc.monthly_impressions,
                "current_ctr": fc.current_ctr,
                "transmissions": fc.transmissions or [],
                "vehicles": fc.vehicles or [],
                "blog_url": fc.blog_url,
                "is_priority": fc.is_priority,
                "has_faq_schema": fc.has_faq_schema
            }
            for fc in fault_codes
        ]
    }


@router.get("/fault-codes/{code}")
async def get_fault_code(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Get a single fault code with full details.
    """
    fc = aeo_service.get_fault_code(db, code)
    if not fc:
        raise HTTPException(status_code=404, detail=f"Fault code {code} not found")
    
    return {
        "code": fc.code,
        "name": fc.name,
        "description": fc.description,
        "severity": fc.severity,
        "monthly_clicks": fc.monthly_clicks,
        "monthly_impressions": fc.monthly_impressions,
        "current_ctr": fc.current_ctr,
        "transmissions": fc.transmissions or [],
        "vehicles": fc.vehicles or [],
        "common_causes": fc.common_causes or [],
        "symptoms_text": fc.symptoms_text or [],
        "blog_url": fc.blog_url,
        "collection_url": fc.collection_url,
        "is_priority": fc.is_priority,
        "include_in_llms_txt": fc.include_in_llms_txt,
        "has_faq_schema": fc.has_faq_schema,
        "solutions": [
            {
                "id": s.id,
                "solution_type": s.solution_type,
                "description": s.description,
                "success_rate": s.success_rate,
                "product_ids": s.product_ids or []
            }
            for s in fc.solutions
        ] if fc.solutions else [],
        # NEW: Dynamic product recommendations from real database
        "recommended_products": aeo_service.get_recommended_skus_dynamic(db, code, limit=5)
    }


@router.get("/fault-codes/{code}/products")
async def get_products_for_fault_code(
    code: str,
    limit: int = Query(10, description="Max products to return"),
    db: Session = Depends(get_db)
):
    """
    Get REAL products from your catalog that can fix a fault code.
    
    Uses transmission_code to match products, ordered by sales volume.
    This replaces hardcoded SKUs with actual inventory.
    """
    products = aeo_service.get_real_products_for_fault_code(db, code, limit)
    
    if not products:
        return {
            "fault_code": code,
            "count": 0,
            "products": [],
            "message": "No products found. Check if transmission codes are synced."
        }
    
    return {
        "fault_code": code,
        "count": len(products),
        "products": [
            {
                "id": p.id,
                "sku": p.sku,
                "title": p.title,
                "price": p.price,
                "vendor": p.vendor,
                "handle": p.handle,
                "url": f"/products/{p.handle}" if p.handle else None,
                "transmission_code": p.transmission_code,
                "total_sold": p.total_sold
            }
            for p in products
        ]
    }


@router.post("/chunks/auto-approve")
async def auto_approve_chunks(
    limit: int = Query(15, description="Max chunks to approve"),
    min_products: int = Query(5, description="Minimum products required"),
    db: Session = Depends(get_db)
):
    """
    Auto-approve top chunks by product count.
    
    Bootstraps your llms.txt with highest-value categories.
    Only approves chunks with at least min_products products.
    """
    result = aeo_service.auto_approve_top_chunks(db, limit=limit, min_products=min_products)
    
    return {
        "status": "completed",
        **result,
        "message": f"Auto-approved {result['approved_count']} chunks. Run /rebuild to regenerate llms.txt."
    }





@router.post("/sync-knowledge-graph")
async def sync_knowledge_graph(db: Session = Depends(get_db)):
    """
    Synchronize the knowledge graph by seeding fault codes AND their solutions.

    This is the recommended way to initialize the GEO Knowledge Graph.
    """
    fc_count = aeo_service.seed_priority_fault_codes(db)
    sol_count = aeo_service.seed_solutions(db)

    return {
        "status": "completed",
        "fault_codes_seeded": fc_count,
        "solutions_seeded": sol_count,
        "message": f"Seeded {fc_count} fault codes and {sol_count} solutions."
    }


@router.post("/refresh-fault-codes")
async def refresh_fault_codes_from_gsc_endpoint(
    days: int = Query(30, ge=1, le=90, description="GSC window in days"),
    min_impressions: int = Query(10, ge=0, description="Drop long-tail codes below this"),
    db: Session = Depends(get_db),
):
    """Refresh FaultCode rows from current GSC search queries (on-demand).

    Also runs automatically every morning at 06:30 America/Mexico_City via
    Celery beat. Use this endpoint when you want to pull a fresh snapshot
    immediately — e.g., after ranking a new cornerstone article.

    Returns a summary: how many codes were created/updated, and the top 10
    by clicks so you can spot which fault codes are currently driving traffic.
    """
    from app.services.google_api_service import GoogleApiService
    service = GoogleApiService()
    return service.refresh_fault_codes_from_gsc(
        db, days=days, min_impressions=min_impressions
    )


@router.get("/solutions")
async def list_solutions(
    fault_code: str = Query(None, description="Filter by fault code (e.g., P0706)"),
    db: Session = Depends(get_db)
):
    """
    List all solutions in the Knowledge Graph.
    """
    solutions = aeo_service.get_solutions(db, fault_code=fault_code)
    return {
        "count": len(solutions),
        "solutions": [
            {
                "fault_code": s.fault_code.code if s.fault_code else "Unknown",
                "title": s.title,
                "description": s.description,
                "recommended_skus": s.recommended_skus or [],
                "collection_url": s.collection_url
            }
            for s in solutions
        ]
    }


# ============ GEO Schema Generation Endpoints ============

@router.get("/schema/faq/{fault_code}")
async def get_faq_schema(
    fault_code: str,
    db: Session = Depends(get_db)
):
    """
    Generate FAQPage JSON-LD schema for a fault code.
    
    Auto-generates FAQ questions from the fault code's knowledge graph data.
    """
    schema = aeo_service.generate_faq_schema(db, fault_code)
    
    if "error" in schema:
        raise HTTPException(status_code=404, detail=schema["error"])
    
    return {
        "fault_code": fault_code,
        "json_ld": schema,
        "validation_status": "valid",
        "usage": "Add this JSON-LD to the <head> of your fault code article page"
    }


@router.get("/schema/howto/{fault_code}")
async def get_howto_schema(
    fault_code: str,
    db: Session = Depends(get_db)
):
    """
    Generate HowTo JSON-LD schema for diagnosing a fault code.
    
    Creates step-by-step diagnostic guide schema for GEO optimization.
    """
    schema = aeo_service.generate_howto_schema(db, fault_code)
    
    if "error" in schema:
        raise HTTPException(status_code=404, detail=schema["error"])
    
    return {
        "fault_code": fault_code,
        "json_ld": schema,
        "validation_status": "valid",
        "usage": "Add this JSON-LD to your diagnostic guide page"
    }


# ============ Shopify Schema Injection Endpoints ============

@router.get("/schema/injection/status")
async def get_schema_injection_status(db: Session = Depends(get_db)):
    """
    Get current status of schema injection across all fault code articles.
    
    Shows which articles have been optimized with structured data.
    """
    from app.services.shopify_schema_service import shopify_schema_service
    
    return shopify_schema_service.get_schema_injection_status(db)


@router.get("/schema/injection/preview")
async def preview_schema_injection(
    limit: int = Query(5, description="Max articles to preview"),
    db: Session = Depends(get_db)
):
    """
    Preview schema injection without making changes.
    
    Use this to see what articles would be updated.
    """
    from app.services.shopify_schema_service import shopify_schema_service
    
    return shopify_schema_service.inject_schemas_to_all_articles(
        db=db,
        dry_run=True,
        limit=limit
    )


@router.post("/schema/injection/execute")
async def execute_schema_injection(
    limit: int = Query(None, description="Max articles to process (None = all)"),
    method: str = Query("metafield", description="Injection method: 'metafield' (safe) or 'html' (legacy)"),
    confirm: bool = Query(False, description="Set to true to actually execute"),
    db: Session = Depends(get_db)
):
    """
    Execute schema injection on Shopify articles.
    
    ⚠️ Metafield method is highly recommended for safety!
    
    Steps:
    1. First call with confirm=false to preview
    2. Review the preview
    3. Call again with confirm=true to apply
    """
    from app.services.shopify_schema_service import shopify_schema_service
    
    if not confirm:
        return {
            "message": "Preview mode - set confirm=true to execute",
            "preview": shopify_schema_service.inject_schemas_to_all_articles(
                db=db,
                method=method,
                dry_run=True,
                limit=limit
            )
        }
    
    result = shopify_schema_service.inject_schemas_to_all_articles(
        db=db,
        method=method,
        dry_run=False,
        limit=limit
    )
    
    return {
        "message": f"Schema injection complete via {method}! Updated {result['success']} articles.",
        "result": result
    }


@router.post("/schema/injection/single/{fault_code}")
async def inject_single_article_schema(
    fault_code: str,
    article_id: int = Query(..., description="Shopify article ID"),
    blog_id: int = Query(..., description="Shopify blog ID"),
    method: str = Query("metafield", description="Injection method: 'metafield' or 'html'"),
    confirm: bool = Query(False, description="Set to true to actually execute"),
    db: Session = Depends(get_db)
):
    """
    Inject schema into a single specific article.
    
    Use this for manual control over individual articles.
    """
    from app.services.shopify_schema_service import shopify_schema_service
    
    result = shopify_schema_service.inject_schema_to_article(
        db=db,
        article_id=article_id,
        blog_id=blog_id,
        fault_code=fault_code,
        method=method,
        dry_run=not confirm
    )
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============ AI Visibility Tracker Endpoints ============

@router.get("/visibility/prompts", response_model=List[PromptPanelItemResponse])
async def list_visibility_prompts(
    active_only: bool = Query(True, description="Only return active prompts"),
    category: str = Query(None, description="Filter by category (fault_code, product, competitor, general)"),
    db: Session = Depends(get_db)
):
    """
    List all prompts in the AI Visibility panel.
    
    Prompts are queries sent to LLMs to check if Example Store is mentioned.
    """
    prompts = ai_visibility_service.get_prompts(db, active_only=active_only, category=category)
    return prompts


@router.post("/visibility/prompts", response_model=PromptPanelItemResponse)
async def add_visibility_prompt(
    request: PromptPanelItemCreate,
    db: Session = Depends(get_db)
):
    """
    Add a new prompt to the visibility panel.
    """
    prompt = ai_visibility_service.add_prompt(
        db=db,
        prompt_text=request.prompt_text,
        category=request.category,
        priority=request.priority,
        linked_fault_code=request.linked_fault_code,
        linked_transmission=request.linked_transmission,
        source=request.source
    )
    return prompt


@router.delete("/visibility/prompts/{prompt_id}")
async def remove_visibility_prompt(
    prompt_id: int,
    db: Session = Depends(get_db)
):
    """
    Remove (deactivate) a prompt from the visibility panel.
    """
    success = ai_visibility_service.remove_prompt(db, prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")
    
    return {"status": "removed", "prompt_id": prompt_id}


@router.post("/visibility/check")
async def run_visibility_check(
    request: VisibilityCheckRequest = None,
    db: Session = Depends(get_db)
):
    """
    Run visibility checks on prompts using specified LLMs.
    
    Queries LLMs with prompts and records whether Example Store is mentioned.
    
    ⚠️ This makes actual API calls to LLM providers - use sparingly!
    """
    if request is None:
        request = VisibilityCheckRequest()
    
    result = await ai_visibility_service.batch_check_visibility(
        db=db,
        prompt_ids=request.prompt_ids,
        provider_names=request.providers,
        limit=request.limit,
        max_concurrent=request.max_concurrent,
        timeout_per_check=request.timeout_per_check
    )
    
    return result


@router.post("/visibility/check/{prompt_id}")
async def check_single_prompt(
    prompt_id: int,
    provider: str = Query("grok", description="LLM provider to use (grok, openai, anthropic)"),
    db: Session = Depends(get_db)
):
    """
    Run visibility check on a single prompt.
    
    Returns the full result including detected mentions.
    """
    try:
        result = await ai_visibility_service.check_visibility_single(
            db=db,
            prompt_id=prompt_id,
            provider_name=provider
        )
        return {
            "prompt_id": prompt_id,
            "provider": provider,
            "brand_mentioned": result.brand_mentioned,
            "url_cited": result.url_cited,
            "competitor_mentioned": result.competitor_mentioned,
            "mentioned_brands": result.mentioned_brands,
            "mentioned_urls": result.mentioned_urls,
            "query_time_ms": result.query_time_ms,
            "error": result.error
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/visibility/results", response_model=List[AIVisibilityResultResponse])
async def get_visibility_results(
    days: int = Query(7, description="Number of days to look back"),
    limit: int = Query(100, description="Max results to return"),
    db: Session = Depends(get_db)
):
    """
    Get recent visibility check results.
    """
    results = ai_visibility_service.get_recent_results(db, days=days, limit=limit)
    return results


@router.get("/visibility/results/prompt/{prompt_id}", response_model=List[AIVisibilityResultResponse])
async def get_prompt_results(
    prompt_id: int,
    limit: int = Query(50, description="Max results to return"),
    db: Session = Depends(get_db)
):
    """
    Get visibility results for a specific prompt.
    """
    results = ai_visibility_service.get_results_by_prompt(db, prompt_id=prompt_id, limit=limit)
    return results


@router.get("/visibility/snapshots", response_model=List[VisibilitySnapshotResponse])
async def get_visibility_snapshots(
    days: int = Query(30, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """
    Get daily visibility snapshots for trend analysis.
    """
    snapshots = ai_visibility_service.get_snapshots(db, days=days)
    return snapshots


@router.post("/visibility/snapshots/create")
async def create_visibility_snapshot(
    db: Session = Depends(get_db)
):
    """
    Create/update the daily visibility snapshot for today.

    Aggregates all check results from today into summary metrics.
    """
    snapshot = ai_visibility_service.create_daily_snapshot(db)

    if not snapshot:
        return {"status": "skipped", "message": "No results to aggregate for today"}

    return {
        "status": "created",
        "snapshot_date": snapshot.snapshot_date,
        "visibility_score": snapshot.visibility_score,
        "share_of_voice": snapshot.share_of_voice,
        "total_checks": snapshot.total_prompts_checked
    }


@router.get("/visibility/competitor-breakdown")
async def get_visibility_competitor_breakdown(
    days: int = Query(30, ge=1, le=365, description="How many days of snapshot history"),
    top_n: int = Query(8, ge=1, le=20, description="Max competitors to include"),
    db: Session = Depends(get_db),
):
    """Relative share-of-voice per named competitor across recent snapshots.

    Returns two views:
      - `current`: most-recent snapshot's per-competitor counts plus Example Store's
        own brand_mentions so the frontend can render a ranked bar.
      - `trend`: per-day series `[{date, example-store, transgo, sonnax, ...}, ...]`
        limited to the top_n competitors by total mentions across the window.
        Lets the dashboard show "Transgo is catching up over time" rather than
        just "a competitor was mentioned once."

    Addresses the audit finding that visibility was being reported in absolute
    terms ("X% mention rate") with no competitor control. Relative positioning
    is the signal that actually informs strategy.
    """
    from app.models.aeo_models import VisibilitySnapshot
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    snapshots = (
        db.query(VisibilitySnapshot)
        .filter(VisibilitySnapshot.snapshot_date >= cutoff)
        .order_by(VisibilitySnapshot.snapshot_date.asc())
        .all()
    )

    if not snapshots:
        return {
            "status": "no_data",
            "message": "No visibility snapshots in window. Run weekly AI visibility check first.",
            "current": None,
            "trend": [],
            "top_competitors": [],
        }

    # Find the top_n competitors across the full window so the trend chart
    # has a stable, meaningful set of series (not 20+ long-tail brands).
    window_totals: Dict[str, int] = {}
    for s in snapshots:
        for brand, count in (s.competitor_breakdown or {}).items():
            window_totals[brand] = window_totals.get(brand, 0) + int(count or 0)
    top_competitors = sorted(window_totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    top_names = [b for b, _ in top_competitors]

    trend = []
    for s in snapshots:
        row = {
            "date": s.snapshot_date.date().isoformat() if s.snapshot_date else None,
            "example-store": s.brand_mentions or 0,
        }
        cb = s.competitor_breakdown or {}
        for name in top_names:
            row[name] = int(cb.get(name, 0) or 0)
        trend.append(row)

    latest = snapshots[-1]
    latest_cb = latest.competitor_breakdown or {}
    current = {
        "snapshot_date": latest.snapshot_date.isoformat() if latest.snapshot_date else None,
        "brand_mentions": latest.brand_mentions or 0,
        "total_prompts_checked": latest.total_prompts_checked or 0,
        "share_of_voice_pct": latest.share_of_voice,
        # Competitor rows sorted descending
        "competitors": [
            {"brand": b, "mentions": int(c or 0)}
            for b, c in sorted(latest_cb.items(), key=lambda kv: kv[1], reverse=True)
        ],
    }

    return {
        "status": "ok",
        "window_days": days,
        "snapshots_in_window": len(snapshots),
        "current": current,
        "trend": trend,
        "top_competitors": [
            {"brand": b, "total_mentions_in_window": c}
            for b, c in top_competitors
        ],
    }


@router.get("/visibility/dashboard", response_model=VisibilityDashboardResponse)
async def get_visibility_dashboard(db: Session = Depends(get_db)):
    """
    Get aggregated dashboard data for AI visibility tracking.
    
    Returns:
    - Current visibility scores
    - 7-day trends
    - Metrics by LLM provider
    - Top performing prompts
    """
    return ai_visibility_service.get_dashboard_data(db)


# ============ GSC Query Import to Prompt Library ============

@router.get("/visibility/prompts/gsc-suggestions")
async def get_gsc_query_suggestions(
    min_impressions: int = Query(50, description="Minimum impressions to include"),
    min_position: float = Query(1.0, description="Minimum position (1 = top)"),
    max_position: float = Query(30.0, description="Maximum position"),
    limit: int = Query(50, description="Maximum queries to return"),
    exclude_existing: bool = Query(True, description="Exclude queries already in library"),
    db: Session = Depends(get_db)
):
    """
    Get GSC query suggestions for importing to prompt library.
    
    Fetches high-value search queries from Google Search Console that could
    be added as visibility tracking prompts.
    
    Filters:
    - High impressions (users are searching for this)
    - Position 1-30 (you have some visibility but room to improve)
    - Not already in prompt library (if exclude_existing=True)
    
    Returns queries with:
    - Query text
    - Impressions, clicks, CTR, position
    - Suggested prompt format
    - Suggested category
    """
    from app.services.google_api_service import GoogleApiService
    from app.models.aeo_models import PromptPanelItem
    
    try:
        google_service = GoogleApiService()
        gsc_data = google_service.get_search_console_data(days=30)
        
        if not gsc_data:
            return {
                "status": "no_data",
                "message": "No GSC data available. Check API credentials.",
                "suggestions": []
            }
        
        # Get existing prompts to exclude
        existing_prompts = set()
        if exclude_existing:
            existing = db.query(PromptPanelItem.prompt_text).filter(
                PromptPanelItem.is_active == True
            ).all()
            existing_prompts = {p.prompt_text.lower()[:50] for p in existing}
        
        suggestions = []
        for query_data in gsc_data:
            query = query_data.get('query', '')
            impressions = query_data.get('impressions', 0)
            position = query_data.get('position', 100)
            clicks = query_data.get('clicks', 0)
            ctr = query_data.get('ctr', 0)
            
            # Apply filters
            if impressions < min_impressions:
                continue
            if position < min_position or position > max_position:
                continue
            if not query or len(query) < 5:
                continue
            
            # Generate suggested prompt
            suggested_prompt = _generate_prompt_from_query(query)
            
            # Check if already exists
            if exclude_existing and suggested_prompt.lower()[:50] in existing_prompts:
                continue
            
            # Detect category
            category = _detect_query_category(query)
            
            # Detect transmission if mentioned
            transmission = _detect_transmission_in_query(query)
            
            suggestions.append({
                "query": query,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr * 100, 2),
                "position": round(position, 1),
                "suggested_prompt": suggested_prompt,
                "suggested_category": category,
                "suggested_transmission": transmission,
                "suggested_priority": _calculate_priority(impressions, position, ctr),
                "opportunity_score": _calculate_opportunity_score(impressions, position, ctr)
            })
        
        # Sort by opportunity score
        suggestions.sort(key=lambda x: x['opportunity_score'], reverse=True)
        
        return {
            "status": "success",
            "total_gsc_queries": len(gsc_data),
            "suggestions_count": len(suggestions[:limit]),
            "suggestions": suggestions[:limit]
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch GSC data: {str(e)}")


@router.post("/visibility/prompts/import-from-gsc")
async def import_gsc_queries_to_library(
    queries: List[str] = Query(..., description="List of queries to import"),
    auto_format: bool = Query(True, description="Auto-format queries as prompts"),
    default_priority: int = Query(60, description="Default priority for imported prompts"),
    db: Session = Depends(get_db)
):
    """
    Import selected GSC queries into the prompt library.
    
    Takes a list of GSC query texts and creates PromptPanelItem entries.
    Optionally formats them as proper prompts (adds "?" and Mexico context).
    """
    from app.models.aeo_models import PromptPanelItem
    
    imported = []
    skipped = []
    
    for query in queries:
        # Check if already exists
        existing = db.query(PromptPanelItem).filter(
            PromptPanelItem.prompt_text.ilike(f"%{query[:30]}%"),
            PromptPanelItem.is_active == True
        ).first()
        
        if existing:
            skipped.append({"query": query, "reason": "Already exists in library"})
            continue
        
        # Format as prompt
        if auto_format:
            prompt_text = _generate_prompt_from_query(query)
        else:
            prompt_text = query
        
        # Detect metadata
        category = _detect_query_category(query)
        transmission = _detect_transmission_in_query(query)
        
        # Create prompt
        prompt = PromptPanelItem(
            prompt_text=prompt_text,
            category=category,
            priority=default_priority,
            linked_transmission=transmission,
            source="gsc_import",
            is_active=True
        )
        db.add(prompt)
        
        imported.append({
            "query": query,
            "prompt_text": prompt_text,
            "category": category,
            "transmission": transmission
        })
    
    db.commit()
    
    return {
        "status": "success",
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped
    }


@router.post("/visibility/prompts/bulk-import-gsc")
async def bulk_import_top_gsc_queries(
    min_impressions: int = Query(100, description="Minimum impressions"),
    max_queries: int = Query(20, description="Maximum queries to import"),
    min_opportunity_score: float = Query(50.0, description="Minimum opportunity score (0-100)"),
    db: Session = Depends(get_db)
):
    """
    Automatically import top GSC queries to prompt library.
    
    Fetches queries with high opportunity scores and imports them
    as prompts. Great for quickly populating your library with
    real user search patterns.
    """
    from app.services.google_api_service import GoogleApiService
    from app.models.aeo_models import PromptPanelItem
    
    try:
        google_service = GoogleApiService()
        gsc_data = google_service.get_search_console_data(days=30)
        
        if not gsc_data:
            return {"status": "no_data", "message": "No GSC data available"}
        
        # Get existing prompts
        existing = db.query(PromptPanelItem.prompt_text).filter(
            PromptPanelItem.is_active == True
        ).all()
        existing_prompts = {p.prompt_text.lower()[:50] for p in existing}
        
        # Score and filter queries
        candidates = []
        for query_data in gsc_data:
            query = query_data.get('query', '')
            impressions = query_data.get('impressions', 0)
            position = query_data.get('position', 100)
            ctr = query_data.get('ctr', 0)
            
            if impressions < min_impressions:
                continue
            if not query or len(query) < 5:
                continue
            
            opportunity_score = _calculate_opportunity_score(impressions, position, ctr)
            if opportunity_score < min_opportunity_score:
                continue
            
            suggested_prompt = _generate_prompt_from_query(query)
            if suggested_prompt.lower()[:50] in existing_prompts:
                continue
            
            candidates.append({
                "query": query,
                "impressions": impressions,
                "position": position,
                "ctr": ctr,
                "opportunity_score": opportunity_score,
                "suggested_prompt": suggested_prompt
            })
        
        # Sort by opportunity and take top N
        candidates.sort(key=lambda x: x['opportunity_score'], reverse=True)
        to_import = candidates[:max_queries]
        
        # Import
        imported = []
        for item in to_import:
            category = _detect_query_category(item['query'])
            transmission = _detect_transmission_in_query(item['query'])
            priority = _calculate_priority(item['impressions'], item['position'], item['ctr'])
            
            prompt = PromptPanelItem(
                prompt_text=item['suggested_prompt'],
                category=category,
                priority=priority,
                linked_transmission=transmission,
                source="gsc_import",
                is_active=True
            )
            db.add(prompt)
            
            imported.append({
                "query": item['query'],
                "prompt_text": item['suggested_prompt'],
                "category": category,
                "priority": priority,
                "opportunity_score": item['opportunity_score']
            })
        
        db.commit()
        
        return {
            "status": "success",
            "total_candidates": len(candidates),
            "imported_count": len(imported),
            "imported": imported
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions for GSC import

def _generate_prompt_from_query(query: str) -> str:
    """Convert a GSC query into a proper visibility prompt."""
    query = query.strip()
    
    # If already a question, just ensure it ends with ?
    if query.lower().startswith(('¿', 'que ', 'qué ', 'como ', 'cómo ', 'donde ', 'dónde ', 'cual ', 'cuál ')):
        if not query.endswith('?'):
            query = query + '?'
        return query
    
    # Convert to question format
    # Common patterns
    if any(kw in query.lower() for kw in ['kit', 'aceite', 'filtro', 'solenoid', 'sensor']):
        return f"¿Dónde comprar {query} en México? ¿Cuál marca es mejor?"
    
    if any(kw in query.lower() for kw in ['precio', 'costo', 'cuanto']):
        return f"¿{query.capitalize()}? ¿Dónde encontrar el mejor precio?"
    
    if any(kw in query.lower() for kw in ['problema', 'falla', 'error', 'código']):
        return f"¿Cómo solucionar {query}? ¿Qué refacción necesito?"
    
    # Default: wrap as question
    return f"¿Dónde comprar {query} en México?"


def _detect_query_category(query: str) -> str:
    """Detect the category for a query."""
    query_lower = query.lower()
    
    if any(kw in query_lower for kw in ['p0', 'p1', 'p2', 'código', 'error', 'falla']):
        return "fault_code"
    
    if any(kw in query_lower for kw in ['vs', 'mejor', 'comparar', 'diferencia']):
        return "competitor"
    
    if any(kw in query_lower for kw in ['kit', 'aceite', 'filtro', 'solenoid', 'sensor', 'bomba']):
        return "product"
    
    return "general"


def _detect_transmission_in_query(query: str) -> Optional[str]:
    """Detect transmission code in query."""
    query_upper = query.upper()
    
    transmissions = [
        "4L60E", "4L65E", "4L80E", "4L85E",
        "6L80", "6L90", "6T70", "6T75",
        "ZF8HP", "ZF9HP", "8HP", "9HP",
        "DQ200", "DQ250", "DQ500",
        "01M", "09G", "09K",
        "A750", "A760", "U660E",
        "JF011E", "JF015E", "JF017E",
        "CVT", "DSG"
    ]
    
    for trans in transmissions:
        if trans in query_upper:
            return trans
    
    return None


def _calculate_priority(impressions: int, position: float, ctr: float) -> int:
    """Calculate prompt priority based on GSC metrics."""
    # Base priority
    priority = 50
    
    # High impressions = high priority
    if impressions > 500:
        priority += 20
    elif impressions > 200:
        priority += 10
    elif impressions > 100:
        priority += 5
    
    # Good position = higher priority
    if position < 5:
        priority += 15
    elif position < 10:
        priority += 10
    elif position < 20:
        priority += 5
    
    # Low CTR with good impressions = opportunity
    if impressions > 100 and ctr < 0.02:
        priority += 10
    
    return min(priority, 95)  # Cap at 95


def _calculate_opportunity_score(impressions: int, position: float, ctr: float) -> float:
    """Calculate opportunity score (0-100) for a query."""
    # High impressions + low CTR + position 5-20 = high opportunity
    score = 0
    
    # Impressions factor (0-40 points)
    if impressions > 1000:
        score += 40
    elif impressions > 500:
        score += 30
    elif impressions > 200:
        score += 20
    elif impressions > 100:
        score += 10
    elif impressions > 50:
        score += 5
    
    # Position factor (0-30 points) - sweet spot is 5-20
    if 5 <= position <= 10:
        score += 30  # Best opportunity
    elif 10 < position <= 20:
        score += 25
    elif 3 <= position < 5:
        score += 20
    elif 20 < position <= 30:
        score += 15
    elif position < 3:
        score += 10  # Already ranking well
    
    # CTR gap factor (0-30 points) - low CTR with good position = opportunity
    expected_ctr = 0.30 if position < 3 else 0.15 if position < 5 else 0.08 if position < 10 else 0.03
    ctr_gap = max(0, expected_ctr - ctr)
    score += min(30, ctr_gap * 300)  # Scale gap to points
    
    return round(score, 1)


# ============ LLM Product Intelligence Endpoints ============

@router.get("/product-intelligence")
async def get_llm_product_intelligence(
    days: int = Query(365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get product intelligence for LLM-attributed sales.
    """
    from app.services.shopify_service import shopify_service
    
    try:
        result = shopify_service.get_llm_product_insights(days=days)
        
        print(f"[API /product-intelligence] Result status: {result.get('status')}")
        print(f"[API /product-intelligence] Products count: {len(result.get('products_from_llm', []))}")
        
        if result.get("status") in ["no_data", "no_products"]:
            return {
                "status": result.get("status", "no_data"),
                "message": result.get("message", "No LLM-attributed orders found"),
                "products_from_llm": [],
                "optimization_opportunities": [],
                "success_patterns": None
            }
        
        return result
    except Exception as e:
        import traceback
        print(f"[API /product-intelligence] ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visibility-correlation", response_model=VisibilitySalesCorrelation)
async def get_visibility_correlation(
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get correlation between AI brand mentions and actual Shopify revenue.

    This feature bridges the gap between:
    1. AI Visibility (how often LLMs mention Example Store for specific topics)
    2. Shopify Sales (how much revenue is actually attributed to those topics)

    Helps identify 'Conversion Gaps' (high visibility, low sales) and
    'Visibility Gaps' (low visibility, high potential sales).
    """
    from app.services.shopify_service import shopify_service

    result = shopify_service.get_visibility_sales_correlation(days=days)
    return result


# ============ Visibility Weekly Trend Endpoint ============

@router.get("/visibility/trend")
async def get_visibility_trend(
    weeks: int = Query(8, description="Number of weeks to look back"),
    db: Session = Depends(get_db)
):
    """
    Get weekly aggregated visibility metrics for trend analysis.

    Aggregates VisibilitySnapshot daily records into per-week averages so the
    frontend can render a line chart showing how brand mention rate, citation
    rate, share-of-voice and competitor mention rate evolve over time.

    Returns list of { week, week_label, brand_mention_pct, citation_pct,
    share_of_voice, competitor_mention_pct, total_checks } sorted oldest first.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    snapshots = (
        db.query(VisibilitySnapshot)
        .filter(VisibilitySnapshot.snapshot_date >= cutoff)
        .order_by(VisibilitySnapshot.snapshot_date)
        .all()
    )

    weeks_data: dict = {}
    for snap in snapshots:
        dt = snap.snapshot_date
        try:
            iso = dt.isocalendar()
            year, week = iso[0], iso[1]
        except Exception:
            continue
        week_key = f"{year}-W{week:02d}"

        if week_key not in weeks_data:
            weeks_data[week_key] = {
                "brand": [], "citation": [], "sov": [], "comp": [],
                "total": 0, "first_date": dt
            }

        weeks_data[week_key]["brand"].append(snap.visibility_score or 0.0)
        weeks_data[week_key]["citation"].append(snap.citation_score or 0.0)
        weeks_data[week_key]["sov"].append(snap.share_of_voice or 0.0)
        total = snap.total_prompts_checked or 0
        comp = snap.competitor_mentions or 0
        weeks_data[week_key]["comp"].append((comp / total * 100) if total > 0 else 0.0)
        weeks_data[week_key]["total"] += total

    result = []
    for week_key in sorted(weeks_data.keys()):
        d = weeks_data[week_key]
        n = len(d["brand"]) or 1

        # Human-readable label: "Feb W2"
        try:
            parts = week_key.split("-W")
            y, w = int(parts[0]), int(parts[1])
            from datetime import date as date_cls
            monday = date_cls.fromisocalendar(y, w, 1)
            month_abbr = monday.strftime("%b")
            # Week-of-month (1-indexed)
            first_monday = date_cls.fromisocalendar(y, date_cls(y, monday.month, 1).isocalendar()[1], 1)
            wom = ((monday - first_monday).days // 7) + 1
            week_label = f"{month_abbr} W{wom}"
        except Exception:
            week_label = week_key

        result.append({
            "week": week_key,
            "week_label": week_label,
            "brand_mention_pct": round(sum(d["brand"]) / n, 1),
            "citation_pct": round(sum(d["citation"]) / n, 1),
            "share_of_voice": round(sum(d["sov"]) / n, 1),
            "competitor_mention_pct": round(sum(d["comp"]) / n, 1),
            "total_checks": d["total"],
        })

    return result


# ============ AEO Events CRUD (Impact Timeline) ============

class AEOEventCreate(BaseModel):
    event_date: str   # ISO 8601, e.g. "2025-02-15"
    event_type: str   # llms_txt_deployed | schema_added | content_updated | keyword_published | other
    title: str
    description: Optional[str] = None


@router.get("/events")
async def list_aeo_events(
    limit: int = Query(50, description="Max events to return"),
    db: Session = Depends(get_db)
):
    """List AEO improvement events for the impact timeline."""
    events = (
        db.query(AEOEvent)
        .order_by(AEOEvent.event_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "event_date": e.event_date.isoformat() if e.event_date else None,
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.post("/events")
async def create_aeo_event(
    payload: AEOEventCreate,
    db: Session = Depends(get_db)
):
    """Record a new AEO improvement event."""
    from datetime import datetime
    try:
        event_dt = datetime.fromisoformat(payload.event_date.replace("Z", "+00:00"))
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid event_date format. Use ISO 8601.")

    event = AEOEvent(
        event_date=event_dt,
        event_type=payload.event_type,
        title=payload.title,
        description=payload.description,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "event_date": event.event_date.isoformat(),
        "event_type": event.event_type,
        "title": event.title,
        "description": event.description,
        "created_at": event.created_at.isoformat(),
    }


@router.delete("/events/{event_id}")
async def delete_aeo_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Delete an AEO event from the timeline."""
    event = db.query(AEOEvent).filter(AEOEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    db.delete(event)
    db.commit()
    return {"status": "deleted", "id": event_id}


# ============ Product Visibility "Why" Analysis ============

@router.get("/product-intelligence/why")
async def get_product_why_analysis(
    product_id: int = Query(None, description="Filter to a specific product (optional)"),
    limit: int = Query(20, description="Max products to return"),
    db: Session = Depends(get_db)
):
    """
    Explain WHY products get recommended by LLMs.

    Queries the ProductVisibilityResult table to compute per-product:
    - visibility_score: % of prompts where the product was mentioned
    - citation_rate: % of mentions that also cite the URL
    - competitor_displacement: % of prompts where a competitor displaced us
    - top_prompt_types: which categories trigger the most mentions
    - sentiment_breakdown: positive / neutral / negative distribution
    - recommendation_strength: strong / moderate / weak breakdown

    Returns empty list when no visibility checks have been run for products yet.
    """
    from app.models.aeo_models import ProductVisibilityResult
    from sqlalchemy import func as sqlfunc, distinct

    try:
        # Base query
        base = db.query(ProductVisibilityResult)
        if product_id:
            base = base.filter(ProductVisibilityResult.product_id == product_id)

        # Get distinct product IDs we have data for
        product_ids = [
            row[0] for row in
            base.with_entities(distinct(ProductVisibilityResult.product_id)).limit(limit).all()
        ]

        if not product_ids:
            return {
                "status": "no_data",
                "message": "No product visibility checks found. Run product visibility checks to populate this analysis.",
                "products": []
            }

        # Bulk-load all visibility rows in one query, then group by product_id
        # (replaces N separate queries inside the loop below).
        all_rows = (
            db.query(ProductVisibilityResult)
            .filter(ProductVisibilityResult.product_id.in_(product_ids))
            .all()
        )
        rows_by_pid: dict = {}
        for r in all_rows:
            rows_by_pid.setdefault(r.product_id, []).append(r)

        results = []
        for pid in product_ids:
            rows = rows_by_pid.get(pid, [])
            if not rows:
                continue

            total = len(rows)
            mentioned = sum(1 for r in rows if r.was_mentioned)
            url_cited = sum(1 for r in rows if r.brand_url_cited)
            comp_rows = [r for r in rows if r.competitors_mentioned and len(r.competitors_mentioned) > 0]

            # Prompt type breakdown
            prompt_types: dict = {}
            for r in rows:
                pt = r.prompt_type or "unknown"
                if pt not in prompt_types:
                    prompt_types[pt] = {"total": 0, "mentioned": 0}
                prompt_types[pt]["total"] += 1
                if r.was_mentioned:
                    prompt_types[pt]["mentioned"] += 1

            top_prompt_types = sorted(
                [
                    {
                        "type": pt,
                        "total": v["total"],
                        "mention_rate": round(v["mentioned"] / v["total"] * 100, 1) if v["total"] else 0,
                    }
                    for pt, v in prompt_types.items()
                ],
                key=lambda x: x["mention_rate"],
                reverse=True,
            )

            # Sentiment breakdown
            sentiment_counts: dict = {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0}
            for r in rows:
                s = r.sentiment or "unknown"
                sentiment_counts[s] = sentiment_counts.get(s, 0) + 1

            # Recommendation strength breakdown
            strength_counts: dict = {"strong": 0, "moderate": 0, "weak": 0, "none": 0}
            for r in rows:
                s = r.recommendation_strength or "none"
                strength_counts[s] = strength_counts.get(s, 0) + 1

            # Top competitors displacing us
            comp_names: dict = {}
            for r in comp_rows:
                for name in (r.competitors_mentioned or []):
                    comp_names[name] = comp_names.get(name, 0) + 1
            top_competitors = sorted(
                [{"name": k, "count": v} for k, v in comp_names.items()],
                key=lambda x: x["count"], reverse=True
            )[:5]

            # LLM provider breakdown
            llm_breakdown: dict = {}
            for r in rows:
                llm = r.llm_provider or "unknown"
                if llm not in llm_breakdown:
                    llm_breakdown[llm] = {"total": 0, "mentioned": 0}
                llm_breakdown[llm]["total"] += 1
                if r.was_mentioned:
                    llm_breakdown[llm]["mentioned"] += 1

            results.append({
                "product_id": pid,
                "total_checks": total,
                "visibility_score": round(mentioned / total * 100, 1) if total else 0,
                "citation_rate": round(url_cited / mentioned * 100, 1) if mentioned else 0,
                "competitor_displacement_pct": round(len(comp_rows) / total * 100, 1) if total else 0,
                "top_prompt_types": top_prompt_types[:5],
                "sentiment_breakdown": sentiment_counts,
                "recommendation_strength": strength_counts,
                "top_competitors": top_competitors,
                "llm_breakdown": [
                    {
                        "llm": k,
                        "total": v["total"],
                        "mention_rate": round(v["mentioned"] / v["total"] * 100, 1) if v["total"] else 0,
                    }
                    for k, v in llm_breakdown.items()
                ],
                "last_checked": max(r.checked_at for r in rows if r.checked_at).isoformat() if any(r.checked_at for r in rows) else None,
            })

        return {
            "status": "ok",
            "total_products_analyzed": len(results),
            "products": results,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Why analysis failed: {str(e)}")


# ============ Article Enrichment ============
# Generates TL;DR + FAQs for a blog article from PAA + GSC + article body,
# then writes back to the three Empire V8 AEO metafields (tldr_summary,
# faqs, last_reviewed_at). See backend/app/services/article_enrichment_service.py.

class ArticleEnrichRequest(BaseModel):
    blog_id: Optional[int] = None
    target_keyword: Optional[str] = None
    dry_run: bool = True
    write_threshold: float = 0.7


class ProductEnrichRequest(BaseModel):
    dry_run: bool = True
    write_threshold: float = 0.7


@router.get("/articles/with-metrics")
async def list_articles_with_metrics(
    blogs_first: int = Query(10, ge=1, le=50),
    articles_per_blog: int = Query(100, ge=1, le=250),
    needs_enrichment_only: bool = Query(False),
):
    """
    Dashboard endpoint — returns every article with its enrichment metafield
    status, GSC + GA4 performance, detected fault codes, and a composite AEO
    score 0-100. Cached at the service layer for 10 minutes.

    Set `needs_enrichment_only=true` to filter out articles that are already
    fully enriched (has tldr_summary + ≥3 FAQs).
    """
    from app.services.article_metrics_service import fetch_article_metrics

    try:
        articles = fetch_article_metrics(
            blogs_first=blogs_first,
            articles_per_blog=articles_per_blog,
        )
        if needs_enrichment_only:
            articles = [a for a in articles if not a["enrichment"]["fully_enriched"]]
        return {
            "count": len(articles),
            "articles": articles,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch article metrics: {str(e)}")


@router.post("/articles/{article_id}/enrich")
async def enrich_article(
    article_id: int,
    payload: ArticleEnrichRequest = ArticleEnrichRequest(),
    db: Session = Depends(get_db),
):
    """
    Run the enrichment pipeline for a single article.

    Pulls article + PAA + GSC + Knowledge Graph facts, calls Grok with strict
    JSON schema, validates, and (when dry_run=false and confidence >= threshold)
    writes three metafields to the Shopify article.

    Default is dry_run=true so you can review output before publishing.
    """
    from app.services.article_enrichment_service import article_enrichment_service

    try:
        result = await article_enrichment_service.enrich_article(
            article_id=article_id,
            blog_id=payload.blog_id,
            target_keyword=payload.target_keyword,
            dry_run=payload.dry_run,
            write_threshold=payload.write_threshold,
            db=db,
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@router.post("/products/{product_id}/enrich-tldr")
async def enrich_product_tldr(
    product_id: str,
    payload: ProductEnrichRequest = ProductEnrichRequest(),
    db: Session = Depends(get_db),
):
    """
    Phase 2.1: generate a citation-friendly TL;DR summary for a product and
    optionally publish it as `custom.product_tldr_summary` on Shopify.

    Pipeline:
      - Reads local Product (title, current_description_html, transmission_codes,
        cached_vehicle_fitments) — leans on the Phase 1.1-1.5 code extraction
        as primary compatibility signal.
      - Calls Grok with strict JSON schema and citability rules (entity in
        first 8 words, ≤320 chars, no scaffolding phrases).
      - Pydantic-validates length + checks for forbidden phrases.
      - When dry_run=false AND confidence >= threshold, writes the metafield.

    Theme's structured-data.liquid emits the metafield as schema.org
    `disambiguatingDescription` in the Product JSON-LD — what LLMs/AI
    Overviews tend to extract over the full HTML description.

    Default dry_run=true so the output can be reviewed before publishing.
    """
    from app.services.product_enrichment_service import product_enrichment_service

    try:
        result = await product_enrichment_service.enrich_product(
            product_id=product_id,
            dry_run=payload.dry_run,
            write_threshold=payload.write_threshold,
            db=db,
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Product enrichment failed: {str(e)}")

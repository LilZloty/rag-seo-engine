"""
Collection Optimizer API Endpoints
Full workflow API for collection optimization
"""

import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.db.session import get_db
from app.services.collection_optimizer_service import CollectionOptimizerService
from app.core.logging import get_logger
from app.core.config import settings
from app.core.rate_limiter import limiter, RATE_SYNC, RATE_ANALYSIS

router = APIRouter()
logger = get_logger(__name__)


# =============================================================================
# DASHBOARD & OVERVIEW
# =============================================================================

@router.get("/dashboard")
async def get_optimizer_dashboard(db: Session = Depends(get_db)):
    """
    Get collection optimizer dashboard overview with GA4 metrics
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    
    # Stats
    total = db.query(CollectionOptimizer).count()
    pending = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_status == "pending"
    ).count()
    analyzed = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_status == "analyzed"
    ).count()
    ready = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_status == "ready"
    ).count()
    published = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_status == "published"
    ).count()
    
    # GA4 Stats
    with_ga4 = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_sessions > 0
    ).count()
    
    total_ga4_conversions = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_conversions > 0
    ).count()
    
    # High priority collections (with GA4 data if available)
    high_priority = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_priority >= 7
    ).order_by(
        CollectionOptimizer.optimization_priority.desc()
    ).limit(5).all()
    
    # Top opportunities (high impressions, low CTR, with GA4 potential)
    opportunities = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.current_impressions > 50000,
        CollectionOptimizer.current_ctr < 1.0
    ).order_by(
        CollectionOptimizer.current_impressions.desc()
    ).limit(5).all()
    
    return {
        "stats": {
            "total_collections": total,
            "pending": pending,
            "analyzed": analyzed,
            "ready": ready,
            "published": published,
            "with_ga4_data": with_ga4,
            "with_conversions": total_ga4_conversions
        },
        "high_priority": [
            {
                "id": c.id,
                "title": c.collection_title,
                "priority": c.optimization_priority,
                "impressions": c.current_impressions,
                "ctr": c.current_ctr,
                "ga4_sessions": c.ga4_sessions,
                "ga4_conversions": c.ga4_conversions,
                "ga4_conversion_rate": f"{c.ga4_conversion_rate:.2f}%" if c.ga4_conversion_rate else None
            }
            for c in high_priority
        ],
        "top_opportunities": [
            {
                "id": c.id,
                "title": c.collection_title,
                "impressions": c.current_impressions,
                "ctr": c.current_ctr,
                "potential_traffic": int(c.current_impressions * (0.02 - c.current_ctr/100)) if c.current_ctr < 2 else 0,
                "ga4_sessions": c.ga4_sessions
            }
            for c in opportunities
        ]
    }


# =============================================================================
# PHASE 1: DISCOVER - Sync Collections
# =============================================================================

@router.post("/sync")
async def sync_collections(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Sync all Shopify collections to the optimizer database
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.sync_collections()
        return {
            "status": "success",
            "message": f"Synced {result['synced']} new collections, updated {result['updated']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Collection sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_id}")
async def get_collection(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single collection by ID with full details.
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    
    collection = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.id == collection_id
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    return {
        "id": collection.id,
        "shopify_id": collection.shopify_collection_id,
        "title": collection.collection_title,
        "handle": collection.collection_handle,
        "category": collection.category,
        "status": collection.optimization_status,
        "priority": collection.optimization_priority,
        "has_content": bool(collection.generated_content),
        
        # GSC
        "impressions": collection.current_impressions or 0,
        "clicks": collection.current_clicks or 0,
        "ctr": collection.current_ctr or 0.0,
        "position": collection.current_position or 0.0,
        "last_analytics_sync": collection.last_analytics_sync,
        
        # GA4
        "ga4_sessions": collection.ga4_sessions or 0,
        "ga4_conversions": collection.ga4_conversions or 0,
        "ga4_conversion_rate": collection.ga4_conversion_rate or 0.0,
        "ga4_revenue": collection.ga4_revenue or 0.0,
        "ga4_ai_referral_sessions": collection.ga4_ai_referral_sessions or 0,
        "ga4_bounce_rate": collection.ga4_bounce_rate or 0.0,
        "ga4_avg_engagement_time": collection.ga4_avg_engagement_time or 0.0,
        "last_ga4_sync": collection.last_ga4_sync,
        
        # Shopify Attribution
        "shopify_attributed_revenue": collection.shopify_attributed_revenue or 0.0,
        "shopify_attributed_orders": collection.shopify_attributed_orders or 0,
        "shopify_llm_revenue": collection.shopify_llm_revenue or 0.0,
        "shopify_llm_orders": collection.shopify_llm_orders or 0,
        "last_shopify_sync": collection.last_shopify_sync,
        
        # DataForSEO
        "dataforseo_primary_keyword": collection.dataforseo_primary_keyword,
        "dataforseo_volume": collection.dataforseo_volume or 0,
        "dataforseo_competition": collection.dataforseo_competition,
        "dataforseo_cpc": collection.dataforseo_cpc or 0.0,
        "dataforseo_top_competitor": collection.dataforseo_top_competitor,
        "dataforseo_serp_features": collection.dataforseo_serp_features or [],
        "dataforseo_people_also_ask": collection.dataforseo_people_also_ask or [],
        "dataforseo_organic_results": collection.dataforseo_organic_results or [],
        "dataforseo_last_sync": collection.dataforseo_last_sync,
        
        # Content
        "generated_content": collection.generated_content,
        "generated_faq": collection.generated_faq,
        "generated_schema": collection.generated_schema,
        "content_generated_at": collection.content_generated_at,
        
        # Timestamps
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
    }


@router.get("/collections")
async def get_collections(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by title"),
    sort_by: Optional[str] = Query("potential", description="Sort by: potential, impressions, clicks, priority, title"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get all collections with their optimization status.
    Sorted by performance potential (impressions * opportunity score) by default.
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    from sqlalchemy import desc

    query = db.query(CollectionOptimizer)

    if status:
        query = query.filter(CollectionOptimizer.optimization_status == status)
    if category:
        query = query.filter(CollectionOptimizer.category == category)
    if search:
        query = query.filter(CollectionOptimizer.collection_title.ilike(f"%{search}%"))

    total = query.count()

    # Apply sorting
    if sort_by == "impressions":
        query = query.order_by(desc(CollectionOptimizer.current_impressions))
    elif sort_by == "clicks":
        query = query.order_by(desc(CollectionOptimizer.current_clicks))
    elif sort_by == "ctr":
        query = query.order_by(desc(CollectionOptimizer.current_ctr))
    elif sort_by == "priority":
        query = query.order_by(desc(CollectionOptimizer.optimization_priority))
    elif sort_by == "title":
        query = query.order_by(CollectionOptimizer.collection_title)
    elif sort_by == "sessions":
        query = query.order_by(desc(CollectionOptimizer.ga4_sessions))
    elif sort_by == "revenue":
        query = query.order_by(desc(CollectionOptimizer.shopify_attributed_revenue))
    elif sort_by == "volume":
        query = query.order_by(desc(CollectionOptimizer.dataforseo_volume))
    elif sort_by == "position":
        query = query.order_by(CollectionOptimizer.current_position)
    elif sort_by == "bounce_rate":
        query = query.order_by(desc(CollectionOptimizer.ga4_bounce_rate))
    else:
        # Default: sort by "potential" - high impressions with low CTR = high opportunity
        # Potential score = impressions * (1 - CTR) * priority
        query = query.order_by(
            desc(
                CollectionOptimizer.current_impressions *
                (1 - func.coalesce(CollectionOptimizer.current_ctr, 0) / 100) *
                func.coalesce(CollectionOptimizer.optimization_priority, 1)
            )
        )

    collections = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "collections": [
            {
                # Identifiers
                "id": c.id,
                "shopify_id": c.shopify_collection_id,
                "title": c.collection_title,
                "handle": c.collection_handle,
                "category": c.category,
                "status": c.optimization_status,
                "priority": c.optimization_priority,
                "has_content": bool(c.generated_content),

                # GSC
                "impressions": c.current_impressions or 0,
                "clicks": c.current_clicks or 0,
                "ctr": c.current_ctr or 0.0,
                "position": c.current_position or 0.0,
                "last_analytics_sync": c.last_analytics_sync,

                # GA4
                "ga4_sessions": c.ga4_sessions or 0,
                "ga4_conversions": c.ga4_conversions or 0,
                "ga4_conversion_rate": c.ga4_conversion_rate or 0.0,
                "ga4_revenue": c.ga4_revenue or 0.0,
                "ga4_ai_referral_sessions": c.ga4_ai_referral_sessions or 0,
                "ga4_bounce_rate": c.ga4_bounce_rate or 0.0,
                "ga4_avg_engagement_time": c.ga4_avg_engagement_time or 0.0,
                "last_ga4_sync": c.last_ga4_sync,

                # Shopify Attribution
                "shopify_attributed_revenue": c.shopify_attributed_revenue or 0.0,
                "shopify_attributed_orders": c.shopify_attributed_orders or 0,
                "shopify_llm_revenue": c.shopify_llm_revenue or 0.0,
                "shopify_llm_orders": c.shopify_llm_orders or 0,
                "last_shopify_sync": c.last_shopify_sync,

                # DataForSEO
                "dataforseo_primary_keyword": c.dataforseo_primary_keyword,
                "dataforseo_volume": c.dataforseo_volume or 0,
                "dataforseo_competition": c.dataforseo_competition,
                "dataforseo_cpc": c.dataforseo_cpc or 0.0,
                "dataforseo_top_competitor": c.dataforseo_top_competitor,
                "dataforseo_serp_features": c.dataforseo_serp_features or [],
                # Limit PAA to 3 items in list view (full data at /collections/{id}/queries)
                "dataforseo_people_also_ask": (c.dataforseo_people_also_ask or [])[:3],
                "dataforseo_organic_results_count": len(c.dataforseo_organic_results or []),
                "dataforseo_last_sync": c.dataforseo_last_sync,
            }
            for c in collections
        ]
    }


# =============================================================================
# PHASE 2: ANALYZE - Search Console Data
# =============================================================================

@router.post("/analyze/{collection_id}")
async def analyze_collection(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze Search Console data for a specific collection
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.analyze_collection_performance(collection_id)
        return {
            "status": "success",
            "message": f"Analysis complete for {result['collection']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-all")
@limiter.limit(RATE_ANALYSIS)
async def analyze_all_collections(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analyze all pending collections
    """
    if settings.USE_CELERY:
        from app.tasks.content_tasks import analyze_all_collections as analyze_task
        task = analyze_task.delay()
        return {"task_id": task.id, "status": "queued"}

    from app.models.collection_optimizer_models import CollectionOptimizer

    service = CollectionOptimizerService(db)
    
    pending = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.optimization_status.in_(["pending", "analyzed"])
    ).all()
    
    results = []
    for collection in pending:
        try:
            result = await service.analyze_collection_performance(collection.id)
            results.append({"id": collection.id, "status": "success", "data": result})
        except Exception as e:
            results.append({"id": collection.id, "status": "error", "error": str(e)})
    
    return {
        "status": "complete",
        "analyzed": len(results),
        "results": results
    }


@router.get("/collections/{collection_id}/queries")
async def get_collection_queries(
    collection_id: int,
    query_type: Optional[str] = Query(None),
    limit: int = Query(20),
    db: Session = Depends(get_db)
):
    """
    Get Search Console queries for a collection
    """
    from app.models.collection_optimizer_models import CollectionSearchQuery
    
    query = db.query(CollectionSearchQuery).filter(
        CollectionSearchQuery.collection_id == collection_id
    )
    
    if query_type:
        query = query.filter(CollectionSearchQuery.query_type == query_type)
    
    queries = query.order_by(
        CollectionSearchQuery.priority_score.desc()
    ).limit(limit).all()
    
    return {
        "collection_id": collection_id,
        "queries": [
            {
                "query": q.query,
                "clicks": q.clicks,
                "impressions": q.impressions,
                "ctr": q.ctr,
                "position": q.position,
                "type": q.query_type,
                "intent": q.intent,
                "priority_score": q.priority_score
            }
            for q in queries
        ]
    }


# =============================================================================
# GA4 ANALYTICS ENDPOINTS
# =============================================================================

@router.post("/ga4/analyze/{collection_id}")
async def analyze_ga4_collection(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze GA4 data for a specific collection
    Fetches engagement metrics, conversions, and AI referral traffic
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.analyze_ga4_performance(collection_id)
        return {
            "status": "success",
            "message": f"GA4 analysis complete for {result.get('collection', 'unknown')}",
            "data": result
        }
    except Exception as e:
        logger.error(f"GA4 analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ga4/analyze-all")
async def analyze_all_ga4_collections(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analyze GA4 data for all analyzed collections
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.analyze_all_ga4()
        return {
            "status": "success",
            "message": f"GA4 analysis complete for {result['analyzed']} collections",
            "data": result
        }
    except Exception as e:
        logger.error(f"GA4 batch analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ga4/opportunities")
async def get_high_opportunity_collections(
    min_sessions: int = Query(50, description="Minimum GA4 sessions"),
    max_conversion_rate: float = Query(2.0, description="Maximum conversion rate %"),
    limit: int = Query(20, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Get collections with high traffic but low conversion rates
    These represent the highest revenue opportunities
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    
    try:
        # Query collections with GA4 data that have high sessions but low conversions
        collections = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.ga4_sessions >= min_sessions,
            CollectionOptimizer.ga4_conversion_rate <= max_conversion_rate
        ).order_by(
            CollectionOptimizer.ga4_sessions.desc()
        ).limit(limit).all()
        
        # Calculate total potential revenue
        # Assumption: If we improve conversion rate to 2%, what's the revenue impact?
        # Using $2000 MXN as average order value
        avg_order_value = 2000
        total_potential_revenue = 0
        
        for c in collections:
            current_revenue = c.ga4_conversions * avg_order_value
            potential_conversions = c.ga4_sessions * 0.02  # 2% target
            potential_revenue = potential_conversions * avg_order_value
            total_potential_revenue += max(0, potential_revenue - current_revenue)
        
        return {
            "collections": [
                {
                    "id": c.id,
                    "title": c.collection_title,
                    "handle": c.collection_handle,
                    "category": c.category,
                    "status": c.optimization_status,
                    "priority": c.optimization_priority,
                    "impressions": c.current_impressions,
                    "clicks": c.current_clicks,
                    "ctr": c.current_ctr,
                    "ga4_sessions": c.ga4_sessions,
                    "ga4_conversions": c.ga4_conversions,
                    "ga4_conversion_rate": c.ga4_conversion_rate,
                    "ga4_revenue": c.ga4_revenue,
                    "potential_revenue_increase": c.ga4_sessions * 0.02 * 2000 - (c.ga4_conversions * 2000)
                }
                for c in collections
            ],
            "total_potential_revenue": total_potential_revenue,
            "count": len(collections),
            "filters": {
                "min_sessions": min_sessions,
                "max_conversion_rate": max_conversion_rate
            }
        }
    except Exception as e:
        logger.error(f"Failed to get high opportunity collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ga4/dashboard")
async def get_ga4_dashboard(
    db: Session = Depends(get_db)
):
    """
    Get GA4 dashboard overview with conversion metrics
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    
    # Collections with GA4 data
    with_ga4 = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_sessions > 0
    ).count()
    
    # Total conversions
    total_conversions = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_conversions > 0
    ).count()
    
    # Top converting collections
    top_converters = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_conversions > 0
    ).order_by(
        CollectionOptimizer.ga4_conversions.desc()
    ).limit(10).all()
    
    # AI referral traffic
    ai_traffic = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.ga4_ai_referral_sessions > 0
    ).all()
    
    total_ai_sessions = sum(c.ga4_ai_referral_sessions for c in ai_traffic)
    
    return {
        "stats": {
            "collections_with_ga4": with_ga4,
            "collections_with_conversions": total_conversions,
            "total_ai_referral_sessions": total_ai_sessions,
            "collections_with_ai_traffic": len(ai_traffic)
        },
        "top_converters": [
            {
                "id": c.id,
                "title": c.collection_title,
                "sessions": c.ga4_sessions,
                "conversions": c.ga4_conversions,
                "conversion_rate": f"{c.ga4_conversion_rate:.2f}%",
                "ai_sessions": c.ga4_ai_referral_sessions
            }
            for c in top_converters
        ]
    }


# =============================================================================
# UNIFIED SEO/AEO/GEO DASHBOARD
# =============================================================================

@router.get("/unified-dashboard")
async def get_unified_dashboard(
    days: int = Query(30, description="Number of days for analytics"),
    db: Session = Depends(get_db)
):
    """
    Get unified dashboard combining SEO, AEO, and GEO metrics
    Covers both products and collections
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    from app.models.product import Product
    from app.models.aeo_models import CacheEntry
    
    try:
        # ==================== SEO METRICS (Products) ====================
        total_products = db.query(Product).count()
        products_needing_seo = db.query(Product).filter(Product.seo_score < 70).count()
        products_optimized = db.query(Product).filter(Product.seo_score >= 70).count()
        avg_seo_score = db.query(Product).filter(Product.seo_score > 0).with_entities(
            func.avg(Product.seo_score)
        ).scalar() or 0
        
        # Top products by sales/revenue
        top_products = db.query(Product).filter(
            Product.total_sold > 0
        ).order_by(
            Product.total_revenue.desc()
        ).limit(5).all()
        
        # ==================== COLLECTION SEO METRICS ====================
        total_collections = db.query(CollectionOptimizer).count()
        collections_analyzed = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status.in_(["analyzed", "ready", "published"])
        ).count()
        collections_optimized = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status == "published"
        ).count()
        
        # Collections with GA4 data
        collections_with_ga4 = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.ga4_sessions > 0
        ).count()
        
        total_ga4_sessions = db.query(CollectionOptimizer).with_entities(
            func.sum(CollectionOptimizer.ga4_sessions)
        ).scalar() or 0
        
        total_ga4_conversions = db.query(CollectionOptimizer).with_entities(
            func.sum(CollectionOptimizer.ga4_conversions)
        ).scalar() or 0
        
        # ==================== AEO METRICS ====================
        # Get LLMS.txt stats from cache
        llms_txt_cache = db.query(CacheEntry).filter(
            CacheEntry.cache_key == "llms_txt:stats"
        ).first()
        
        llms_txt_stats = json.loads(llms_txt_cache.cache_value) if llms_txt_cache else {
            "approved_chunks": 0,
            "total_chunks": 0,
            "token_estimate": 0
        }
        
        # FAQ Schema coverage
        faq_schema_count = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.has_faq_section == True
        ).count()
        
        # ==================== GEO METRICS ====================
        # AI referral traffic
        ai_referral_collections = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.ga4_ai_referral_sessions > 0
        ).all()
        
        total_ai_sessions = sum(c.ga4_ai_referral_sessions for c in ai_referral_collections)
        total_ai_conversions = sum(c.ga4_ai_referral_conversions for c in ai_referral_collections)
        
        # Get visibility data if available
        visibility_cache = db.query(CacheEntry).filter(
            CacheEntry.cache_key.like("visibility:%")
        ).order_by(CacheEntry.cached_at.desc()).first()
        
        import json
        visibility_score = 0
        if visibility_cache:
            try:
                visibility_data = json.loads(visibility_cache.cache_value)
                visibility_score = visibility_data.get("visibility_score", 0)
            except:
                visibility_score = 0
        
        # ==================== HIGH OPPORTUNITY ITEMS ====================
        # Products needing SEO that have sales
        high_value_products_needing_seo = db.query(Product).filter(
            Product.seo_score < 70,
            Product.total_sold > 10
        ).order_by(
            Product.total_revenue.desc()
        ).limit(5).all()
        
        # Collections with high traffic but low conversion
        high_opportunity_collections = db.query(CollectionOptimizer).filter(
            CollectionOptimizer.ga4_sessions >= 50,
            CollectionOptimizer.ga4_conversion_rate < 2
        ).order_by(
            CollectionOptimizer.ga4_sessions.desc()
        ).limit(5).all()
        
        return {
            "overview": {
                "seo_health": {
                    "products": {
                        "total": total_products,
                        "needing_seo": products_needing_seo,
                        "optimized": products_optimized,
                        "avg_score": round(float(avg_seo_score), 1)
                    },
                    "collections": {
                        "total": total_collections,
                        "analyzed": collections_analyzed,
                        "optimized": collections_optimized,
                        "with_ga4": collections_with_ga4
                    }
                },
                "aeo_health": {
                    "llms_txt_coverage": f"{llms_txt_stats.get('approved_chunks', 0)}/{llms_txt_stats.get('total_chunks', 0)}",
                    "faq_schema_coverage": faq_schema_count,
                    "total_collections": total_collections,
                    "coverage_percentage": round((faq_schema_count / total_collections * 100), 1) if total_collections > 0 else 0
                },
                "geo_health": {
                    "ai_referral_sessions": total_ai_sessions,
                    "ai_referral_conversions": total_ai_conversions,
                    "collections_with_ai_traffic": len(ai_referral_collections),
                    "visibility_score": visibility_score
                }
            },
            "performance": {
                "ga4_summary": {
                    "total_sessions": total_ga4_sessions,
                    "total_conversions": total_ga4_conversions,
                    "avg_conversion_rate": round((total_ga4_conversions / total_ga4_sessions * 100), 2) if total_ga4_sessions > 0 else 0
                },
                "top_products": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "sku": p.sku,
                        "seo_score": p.seo_score,
                        "total_sold": p.total_sold,
                        "total_revenue": float(p.total_revenue) if p.total_revenue else 0
                    }
                    for p in top_products
                ],
                "top_collections": [
                    {
                        "id": c.id,
                        "title": c.collection_title,
                        "sessions": c.ga4_sessions,
                        "conversions": c.ga4_conversions,
                        "conversion_rate": round(c.ga4_conversion_rate, 2)
                    }
                    for c in db.query(CollectionOptimizer).filter(
                        CollectionOptimizer.ga4_conversions > 0
                    ).order_by(
                        CollectionOptimizer.ga4_conversions.desc()
                    ).limit(5).all()
                ]
            },
            "opportunities": {
                "high_value_products_needing_seo": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "sku": p.sku,
                        "seo_score": p.seo_score,
                        "total_sold": p.total_sold,
                        "total_revenue": float(p.total_revenue) if p.total_revenue else 0,
                        "potential_impact": "High"
                    }
                    for p in high_value_products_needing_seo
                ],
                "high_traffic_low_conversion_collections": [
                    {
                        "id": c.id,
                        "title": c.collection_title,
                        "sessions": c.ga4_sessions,
                        "conversion_rate": round(c.ga4_conversion_rate, 2),
                        "potential_revenue_increase": c.ga4_sessions * 0.02 * 2000 - (c.ga4_conversions * 2000)
                    }
                    for c in high_opportunity_collections
                ]
            },
            "recommendations": generate_unified_recommendations(
                products_needing_seo,
                collections_optimized,
                faq_schema_count,
                total_collections,
                total_ai_sessions
            )
        }
    except Exception as e:
        logger.error(f"Failed to get unified dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def generate_unified_recommendations(
    products_needing_seo: int,
    collections_optimized: int,
    faq_schema_count: int,
    total_collections: int,
    total_ai_sessions: int
) -> list:
    """Generate actionable recommendations based on metrics"""
    recommendations = []
    
    if products_needing_seo > 50:
        recommendations.append({
            "priority": "high",
            "category": "SEO",
            "title": f"{products_needing_seo} products need SEO optimization",
            "action": "Run batch SEO generation for products with sales history",
            "impact": "High"
        })
    
    if collections_optimized < total_collections * 0.3:
        recommendations.append({
            "priority": "high",
            "category": "SEO",
            "title": "Collection optimization incomplete",
            "action": f"Only {collections_optimized}/{total_collections} collections have optimized content",
            "impact": "High"
        })
    
    if faq_schema_count < total_collections * 0.5:
        recommendations.append({
            "priority": "medium",
            "category": "AEO",
            "title": "Expand FAQ schema coverage",
            "action": f"Add FAQ sections to {total_collections - faq_schema_count} more collections",
            "impact": "Medium"
        })
    
    if total_ai_sessions < 100:
        recommendations.append({
            "priority": "medium",
            "category": "GEO",
            "title": "Increase AI engine visibility",
            "action": "Optimize content for AI citations and create more educational content",
            "impact": "Medium"
        })
    
    return recommendations


# =============================================================================
# PHASE 3: GENERATE - AI Content Generation
# =============================================================================

@router.post("/generate/{collection_id}")
async def generate_content(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate optimized content for a collection using AI
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.generate_collection_content(collection_id)
        return {
            "status": "success",
            "message": f"Content generated for {result['collection']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_id}/preview")
async def preview_content(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Preview generated content before deployment
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    
    collection = db.query(CollectionOptimizer).get(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if not collection.generated_content:
        raise HTTPException(status_code=400, detail="No content generated yet")
    
    return {
        "collection": {
            "id": collection.id,
            "title": collection.collection_title,
            "handle": collection.collection_handle
        },
        "educational_content": collection.generated_content,
        "faq": collection.generated_faq,
        "schema_markup": collection.generated_schema,
        "generated_at": collection.content_generated_at
    }


# =============================================================================
# PHASE 4: DEPLOY - Push to Shopify
# =============================================================================

@router.post("/deploy/{collection_id}")
async def deploy_content(
    collection_id: int,
    dry_run: bool = Query(False, description="Preview without deploying"),
    db: Session = Depends(get_db)
):
    """
    Deploy generated content to Shopify collection metafields
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.deploy_to_shopify(collection_id, dry_run=dry_run)
        return {
            "status": "success",
            "message": f"Deployment {'preview' if dry_run else 'complete'} for {result['collection']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PHASE 5: TRACK - Performance Monitoring
# =============================================================================

@router.post("/track/{collection_id}")
async def track_performance(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Track performance improvements after optimization
    """
    service = CollectionOptimizerService(db)
    
    try:
        result = await service.track_performance(collection_id)
        return {
            "status": "success",
            "message": f"Performance tracked for {result['collection']}",
            "data": result
        }
    except Exception as e:
        logger.error(f"Tracking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_id}/history")
async def get_optimization_history(
    collection_id: int,
    limit: int = Query(20),
    db: Session = Depends(get_db)
):
    """
    Get optimization history for a collection
    """
    from app.models.collection_optimizer_models import CollectionOptimizationHistory
    
    history = db.query(CollectionOptimizationHistory).filter(
        CollectionOptimizationHistory.collection_id == collection_id
    ).order_by(
        CollectionOptimizationHistory.created_at.desc()
    ).limit(limit).all()
    
    return {
        "collection_id": collection_id,
        "history": [
            {
                "action": h.action_type,
                "status": h.action_status,
                "details": h.action_details,
                "created_at": h.created_at,
                "impressions_change": h.impressions_change,
                "clicks_change": h.clicks_change,
                "ctr_change": h.ctr_change
            }
            for h in history
        ]
    }


# =============================================================================
# SHOPIFY ATTRIBUTION
# =============================================================================

@router.post("/shopify-sync-all")
async def shopify_sync_all_collections(
    days: int = Query(30, description="Days of order history to attribute"),
    db: Session = Depends(get_db)
):
    """
    Sync Shopify order revenue attribution to all collections.
    Attributes revenue from orders where the customer's first-touch landing
    page was /collections/{handle}.
    """
    service = CollectionOptimizerService(db)
    try:
        result = await service.sync_shopify_attribution(days=days)
        return {
            "status": "success",
            "message": f"Shopify attribution synced: {result['collections_with_revenue']} collections with revenue",
            "data": result
        }
    except Exception as e:
        logger.error(f"Shopify attribution sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DATAFORSEO
# =============================================================================

@router.post("/dataforseo/{collection_id}")
async def run_dataforseo_for_collection(
    collection_id: int,
    force_refresh: bool = Query(False, description="Force API refresh even if cached data exists"),
    db: Session = Depends(get_db)
):
    """
    Fetch DataForSEO SERP and keyword volume data for a single collection.
    The collection must have been analyzed first (needs GSC queries).

    By default, returns cached data if synced within the last 30 days.
    Use force_refresh=true to bypass cache and hit the API.
    """
    from app.models.collection_optimizer_models import CollectionOptimizer
    from datetime import datetime, timedelta

    collection = db.query(CollectionOptimizer).filter(
        CollectionOptimizer.id == collection_id
    ).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Check if we have recent data (within 30 days) and force_refresh is not set
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    has_recent_data = (
        collection.dataforseo_last_sync and
        collection.dataforseo_last_sync > thirty_days_ago and
        collection.dataforseo_primary_keyword  # Has actual data
    )

    if has_recent_data and not force_refresh:
        logger.info(f"[DataForSEO] Returning cached data for collection {collection_id} (synced {collection.dataforseo_last_sync})")
        return {
            "status": "cached",
            "message": "Returning cached DataForSEO data (use force_refresh=true to refresh)",
            "data": {
                "collection": collection.collection_title,
                "primary_keyword": collection.dataforseo_primary_keyword,
                "volume": collection.dataforseo_volume,
                "competition": collection.dataforseo_competition,
                "cpc": collection.dataforseo_cpc,
                "top_competitor": collection.dataforseo_top_competitor,
                "serp_features": collection.dataforseo_serp_features,
                "paa_count": len(collection.dataforseo_people_also_ask or []),
                "organic_results_count": len(collection.dataforseo_organic_results or []),
                "last_sync": collection.dataforseo_last_sync.isoformat() if collection.dataforseo_last_sync else None,
                "cached": True
            }
        }

    service = CollectionOptimizerService(db)
    try:
        result = await service.run_dataforseo_for_collection(collection_id)
        return {
            "status": "success",
            "message": f"DataForSEO sync complete",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"DataForSEO sync failed for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dataforseo-all")
@limiter.limit(RATE_ANALYSIS)
async def run_dataforseo_all_collections(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Fetch DataForSEO data for all analyzed/ready/published collections.
    Automatically skips collections synced within the last 7 days.
    """
    if settings.USE_CELERY:
        from app.tasks.analytics_tasks import run_dataforseo_batch as batch_task
        task = batch_task.delay()
        return {"task_id": task.id, "status": "queued"}

    service = CollectionOptimizerService(db)
    try:
        result = await service.run_dataforseo_for_all_collections()
        return {
            "status": "success",
            "message": f"DataForSEO batch complete: {result['processed']} processed, {result['skipped_cached']} skipped (cached)",
            "data": result
        }
    except Exception as e:
        logger.error(f"DataForSEO batch sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FULL WORKFLOW
# =============================================================================

@router.post("/workflow/{collection_id}")
async def run_full_workflow(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Run complete workflow: Analyze → Generate → Deploy Preview
    """
    service = CollectionOptimizerService(db)
    
    try:
        results = await service.run_full_workflow(collection_id)
        return {
            "status": "success",
            "message": "Full workflow complete",
            "phases": results
        }
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow-batch")
async def run_batch_workflow(
    collection_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Run workflow for multiple collections
    """
    service = CollectionOptimizerService(db)
    
    results = []
    for collection_id in collection_ids:
        try:
            result = await service.run_full_workflow(collection_id)
            results.append({"id": collection_id, "status": "success", "data": result})
        except Exception as e:
            results.append({"id": collection_id, "status": "error", "error": str(e)})
    
    return {
        "status": "complete",
        "processed": len(results),
        "results": results
    }

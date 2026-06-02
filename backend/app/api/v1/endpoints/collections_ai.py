"""
Collections AI API Endpoints
==============================

Multi-agent powered endpoints for collection analysis, smart recommendations,
cannibalization detection, content drafts, snapshots, and intelligence reports.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from app.db.session import get_db
from app.models.collection_optimizer_models import CollectionOptimizer
from app.models.collection_intelligence_models import (
    CollectionContentDraft, CollectionAnalyticsSnapshot, CollectionCannibalizationResult
)
from app.services.collection_cannibalization_guard import (
    CollectionCannibalizationGuard,
    CannibalizationCheckResult,
)
from app.services.collection_smart_recommendations import (
    CollectionSmartRecommendationsService,
    CollectionRecommendationsResponse,
)
from app.services.smart_recommendations import (
    RecommendationCategory,
    RecommendationFilters,
)

logger = logging.getLogger("collections_ai_api")

router = APIRouter(prefix="/collections-ai", tags=["Collections AI"])


# ============================================================================
# Request Models
# ============================================================================

class BatchCannibalizationRequest(BaseModel):
    collection_ids: List[int]


class BatchRecommendationsRequest(BaseModel):
    collection_ids: List[int]
    multi_agent: bool = False


class ApproveDraftRequest(BaseModel):
    deploy_to_shopify: bool = False


# ============================================================================
# CANNIBALIZATION CHECK ENDPOINTS
# ============================================================================

@router.get("/cannibalization-check/{collection_id}")
async def check_cannibalization(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Run cannibalization analysis for a collection.

    Checks if the collection's target keywords conflict with existing
    blog articles or product pages. Returns safe/blocked/warning keywords
    with recommendations.
    """
    try:
        guard = CollectionCannibalizationGuard(db)
        result = await guard.check_collection(collection_id)
        return {
            "status": "success",
            "data": result.model_dump()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Cannibalization check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cannibalization-check/batch")
async def batch_cannibalization_check(
    request: BatchCannibalizationRequest,
    db: Session = Depends(get_db)
):
    """Run cannibalization check for multiple collections."""
    guard = CollectionCannibalizationGuard(db)
    results = await guard.check_batch(request.collection_ids)
    return {
        "status": "success",
        "total": len(results),
        "data": {
            str(cid): result.model_dump()
            for cid, result in results.items()
        }
    }


@router.get("/cannibalization-check/{collection_id}/gaps")
async def get_transactional_gaps(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Find transactional keyword gaps — keywords the collection SHOULD rank for
    but nobody on the site currently does. These are the safest to target.
    """
    guard = CollectionCannibalizationGuard(db)
    gaps = guard.get_transactional_gap_keywords(collection_id)
    return {
        "status": "success",
        "collection_id": collection_id,
        "gaps": gaps,
        "total": len(gaps)
    }


# ============================================================================
# SMART RECOMMENDATIONS ENDPOINTS
# ============================================================================

@router.post("/recommendations/{collection_id}")
async def get_collection_recommendations(
    collection_id: int,
    multi_agent: bool = Query(default=False),
    min_confidence: int = Query(default=60, ge=0, le=100),
    categories: Optional[str] = Query(default=None, description="Comma-separated: seo,aeo,geo,conversion"),
    max_results: int = Query(default=10, ge=1, le=50),
    sort_by: str = Query(default="impact", pattern="^(impact|confidence|effort)$"),
    db: Session = Depends(get_db)
):
    """
    Generate smart, cannibalization-aware recommendations for a collection.

    Uses multi-agent consensus (Harper/Benjamin/Lucas/Captain) when enabled.
    All recommendations respect the cannibalization guard.
    """
    # Parse categories
    cat_list = [RecommendationCategory.SEO, RecommendationCategory.AEO,
                RecommendationCategory.GEO, RecommendationCategory.CONVERSION]
    if categories:
        cat_list = [RecommendationCategory(c.strip()) for c in categories.split(",")]

    filters = RecommendationFilters(
        min_confidence=min_confidence,
        categories=cat_list,
        max_results=max_results,
        sort_by=sort_by
    )

    try:
        service = CollectionSmartRecommendationsService(db)
        result = await service.get_collection_recommendations(
            collection_id=collection_id,
            filters=filters,
            multi_agent=multi_agent
        )
        return {
            "status": "success",
            "data": result.model_dump()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Collection recommendations failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/recommendations")
async def batch_recommendations(
    request: BatchRecommendationsRequest,
    db: Session = Depends(get_db)
):
    """Generate recommendations for multiple collections."""
    service = CollectionSmartRecommendationsService(db)
    results = await service.get_batch_recommendations(
        collection_ids=request.collection_ids,
        multi_agent=request.multi_agent
    )
    return {
        "status": "success",
        "total": len(results),
        "data": {
            str(cid): result.model_dump()
            for cid, result in results.items()
        }
    }


# ============================================================================
# DATA SYNC
# ============================================================================

@router.post("/sync-all/{collection_id}")
async def sync_all_data_sources(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """
    Sync all 4 data sources (GSC, GA4, Shopify, DataForSEO) for a collection.
    Run this before generating recommendations or intelligence reports to
    ensure all data is fresh.
    """
    from app.services.collection_optimizer_service import CollectionOptimizerService

    try:
        service = CollectionOptimizerService(db)
        result = await service.sync_all_data_sources(collection_id)
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Sync all data sources failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-all-batch")
async def sync_all_batch(
    collection_ids: List[int] = Body(...),
    db: Session = Depends(get_db)
):
    """Sync all data sources for multiple collections."""
    from app.services.collection_optimizer_service import CollectionOptimizerService

    service = CollectionOptimizerService(db)
    results = {}
    for cid in collection_ids:
        try:
            results[str(cid)] = await service.sync_all_data_sources(cid)
        except Exception as e:
            results[str(cid)] = {"status": "failed", "error": str(e)}

    successful = sum(1 for r in results.values() if r.get("summary", {}).get("failed", 4) == 0)
    return {
        "status": "success",
        "total": len(collection_ids),
        "fully_synced": successful,
        "results": results
    }


# ============================================================================
# OPPORTUNITY DISCOVERY
# ============================================================================

@router.get("/discover-opportunities")
async def discover_opportunities(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Find collections with the highest safe optimization potential.
    Filters out collections with high cannibalization risk.
    """
    service = CollectionSmartRecommendationsService(db)
    opportunities = await service.discover_opportunities(limit=limit)
    return {
        "status": "success",
        "total": len(opportunities),
        "data": opportunities
    }


# ============================================================================
# CONTENT GENERATION + DRAFTS
# ============================================================================

@router.post("/generate-content/{collection_id}")
async def generate_content_with_guard(
    collection_id: int,
    skip_cannibalization_check: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Generate collection content with cannibalization guard.
    Creates a CollectionContentDraft for review before deployment.

    If cannibalization risk is too high (blocked), generation is prevented
    and a detailed report is returned instead.
    """
    from app.services.collection_optimizer_service import CollectionOptimizerService

    try:
        service = CollectionOptimizerService(db)
        result = await service.generate_collection_content(
            collection_id=collection_id,
            skip_cannibalization_check=skip_cannibalization_check
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{collection_id}")
async def list_content_drafts(
    collection_id: int,
    status: Optional[str] = Query(default=None, description="Filter by: draft, approved, deployed, archived"),
    db: Session = Depends(get_db)
):
    """List all content drafts for a collection."""
    query = db.query(CollectionContentDraft).filter(
        CollectionContentDraft.collection_id == collection_id
    )
    if status:
        query = query.filter(CollectionContentDraft.draft_status == status)

    drafts = query.order_by(CollectionContentDraft.version.desc()).all()

    return {
        "status": "success",
        "collection_id": collection_id,
        "total": len(drafts),
        "data": [
            {
                "id": d.id,
                "version": d.version,
                "draft_status": d.draft_status,
                "educational_content_preview": (d.educational_content or "")[:300],
                "faq_count": len(d.faq_content) if d.faq_content else 0,
                "has_schema": bool(d.schema_markup),
                "meta_title": d.meta_title,
                "generation_provider": d.generation_provider,
                "cannibalization_status": (d.cannibalization_check or {}).get("status", "unknown"),
                "risk_score": (d.cannibalization_check or {}).get("risk_score", 0),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in drafts
        ]
    }


@router.get("/drafts/{collection_id}/{draft_id}")
async def get_draft_detail(
    collection_id: int,
    draft_id: str,
    db: Session = Depends(get_db)
):
    """Get full content draft for review."""
    draft = db.query(CollectionContentDraft).filter(
        CollectionContentDraft.id == draft_id,
        CollectionContentDraft.collection_id == collection_id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "status": "success",
        "data": {
            "id": draft.id,
            "collection_id": draft.collection_id,
            "version": draft.version,
            "draft_status": draft.draft_status,
            "educational_content": draft.educational_content,
            "faq_content": draft.faq_content,
            "schema_markup": draft.schema_markup,
            "meta_title": draft.meta_title,
            "meta_description": draft.meta_description,
            "cannibalization_check": draft.cannibalization_check,
            "safe_keywords_used": draft.safe_keywords_used,
            "blocked_keywords_avoided": draft.blocked_keywords_avoided,
            "generation_provider": draft.generation_provider,
            "multi_agent": draft.multi_agent,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }
    }


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    db: Session = Depends(get_db)
):
    """
    Approve a content draft. Copies draft content to the collection's
    generated_content fields and sets status to 'ready'.
    """
    draft = db.query(CollectionContentDraft).filter(
        CollectionContentDraft.id == draft_id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    collection = db.query(CollectionOptimizer).get(draft.collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Update draft status
    draft.draft_status = "approved"
    draft.updated_at = datetime.utcnow()

    # Archive other drafts for this collection
    other_drafts = db.query(CollectionContentDraft).filter(
        CollectionContentDraft.collection_id == draft.collection_id,
        CollectionContentDraft.id != draft_id,
        CollectionContentDraft.draft_status == "draft"
    ).all()
    for d in other_drafts:
        d.draft_status = "archived"

    # Copy approved content to collection
    collection.generated_content = draft.educational_content
    collection.generated_faq = draft.faq_content
    collection.generated_schema = draft.schema_markup
    collection.content_generated_at = datetime.utcnow()
    collection.optimization_status = "ready"

    db.commit()

    return {
        "status": "success",
        "message": f"Draft v{draft.version} approved for '{collection.collection_title}'",
        "collection_status": "ready"
    }


# ============================================================================
# INTELLIGENCE REPORTS
# ============================================================================

@router.get("/intelligence/overview")
async def get_collections_health_overview(
    db: Session = Depends(get_db)
):
    """Get store-wide collection health overview."""
    from app.services.collection_intelligence_service import CollectionIntelligenceService

    try:
        service = CollectionIntelligenceService(db)
        health = await service.get_store_collection_health()
        return {"status": "success", "data": health}
    except Exception as e:
        logger.error(f"Collection health overview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intelligence/{collection_id}")
async def get_collection_intelligence(
    collection_id: int,
    db: Session = Depends(get_db)
):
    """Get intelligence report for a single collection."""
    from app.services.collection_intelligence_service import CollectionIntelligenceService

    try:
        service = CollectionIntelligenceService(db)
        report = await service.generate_collection_report(collection_id)
        return {"status": "success", "data": report}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Intelligence report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANALYTICS SNAPSHOTS
# ============================================================================

@router.post("/snapshots/create")
async def create_collection_snapshots(
    collection_ids: Optional[List[int]] = Body(default=None),
    db: Session = Depends(get_db)
):
    """Create daily analytics snapshots for collections."""
    from app.services.collection_snapshot_service import create_collection_daily_snapshot

    try:
        result = create_collection_daily_snapshot(db, collection_ids)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots/{collection_id}")
async def get_collection_trends(
    collection_id: int,
    days: int = Query(default=30, ge=7, le=180),
    db: Session = Depends(get_db)
):
    """Get trend data for a collection with sparkline-ready points."""
    from app.services.collection_snapshot_service import get_collection_trends

    try:
        trends = get_collection_trends(db, collection_id, days)
        return {"status": "success", "collection_id": collection_id, "days": days, **trends}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Trend retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
SERP cluster sync endpoints.

POST /api/v1/serp/sync           Run sync (default: all 5 layers, ~305 keywords)
POST /api/v1/serp/preview        Show keywords that would be synced (no API calls)
GET  /api/v1/serp/status         Cache inventory + age
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.serp_cluster_sync_service import SerpClusterSyncService

router = APIRouter()


class SyncRequest(BaseModel):
    layers: Optional[List[int]] = Field(
        default=None,
        description="Subset of [1, 2, 3, 4, 5]. Null/omit = all layers.",
    )
    force_refresh: bool = Field(
        default=False,
        description="If true, invalidate existing cache entries before fetching.",
    )
    max_concurrent: int = Field(default=5, ge=1, le=20)


@router.post("/sync")
async def sync_serp_clusters(
    request: Optional[SyncRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Run the catalog-wide SERP sync. Cache hits are free; only misses
    call DataForSEO. With all 5 layers + cache empty, expect ~305 API
    calls (~$0.02 on the async tier).
    """
    req = request or SyncRequest()
    service = SerpClusterSyncService(db)
    result = await service.sync(
        layers=req.layers,
        force_refresh=req.force_refresh,
        max_concurrent=req.max_concurrent,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


@router.post("/preview")
def preview_keywords(
    request: Optional[SyncRequest] = None,
    db: Session = Depends(get_db),
):
    """Return the keyword list per layer without making any API calls."""
    req = request or SyncRequest()
    service = SerpClusterSyncService(db)
    keywords = service.generate_keywords(req.layers)
    return {
        "total_keywords": sum(len(v) for v in keywords.values()),
        "per_layer": {
            l: {"count": len(kws), "sample": kws[:5], "all": kws}
            for l, kws in keywords.items()
        },
    }


@router.get("/status")
def serp_cache_status(db: Session = Depends(get_db)):
    """Cache inventory: total cached SERPs, fresh count, oldest/newest."""
    row = db.execute(text("""
        SELECT
          COUNT(*) AS total,
          MIN(cached_at) AS oldest,
          MAX(cached_at) AS newest,
          COUNT(*) FILTER (
            WHERE expires_at IS NULL OR expires_at > NOW()
          ) AS fresh
        FROM cache_entries
        WHERE cache_key LIKE 'dataforseo_serp:%'
    """)).fetchone()
    return {
        "total_cached_serps": row[0],
        "fresh_cached_serps": row[3],
        "oldest_cached_at": row[1].isoformat() if row[1] else None,
        "newest_cached_at": row[2].isoformat() if row[2] else None,
    }

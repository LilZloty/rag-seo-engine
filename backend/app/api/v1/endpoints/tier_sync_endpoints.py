"""
Tier Tag Sync API Endpoints
============================
Endpoints for managing B2B tier tag synchronization.
"""

from fastapi import APIRouter, Query
from app.services.tier_tag_sync_service import tier_sync_service

router = APIRouter()


@router.post("/tier-sync/sync")
async def sync_tier_tags(dry_run: bool = Query(False, description="If true, preview changes without applying them")):
    """
    Run tier tag sync for all B2B customer segments.
    
    - **dry_run=true**: Preview what would change (no actual modifications)
    - **dry_run=false**: Apply tier tags (add correct tag, remove conflicting ones)
    
    Priority: Platino > Oro > Plata > Bronce
    """
    result = tier_sync_service.sync_tier_tags(dry_run=dry_run)
    return result.to_dict()


@router.get("/tier-sync/preview")
async def preview_tier_status():
    """
    Get a detailed preview of all tier segments and tag status.
    
    Shows:
    - Member count per tier segment
    - How many have the correct tag
    - How many are missing their tag
    - How many have wrong tier tags
    - Full member list with tag details
    """
    return tier_sync_service.get_preview()


@router.get("/tier-sync/status")
async def get_sync_status():
    """
    Get the result of the last sync operation.
    Returns null if no sync has been run in this session.
    """
    result = tier_sync_service.get_last_sync_status()
    if result:
        return result
    return {
        "message": "No sync has been run yet in this session",
        "last_sync": None
    }

"""
Sucursales — In-Store Sales Endpoints
=====================================

Exposes the TopProducts feed from the 4 Example Store physical-store nodes
(m107/m207/m407/m507.internal.example) to the frontend. Snapshot persisted
via Redis cache (24h TTL); manual refresh is the primary refresh path.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.rate_limiter import RATE_GENERAL, RATE_SYNC, limiter
from app.db.session import get_db
from app.services.sucursales_sales_service import (
    SUCURSALES,
    get_last_snapshot,
    refresh_snapshot,
)

router = APIRouter()


@router.get("/sucursales/top-products")
@limiter.limit(RATE_GENERAL)
async def read_top_products(request: Request):
    """Return the last in-memory snapshot, or an empty shell if none fetched yet."""
    snapshot = get_last_snapshot()
    if snapshot is None:
        return {
            "fetched_at": None,
            "snapshot": None,
            "message": "No snapshot yet — click Refresh to fetch from the 4 sucursales.",
            "sucursales_configured": [
                {"name": node.name, "host": node.host} for node in SUCURSALES
            ],
        }
    return {
        "fetched_at": snapshot["fetched_at"],
        "snapshot": snapshot,
        "message": None,
        "sucursales_configured": [
            {"name": node.name, "host": node.host} for node in SUCURSALES
        ],
    }


@router.post("/sucursales/refresh")
@limiter.limit(RATE_SYNC)
async def refresh(request: Request, db: Session = Depends(get_db)):
    """Hit all 4 sucursal nodes in parallel and store the result in cache."""
    snapshot = await refresh_snapshot(db)
    return {
        "fetched_at": snapshot["fetched_at"],
        "snapshot": snapshot,
        "message": None,
        "sucursales_configured": [
            {"name": node.name, "host": node.host} for node in SUCURSALES
        ],
    }


@router.get("/sucursales/transmission/{code}/products")
@limiter.limit(RATE_GENERAL)
async def transmission_products(request: Request, code: str):
    """Return all products (matched + unmatched) for a transmission code.

    Reads from the cached snapshot — no external calls needed.
    """
    snapshot = get_last_snapshot()
    if not snapshot:
        raise HTTPException(404, "No snapshot cached — click Refresh first.")

    code_upper = code.upper()
    matched: list[dict] = []
    unmatched: list[dict] = []
    seen_skus: set[str] = set()

    for suc in snapshot.get("sucursales", []):
        for item in suc.get("items", []):
            if item["sku"] in seen_skus:
                continue
            detail = item.get("internal_details") or {}
            trans_names = {
                t.get("name", "").upper()
                for t in (detail.get("transmissions") or [])
            }
            other_codes = set()
            for t in detail.get("transmissions") or []:
                for oc in t.get("otherCodes") or []:
                    other_codes.add(oc.upper())

            if code_upper not in trans_names and code_upper not in other_codes:
                continue

            seen_skus.add(item["sku"])
            entry = {
                "sku": item["sku"],
                "in_store_qty": item["quantity"],
                "sucursal": suc["name"],
                "title": (detail.get("title") or (item.get("product") or {}).get("title") or item["sku"]),
                "internal_details": detail or None,
            }
            if item.get("matched") and item.get("product"):
                entry["shopify_product"] = item["product"]
                matched.append(entry)
            else:
                unmatched.append(entry)

    # Aggregate in-store qty across sucursales for items appearing in multiple
    qty_by_sku: dict[str, int] = {}
    for suc in snapshot.get("sucursales", []):
        for item in suc.get("items", []):
            if item["sku"] in seen_skus:
                qty_by_sku[item["sku"]] = qty_by_sku.get(item["sku"], 0) + item["quantity"]
    for entry in matched + unmatched:
        entry["total_in_store_qty"] = qty_by_sku.get(entry["sku"], entry["in_store_qty"])

    matched.sort(key=lambda x: x["total_in_store_qty"], reverse=True)
    unmatched.sort(key=lambda x: x["total_in_store_qty"], reverse=True)

    return {
        "transmission_code": code,
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "matched": matched,
        "unmatched": unmatched,
    }

"""
Inventory Intelligence API Endpoints
Provides inventory tracking, stock health, demand analysis, and alert management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db
from app.services.inventory_service import InventoryService
from app.services.stock_health_scorer import StockHealthScorer

router = APIRouter(prefix="/inventory", tags=["Inventory Intelligence"])


# ============================================================================
# DASHBOARD & OVERVIEW
# ============================================================================

@router.get("/dashboard")
async def get_inventory_dashboard(db: Session = Depends(get_db)):
    """
    Full inventory overview: totals, in-stock rate, OOS count, alerts, restocks.
    Cached for 5 minutes.
    """
    service = InventoryService(db)
    return service.get_inventory_dashboard()


@router.get("/health-score")
async def get_health_score(db: Session = Depends(get_db)):
    """
    Store-level inventory health score (0-100) with breakdown:
    - In-Stock Rate (30%)
    - Stockout Frequency (20%)
    - Supply Coverage (20%)
    - Dead Stock Ratio (15%)
    - Velocity Alignment (15%)
    """
    scorer = StockHealthScorer(db)
    return scorer.calculate()


# ============================================================================
# PRODUCT INVENTORY DATA
# ============================================================================

@router.get("/products")
async def get_inventory_products(
    status: Optional[str] = Query(None, description="Filter: in_stock, out_of_stock, low_stock"),
    sort_by: str = Query("demand_score", description="Sort: demand_score, velocity, days_of_supply, quantity, urgency, title, sku, price_asc, price_desc"),
    search: Optional[str] = Query(None, description="Search by title, SKU, handle, or product type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """Get products with inventory data, with server-side pagination, filtering, and search."""
    service = InventoryService(db)
    return service.get_products_paginated(
        status=status, sort_by=sort_by, search=search,
        page=page, page_size=page_size,
    )


@router.get("/out-of-stock")
async def get_out_of_stock(db: Session = Depends(get_db)):
    """OOS products ranked by demand score (highest demand first)."""
    service = InventoryService(db)
    return service.get_products_by_status(status="out_of_stock", sort_by="demand_score")


@router.get("/low-stock")
async def get_low_stock(db: Session = Depends(get_db)):
    """Products below their individual low_stock_threshold."""
    service = InventoryService(db)
    return service.get_products_by_status(status="low_stock", sort_by="quantity")


@router.get("/dead-stock")
async def get_dead_stock(
    no_sales_days: int = Query(90, description="No sales in N days (30, 90, or 365)"),
    tier: Optional[str] = Query(None, description="Filter by tier: slow, stale, dead, obsolete"),
    db: Session = Depends(get_db),
):
    """
    Products with stock but no sales — candidates for discounting or bundling.

    Tiers (granular sub-classification):
      - slow     : Has 30d sales but velocity < 0.05/day (~1.5 units/month)
      - stale    : 0 sales in 30d, but had sales in 31-90d
      - dead     : 0 sales in 90d, but had sales in 91-365d
      - obsolete : 0 sales in 365d (zombie inventory)

    If tier is provided, no_sales_days is ignored.
    """
    service = InventoryService(db)
    return service.get_dead_stock(no_sales_days=no_sales_days, tier=tier)


@router.post("/recompute-health")
async def recompute_inventory_health(db: Session = Depends(get_db)):
    """
    Recompute stock_health, dead_stock_tier, velocity, demand, and urgency for every product
    using the existing sold_30d/90d/365d data. Does NOT call Shopify.

    Use this after the classification logic changes to refresh the dashboard without
    a full Shopify re-sync.
    """
    service = InventoryService(db)
    return service.recompute_inventory_health()


@router.get("/stockout-risk")
async def get_stockout_risk(
    days: int = Query(7, description="Will sell out within N days"),
    db: Session = Depends(get_db),
):
    """Products likely to sell out within N days based on current velocity."""
    service = InventoryService(db)
    return service.get_stockout_risk_products(days=days)


@router.get("/restock-priority")
async def get_restock_priority(db: Session = Depends(get_db)):
    """
    What to restock first — OOS products ranked by demand score.
    Demand score factors: subscribers (40%), velocity (25%), revenue (20%), traffic (15%).
    """
    service = InventoryService(db)
    return service.get_restock_priority()


@router.get("/velocity")
async def get_velocity_report(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Sales velocity per product — fastest movers first."""
    service = InventoryService(db)
    return service.get_products_by_status(sort_by="velocity", limit=limit)


@router.get("/snapshots/{product_id}")
async def get_product_snapshots(
    product_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Historical inventory snapshots for a specific product."""
    service = InventoryService(db)
    snapshots = service.get_product_snapshots(product_id, days=days)
    if not snapshots:
        return {"product_id": product_id, "snapshots": [], "message": "No snapshot data yet"}
    return {"product_id": product_id, "snapshots": snapshots}


# ============================================================================
# ACTION CENTER
# ============================================================================

@router.get("/action-center")
async def get_action_center(db: Session = Depends(get_db)):
    """
    Action Center: products grouped by required action.
    Returns: restock_now, order_soon, slow_movers, star_products with counts.
    Cached for 5 minutes.
    """
    service = InventoryService(db)
    return service.get_action_center()


@router.get("/revenue-at-risk")
async def get_revenue_at_risk(db: Session = Depends(get_db)):
    """Total estimated revenue being lost from all OOS products."""
    service = InventoryService(db)
    return service.get_revenue_at_risk()


# ============================================================================
# ANALYTICS (server-side computed for full catalog)
# ============================================================================

@router.get("/analytics/fastest-movers")
async def get_fastest_movers(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Top products by velocity across ALL products."""
    service = InventoryService(db)
    return service.get_fastest_movers(limit=limit)


@router.get("/analytics/stockout-risk")
async def get_stockout_risk_timeline(db: Session = Depends(get_db)):
    """Products at risk of stockout by time horizon, computed across full catalog."""
    service = InventoryService(db)
    return service.get_stockout_risk_timeline()


# ============================================================================
# WAITLIST (Back-in-Stock Subscribers)
# ============================================================================

@router.get("/waitlist")
async def get_waitlist_products(
    sort_by: str = Query("subscribers", description="Sort: subscribers, demand, revenue_lost"),
    db: Session = Depends(get_db),
):
    """Products with active back-in-stock notification subscribers (AMP by Aisle)."""
    service = InventoryService(db)
    return service.get_waitlist_products(sort_by=sort_by)


@router.get("/waitlist/summary")
async def get_waitlist_summary(db: Session = Depends(get_db)):
    """Waitlist overview: total subscribers, OOS with subs, potential revenue."""
    service = InventoryService(db)
    return service.get_waitlist_summary()


@router.post("/waitlist/import")
async def import_subscriber_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Import subscriber counts from AMP by Aisle CSV export.
    Expected AMP columns: SKU, Product ID, Variant ID, Description, Unsent, Sent, Total, ...
    Also supports generic CSVs with sku/shopify_id/handle + subscriber_count/Total columns.
    """
    import csv
    import io

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))

    data = []
    for row in reader:
        item = {}

        # --- SKU ---
        for key in ["SKU", "sku", "Sku"]:
            if key in row and row[key] and row[key].strip():
                item["sku"] = row[key].strip()
                break

        # --- Shopify Product ID (AMP exports as scientific notation e.g. 6.76456E+12) ---
        for key in ["Product ID", "shopify_id", "product_id", "Shopify ID"]:
            if key in row and row[key] and row[key].strip():
                raw = row[key].strip()
                try:
                    # Handle scientific notation: 6.76456E+12 -> 6764560000000 -> "6764560000000"
                    numeric = int(float(raw))
                    item["shopify_id"] = str(numeric)
                except (ValueError, OverflowError):
                    item["shopify_id"] = raw
                break

        # --- Handle ---
        for key in ["handle", "Handle"]:
            if key in row and row[key] and row[key].strip():
                item["handle"] = row[key].strip()
                break

        # --- Subscriber count (AMP uses "Total" column) ---
        for key in ["Total", "total", "subscriber_count", "subscribers", "Subscribers", "Subscriber Count", "count", "Count"]:
            if key in row and row[key] and row[key].strip():
                try:
                    item["subscriber_count"] = int(row[key].strip())
                except ValueError:
                    continue
                break

        if item.get("subscriber_count", 0) > 0 and (item.get("sku") or item.get("shopify_id") or item.get("handle")):
            data.append(item)

    if not data:
        raise HTTPException(status_code=400, detail="No valid rows found. AMP CSV should have SKU and Total columns.")

    service = InventoryService(db)
    result = service.import_subscriber_counts(data)
    return result


@router.post("/waitlist/update")
async def update_subscriber_count(
    payload: List[dict],
    db: Session = Depends(get_db),
):
    """
    Manually update subscriber counts for specific products.
    Body: [{"sku": "ABC123", "subscriber_count": 15}, ...]
    Accepts: sku, shopify_id, product_id, or handle as identifier.
    """
    service = InventoryService(db)
    return service.import_subscriber_counts(payload)


# ============================================================================
# SYNC & WEBHOOKS
# ============================================================================

@router.post("/sync")
async def sync_inventory(
    force_full: bool = Query(False, description="Force a full 365d re-sync instead of incremental"),
    db: Session = Depends(get_db),
):
    """
    Shopify sync: inventory quantities + incremental order line items.

    Default: incremental — only fetches orders updated since the last sync (~10-30s).
    With ?force_full=true: fetches all 365 days of orders (~5-10 min). Use as escape
    hatch when reconciliation is needed.

    Updates stock levels, upserts order line items, re-aggregates sales counters
    only for affected products, and recomputes their classification.
    """
    try:
        service = InventoryService(db)

        # 1) Fetch current stock levels (always full — Shopify doesn't expose
        #    incremental inventory cleanly without webhooks)
        stats = service.sync_inventory_from_shopify()

        # 2) Incremental order sync (or full backfill if forced/empty)
        try:
            order_stats = service.sync_orders_incremental(force_full=force_full)
            stats["orders"] = order_stats
        except Exception as e:
            print(f"[Inventory] Order sync failed (inventory still OK): {e}")
            stats["orders"] = {"error": str(e)}

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync/orders")
async def sync_orders_only(
    force_full: bool = Query(False, description="Force a full 365d re-sync"),
    db: Session = Depends(get_db),
):
    """
    Sync ONLY the order line items (skip inventory level fetch).
    Faster than /sync when you just want fresh sales data.
    """
    try:
        service = InventoryService(db)
        return service.sync_orders_incremental(force_full=force_full)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order sync failed: {str(e)}")


@router.get("/products/{shopify_product_id}/order-history")
async def get_product_order_history(
    shopify_product_id: str,
    days: int = Query(365, ge=1, le=730),
    db: Session = Depends(get_db),
):
    """
    Raw order history for a single product — every line item from every order
    in the last N days. Powers the per-product drill-down view.
    """
    service = InventoryService(db)
    history = service.get_order_history_for_product(shopify_product_id, days=days)
    return {
        "shopify_product_id": shopify_product_id,
        "days": days,
        "total_orders": len(history),
        "total_units": sum(h["quantity"] for h in history),
        "total_revenue": round(sum(h["revenue"] for h in history), 2),
        "orders": history,
    }


@router.post("/webhooks/shopify/inventory")
async def receive_inventory_webhook(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Receives Shopify inventory_levels/update webhook.
    Payload: {inventory_item_id, location_id, available, updated_at}
    """
    try:
        service = InventoryService(db)
        result = service.process_inventory_webhook(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# ============================================================================
# ALERTS
# ============================================================================

@router.get("/alerts")
async def get_alerts(
    status: str = Query("active", description="Filter: active, acknowledged, resolved"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get inventory alerts (low stock, OOS, restocks, dead stock)."""
    service = InventoryService(db)
    return service.get_alerts(status=status, limit=limit)


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
):
    """Mark an alert as acknowledged."""
    service = InventoryService(db)
    if service.acknowledge_alert(alert_id):
        return {"message": "Alert acknowledged"}
    raise HTTPException(status_code=404, detail="Alert not found")


# ============================================================================
# DAILY SNAPSHOT JOB
# ============================================================================

@router.post("/snapshot/daily")
async def take_daily_snapshot(db: Session = Depends(get_db)):
    """Manually trigger a daily inventory snapshot for all products."""
    service = InventoryService(db)
    count = service.take_daily_snapshot()
    return {"snapshots_created": count}


# ============================================================================
# CO-PURCHASE / ANCHOR PRODUCT ANALYSIS
# ============================================================================

@router.post("/sync-co-purchases")
async def sync_co_purchase_data(
    days: int = Query(90, ge=30, le=365, description="Analyze orders from last N days"),
    db: Session = Depends(get_db),
):
    """
    Analyze co-purchase patterns from Shopify orders.
    Detects anchor products (products that drive multi-product carts).
    Updates anchor_score, co_purchase_count, top_companions on each product.
    """
    try:
        service = InventoryService(db)
        result = service.sync_co_purchase_data(days=days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Co-purchase sync failed: {str(e)}")


@router.get("/anchor-products")
async def get_anchor_products(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Products ranked by anchor score — these drive multi-product purchases.
    When an anchor product goes OOS, the revenue impact is multiplied.
    """
    service = InventoryService(db)
    return service.get_anchor_products(limit=limit)


# ============================================================================
# EXCEL EXPORT
# ============================================================================

@router.get("/export/excel")
async def export_inventory_excel(
    view: str = Query("products", description="View: products or action_center"),
    status: Optional[str] = Query(None, description="Filter: in_stock, out_of_stock, low_stock"),
    db: Session = Depends(get_db),
):
    """
    Download inventory data as Excel (.xlsx).
    - view=products: all products in one sheet, sorted by demand
    - view=action_center: 4 sheets (Restock Ahora, Ordenar Pronto, Sin Movimiento, Productos Estrella)
    """
    service = InventoryService(db)
    xlsx_bytes = service.export_to_excel(view=view, status=status)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"Inventario_{view}_{today}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/excel")
async def export_selected_products_excel(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Export selected products to Excel.
    Body: {"product_ids": ["id1", "id2", ...]}
    """
    product_ids = payload.get("product_ids", [])
    if not product_ids:
        raise HTTPException(status_code=400, detail="No product_ids provided")

    service = InventoryService(db)
    xlsx_bytes = service.export_to_excel(view="products", product_ids=product_ids)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"Inventario_selection_{len(product_ids)}_{today}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

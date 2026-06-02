from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.google_api_service import GoogleApiService
from app.services.redis_service import cache
from app.core.config import settings
from app.core.rate_limiter import limiter, RATE_SYNC, RATE_ANALYSIS
from typing import Optional
from datetime import datetime

router = APIRouter()

@router.post("/sync")
@limiter.limit(RATE_SYNC)
async def sync_analytics(request: Request, db: Session = Depends(get_db)):
    """
    Manually trigger a sync of search performance data from GSC and GA4.
    """
    if settings.USE_CELERY:
        from app.tasks.analytics_tasks import sync_analytics_data as sync_task
        task = sync_task.delay()
        return {"task_id": task.id, "status": "queued"}

    try:
        service = GoogleApiService()
        if not service.credentials:
            raise HTTPException(
                status_code=400, 
                detail="Google API credentials not configured. Please check your .env file."
            )
            
        result = service.sync_performance_data(db)
        return {
            "status": "success",
            "message": "Analytics synchronization completed successfully.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@router.get("/status")
async def get_sync_status(db: Session = Depends(get_db)):
    """
    Check the status and last sync time for ALL analytics data sources.
    Returns freshness info for GSC, GA4, and Shopify sales data.
    """
    from app.models.aeo_models import FaultCode
    from app.models.product import Product
    from sqlalchemy import func
    from datetime import timedelta

    now = datetime.utcnow()
    stale_threshold = now - timedelta(hours=24)

    # Fault codes sync status (legacy)
    last_fc_sync = db.query(func.max(FaultCode.updated_at)).scalar()
    fc_count = db.query(FaultCode).count()

    # Product analytics sync status
    last_analytics_sync = db.query(func.max(Product.last_analytics_sync)).scalar()
    total_products = db.query(Product).count()
    products_with_gsc = db.query(Product).filter(Product.gsc_impressions > 0).count()
    products_with_ga4 = db.query(Product).filter(Product.ga4_sessions > 0).count()
    products_with_sales = db.query(Product).filter(Product.sold_90d > 0).count()

    analytics_stale = not last_analytics_sync or last_analytics_sync < stale_threshold
    analytics_age_hours = ((now - last_analytics_sync).total_seconds() / 3600) if last_analytics_sync else None

    return {
        "last_sync": last_fc_sync,
        "total_fault_codes": fc_count,
        "product_analytics": {
            "last_sync": last_analytics_sync.isoformat() if last_analytics_sync else None,
            "age_hours": round(analytics_age_hours, 1) if analytics_age_hours else None,
            "is_stale": analytics_stale,
            "total_products": total_products,
            "with_gsc_data": products_with_gsc,
            "with_ga4_data": products_with_ga4,
            "with_sales_data": products_with_sales,
        },
        "warnings": [
            msg for msg in [
                f"Analytics data is {analytics_age_hours:.0f}h old — run POST /products/sync-analytics" if analytics_stale and analytics_age_hours else None,
                "Analytics never synced — run POST /products/sync-analytics and POST /products/sync-sales" if not last_analytics_sync else None,
                f"Only {products_with_gsc}/{total_products} products have GSC data" if products_with_gsc < total_products * 0.1 and total_products > 0 else None,
                f"Only {products_with_ga4}/{total_products} products have GA4 data" if products_with_ga4 < total_products * 0.1 and total_products > 0 else None,
            ] if msg
        ]
    }

@router.get("/ai-traffic")
async def get_ai_traffic(days: int = Query(30), db: Session = Depends(get_db)):
    """
    Get traffic reports specialized for AI agents and llms.txt.
    """
    try:
        service = GoogleApiService()
        if not service.credentials:
            raise HTTPException(status_code=400, detail="Google API credentials not configured.")
            
        llm_traffic = service.get_llm_txt_traffic(days=days)
        ai_referrals = service.get_ai_referral_traffic(days=days)
        
        from app.services.ai_referral_tracker import AIReferralTracker
        combined = llm_traffic + ai_referrals
        summary = AIReferralTracker.categorize_sessions(combined)
        
        return {
            "status": "success",
            "summary": summary,
            "raw_data": {
                "llm_traffic": llm_traffic,
                "ai_referrals": ai_referrals
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch AI traffic: {str(e)}")


@router.get("/diagnose-spike")
async def diagnose_traffic_spike(
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
):
    """
    Diagnose a traffic spike — breaks down sessions by source/medium, country,
    channel, device, landing page, and daily trend. Includes bot signal detection.

    Use this when you see an unusual spike in sessions to identify the source.
    """
    try:
        service = GoogleApiService()
        if not service.credentials:
            raise HTTPException(status_code=400, detail="Google API credentials not configured.")

        report = service.diagnose_traffic_spike(days=days)

        return {
            "status": "success",
            "period": f"last {days} days",
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to diagnose spike: {str(e)}")


@router.get("/llm-sales")
async def get_llm_sales(
    days: int = Query(365, ge=1, le=730, description="Days to look back (max 2 years)"),
    compare: bool = Query(True, description="Include comparison to previous period"),
    refresh: bool = Query(False, description="Force refresh (bypass cache)"),
    db: Session = Depends(get_db)
):
    """
    Get sales attributed to LLM sources (ChatGPT, Gemini, Claude, Perplexity).
    
    Uses Shopify Orders API to find orders with LLM-related landing page URLs.
    Results are cached for 1 hour. Use refresh=true to bypass cache.
    
    Note: ShopifyQL was sunset in API version 2024-07, so we use Orders API.
    
    **For LLM attribution to work**, orders need UTM parameters in the landing page:
    - ?utm_source=chatgpt
    - ?utm_source=gemini
    - ?utm_source=perplexity
    
    **Returns:**
    - summary: Aggregated totals (sales, orders, AOV)
    - by_source: Breakdown by LLM provider with order details
    - monthly_trend: Sales by month
    - comparison: Period-over-period changes (if compare=true)
    """
    try:
        from app.services.shopify_service import ShopifyService, _llm_sales_cache
        
        # Clear cache if refresh requested
        if refresh:
            _llm_sales_cache.clear()
            print("[API] Cache cleared - fetching fresh LLM sales data")
        
        service = ShopifyService()
        result = service.get_llm_attributed_sales(days=days, compare=compare)

        
        if not result or result.get("summary", {}).get("total_orders", 0) == 0:
            return {
                "status": "no_data",
                "message": "No LLM-attributed sales found. Ensure your landing pages have UTM parameters (e.g., ?utm_source=chatgpt).",
                "summary": {
                    "total_sales": 0,
                    "total_orders": 0,
                    "average_order_value": 0,
                },
                "by_source": [],
                "comparison": None,
                "period": result.get("period") if result else None,
            }
        
        return {
            "status": "success",
            **result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch LLM sales: {str(e)}")


@router.get("/llm-sales/enhanced")
async def get_enhanced_llm_sales(
    days: int = Query(365, ge=1, le=730, description="Days to look back (max 2 years)"),
    compare: bool = Query(True, description="Include comparison to previous period"),
    refresh: bool = Query(False, description="Force refresh (bypass cache)"),
    include_funnel: bool = Query(True, description="Include conversion funnel data"),
    include_assisted: bool = Query(True, description="Include multi-touch attribution"),
    include_geo: bool = Query(True, description="Include geographic analysis"),
    include_time_to_conversion: bool = Query(True, description="Include time-to-conversion analysis"),
    include_cohorts: bool = Query(True, description="Include cohort retention analysis"),
    include_categories: bool = Query(True, description="Include category performance"),
    source: Optional[str] = Query(None, description="Filter by specific LLM source (chatgpt, gemini, perplexity, claude, copilot)"),
    db: Session = Depends(get_db)
):
    """
    Get ENHANCED sales attributed to LLM sources with comprehensive analytics.
    
    This endpoint provides all the standard LLM sales data PLUS:
    
    **Enhanced Metrics:**
    - **assisted_conversions**: Multi-touch attribution showing how LLMs influence journeys
      - direct: LLM was first AND last touch
      - first_touch: LLM started the journey but didn't close
      - last_touch: Current attribution (LLM closed)
    - **time_to_conversion**: Statistical analysis of buying cycles
      - avg_hours, median_hours, percentiles
      - Distribution by time buckets (0-1h, 1-24h, 1-7d, 1-30d, 30d+)
    - **category_performance**: Which product categories perform via LLMs
      - LLM penetration by category
      - Top categories by revenue
    - **cohort_analysis**: Customer retention patterns
      - Cohort months, retention rates
      - LTV by source
    - **geographic**: Geographic distribution of LLM sales
      - Country/region breakdown
      - Source distribution by geography
    - **funnel**: Conversion funnel (impressions → traffic → purchases)
      - Requires GA4 integration for full funnel
    
    **Automated Alerts:**
    - Trend detection (up/down vs previous period)
    - Anomaly detection (unusual drops in AOV/conversion)
    - Opportunity identification (high-performing sources)
    
    **Query Parameters:**
    - All `include_*` flags default to true but can be disabled for faster response
    - Use `source=chatgpt` to get data for specific LLM only
    
    **Returns:**
    - basic: Original sales data structure (summary, by_source, monthly_trend, comparison)
    - enhanced: New analytics data (assisted_conversions, time_to_conversion, etc.)
    - alerts: Automated insights and warnings
    """
    try:
        from app.services.shopify_service import ShopifyService, _llm_sales_cache
        from app.services.llm_analytics import LLMAnalyticsEnhancer
        
        # Clear cache if refresh requested
        if refresh:
            _llm_sales_cache.clear()
            LLMAnalyticsEnhancer.clear_cache()
            print("[API] Cache cleared - fetching fresh LLM sales data")
        
        # Initialize services
        shopify_service = ShopifyService()
        analytics = LLMAnalyticsEnhancer(shopify_service)
        
        # Get enhanced data
        result = analytics.get_enhanced_llm_sales(
            days=days,
            include_funnel=include_funnel,
            include_assisted=include_assisted,
            include_geo=include_geo,
            include_time_to_conversion=include_time_to_conversion,
            include_cohorts=include_cohorts,
            include_categories=include_categories
        )
        
        # Filter by source if requested
        if source and result.get("basic", {}).get("by_source"):
            result["basic"]["by_source"] = [
                s for s in result["basic"]["by_source"]
                if s.get("source") == source
            ]
            
            # Filter enhanced data too
            for key in ["assisted_conversions", "time_to_conversion", "geographic"]:
                if key in result.get("enhanced", {}):
                    enhanced_data = result["enhanced"][key]
                    if isinstance(enhanced_data, dict):
                        result["enhanced"][key] = {
                            k: v for k, v in enhanced_data.items()
                            if k == source or not isinstance(k, str) or k not in ["chatgpt", "gemini", "perplexity", "claude", "copilot"]
                        }
        
        # Check if we have data
        basic_data = result.get("basic", {})
        if not basic_data or basic_data.get("summary", {}).get("total_orders", 0) == 0:
            return {
                "status": "no_data",
                "message": "No LLM-attributed sales found. Ensure your landing pages have UTM parameters (e.g., ?utm_source=chatgpt).",
                "basic": {
                    "summary": {"total_sales": 0, "total_orders": 0, "average_order_value": 0},
                    "by_source": [],
                    "comparison": None,
                },
                "enhanced": {},
                "alerts": [{
                    "type": "insight",
                    "severity": "medium",
                    "message": "No LLM sales detected. Verify UTM tracking is configured correctly.",
                    "recommendation": "Add UTM parameters to your llms.txt citations: ?utm_source=chatgpt&utm_medium=referral"
                }]
            }
        
        return {
            "status": "success",
            **result
        }
        
    except Exception as e:
        import traceback
        print(f"[API Error] Enhanced LLM sales failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch enhanced LLM sales: {str(e)}")


@router.get("/llm-sales/funnel")
async def get_llm_conversion_funnel(
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    source: Optional[str] = Query(None, description="Filter by specific LLM source"),
    db: Session = Depends(get_db)
):
    """
    Get conversion funnel metrics for LLM-attributed traffic.
    
    Shows the full funnel from impressions → traffic → purchases.
    
    **Funnel Stages:**
    - impressions: Estimated LLM impressions (3x traffic estimate)
    - traffic: Actual site visits from LLM sources (requires GA4)
    - product_views: Product page views (requires GA4 e-commerce)
    - add_to_carts: Add to cart events (requires GA4 e-commerce)
    - checkouts: Checkout initiations (requires GA4 e-commerce)
    - purchases: Completed orders from Shopify
    
    **Conversion Rates:**
    - traffic_to_view: % of traffic viewing products
    - view_to_cart: % of viewers adding to cart
    - cart_to_checkout: % of carts proceeding to checkout
    - checkout_to_purchase: % of checkouts completing
    - overall: % of traffic converting to purchase
    
    Note: Full funnel requires GA4 integration with custom dimensions.
    """
    try:
        from app.services.shopify_service import ShopifyService
        from app.services.llm_analytics import LLMAnalyticsEnhancer
        
        shopify_service = ShopifyService()
        analytics = LLMAnalyticsEnhancer(shopify_service)
        
        funnel = analytics.get_conversion_funnel(days=days, source=source)
        
        return {
            "status": "success",
            "funnel": funnel
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversion funnel: {str(e)}")


@router.get("/llm-sales/export")
async def export_llm_sales(
    days: int = Query(365, ge=1, le=730, description="Days to look back"),
    format: str = Query("csv", description="Export format: csv or json"),
    db: Session = Depends(get_db)
):
    """
    Export LLM sales data for external analysis.
    
    **Formats:**
    - csv: Comma-separated values for Excel/Sheets
    - json: JSON format for programmatic use
    
    **Includes:**
    - All order-level data with attribution
    - Source breakdown
    - Monthly trends
    - Geographic data
    
    Useful for:
    - Executive reporting
    - Custom dashboarding
    - Data warehouse ingestion
    """
    try:
        from app.services.shopify_service import ShopifyService
        from app.services.llm_analytics import LLMAnalyticsEnhancer
        import csv
        import io
        from fastapi.responses import StreamingResponse
        import json
        
        shopify_service = ShopifyService()
        analytics = LLMAnalyticsEnhancer(shopify_service)
        
        # Get enhanced data
        data = analytics.get_enhanced_llm_sales(days=days)
        
        if format.lower() == "json":
            # Return JSON
            output = io.StringIO()
            json.dump(data, output, indent=2, default=str)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=llm_sales_{days}d.json"}
            )
        
        else:
            # Return CSV - create multiple sheets as separate CSV sections
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Summary section
            writer.writerow(["LLM SALES ATTRIBUTION REPORT"])
            writer.writerow(["Generated:", datetime.now().isoformat()])
            writer.writerow(["Period:", f"Last {days} days"])
            writer.writerow([])
            
            # Basic summary
            summary = data.get("basic", {}).get("summary", {})
            writer.writerow(["SUMMARY"])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Sales", summary.get("total_sales", 0)])
            writer.writerow(["Total Orders", summary.get("total_orders", 0)])
            writer.writerow(["Average Order Value", summary.get("average_order_value", 0)])
            writer.writerow(["Sources Detected", summary.get("sources_detected", 0)])
            writer.writerow([])
            
            # Source breakdown
            writer.writerow(["SOURCE BREAKDOWN"])
            writer.writerow(["Source", "Sales", "Orders", "AOV", "% of Total"])
            for source in data.get("basic", {}).get("by_source", []):
                writer.writerow([
                    source.get("source"),
                    source.get("sales", 0),
                    source.get("orders", 0),
                    source.get("aov", 0),
                    source.get("percent_of_total", 0)
                ])
            writer.writerow([])
            
            # Monthly trend
            writer.writerow(["MONTHLY TREND"])
            writer.writerow(["Month", "Sales", "Orders"])
            for month in data.get("basic", {}).get("monthly_trend", []):
                writer.writerow([
                    month.get("month"),
                    month.get("sales", 0),
                    month.get("orders", 0)
                ])
            writer.writerow([])
            
            # Geographic data
            geo_data = data.get("enhanced", {}).get("geographic", [])
            if geo_data:
                writer.writerow(["GEOGRAPHIC BREAKDOWN"])
                writer.writerow(["Country", "Region", "Sales", "Orders", "Customers", "AOV"])
                for geo in geo_data:
                    writer.writerow([
                        geo.get("country"),
                        geo.get("region") or "",
                        geo.get("sales", 0),
                        geo.get("orders", 0),
                        geo.get("customers", 0),
                        geo.get("avg_order_value", 0)
                    ])
                writer.writerow([])
            
            # Category performance
            cat_data = data.get("enhanced", {}).get("category_performance", [])
            if cat_data:
                writer.writerow(["CATEGORY PERFORMANCE"])
                writer.writerow(["Category", "LLM Sales", "LLM Orders", "Total Sales", "LLM Penetration %"])
                for cat in cat_data:
                    writer.writerow([
                        cat.get("category"),
                        cat.get("llm_sales", 0),
                        cat.get("llm_orders", 0),
                        cat.get("total_sales", 0),
                        cat.get("llm_penetration_pct", 0)
                    ])
            
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=llm_sales_{days}d.csv"}
            )
        
    except Exception as e:
        import traceback
        print(f"[API Error] Export failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")


# ============ ANALYTICS SNAPSHOT ENDPOINTS ============

@router.post("/snapshots/refresh-and-snapshot")
@limiter.limit(RATE_SYNC)
async def refresh_and_snapshot(request: Request, db: Session = Depends(get_db)):
    """
    Atomic "fetch fresh + snapshot" pipeline for the SEO Intelligence dashboard.

    Steps (synchronous, returns when all complete):
      1. Pull fresh GSC + GA4 data → updates Product.gsc_* and Product.ga4_* fields
      2. Recompute SEO scores from current HTML
      3. Persist a snapshot row per product so the trend tables get a fresh data point

    Use this when the user wants up-to-the-minute data on the SEO Intelligence page.
    Powered by the same Celery task that runs daily at 06:00 from beat.
    """
    if settings.USE_CELERY:
        from app.tasks.analytics_tasks import refresh_and_snapshot_analytics as task_fn
        task = task_fn.delay()
        return {"task_id": task.id, "status": "queued"}

    # Synchronous fallback (no Celery)
    import asyncio
    from app.services.product_service import ProductService
    from app.services.shopify_service import ShopifyService
    from app.models.product import Product
    from app.jobs.analytics_snapshot import create_daily_snapshot

    result = {"steps": {}}

    # Step 1: GSC + GA4 sync
    try:
        service = ProductService(db)
        sync_result = await service.sync_product_analytics()
        result["steps"]["analytics_sync"] = sync_result
    except Exception as e:
        result["steps"]["analytics_sync"] = {"error": str(e)}

    # Step 2: SEO score recalc
    try:
        shopify_svc = ShopifyService()
        products = db.query(Product).all()
        updated_scores = 0
        for product in products:
            new_score = shopify_svc.get_seo_score(product.current_description_html or "")
            if product.seo_score != new_score:
                product.seo_score = new_score
                updated_scores += 1
        db.commit()
        result["steps"]["seo_recalc"] = {"updated": updated_scores, "total": len(products)}
    except Exception as e:
        db.rollback()
        result["steps"]["seo_recalc"] = {"error": str(e)}

    # Step 3: Snapshot
    try:
        snap_result = create_daily_snapshot(db=db)
        result["steps"]["snapshot"] = snap_result
    except Exception as e:
        result["steps"]["snapshot"] = {"error": str(e)}

    return result


@router.get("/snapshots/freshness")
async def get_data_freshness(db: Session = Depends(get_db)):
    """
    Returns timestamps describing how fresh the SEO Intelligence data is.
    Used by the dashboard freshness badge.

    Returns:
      - last_analytics_sync: max(Product.last_analytics_sync) → freshness of GSC/GA4 fields
      - last_snapshot_at: max(ProductAnalyticsSnapshot.snapshot_date)
      - last_snapshot_count: how many products were captured in that snapshot batch
      - hours_since_sync: convenience field
      - hours_since_snapshot: convenience field
      - status: "fresh" (<24h) | "stale" (24-168h) | "very_stale" (>168h)
    """
    from app.models.product import Product, ProductAnalyticsSnapshot
    from sqlalchemy import func as sql_func

    last_sync = db.query(sql_func.max(Product.last_analytics_sync)).scalar()
    last_snap = db.query(sql_func.max(ProductAnalyticsSnapshot.snapshot_date)).scalar()

    last_snap_count = 0
    if last_snap:
        # Count snapshots taken on the same calendar day as the latest one
        from datetime import timedelta
        day_start = last_snap.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        last_snap_count = db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.snapshot_date >= day_start,
            ProductAnalyticsSnapshot.snapshot_date < day_end,
        ).count()

    now = datetime.utcnow()
    hours_since_sync = None
    hours_since_snapshot = None

    if last_sync:
        # Strip tz to compare with naive utcnow()
        last_sync_naive = last_sync.replace(tzinfo=None) if last_sync.tzinfo else last_sync
        hours_since_sync = round((now - last_sync_naive).total_seconds() / 3600, 1)

    if last_snap:
        last_snap_naive = last_snap.replace(tzinfo=None) if last_snap.tzinfo else last_snap
        hours_since_snapshot = round((now - last_snap_naive).total_seconds() / 3600, 1)

    # Status classification (uses the worse of the two)
    worst = max(hours_since_sync or 0, hours_since_snapshot or 0)
    if worst < 24:
        status = "fresh"
    elif worst < 168:  # 7 days
        status = "stale"
    else:
        status = "very_stale"

    return {
        "last_analytics_sync": last_sync.isoformat() if last_sync else None,
        "last_snapshot_at": last_snap.isoformat() if last_snap else None,
        "last_snapshot_count": last_snap_count,
        "hours_since_sync": hours_since_sync,
        "hours_since_snapshot": hours_since_snapshot,
        "status": status,
    }


@router.post("/snapshots/create")
async def create_analytics_snapshot(
    product_ids: Optional[str] = Query(None, description="Comma-separated product IDs (optional, all if not provided)"),
    db: Session = Depends(get_db)
):
    """
    Create daily analytics snapshots for historical trend tracking.
    
    Run this daily via cron or scheduler to enable trend analysis.
    
    After creating snapshots, the Grok Deep Analysis will show:
    - Traffic trends (↗ +5% or ↘ -12%)
    - Position trends
    - Sales trends
    
    **Example cron job:**
    0 6 * * * curl -X POST http://localhost:8000/api/v1/analytics/snapshots/create
    """
    from app.jobs.analytics_snapshot import create_daily_snapshot
    
    ids_list = None
    if product_ids:
        ids_list = [pid.strip() for pid in product_ids.split(',')]
    
    result = create_daily_snapshot(db=db, product_ids=ids_list)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result


@router.post("/seo-scores/recalculate")
@limiter.limit(RATE_ANALYSIS)
async def recalculate_seo_scores(request: Request, db: Session = Depends(get_db)):
    """
    Recalculate and persist SEO scores for ALL products based on their current HTML content.
    One-time backfill or periodic refresh to keep Product.seo_score accurate.
    """
    if settings.USE_CELERY:
        from app.tasks.analytics_tasks import recalculate_seo_scores as recalc_task
        task = recalc_task.delay()
        return {"task_id": task.id, "status": "queued"}

    from app.services.shopify_service import ShopifyService
    from app.models.product import Product
    shopify_svc = ShopifyService()

    products = db.query(Product).all()
    updated = 0

    for product in products:
        html = product.current_description_html or ""
        new_score = shopify_svc.get_seo_score(html)
        if product.seo_score != new_score:
            product.seo_score = new_score
            updated += 1

    db.commit()

    # Also update today's snapshots with the correct SEO scores
    from app.models.product import ProductAnalyticsSnapshot
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    snapshots_updated = 0
    
    today_snapshots = db.query(ProductAnalyticsSnapshot).filter(
        ProductAnalyticsSnapshot.snapshot_date >= today_start
    ).all()
    
    # Build product score lookup
    score_map = {str(p.id): p.seo_score for p in products}
    
    for snap in today_snapshots:
        correct_score = score_map.get(str(snap.product_id), 0)
        if snap.seo_score != correct_score:
            snap.seo_score = correct_score
            snapshots_updated += 1
    
    db.commit()

    return {
        "status": "success",
        "total_products": len(products),
        "updated": updated,
        "unchanged": len(products) - updated,
        "snapshots_fixed": snapshots_updated
    }


@router.get("/snapshots/optimized-recently")
async def get_optimized_recently(
    days: int = Query(30, ge=1, le=3650, description="Days to look back for optimizations (up to ~10 years for 'all time')"),
    limit: int = Query(50, ge=1, le=5000, description="Max products to return (catalog has ~5,000 SKUs)"),
    verdict_lag_days: int = Query(7, ge=1, le=30, description="Days to wait after an optimization before computing a verdict"),
    db: Session = Depends(get_db)
):
    """
    Get products optimized in the last N days with optimization-anchored before/after deltas.

    For each product:
      - "before" = LAST snapshot taken BEFORE the optimization (preferred)
                   FALLBACK: FIRST non-zero snapshot taken WITHIN 5 days AFTER the
                   optimization. This is reliable because GSC data lags 2-3 days,
                   so a snapshot taken right after the edit still reflects pre-edit
                   reality. When this fallback is used, baseline_source='post_edit'
                   instead of 'pre_edit', and the verdict is 'tracked_only' so the
                   user knows the comparison is approximate.
      - "after"  = FIRST non-zero snapshot taken AT LEAST `verdict_lag_days` AFTER
                   the optimization event.

    "Non-zero" = at least one of (seo_score, gsc_impressions, ga4_sessions, gsc_position)
    is > 0. This filters out early snapshots that were captured before the analytics
    pipeline had populated the underlying fields (zero-only snapshots are calculation
    lag, not real "no traffic" measurements).

    Verdict field:
      - "positive"     : SEO/position/sessions all improved
      - "negative"     : all dropped
      - "mixed"        : some up, some down
      - "neutral"      : nothing meaningful moved
      - "pending"      : optimization happened, waiting for verdict_lag_days to elapse
      - "tracked_only" : no strict pre-edit baseline; using a soft post-edit baseline
      - "no_baseline"  : no usable snapshot exists at all
    """
    cache_key = f"analytics:optimized_recently:v6:{days}:{limit}:{verdict_lag_days}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    from app.models.product import ProductAnalyticsSnapshot, Product
    from app.models.library import GenerationHistory
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Find products with generation events in the window — use latest event per product
    optimized_products = db.query(
        GenerationHistory.product_id,
        func.max(GenerationHistory.generated_at).label('last_optimized'),
        func.count(GenerationHistory.id).label('generation_count')
    ).filter(
        GenerationHistory.generated_at >= cutoff,
        GenerationHistory.status.in_(['published', 'approved', 'draft', 'manual_edit'])
    ).group_by(
        GenerationHistory.product_id
    ).order_by(
        func.max(GenerationHistory.generated_at).desc()
    ).limit(limit).all()

    if not optimized_products:
        response = {"days": days, "total_optimized": 0, "products": []}
        cache.set(cache_key, response, ttl=300)
        return response

    product_ids = [opt.product_id for opt in optimized_products]
    opt_map = {opt.product_id: opt for opt in optimized_products}

    # Batch: products + latest gen event metadata
    products_map = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}

    latest_gen_sub = db.query(
        GenerationHistory.product_id,
        func.max(GenerationHistory.generated_at).label('max_gen')
    ).filter(
        GenerationHistory.product_id.in_(product_ids)
    ).group_by(GenerationHistory.product_id).subquery()

    latest_gens = db.query(GenerationHistory).join(
        latest_gen_sub,
        (GenerationHistory.product_id == latest_gen_sub.c.product_id) &
        (GenerationHistory.generated_at == latest_gen_sub.c.max_gen)
    ).all()
    gen_map = {g.product_id: g for g in latest_gens}

    # Batch-load ALL snapshots for these products (we need to pick before/after per opt date)
    all_snaps = db.query(ProductAnalyticsSnapshot).filter(
        ProductAnalyticsSnapshot.product_id.in_(product_ids)
    ).order_by(ProductAnalyticsSnapshot.snapshot_date.asc()).all()

    snaps_by_product = {}
    for s in all_snaps:
        snaps_by_product.setdefault(s.product_id, []).append(s)

    def _strip_tz(dt):
        return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt

    def _is_meaningful_snapshot(s):
        """A snapshot is meaningful if at least one metric has a non-zero value.
        Zero-only snapshots are calculation lag, not real measurements."""
        if not s:
            return False
        return any([
            (s.seo_score or 0) > 0,
            (s.gsc_impressions or 0) > 0,
            (s.gsc_position or 0) > 0,
            (s.ga4_sessions or 0) > 0,
        ])

    def _snap_dict(s):
        return {
            "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else None,
            "seo_score": s.seo_score,
            "gsc_position": s.gsc_position,
            "gsc_impressions": s.gsc_impressions,
            "gsc_clicks": s.gsc_clicks,
            "gsc_ctr": s.gsc_ctr,
            "ga4_sessions": s.ga4_sessions,
            "sold_30d": s.sold_30d,
            "revenue_30d": s.revenue_30d,
            # Shopify state — enables "what else changed" detection
            "price": s.price,
            "inventory_quantity": s.inventory_quantity,
            "image_count": s.image_count,
            "description_length": s.description_length,
        } if s else None

    def _parse_price(p):
        """Shopify stores price as a string like '450.00' or None. Returns a float
        or None — survives bad data without crashing the response."""
        if p is None or p == "":
            return None
        try:
            return float(p)
        except (ValueError, TypeError):
            return None

    def _detect_overlaps(before_snap, after_snap):
        """Return a list of concurrent non-content changes between the two
        snapshots. Each entry has {type, before, after, pct_change}.

        The point: if price dropped 15% AND content was edited in the same
        window, we can't credit/blame the content edit alone. Surfacing this
        prevents the attribution lie that the current UI tells.

        We intentionally ignore description_length diffs here — those ARE the
        content edit, not a concurrent change."""
        if not before_snap or not after_snap:
            return []

        overlaps = []

        # Price: a move of >=5% is worth flagging (cheap items can swing a few cents)
        p_before = _parse_price(before_snap.price)
        p_after = _parse_price(after_snap.price)
        if p_before is not None and p_after is not None and p_before > 0:
            pct = ((p_after - p_before) / p_before) * 100.0
            if abs(pct) >= 5:
                overlaps.append({
                    "type": "price",
                    "before": p_before,
                    "after": p_after,
                    "pct_change": round(pct, 1),
                })

        # Inventory: flag crossings of the zero boundary (stockout / restock) OR
        # a >=50% change (a slow-moving shift matters less than an OOS)
        inv_b = before_snap.inventory_quantity
        inv_a = after_snap.inventory_quantity
        if inv_b is not None and inv_a is not None:
            if (inv_b > 0 and inv_a == 0) or (inv_b == 0 and inv_a > 0):
                overlaps.append({
                    "type": "inventory",
                    "before": inv_b,
                    "after": inv_a,
                    "pct_change": None,  # category change, not a ratio story
                })
            elif inv_b > 0:
                pct = ((inv_a - inv_b) / inv_b) * 100.0
                if abs(pct) >= 50:
                    overlaps.append({
                        "type": "inventory",
                        "before": inv_b,
                        "after": inv_a,
                        "pct_change": round(pct, 1),
                    })

        # Images: any count change is a likely visual refresh (matters for CTR)
        img_b = before_snap.image_count or 0
        img_a = after_snap.image_count or 0
        if img_b != img_a:
            overlaps.append({
                "type": "images",
                "before": img_b,
                "after": img_a,
                "pct_change": None,
            })

        return overlaps

    def _pct_change(before, after):
        """Percent change from before -> after. Returns None if before is zero
        (undefined) so the caller can handle it separately."""
        b = before or 0
        a = after or 0
        if b == 0:
            return None if a == 0 else (100.0 if a > 0 else -100.0)
        return round(((a - b) / b) * 100.0, 2)

    def _real_impact(before_snap, after_snap):
        """Traffic-weighted Real Impact score (-100 .. +100).

        Weights (traffic dominates, SEO score is a tiebreaker, sales is separate):
          Impressions 40%, Clicks 30%, Position 25%, SEO 5%

        Position is inverted (lower rank = better traffic outcome). Each component
        is clamped to [-100, +100] to prevent extreme before-values (e.g. going
        from 1 impression to 100) from swinging the whole score."""
        if not before_snap or not after_snap:
            return None

        impr_pct = _pct_change(before_snap.gsc_impressions, after_snap.gsc_impressions)
        # Clicks: fall back to sessions when GSC clicks is absent
        clicks_before = (before_snap.gsc_clicks or 0) or (before_snap.ga4_sessions or 0)
        clicks_after = (after_snap.gsc_clicks or 0) or (after_snap.ga4_sessions or 0)
        clicks_pct = _pct_change(clicks_before, clicks_after)

        # Position is already absolute; convert to a pseudo-% where -100..+100
        # represents a full page shift (10 positions = 100% change in visibility)
        pos_before = before_snap.gsc_position or 0
        pos_after = after_snap.gsc_position or 0
        if pos_before == 0 and pos_after == 0:
            pos_component = None
        else:
            # lower position = better; invert so improvement is positive
            pos_component = max(-100.0, min(100.0, (pos_before - pos_after) * 10.0))

        seo_before = before_snap.seo_score or 0
        seo_after = after_snap.seo_score or 0
        # SEO score is already 0-100, so delta is already in the right scale
        seo_component = max(-100.0, min(100.0, float(seo_after - seo_before)))

        def _clamp(x):
            return max(-100.0, min(100.0, x))

        parts = []  # (weight, value)
        traffic_signals = 0  # count of actual traffic signals (impr/clicks/pos)
        if impr_pct is not None:
            parts.append((0.40, _clamp(impr_pct)))
            traffic_signals += 1
        if clicks_pct is not None:
            parts.append((0.30, _clamp(clicks_pct)))
            traffic_signals += 1
        if pos_component is not None:
            parts.append((0.25, pos_component))
            traffic_signals += 1

        # Require at least one traffic signal. SEO score on its own should not
        # drive a "strong win" verdict — the whole point of this rewrite is that
        # SEO score moving without traffic moving is meaningless.
        if traffic_signals == 0:
            return None

        parts.append((0.05, seo_component))

        # Renormalise so the remaining weights sum to 1.0 when some signals
        # are missing (e.g. a product with zero baseline impressions)
        total_weight = sum(w for w, _ in parts)
        if total_weight == 0:
            return None
        score = sum(w * v for w, v in parts) / total_weight
        return round(score, 1)

    def _classify_verdict(impact_score, baseline_source, has_baseline):
        """Map a Real Impact score to a verdict. Thresholds:
          >= +5   -> positive   (clear win)
          <= -5   -> negative   (clear regression)
          otherwise neutral / mixed

        Soft baselines (post_edit) get a dedicated 'tracked_only' verdict so the
        user knows the comparison is approximate. When both before/after exist
        but traffic is flat on both sides (impact_score=None), we call it
        'neutral' — we have the data, it just didn't move."""
        if not has_baseline:
            return "no_baseline"
        if impact_score is None:
            # Snapshots exist but no traffic signal to judge — call it neutral
            return "neutral"
        if baseline_source == "post_edit":
            return "tracked_only"
        if impact_score >= 5:
            return "positive"
        if impact_score <= -5:
            return "negative"
        if abs(impact_score) < 2:
            return "neutral"
        return "mixed"

    def _sales_flag(before_snap, after_snap):
        """Separate sales signal. Not a verdict input — sales can stay flat
        while SEO works fine (price / stock / competition drive conversion).

        Returns: 'converting' | 'dropping' | None (flat or no data)."""
        if not before_snap or not after_snap:
            return None

        rev_before = before_snap.revenue_30d or 0
        rev_after = after_snap.revenue_30d or 0
        sold_before = before_snap.sold_30d or 0
        sold_after = after_snap.sold_30d or 0

        # Need at least some baseline or post-value to call it
        if rev_before == 0 and rev_after == 0 and sold_before == 0 and sold_after == 0:
            return None

        rev_pct = _pct_change(rev_before, rev_after)
        sold_pct = _pct_change(sold_before, sold_after)

        # Dominant signal: whichever moved more
        signal_pct = rev_pct if (rev_pct is not None and abs(rev_pct) >= abs(sold_pct or 0)) else sold_pct
        if signal_pct is None:
            return None
        if signal_pct >= 15:
            return "converting"
        if signal_pct <= -15:
            return "dropping"
        return None

    # Soft-baseline window: how many days after the optimization can we still
    # treat a snapshot as a "pre-edit" baseline? GSC data lags 2-3 days, so a
    # snapshot taken within 5 days post-edit still reflects pre-edit reality.
    SOFT_BASELINE_WINDOW_DAYS = 5

    results = []
    now = datetime.utcnow()
    counts = {
        "positive": 0, "negative": 0, "mixed": 0, "neutral": 0,
        "pending": 0, "no_baseline": 0, "tracked_only": 0,
        "inconclusive": 0,
    }
    sales_counts = {"converting": 0, "dropping": 0}

    for pid in product_ids:
        product = products_map.get(pid)
        if not product:
            continue

        opt = opt_map[pid]
        opt_date_naive = _strip_tz(opt.last_optimized)
        if not opt_date_naive:
            continue

        snaps = snaps_by_product.get(pid, [])
        latest_gen = gen_map.get(pid)

        # ── Step 1: prefer a strict pre-edit baseline ──
        # Latest MEANINGFUL snapshot strictly before the optimization timestamp
        before_snap = None
        baseline_source = "pre_edit"
        for s in snaps:
            sd = _strip_tz(s.snapshot_date)
            if sd and sd < opt_date_naive and _is_meaningful_snapshot(s):
                before_snap = s  # advance — snaps are sorted ascending

        # ── Step 2: soft fallback baseline ──
        # If no strict pre-edit baseline exists, use the FIRST meaningful snapshot
        # taken WITHIN SOFT_BASELINE_WINDOW_DAYS after the optimization. GSC data
        # lag means this still reflects pre-edit reality.
        if not before_snap:
            soft_window_end = opt_date_naive + timedelta(days=SOFT_BASELINE_WINDOW_DAYS)
            for s in snaps:
                sd = _strip_tz(s.snapshot_date)
                if sd and opt_date_naive <= sd <= soft_window_end and _is_meaningful_snapshot(s):
                    before_snap = s
                    baseline_source = "post_edit"  # soft baseline marker
                    break

        # ── Step 3: pick "after" — first MEANINGFUL snapshot at least verdict_lag_days
        #             after the soft baseline (or the optimization, whichever is later) ──
        if before_snap:
            before_date = _strip_tz(before_snap.snapshot_date)
            after_target = max(opt_date_naive, before_date) + timedelta(days=verdict_lag_days)
        else:
            after_target = opt_date_naive + timedelta(days=verdict_lag_days)

        after_snap = None
        for s in snaps:
            sd = _strip_tz(s.snapshot_date)
            if sd and sd >= after_target and _is_meaningful_snapshot(s):
                after_snap = s
                break

        # ── Step 4: classify verdict ──
        verdict = "no_baseline"
        days_until_verdict = 0
        deltas = None
        impact_score = None
        sales_flag = None
        overlaps = []

        if before_snap and after_snap:
            # Full delta matrix (absolute values)
            deltas = {
                "seo_score": (after_snap.seo_score or 0) - (before_snap.seo_score or 0),
                "gsc_position": round((after_snap.gsc_position or 0) - (before_snap.gsc_position or 0), 2),
                "gsc_impressions": (after_snap.gsc_impressions or 0) - (before_snap.gsc_impressions or 0),
                "gsc_clicks": (after_snap.gsc_clicks or 0) - (before_snap.gsc_clicks or 0),
                "gsc_ctr": round((after_snap.gsc_ctr or 0) - (before_snap.gsc_ctr or 0), 4),
                "ga4_sessions": (after_snap.ga4_sessions or 0) - (before_snap.ga4_sessions or 0),
                "sold_30d": (after_snap.sold_30d or 0) - (before_snap.sold_30d or 0),
                "revenue_30d": round((after_snap.revenue_30d or 0) - (before_snap.revenue_30d or 0), 2),
                # Percent changes for the traffic metrics (what the card hero uses)
                "gsc_impressions_pct": _pct_change(before_snap.gsc_impressions, after_snap.gsc_impressions),
                "gsc_clicks_pct": _pct_change(before_snap.gsc_clicks, after_snap.gsc_clicks),
                "ga4_sessions_pct": _pct_change(before_snap.ga4_sessions, after_snap.ga4_sessions),
                "revenue_30d_pct": _pct_change(before_snap.revenue_30d, after_snap.revenue_30d),
                "sold_30d_pct": _pct_change(before_snap.sold_30d, after_snap.sold_30d),
            }
            impact_score = _real_impact(before_snap, after_snap)
            sales_flag = _sales_flag(before_snap, after_snap)
            overlaps = _detect_overlaps(before_snap, after_snap)
            verdict = _classify_verdict(impact_score, baseline_source, has_baseline=True)
            # If non-content changes happened in the same window, we can't
            # honestly attribute the traffic move to the content edit. Downgrade
            # clear verdicts to "inconclusive" — but keep the impact score so
            # the card can still show the magnitude of the traffic change.
            if overlaps and verdict in ("positive", "negative", "mixed"):
                verdict = "inconclusive"
        elif before_snap and not after_snap:
            # Baseline exists but verdict window hasn't elapsed yet
            verdict = "pending"
            elapsed = (now - opt_date_naive).days
            days_until_verdict = max(0, verdict_lag_days - elapsed)
        else:
            verdict = "no_baseline"

        counts[verdict] = counts.get(verdict, 0) + 1
        if sales_flag in sales_counts:
            sales_counts[sales_flag] += 1

        result = {
            "product_id": pid,
            "title": product.title,
            "handle": product.handle,
            "product_type": product.product_type,
            "optimized_at": opt.last_optimized.isoformat() if opt.last_optimized else None,
            "generation_count": opt.generation_count,
            "llm_used": latest_gen.llm_used if latest_gen else None,
            "verdict": verdict,
            "baseline_source": baseline_source if before_snap else None,
            "days_until_verdict": days_until_verdict,
            "real_impact_score": impact_score,
            "sales_flag": sales_flag,
            "overlaps": overlaps,
            "current": {
                "seo_score": product.seo_score,
                "gsc_position": product.gsc_position,
                "gsc_impressions": product.gsc_impressions,
                "gsc_clicks": product.gsc_clicks,
                "gsc_ctr": product.gsc_ctr,
                "ga4_sessions": product.ga4_sessions,
                "sold_30d": product.sold_30d,
                "revenue_30d": product.revenue_30d,
                "sold_90d": product.sold_90d,
                "revenue_90d": product.revenue_90d,
                "sold_365d": product.sold_365d,
                "revenue_365d": product.revenue_365d,
            },
            "before": _snap_dict(before_snap),
            "after": _snap_dict(after_snap),
            "deltas": deltas,
        }
        results.append(result)

    # Sort: show clear regressions first (red flag), then neutrals, then wins.
    # Within each bucket, bigger impact magnitude (positive or negative) bubbles up.
    def _sort_key(r):
        verdict_order = {
            "negative": 0,       # regressions scream loudest
            "inconclusive": 1,   # attribution unclear — needs human review
            "mixed": 2,
            "tracked_only": 3,
            "neutral": 4,
            "positive": 5,
            "pending": 6,
            "no_baseline": 7,
        }
        impact = r.get("real_impact_score") or 0
        # Within a bucket, rank by magnitude of change so the worst regressions
        # and biggest wins both surface near the top of their section
        return (verdict_order.get(r["verdict"], 99), -abs(impact))

    results.sort(key=_sort_key)

    response = {
        "days": days,
        "verdict_lag_days": verdict_lag_days,
        "soft_baseline_window_days": SOFT_BASELINE_WINDOW_DAYS,
        "total_optimized": len(results),
        "verdict_summary": counts,
        "sales_summary": sales_counts,
        "products": results
    }
    cache.set(cache_key, response, ttl=300)
    return response


@router.get("/snapshots/{product_id}")
async def get_product_snapshots(
    product_id: str,
    days: int = Query(30, ge=1, le=365, description="Days of history to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get historical analytics snapshots for a specific product.
    
    Returns daily snapshot data ordered by date (oldest first) for trend sparklines,
    before/after comparisons, and the product optimization timeline.
    """
    from app.models.product import ProductAnalyticsSnapshot, Product
    from datetime import timedelta
    
    # Verify product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    snapshots = db.query(ProductAnalyticsSnapshot)\
        .filter(ProductAnalyticsSnapshot.product_id == product_id)\
        .filter(ProductAnalyticsSnapshot.snapshot_date >= cutoff)\
        .order_by(ProductAnalyticsSnapshot.snapshot_date.asc())\
        .all()
    
    return {
        "product_id": product_id,
        "product_title": product.title,
        "days": days,
        "snapshot_count": len(snapshots),
        "snapshots": [
            {
                "id": s.id,
                "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                "seo_score": s.seo_score,
                "performance_score": s.performance_score,
                "gsc_impressions": s.gsc_impressions,
                "gsc_clicks": s.gsc_clicks,
                "gsc_ctr": s.gsc_ctr,
                "gsc_position": s.gsc_position,
                "gsc_top_queries": s.gsc_top_queries or [],
                "ga4_sessions": s.ga4_sessions,
                "ga4_bounce_rate": s.ga4_bounce_rate,
                "ga4_revenue": s.ga4_revenue,
                "sold_30d": s.sold_30d,
                "revenue_30d": s.revenue_30d,
                "sold_90d": s.sold_90d,
                "revenue_90d": s.revenue_90d,
                "sold_365d": s.sold_365d,
                "revenue_365d": s.revenue_365d,
                "ai_visibility_score": s.ai_visibility_score,
                # Shopify product state (overlap detection source)
                "price": s.price,
                "inventory_quantity": s.inventory_quantity,
                "image_count": s.image_count,
                "description_length": s.description_length,
            }
            for s in snapshots
        ]
    }



@router.delete("/snapshots/cleanup")
async def cleanup_old_snapshots(
    days_to_keep: int = Query(90, ge=30, le=365, description="Days of snapshots to keep"),
    db: Session = Depends(get_db)
):
    """
    Delete old analytics snapshots to save disk space.
    
    Default: keeps last 90 days.
    """
    from app.jobs.analytics_snapshot import cleanup_old_snapshots as do_cleanup
    
    result = do_cleanup(days_to_keep=days_to_keep, db=db)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result



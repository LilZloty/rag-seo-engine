"""
SEO Intelligence API Endpoints
Semrush-level keyword tracking, CTR optimization, alerts, and funnel analytics.

All endpoints under /api/v1/seo-intelligence/
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc
from typing import List, Optional
from datetime import datetime, timedelta, date

from app.db.session import get_db
from app.services.seo_intelligence.daily_collector import DailyCollector
from app.services.seo_intelligence.alert_service import AlertService
from app.models.seo_intelligence import (
    KeywordDailyMetric, PageDailyMetric, KeywordPageMapping,
    GA4FunnelDaily, SEOAlert,
    # Pydantic response schemas
    KeywordMetricResponse, KeywordTrendResponse, CTRUnderperformerResponse,
    CTRSummaryResponse, PositionSummaryResponse, MoversAndShakersResponse,
    CannibalizationResponse, GA4FunnelResponse, SEOAlertResponse,
    AlertSummaryResponse, CollectionStatusResponse, ProductROIResponse,
)

router = APIRouter(prefix="/seo-intelligence", tags=["SEO Intelligence"])


# ============================================================================
# DAILY COLLECTOR ENDPOINTS
# ============================================================================

@router.post("/collect", response_model=CollectionStatusResponse)
def trigger_daily_collection(db: Session = Depends(get_db)):
    """
    Trigger the daily SEO intelligence data collection.
    
    Harvests GSC queries, page data, GA4 funnel, computes deltas,
    CTR benchmarks, cannibalization detection, and generates alerts.
    
    Typically triggered by cron at 06:00 UTC:
        curl -X POST http://localhost:8000/api/v1/seo-intelligence/collect
    """
    import traceback
    try:
        collector = DailyCollector(db)
        result = collector.run_daily_harvest()
        
        # Also run alert generation
        alert_service = AlertService(db)
        alerts_count = alert_service.generate_alerts()
        result["alerts_generated"] = alerts_count
        
        db.commit()
        return CollectionStatusResponse(**result)
    except Exception as e:
        db.rollback()
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[COLLECT ERROR] {error_detail}")
        return CollectionStatusResponse(
            status="error",
            error=str(e),
            harvested_at=datetime.utcnow().isoformat()
        )


@router.get("/collect/status", response_model=CollectionStatusResponse)
def get_collection_status(db: Session = Depends(get_db)):
    """
    Get the status of the last daily collection run.
    Returns the date and counts of the most recent harvest.
    """
    # Find the most recent harvest date
    latest = db.query(
        KeywordDailyMetric.date,
        sql_func.count(KeywordDailyMetric.id).label('count')
    ).group_by(
        KeywordDailyMetric.date
    ).order_by(
        desc(KeywordDailyMetric.date)
    ).first()
    
    if not latest:
        return CollectionStatusResponse(
            status="no_data",
            harvested_at="never"
        )
    
    latest_date = latest.date
    
    # Count records for that date
    queries = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.date == latest_date
    ).count()
    
    mappings = db.query(KeywordPageMapping).filter(
        KeywordPageMapping.date == latest_date
    ).count()
    
    pages = db.query(PageDailyMetric).filter(
        PageDailyMetric.date == latest_date
    ).count()
    
    funnel = db.query(GA4FunnelDaily).filter(
        GA4FunnelDaily.date == latest_date
    ).count()
    
    return CollectionStatusResponse(
        queries_stored=queries,
        mappings_stored=mappings,
        pages_stored=pages,
        funnel_days_stored=funnel,
        harvested_at=latest_date.isoformat(),
        status="success"
    )


@router.post("/cleanup")
def trigger_cleanup(
    days_to_keep: int = Query(default=90, description="Days of data to retain"),
    db: Session = Depends(get_db)
):
    """
    Clean up old historical data. Run weekly.
    Default: keep 90 days of keyword/page metrics, 30 days of mappings.
    """
    collector = DailyCollector(db)
    result = collector.cleanup_old_data(days_to_keep=days_to_keep)
    return {"status": "success", "deleted": result}


@router.get("/diagnostics/data-range")
def get_data_range(db: Session = Depends(get_db)):
    """
    Check what date range is available in the database.
    Helps debug why different time periods show the same data.
    """
    from sqlalchemy import func as sql_func
    
    # Get date range for keywords
    keyword_dates = db.query(
        sql_func.min(KeywordDailyMetric.date).label('min_date'),
        sql_func.max(KeywordDailyMetric.date).label('max_date'),
        sql_func.count(sql_func.distinct(KeywordDailyMetric.date)).label('unique_dates')
    ).first()
    
    # Get list of all unique dates
    all_dates = db.query(
        sql_func.distinct(KeywordDailyMetric.date)
    ).order_by(KeywordDailyMetric.date).all()
    
    # Get funnel data info
    funnel_dates = db.query(
        sql_func.min(GA4FunnelDaily.date).label('min_date'),
        sql_func.max(GA4FunnelDaily.date).label('max_date'),
        sql_func.count(sql_func.distinct(GA4FunnelDaily.date)).label('unique_dates')
    ).first()
    
    # Sample funnel data
    sample_funnel = db.query(GA4FunnelDaily).order_by(GA4FunnelDaily.date.desc()).limit(1).first()
    
    return {
        "keyword_data": {
            "earliest_date": str(keyword_dates.min_date) if keyword_dates and keyword_dates.min_date else None,
            "latest_date": str(keyword_dates.max_date) if keyword_dates and keyword_dates.max_date else None,
            "unique_date_count": keyword_dates.unique_dates if keyword_dates else 0,
            "all_dates": [str(d[0]) for d in all_dates]
        },
        "funnel_data": {
            "earliest_date": str(funnel_dates.min_date) if funnel_dates and funnel_dates.min_date else None,
            "latest_date": str(funnel_dates.max_date) if funnel_dates and funnel_dates.max_date else None,
            "unique_date_count": funnel_dates.unique_dates if funnel_dates else 0,
            "latest_sample": {
                "date": str(sample_funnel.date) if sample_funnel else None,
                "device": sample_funnel.device_category if sample_funnel else None,
                "sessions": sample_funnel.sessions if sample_funnel else 0,
                "product_views": sample_funnel.product_views if sample_funnel else 0,
                "add_to_carts": sample_funnel.add_to_carts if sample_funnel else 0,
                "begin_checkouts": sample_funnel.begin_checkouts if sample_funnel else 0,
                "purchases": sample_funnel.purchases if sample_funnel else 0,
                "revenue": float(sample_funnel.revenue) if sample_funnel else 0,
            } if sample_funnel else None
        }
    }


@router.post("/diagnostics/test-collection")
def test_collection_directly(db: Session = Depends(get_db)):
    """
    Directly test the GA4 funnel collection and return detailed debug output.
    This runs the collection logic without storing to see what GA4 returns.
    """
    from app.services.google_api_service import GoogleAPIService
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest, FilterExpression, Filter
    )
    from datetime import datetime, timedelta
    
    google = GoogleAPIService()
    
    if not google.credentials or not google.property_id:
        return {"error": "GA4 not configured"}
    
    client = BetaAnalyticsDataClient(credentials=google.credentials)
    target_date = (datetime.now() - timedelta(days=1)).date()
    
    results = {
        "target_date": str(target_date),
        "property_id": google.property_id,
        "ecommerce_metrics": {},
        "event_metrics": {},
        "combined_result": {}
    }
    
    # Test 1: Ecommerce metrics
    try:
        request = RunReportRequest(
            property=f"properties/{google.property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="ecommerce:itemsViewed"),
                Metric(name="ecommerce:itemsAddedToCart"),
                Metric(name="ecommerce:itemsCheckedOut"),
                Metric(name="ecommerce:itemsPurchased"),
                Metric(name="purchaseRevenue"),
            ],
            date_ranges=[DateRange(start_date=str(target_date), end_date=str(target_date))]
        )
        response = client.run_report(request)
        
        results["ecommerce_metrics"]["status"] = "success"
        results["ecommerce_metrics"]["rows"] = []
        
        total_sessions = 0
        total_views = 0
        total_add_carts = 0
        total_checkouts = 0
        total_purchases = 0
        total_revenue = 0.0
        
        for row in response.rows:
            device = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            add_carts = int(row.metric_values[2].value)
            checkouts = int(row.metric_values[3].value)
            purchases = int(row.metric_values[4].value)
            revenue = float(row.metric_values[5].value)
            
            total_sessions += sessions
            total_views += views
            total_add_carts += add_carts
            total_checkouts += checkouts
            total_purchases += purchases
            total_revenue += revenue
            
            results["ecommerce_metrics"]["rows"].append({
                "device": device,
                "sessions": sessions,
                "views": views,
                "add_carts": add_carts,
                "checkouts": checkouts,
                "purchases": purchases,
                "revenue": revenue
            })
        
        results["ecommerce_metrics"]["totals"] = {
            "sessions": total_sessions,
            "views": total_views,
            "add_carts": total_add_carts,
            "checkouts": total_checkouts,
            "purchases": total_purchases,
            "revenue": total_revenue
        }
    except Exception as e:
        results["ecommerce_metrics"]["status"] = "error"
        results["ecommerce_metrics"]["error"] = str(e)
    
    # Test 2: Event-based metrics
    event_names = ['view_item', 'add_to_cart', 'begin_checkout', 'purchase']
    for event_name in event_names:
        try:
            event_request = RunReportRequest(
                property=f"properties/{google.property_id}",
                dimensions=[Dimension(name="deviceCategory")],
                metrics=[Metric(name="eventCount")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="eventName",
                        string_filter=Filter.StringFilter(value=event_name)
                    )
                ),
                date_ranges=[DateRange(start_date=str(target_date), end_date=str(target_date))]
            )
            event_response = client.run_report(event_request)
            total = sum(int(row.metric_values[0].value) for row in event_response.rows) if event_response.rows else 0
            results["event_metrics"][event_name] = {
                "status": "success",
                "total": total
            }
        except Exception as e:
            results["event_metrics"][event_name] = {
                "status": "error",
                "error": str(e)
            }
    
    # Test 3: What the collector would use
    eco_totals = results["ecommerce_metrics"].get("totals", {})
    use_events = (eco_totals.get("add_carts", 0) == 0 and 
                  results["event_metrics"].get("add_to_cart", {}).get("total", 0) > 0)
    
    results["combined_result"] = {
        "use_event_fallback": use_events,
        "final_add_to_carts": results["event_metrics"].get("add_to_cart", {}).get("total", 0) if use_events else eco_totals.get("add_carts", 0),
        "final_checkouts": results["event_metrics"].get("begin_checkout", {}).get("total", 0) if use_events else eco_totals.get("checkouts", 0),
        "final_purchases": eco_totals.get("purchases", 0),
        "final_revenue": eco_totals.get("revenue", 0)
    }
    
    return results


@router.get("/diagnostics/ga4")
def test_ga4_connection():
    """
    Test GA4 connection and return diagnostic information.
    Helps troubleshoot why funnel data isn't being collected.
    """
    from app.services.google_api_service import GoogleAPIService
    from app.core.config import settings
    import os
    
    results = {
        "credentials_path": settings.GOOGLE_APPLICATION_CREDENTIALS,
        "credentials_exist": os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS or ""),
        "ga4_property_id": settings.GOOGLE_GA4_PROPERTY_ID,
        "credentials_loaded": False,
        "property_accessible": False,
        "sample_data": None,
        "ecommerce_metrics": {},
        "error": None
    }
    
    try:
        google = GoogleAPIService()
        results["credentials_loaded"] = google.credentials is not None
        results["property_id"] = google.property_id
        
        if google.credentials and google.property_id:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest, Dimension
            
            client = BetaAnalyticsDataClient(credentials=google.credentials)
            
            # Test basic connection
            request = RunReportRequest(
                property=f"properties/{google.property_id}",
                metrics=[Metric(name="sessions")],
                date_ranges=[DateRange(start_date="7daysAgo", end_date="today")]
            )
            response = client.run_report(request)
            results["property_accessible"] = True
            results["sample_data"] = {
                "rows": len(response.rows),
                "sessions": int(response.rows[0].metric_values[0].value) if response.rows else 0
            }
            
            # Test each ecommerce metric individually
            ecommerce_metrics = [
                ("sessions", "Sessions"),
                ("ecommerce:itemsViewed", "Product Views"),
                ("ecommerce:itemsAddedToCart", "Add to Cart"),
                ("ecommerce:itemsCheckedOut", "Checkout"),
                ("ecommerce:itemsPurchased", "Purchases"),
                ("purchaseRevenue", "Revenue"),
            ]
            
            for metric_name, label in ecommerce_metrics:
                try:
                    test_request = RunReportRequest(
                        property=f"properties/{google.property_id}",
                        dimensions=[Dimension(name="deviceCategory")],
                        metrics=[Metric(name=metric_name)],
                        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")]
                    )
                    test_response = client.run_report(test_request)
                    total_value = sum(int(row.metric_values[0].value) for row in test_response.rows) if test_response.rows else 0
                    results["ecommerce_metrics"][metric_name] = {
                        "status": "available",
                        "label": label,
                        "7_day_total": total_value
                    }
                except Exception as metric_error:
                    results["ecommerce_metrics"][metric_name] = {
                        "status": "error",
                        "label": label,
                        "error": str(metric_error)
                    }
    except Exception as e:
        results["error"] = str(e)
    
    return results


# ============================================================================
# KEYWORD POSITION TRACKER ENDPOINTS
# ============================================================================

@router.get("/keywords", response_model=List[KeywordMetricResponse])
def get_tracked_keywords(
    days: int = Query(default=7, description="Number of days to look back"),
    min_impressions: int = Query(default=10, description="Minimum impressions filter"),
    limit: int = Query(default=100, description="Maximum results"),
    sort_by: str = Query(default="impressions", description="Sort field: impressions, clicks, position, ctr"),
    db: Session = Depends(get_db)
):
    """
    Get all tracked keywords with their latest metrics and trends.
    Returns aggregated data over the specified date range.
    """
    # Find the latest date we have data for
    latest_date = db.query(
        sql_func.max(KeywordDailyMetric.date)
    ).scalar()
    
    print(f"[DEBUG /keywords] days={days}, latest_date={latest_date}")
    
    if not latest_date:
        return []
    
    # Calculate the start date based on days parameter
    since = latest_date - timedelta(days=days)
    
    print(f"[DEBUG /keywords] since={since}, filtering date >= {since}")
    
    # Aggregate data over the date range - sum impressions/clicks, avg position
    query = db.query(
        KeywordDailyMetric.query,
        sql_func.sum(KeywordDailyMetric.impressions).label('total_impressions'),
        sql_func.sum(KeywordDailyMetric.clicks).label('total_clicks'),
        sql_func.avg(KeywordDailyMetric.position).label('avg_position'),
        sql_func.max(KeywordDailyMetric.date).label('latest_date'),
        # Get the most recent change values
        sql_func.max(KeywordDailyMetric.position_change_7d).label('position_change_7d'),
        sql_func.max(KeywordDailyMetric.position_change_30d).label('position_change_30d'),
        sql_func.max(KeywordDailyMetric.ctr_change_7d).label('ctr_change_7d'),
        sql_func.max(KeywordDailyMetric.expected_ctr).label('expected_ctr'),
        sql_func.max(KeywordDailyMetric.ctr_gap).label('ctr_gap'),
        sql_func.max(KeywordDailyMetric.is_underperforming).label('is_underperforming'),
    ).filter(
        KeywordDailyMetric.date >= since,
        KeywordDailyMetric.impressions >= min_impressions
    ).group_by(KeywordDailyMetric.query)
    
    # Sort by aggregated columns
    sort_map = {
        "impressions": desc('total_impressions'),
        "clicks": desc('total_clicks'),
        "position": 'avg_position',  # Lower position = better
    }
    if sort_by in sort_map:
        query = query.order_by(sort_map[sort_by])
    else:
        query = query.order_by(desc('total_impressions'))
    
    records = query.limit(limit).all()
    
    return [
        KeywordMetricResponse(
            query=r.query,
            date=r.latest_date,
            clicks=r.total_clicks or 0,
            impressions=r.total_impressions or 0,
            ctr=(r.total_clicks / r.total_impressions) if r.total_impressions else 0.0,
            position=r.avg_position or 0.0,
            position_change_7d=r.position_change_7d,
            position_change_30d=r.position_change_30d,
            ctr_change_7d=r.ctr_change_7d,
            impressions_change_7d=None,
            expected_ctr=r.expected_ctr,
            ctr_gap=r.ctr_gap,
            is_underperforming=bool(r.is_underperforming) if r.is_underperforming else False,
        )
        for r in records
    ]


@router.get("/keywords/{query_text}", response_model=List[KeywordMetricResponse])
def get_keyword_history(
    query_text: str,
    days: int = Query(default=30, description="Number of days of history"),
    db: Session = Depends(get_db)
):
    """
    Get daily position/CTR history for a specific keyword.
    Returns data points for trend chart (sparklines).
    """
    since = date.today() - timedelta(days=days)
    
    records = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.query == query_text,
        KeywordDailyMetric.date >= since
    ).order_by(
        KeywordDailyMetric.date
    ).all()
    
    return [
        KeywordMetricResponse(
            query=r.query,
            date=r.date,
            clicks=r.clicks,
            impressions=r.impressions,
            ctr=r.ctr,
            position=r.position,
            position_change_7d=r.position_change_7d,
            position_change_30d=r.position_change_30d,
            ctr_change_7d=r.ctr_change_7d,
            impressions_change_7d=r.impressions_change_7d,
            expected_ctr=r.expected_ctr,
            ctr_gap=r.ctr_gap,
            is_underperforming=r.is_underperforming or False,
        )
        for r in records
    ]


@router.get("/keywords/movers/shakers", response_model=MoversAndShakersResponse)
def get_movers_and_shakers(
    days: int = Query(default=7, description="Lookback period"),
    limit: int = Query(default=20, description="Results per category"),
    db: Session = Depends(get_db)
):
    """
    Biggest position gainers and losers in the last N days.
    """
    latest_date = db.query(sql_func.max(KeywordDailyMetric.date)).scalar()
    if not latest_date:
        return MoversAndShakersResponse()
    
    # Biggest gains (position_change_7d is most negative = biggest improvement)
    gains = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.date == latest_date,
        KeywordDailyMetric.position_change_7d != None,
        KeywordDailyMetric.position_change_7d < 0,  # Improved
        KeywordDailyMetric.impressions >= 20
    ).order_by(
        KeywordDailyMetric.position_change_7d  # Most negative first
    ).limit(limit).all()
    
    # Biggest losses (position_change_7d is most positive = biggest drop)
    losses = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.date == latest_date,
        KeywordDailyMetric.position_change_7d != None,
        KeywordDailyMetric.position_change_7d > 0,  # Worsened
        KeywordDailyMetric.impressions >= 20
    ).order_by(
        desc(KeywordDailyMetric.position_change_7d)  # Most positive first
    ).limit(limit).all()
    
    return MoversAndShakersResponse(
        biggest_gains=[
            {
                "query": r.query,
                "change": r.position_change_7d,
                "from_position": r.position - r.position_change_7d,
                "to_position": r.position,
                "impressions": r.impressions
            }
            for r in gains
        ],
        biggest_losses=[
            {
                "query": r.query,
                "change": r.position_change_7d,
                "from_position": r.position - r.position_change_7d,
                "to_position": r.position,
                "impressions": r.impressions
            }
            for r in losses
        ]
    )


@router.get("/keywords/summary", response_model=PositionSummaryResponse)
def get_position_summary(
    days: int = Query(default=7, description="Lookback period for position changes"),
    db: Session = Depends(get_db)
):
    """
    Summary of all tracked keyword positions: total, improving, stable, declining.
    """
    latest_date = db.query(sql_func.max(KeywordDailyMetric.date)).scalar()
    if not latest_date:
        return PositionSummaryResponse()
    
    records = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.date == latest_date,
        KeywordDailyMetric.impressions >= 10
    ).all()
    
    total = len(records)
    
    # Use the appropriate change field based on days
    if days <= 7:
        change_field = 'position_change_7d'
    elif days <= 30:
        change_field = 'position_change_30d'
    else:
        change_field = 'position_change_30d'  # Fallback to 30d for 90d
    
    improving = sum(1 for r in records if getattr(r, change_field, None) is not None and getattr(r, change_field) < -0.5)
    declining = sum(1 for r in records if getattr(r, change_field, None) is not None and getattr(r, change_field) > 0.5)
    stable = total - improving - declining
    
    # New in top 10 (position <= 10 and change was significant improvement)
    new_top10 = sum(
        1 for r in records 
        if r.position <= 10 
        and getattr(r, change_field, None) is not None 
        and getattr(r, change_field) < -3
        and (r.position - getattr(r, change_field)) > 10
    )
    
    # Lost from top 10
    lost_top10 = sum(
        1 for r in records
        if r.position > 10
        and getattr(r, change_field, None) is not None
        and getattr(r, change_field) > 3
        and (r.position - getattr(r, change_field)) <= 10
    )
    
    return PositionSummaryResponse(
        total_tracked=total,
        improving=improving,
        stable=stable,
        declining=declining,
        new_in_top_10=new_top10,
        lost_from_top_10=lost_top10,
    )


# ============================================================================
# CTR OPTIMIZER ENDPOINTS
# ============================================================================

@router.get("/ctr/underperformers", response_model=List[CTRUnderperformerResponse])
def get_ctr_underperformers(
    min_impressions: int = Query(default=50, description="Minimum impressions"),
    min_ctr_gap: float = Query(default=-0.01, description="Minimum CTR gap (negative)"),
    limit: int = Query(default=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Get queries where actual CTR is below position-based benchmark.
    These are the highest-ROI optimization opportunities.
    """
    latest_date = db.query(sql_func.max(KeywordDailyMetric.date)).scalar()
    if not latest_date:
        return []
    
    records = db.query(KeywordDailyMetric).filter(
        KeywordDailyMetric.date == latest_date,
        KeywordDailyMetric.is_underperforming == True,
        KeywordDailyMetric.impressions >= min_impressions,
        KeywordDailyMetric.ctr_gap != None,
        KeywordDailyMetric.ctr_gap <= min_ctr_gap,
    ).order_by(
        KeywordDailyMetric.ctr_gap  # Most underperforming first
    ).limit(limit).all()
    
    # Try to find page URLs from mappings
    query_page_map = {}
    if records:
        query_list = [r.query for r in records]
        mappings = db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date == latest_date,
            KeywordPageMapping.query.in_(query_list)
        ).order_by(desc(KeywordPageMapping.clicks)).all()
        
        for m in mappings:
            if m.query not in query_page_map:
                query_page_map[m.query] = m.page_url
    
    results = []
    for r in records:
        potential_clicks = int(
            r.impressions * abs(r.ctr_gap)
        ) if r.ctr_gap else 0
        
        results.append(CTRUnderperformerResponse(
            query=r.query,
            position=r.position,
            actual_ctr=r.ctr,
            expected_ctr=r.expected_ctr or 0.0,
            ctr_gap=r.ctr_gap or 0.0,
            impressions=r.impressions,
            potential_extra_clicks=potential_clicks,
            page_url=query_page_map.get(r.query),
        ))
    
    return results


@router.get("/ctr/summary", response_model=CTRSummaryResponse)
def get_ctr_summary(
    days: int = Query(default=7, description="Lookback period for CTR analysis"),
    db: Session = Depends(get_db)
):
    """
    Dashboard summary for CTR optimization.
    Total underperformers, potential clicks, breakdown by position bucket.
    Aggregated over the specified date range.
    """
    latest_date = db.query(sql_func.max(KeywordDailyMetric.date)).scalar()
    if not latest_date:
        return CTRSummaryResponse()
    
    # Calculate date range
    since = latest_date - timedelta(days=days)
    
    # Aggregate underperformers over the date range
    underperformers = db.query(
        KeywordDailyMetric.query,
        sql_func.sum(KeywordDailyMetric.impressions).label('total_impressions'),
        sql_func.avg(KeywordDailyMetric.position).label('avg_position'),
        sql_func.max(KeywordDailyMetric.ctr_gap).label('ctr_gap'),
        sql_func.max(KeywordDailyMetric.expected_ctr).label('expected_ctr'),
    ).filter(
        KeywordDailyMetric.date >= since,
        KeywordDailyMetric.is_underperforming == True,
        KeywordDailyMetric.impressions >= 20,
    ).group_by(KeywordDailyMetric.query).all()
    
    total = len(underperformers)
    total_potential = sum(
        int(r.total_impressions * abs(r.ctr_gap)) for r in underperformers if r.ctr_gap
    )
    avg_gap = (
        sum(r.ctr_gap for r in underperformers if r.ctr_gap) / total 
        if total > 0 else 0.0
    )
    
    # Bucket by position
    buckets = {"1-3": [], "4-10": [], "11-20": [], "21+": []}
    for r in underperformers:
        if r.avg_position <= 3:
            buckets["1-3"].append(r)
        elif r.avg_position <= 10:
            buckets["4-10"].append(r)
        elif r.avg_position <= 20:
            buckets["11-20"].append(r)
        else:
            buckets["21+"].append(r)
    
    by_position_bucket = {}
    for bucket_name, items in buckets.items():
        by_position_bucket[bucket_name] = {
            "count": len(items),
            "avg_gap": (
                sum(r.ctr_gap for r in items if r.ctr_gap) / len(items)
                if items else 0.0
            ),
            "total_potential_clicks": sum(
                int(r.total_impressions * abs(r.ctr_gap)) for r in items if r.ctr_gap
            )
        }
    
    # Top 10 opportunities
    top = sorted(
        underperformers,
        key=lambda r: r.total_impressions * abs(r.ctr_gap) if r.ctr_gap else 0,
        reverse=True
    )[:10]
    
    return CTRSummaryResponse(
        total_underperforming=total,
        total_potential_clicks=total_potential,
        avg_ctr_gap=avg_gap,
        top_opportunities=[
            CTRUnderperformerResponse(
                query=r.query,
                position=r.avg_position or 0.0,
                actual_ctr=(r.expected_ctr or 0.0) - (r.ctr_gap or 0.0) if r.expected_ctr and r.ctr_gap else 0.0,
                expected_ctr=r.expected_ctr or 0.0,
                ctr_gap=r.ctr_gap or 0.0,
                impressions=r.total_impressions or 0,
                potential_extra_clicks=int(r.total_impressions * abs(r.ctr_gap)) if r.ctr_gap and r.total_impressions else 0,
            )
            for r in top
        ],
        by_position_bucket=by_position_bucket,
    )


# ============================================================================
# CANNIBALIZATION ENDPOINTS
# ============================================================================

@router.get("/cannibalization", response_model=List[CannibalizationResponse])
def get_cannibalized_queries(
    min_impressions: int = Query(default=20, description="Minimum total impressions"),
    limit: int = Query(default=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Get all queries where multiple pages compete for the same keyword.
    """
    latest_date = db.query(sql_func.max(KeywordPageMapping.date)).scalar()
    if not latest_date:
        return []
    
    # Find cannibalized queries
    cannibalized = db.query(
        KeywordPageMapping.query,
        sql_func.count(sql_func.distinct(KeywordPageMapping.page_url)).label('page_count'),
        sql_func.sum(KeywordPageMapping.impressions).label('total_impressions'),
    ).filter(
        KeywordPageMapping.date == latest_date,
        KeywordPageMapping.is_cannibalized == True,
    ).group_by(
        KeywordPageMapping.query
    ).having(
        sql_func.sum(KeywordPageMapping.impressions) >= min_impressions
    ).order_by(
        desc('total_impressions')
    ).limit(limit).all()
    
    results = []
    for row in cannibalized:
        # Get the competing pages for this query
        pages = db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date == latest_date,
            KeywordPageMapping.query == row.query
        ).order_by(desc(KeywordPageMapping.clicks)).all()
        
        results.append(CannibalizationResponse(
            query=row.query,
            pages=[
                {
                    "page_url": p.page_url,
                    "clicks": p.clicks,
                    "impressions": p.impressions,
                    "ctr": p.ctr,
                    "position": p.position,
                }
                for p in pages
            ],
            total_impressions=row.total_impressions,
            recommendation=(
                f"Consolidate {row.page_count} pages into one authoritative page, "
                f"or use canonical tags to signal the preferred URL."
            ),
        ))
    
    return results


# ============================================================================
# GA4 FUNNEL ENDPOINTS
# ============================================================================

@router.get("/funnel", response_model=List[GA4FunnelResponse])
def get_funnel_data(
    days: int = Query(default=30, description="Number of days"),
    device: str = Query(default="all", description="Device: all, mobile, desktop, tablet"),
    db: Session = Depends(get_db)
):
    """
    Real GA4 ecommerce funnel data (replaces the placeholder data
    in CROAnalyticsService._get_ga4_funnel).
    """
    since = date.today() - timedelta(days=days)
    
    query = db.query(GA4FunnelDaily).filter(
        GA4FunnelDaily.date >= since,
    )
    
    # Filter by device if not "all"
    if device != "all":
        query = query.filter(GA4FunnelDaily.device_category == device)
    
    query = query.order_by(GA4FunnelDaily.date)
    
    records = query.all()
    
    return [
        GA4FunnelResponse(
            date=r.date,
            device_category=r.device_category,
            sessions=r.sessions,
            product_views=r.product_views,
            add_to_carts=r.add_to_carts,
            begin_checkouts=r.begin_checkouts,
            purchases=r.purchases,
            revenue=r.revenue,
            view_rate=r.view_rate,
            cart_rate=r.cart_rate,
            checkout_rate=r.checkout_rate,
            purchase_rate=r.purchase_rate,
            overall_conversion=r.overall_conversion,
        )
        for r in records
    ]


@router.get("/funnel/by-device", response_model=List[GA4FunnelResponse])
def get_funnel_by_device(
    days: int = Query(default=7, description="Number of days to aggregate"),
    db: Session = Depends(get_db)
):
    """
    Funnel breakdown by device type (aggregated over days).
    """
    since = date.today() - timedelta(days=days)
    
    results = db.query(
        GA4FunnelDaily.device_category,
        sql_func.sum(GA4FunnelDaily.sessions).label('sessions'),
        sql_func.sum(GA4FunnelDaily.product_views).label('product_views'),
        sql_func.sum(GA4FunnelDaily.add_to_carts).label('add_to_carts'),
        sql_func.sum(GA4FunnelDaily.begin_checkouts).label('begin_checkouts'),
        sql_func.sum(GA4FunnelDaily.purchases).label('purchases'),
        sql_func.sum(GA4FunnelDaily.revenue).label('revenue'),
    ).filter(
        GA4FunnelDaily.date >= since,
        GA4FunnelDaily.device_category != 'all'
    ).group_by(
        GA4FunnelDaily.device_category
    ).all()
    
    response = []
    for r in results:
        sessions = r.sessions or 0
        views = r.product_views or 0
        carts = r.add_to_carts or 0
        checkouts = r.begin_checkouts or 0
        purchases = r.purchases or 0
        revenue = r.revenue or 0.0
        
        response.append(GA4FunnelResponse(
            date=since,  # aggregate date
            device_category=r.device_category,
            sessions=sessions,
            product_views=views,
            add_to_carts=carts,
            begin_checkouts=checkouts,
            purchases=purchases,
            revenue=revenue,
            view_rate=views / sessions if sessions > 0 else 0.0,
            cart_rate=carts / views if views > 0 else 0.0,
            checkout_rate=checkouts / carts if carts > 0 else 0.0,
            purchase_rate=purchases / checkouts if checkouts > 0 else 0.0,
            overall_conversion=purchases / sessions if sessions > 0 else 0.0,
        ))
    
    return response


# ============================================================================
# PRODUCT ROI ENDPOINTS
# ============================================================================

@router.get("/products/roi", response_model=List[ProductROIResponse])
def get_product_roi_ranking(
    days: int = Query(default=30, description="Number of days to aggregate"),
    min_impressions: int = Query(default=50, description="Minimum impressions"),
    limit: int = Query(default=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Products ranked by revenue per impression (ROI).
    Shows which products generate the most revenue relative to their SEO visibility.
    """
    from app.models.product import Product
    
    since = date.today() - timedelta(days=days)
    
    results = db.query(
        PageDailyMetric.page_url,
        PageDailyMetric.product_id,
        sql_func.sum(PageDailyMetric.gsc_impressions).label('total_impressions'),
        sql_func.sum(PageDailyMetric.gsc_clicks).label('total_clicks'),
        sql_func.sum(PageDailyMetric.ga4_revenue).label('total_revenue'),
        sql_func.sum(PageDailyMetric.ga4_sessions).label('total_sessions'),
        sql_func.sum(PageDailyMetric.ga4_purchases).label('total_purchases'),
    ).filter(
        PageDailyMetric.date >= since
    ).group_by(
        PageDailyMetric.page_url, PageDailyMetric.product_id
    ).having(
        sql_func.sum(PageDailyMetric.gsc_impressions) >= min_impressions
    ).all()
    
    # Get product titles
    product_titles = {}
    if results:
        product_ids = [r.product_id for r in results if r.product_id]
        if product_ids:
            products = db.query(Product.id, Product.title).filter(
                Product.id.in_(product_ids)
            ).all()
            product_titles = {p.id: p.title for p in products}
    
    response = []
    for r in results:
        impressions = r.total_impressions or 0
        clicks = r.total_clicks or 0
        revenue = r.total_revenue or 0.0
        
        response.append(ProductROIResponse(
            product_id=r.product_id,
            page_url=r.page_url,
            title=product_titles.get(r.product_id),
            gsc_impressions=impressions,
            gsc_clicks=clicks,
            ga4_revenue=revenue,
            revenue_per_impression=revenue / impressions if impressions > 0 else 0.0,
            revenue_per_click=revenue / clicks if clicks > 0 else 0.0,
            ga4_sessions=r.total_sessions or 0,
            ga4_purchases=r.total_purchases or 0,
        ))
    
    # Sort by revenue per impression descending
    response.sort(key=lambda x: x.revenue_per_impression, reverse=True)
    return response[:limit]


# ============================================================================
# ALERT ENDPOINTS
# ============================================================================

@router.get("/alerts", response_model=List[SEOAlertResponse])
def get_alerts(
    status: Optional[str] = Query(default=None, description="Filter: open, acknowledged, resolved, dismissed"),
    severity: Optional[str] = Query(default=None, description="Filter: critical, high, medium, low"),
    alert_type: Optional[str] = Query(default=None, description="Filter: position_drop, traffic_drop, ctr_drop, new_opportunity, cannibalization"),
    days: int = Query(default=30, description="Lookback period"),
    limit: int = Query(default=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Get SEO alerts with optional filtering.
    """
    alert_service = AlertService(db)
    alerts = alert_service.get_alerts(
        status=status,
        severity=severity,
        alert_type=alert_type,
        days=days,
        limit=limit
    )
    
    return [
        SEOAlertResponse(
            id=a.id,
            created_at=a.created_at,
            alert_type=a.alert_type,
            severity=a.severity,
            title=a.title,
            description=a.description,
            affected_query=a.affected_query,
            affected_page=a.affected_page,
            metric_before=a.metric_before,
            metric_after=a.metric_after,
            metric_change=a.metric_change,
            status=a.status,
        )
        for a in alerts
    ]


@router.get("/alerts/summary", response_model=AlertSummaryResponse)
def get_alert_summary(
    days: int = Query(default=30, description="Lookback period for alerts"),
    db: Session = Depends(get_db)
):
    """
    Alert dashboard summary: open count, by severity, by type, recent alerts.
    """
    alert_service = AlertService(db)
    summary = alert_service.get_alert_summary()
    
    return AlertSummaryResponse(
        open_alerts=summary["open_alerts"],
        by_severity=summary["by_severity"],
        by_type=summary["by_type"],
        recent=[
            SEOAlertResponse(
                id=a.id,
                created_at=a.created_at,
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                description=a.description,
                affected_query=a.affected_query,
                affected_page=a.affected_page,
                metric_before=a.metric_before,
                metric_after=a.metric_after,
                metric_change=a.metric_change,
                status=a.status,
            )
            for a in summary["recent"]
        ],
    )


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: str,
    status: str = Query(description="New status: acknowledged, resolved, dismissed"),
    notes: Optional[str] = Query(default=None, description="Resolution notes"),
    db: Session = Depends(get_db)
):
    """
    Update alert status (acknowledge, resolve, or dismiss).
    """
    alert_service = AlertService(db)
    alert = alert_service.update_alert_status(alert_id, status, notes)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.commit()
    return {"status": "updated", "alert_id": alert_id, "new_status": status}


# ============================================================================
# PRODUCT INSIGHTS — per-product cross-silo enrichment for queue cards
# ============================================================================

@router.get("/products/{product_id}/insights")
def get_product_insights_endpoint(product_id: str, db: Session = Depends(get_db)):
    """Cross-silo enrichment for a single product card.

    Returns:
      - `top_underperforming_queries`: queries this product ranks for that
        aren't clicking as well as their position deserves (CTR gap)
      - `position_trend_30d`: daily {date, position, impressions, clicks}
        for sparkline rendering
      - `cannibalization`: queries where another Example Store page is competing
        for the same SERP — pre-flagged by the SEO Intelligence daily harvest

    Called lazily by the OptimizationQueue when the user expands a card.
    Returns 404 if the product doesn't exist.
    """
    from app.services.product_insights import get_product_insights

    result = get_product_insights(db, product_id)
    if result.get("error") == "product_not_found":
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return result


# ============================================================================
# OPTIMIZATION QUEUE — top-N products ranked by priority_score
# ============================================================================

@router.get("/optimization-queue")
def get_optimization_queue(
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    db: Session = Depends(get_db),
):
    """Top products ranked by priority_score — replaces the dashboard's old
    heuristic Smart Recommendations panel.

    Each entry includes the full component breakdown so the UI can show:
      - projected click gain at the suggested target rank
      - revenue potential
      - trend (got worse over 30d?)
      - fixability flags (has images / in stock / convertible / has content)
      - confidence (GSC + GA4 sample sizes)
      - effort drivers (what needs doing)

    Sorted by priority_score DESC. Products with no priority_computed_at yet
    (haven't been through the nightly task) are excluded.
    """
    from app.models.product import Product as ProductModel
    from sqlalchemy import desc as sql_desc

    products = (
        db.query(ProductModel)
        .filter(ProductModel.priority_computed_at.isnot(None))
        .filter(ProductModel.priority_score >= min_score)
        .order_by(sql_desc(ProductModel.priority_score))
        .limit(limit)
        .all()
    )

    return {
        "limit": limit,
        "min_score": min_score,
        "count": len(products),
        "products": [
            {
                "id": p.id,
                "shopify_id": p.shopify_id,
                "title": p.title,
                "sku": p.sku,
                "handle": p.handle,
                "priority_score": p.priority_score,
                "priority_components": p.priority_components,
                "priority_computed_at": (
                    p.priority_computed_at.isoformat()
                    if p.priority_computed_at
                    else None
                ),
                # Current data for the queue card
                "gsc_impressions": p.gsc_impressions or 0,
                "gsc_position": p.gsc_position or 0,
                "ga4_sessions": p.ga4_sessions or 0,
                "revenue_90d": p.revenue_90d or 0,
                "seo_score": p.seo_score or 0,
                "image_count": p.image_count or 0,
                "inventory_status": p.inventory_status,
            }
            for p in products
        ],
    }


@router.post("/optimization-queue/recompute")
def recompute_optimization_queue(db: Session = Depends(get_db)):
    """Force a fresh priority_score recompute for every product.

    Normally runs nightly via Celery beat (07:45 America/Mexico_City). Call
    this after a big content push or to validate the formula.
    """
    from app.services.priority_score import compute_priority_scores_bulk

    return {"status": "refreshed", **compute_priority_scores_bulk(db)}


# ============================================================================
# CTR CURVE — opportunity sizing foundation
# ============================================================================

@router.get("/ctr-curve")
def get_ctr_curve_endpoint():
    """Return the current position→CTR curve used for opportunity sizing.

    `source` is `derived` when built from Example Store's own GSC history this week,
    or `industry_fallback_only` when no bucket had enough samples (cold cache
    or very early in the catalog's data life).

    Used by the priority-score pipeline and the SEO dashboard for showing
    "projected click gain" instead of the old `revenue × 0.25` heuristic.
    """
    from app.services.seo_opportunity import get_ctr_curve_with_meta
    return get_ctr_curve_with_meta()


@router.post("/ctr-curve/refresh")
def refresh_ctr_curve(db: Session = Depends(get_db)):
    """Force a fresh derivation of the CTR curve.

    Normally runs weekly via Celery beat (Monday 03:00 America/Mexico_City).
    Call this when GSC data has materially shifted, or for ad-hoc validation.
    """
    from app.services.seo_opportunity import build_and_cache_ctr_curve
    payload = build_and_cache_ctr_curve(db)
    return {
        "status": "refreshed",
        "source": payload["source"],
        "derived_from_count": payload["derived_from_count"],
        "fallback_positions": payload["fallback_positions"],
        "curve": payload["curve"],
        "sample_counts": payload["sample_counts"],
        "derived_at": payload["derived_at"],
    }

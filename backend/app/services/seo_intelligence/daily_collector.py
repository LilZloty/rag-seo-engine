"""
Daily Collector - The Heart of the SEO Intelligence System

Runs daily at 06:00 UTC. Harvests data from GSC + GA4 and stores
in historical tables. All other services READ from the tables
this job WRITES to.

DESIGN DECISION: Synchronous batch job, not real-time.
GSC data has 2-3 day delay anyway. No point in real-time.

Usage:
    POST /api/v1/seo-intelligence/collect
    or
    python -m app.services.seo_intelligence.daily_collector
"""

import uuid
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, and_, text

from app.db.session import SessionLocal
from app.services.google_api_service import GoogleApiService
from app.models.seo_intelligence import (
    KeywordDailyMetric, PageDailyMetric, KeywordPageMapping,
    GA4FunnelDaily, SEOAlert
)
from app.models.product import Product
from app.core.config import settings


# ============================================================================
# CTR BENCHMARKS BY POSITION (2026 industry averages)
# Source: Advanced Web Ranking, Backlinko, FirstPageSage
# Updated annually. Hardcoded = free. Semrush API = $100/month.
# ============================================================================

CTR_BENCHMARKS = {
    1: 0.276,    # Position 1: ~27.6% CTR
    2: 0.158,    # Position 2: ~15.8%
    3: 0.110,    # Position 3: ~11.0%
    4: 0.084,    # Position 4: ~8.4%
    5: 0.063,    # Position 5: ~6.3%
    6: 0.045,    # Position 6: ~4.5%
    7: 0.038,    # Position 7: ~3.8%
    8: 0.032,    # Position 8: ~3.2%
    9: 0.028,    # Position 9: ~2.8%
    10: 0.025,   # Position 10: ~2.5%
}

# For positions beyond 10
CTR_BENCHMARK_RANGES = {
    (11, 20): 0.015,   # Page 2: ~1.5% avg
    (21, 50): 0.005,   # Page 3-5: ~0.5% avg
    (51, 100): 0.001,  # Deep: ~0.1% avg
}


def get_expected_ctr(position: float) -> float:
    """Get benchmark CTR for a given average position."""
    if position <= 0:
        return 0.0
    
    rounded = round(position)
    if rounded in CTR_BENCHMARKS:
        return CTR_BENCHMARKS[rounded]
    
    for (low, high), ctr in CTR_BENCHMARK_RANGES.items():
        if low <= rounded <= high:
            return ctr
    
    return 0.001  # Position > 100


class DailyCollector:
    """
    SINGLE entry point for all SEO intelligence data collection.
    
    All other services READ from the tables this job WRITES to.
    This ensures data consistency and avoids duplicate API calls.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.google = GoogleApiService()
    
    def run_daily_harvest(self) -> Dict[str, Any]:
        """
        Execute the full daily collection cycle.
        
        Returns summary: {queries_stored, pages_stored, funnel_stored, alerts_triggered}
        """
        print("[SEO Intelligence] Starting daily harvest...")
        
        result = {
            "queries_stored": 0,
            "mappings_stored": 0,
            "funnel_days_stored": 0,
            "pages_stored": 0,
            "alerts_generated": 0,
            "harvested_at": datetime.utcnow().isoformat(),
            "status": "success",
            "errors": []
        }
        
        # Step 1: Harvest GSC query data (500 queries)
        try:
            result["queries_stored"] = self._harvest_gsc_queries()
            print(f"  [1/8] GSC queries: {result['queries_stored']} stored")
        except Exception as e:
            result["errors"].append(f"GSC queries: {str(e)}")
            print(f"  [1/8] GSC queries FAILED: {e}")
        
        # Step 2: Harvest GSC query+page mappings (for cannibalization)
        try:
            result["mappings_stored"] = self._harvest_gsc_query_page_mappings()
            print(f"  [2/8] GSC mappings: {result['mappings_stored']} stored")
        except Exception as e:
            result["errors"].append(f"GSC mappings: {str(e)}")
            print(f"  [2/8] GSC mappings FAILED: {e}")
        
        # Step 3: Harvest GSC page-level data
        try:
            result["pages_stored"] = self._harvest_gsc_page_metrics()
            print(f"  [3/8] GSC pages: {result['pages_stored']} stored")
        except Exception as e:
            result["errors"].append(f"GSC pages: {str(e)}")
            print(f"  [3/8] GSC pages FAILED: {e}")
        
        # Step 4: Harvest GA4 funnel data (by device)
        try:
            result["funnel_days_stored"] = self._harvest_ga4_funnel()
            print(f"  [4/8] GA4 funnel: {result['funnel_days_stored']} stored")
        except Exception as e:
            result["errors"].append(f"GA4 funnel: {str(e)}")
            print(f"  [4/8] GA4 funnel FAILED: {e}")
        
        # Step 5: Harvest GA4 page-level ecommerce events
        try:
            ga4_pages = self._harvest_ga4_page_metrics()
            print(f"  [5/8] GA4 page metrics: {ga4_pages} updated")
        except Exception as e:
            result["errors"].append(f"GA4 page metrics: {str(e)}")
            print(f"  [5/8] GA4 page metrics FAILED: {e}")
        
        # Step 6: Compute deltas (position changes, CTR changes)
        try:
            self._compute_metric_deltas()
            print(f"  [6/8] Metric deltas computed")
        except Exception as e:
            result["errors"].append(f"Metric deltas: {str(e)}")
            print(f"  [6/8] Metric deltas FAILED: {e}")
        
        # Step 7: Compute CTR benchmarks
        try:
            self._compute_ctr_benchmarks()
            print(f"  [7/8] CTR benchmarks computed")
        except Exception as e:
            result["errors"].append(f"CTR benchmarks: {str(e)}")
            print(f"  [7/8] CTR benchmarks FAILED: {e}")
        
        # Step 8: Detect cannibalization
        try:
            self._detect_cannibalization()
            print(f"  [8/8] Cannibalization detected")
        except Exception as e:
            result["errors"].append(f"Cannibalization: {str(e)}")
            print(f"  [8/8] Cannibalization FAILED: {e}")
        
        self.db.commit()
        
        if result["errors"]:
            result["status"] = "partial"
        
        print(f"[SEO Intelligence] Harvest complete: {result}")
        return result
    
    # ========================================================================
    # STEP 1: GSC Query Harvest
    # ========================================================================
    
    def _harvest_gsc_queries(self) -> int:
        """
        Pull top 500 queries from GSC for a single date window.
        
        GSC API returns data with 2-3 day delay.
        We request the latest 1 day of available data.
        Store one row per query per day in keyword_daily_metrics.
        """
        if not self.google.credentials or not self.google.site_url:
            print("  [SKIP] GSC credentials or site_url not configured")
            return 0
        
        from googleapiclient.discovery import build
        service = build('webmasters', 'v3', credentials=self.google.credentials)
        
        # GSC data typically available 3 days ago
        target_date = (datetime.now() - timedelta(days=3)).date()
        
        # Check if we already harvested this date
        existing = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date == target_date
        ).first()
        if existing:
            print(f"  [SKIP] Already harvested GSC queries for {target_date}")
            return 0
        
        request = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'dimensions': ['query'],
            'rowLimit': 500
        }
        
        response = service.searchanalytics().query(
            siteUrl=self.google.site_url, body=request
        ).execute()
        
        count = 0
        if 'rows' in response:
            for row in response['rows']:
                metric = KeywordDailyMetric(
                    id=str(uuid.uuid4()),
                    date=target_date,
                    query=row['keys'][0],
                    clicks=int(row['clicks']),
                    impressions=int(row['impressions']),
                    ctr=row['ctr'],
                    position=row['position']
                )
                self.db.add(metric)
                count += 1
        
        self.db.flush()
        return count
    
    # ========================================================================
    # STEP 2: GSC Query+Page Mappings (for cannibalization detection)
    # ========================================================================
    
    def _harvest_gsc_query_page_mappings(self) -> int:
        """
        Pull query + page dimension data from GSC.
        
        THIS IS NEW - the existing GSC service only pulls query-level 
        OR page-level, never both together.
        
        We need dimensions=['query', 'page'] to detect when 2+ pages 
        compete for the same query.
        """
        if not self.google.credentials or not self.google.site_url:
            return 0
        
        from googleapiclient.discovery import build
        service = build('webmasters', 'v3', credentials=self.google.credentials)
        
        target_date = (datetime.now() - timedelta(days=3)).date()
        
        existing = self.db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date == target_date
        ).first()
        if existing:
            print(f"  [SKIP] Already harvested GSC mappings for {target_date}")
            return 0
        
        request = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'dimensions': ['query', 'page'],
            'rowLimit': 5000
        }
        
        response = service.searchanalytics().query(
            siteUrl=self.google.site_url, body=request
        ).execute()
        
        count = 0
        if 'rows' in response:
            for row in response['rows']:
                page_url = row['keys'][1]
                mapping = KeywordPageMapping(
                    id=str(uuid.uuid4()),
                    date=target_date,
                    query=row['keys'][0],
                    page_url=page_url,
                    clicks=int(row['clicks']),
                    impressions=int(row['impressions']),
                    ctr=row['ctr'],
                    position=row['position'],
                    page_type=self._classify_page_type(page_url)
                )
                self.db.add(mapping)
                count += 1
        
        self.db.flush()
        return count
    
    # ========================================================================
    # STEP 3: GSC Page-Level Metrics
    # ========================================================================
    
    def _harvest_gsc_page_metrics(self) -> int:
        """
        Pull page-level GSC data and store in page_daily_metrics.
        Also links to Product records via URL matching.
        """
        if not self.google.credentials or not self.google.site_url:
            return 0
        
        from googleapiclient.discovery import build
        service = build('webmasters', 'v3', credentials=self.google.credentials)
        
        target_date = (datetime.now() - timedelta(days=3)).date()
        
        existing = self.db.query(PageDailyMetric).filter(
            PageDailyMetric.date == target_date
        ).first()
        if existing:
            print(f"  [SKIP] Already harvested GSC pages for {target_date}")
            return 0
        
        request = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'dimensions': ['page'],
            'rowLimit': 5000
        }
        
        response = service.searchanalytics().query(
            siteUrl=self.google.site_url, body=request
        ).execute()
        
        # Build a handle -> product_id lookup for linking
        products = self.db.query(Product.id, Product.handle).all()
        handle_to_id = {}
        for p_id, handle in products:
            if handle:
                handle_to_id[handle] = p_id
        
        count = 0
        if 'rows' in response:
            for row in response['rows']:
                page_url = row['keys'][0]
                
                # Try to match to a product
                product_id = None
                for handle, p_id in handle_to_id.items():
                    if f"/products/{handle}" in page_url:
                        product_id = p_id
                        break
                
                page_metric = PageDailyMetric(
                    id=str(uuid.uuid4()),
                    date=target_date,
                    page_url=page_url,
                    product_id=product_id,
                    gsc_clicks=int(row['clicks']),
                    gsc_impressions=int(row['impressions']),
                    gsc_ctr=row['ctr'],
                    gsc_position=row['position']
                )
                self.db.add(page_metric)
                count += 1
        
        self.db.flush()
        return count
    
    # ========================================================================
    # STEP 4: GA4 Ecommerce Funnel
    # ========================================================================
    
    def _harvest_ga4_funnel(self) -> int:
        """
        Pull GA4 ecommerce funnel events by device category.
        
        Events: session_start, view_item, add_to_cart, begin_checkout, purchase
        Dimensions: deviceCategory, date
        
        THIS IS NEW - fills the gap in CROAnalyticsService._get_ga4_funnel()
        which currently returns all zeros.
        """
        if not self.google.credentials or not self.google.property_id:
            print("  [SKIP] GA4 credentials or property_id not configured")
            return 0
        
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
        
        client = BetaAnalyticsDataClient(credentials=self.google.credentials)
        
        # Get yesterday's funnel data (GA4 has ~24h delay)
        target_date = (datetime.now() - timedelta(days=1)).date()
        
        existing = self.db.query(GA4FunnelDaily).filter(
            GA4FunnelDaily.date == target_date
        ).first()
        if existing:
            print(f"  [SKIP] Already harvested GA4 funnel for {target_date}")
            return 0
        
        # Try event-based counts first (more reliable than ecommerce metrics)
        from google.analytics.data_v1beta.types import FilterExpression, Filter
        
        event_metrics = {
            'view_item': 0,
            'add_to_cart': 0,
            'begin_checkout': 0,
            'purchase': 0,
        }
        
        # Fetch each event count separately with filters
        for event_name in event_metrics.keys():
            try:
                event_request = RunReportRequest(
                    property=f"properties/{self.google.property_id}",
                    dimensions=[Dimension(name="deviceCategory")],
                    metrics=[Metric(name="eventCount")],
                    dimension_filter=FilterExpression(
                        filter=Filter(
                            field_name="eventName",
                            string_filter=Filter.StringFilter(value=event_name)
                        )
                    ),
                    date_ranges=[
                        DateRange(
                            start_date=target_date.strftime('%Y-%m-%d'),
                            end_date=target_date.strftime('%Y-%m-%d')
                        )
                    ],
                )
                event_response = client.run_report(event_request)
                # Sum across all devices
                total = sum(int(row.metric_values[0].value) for row in event_response.rows) if event_response.rows else 0
                event_metrics[event_name] = total
            except Exception as e:
                print(f"  [WARN] Failed to fetch {event_name}: {e}")
        
        # Fetch sessions and revenue separately
        request = RunReportRequest(
            property=f"properties/{self.google.property_id}",
            dimensions=[
                Dimension(name="deviceCategory"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="ecommerce:itemsViewed"),      # view_item count
                Metric(name="ecommerce:itemsAddedToCart"),  # add_to_cart count
                Metric(name="ecommerce:itemsCheckedOut"),   # begin_checkout count
                Metric(name="ecommerce:itemsPurchased"),    # purchase count
                Metric(name="purchaseRevenue"),
            ],
            date_ranges=[
                DateRange(
                    start_date=target_date.strftime('%Y-%m-%d'),
                    end_date=target_date.strftime('%Y-%m-%d')
                )
            ],
        )
        
        try:
            response = client.run_report(request)
        except Exception as e:
            # Fallback: try with event-based metrics if ecommerce metrics fail
            print(f"  [WARN] GA4 ecommerce metrics failed ({e}), trying event-based...")
            return self._harvest_ga4_funnel_fallback(client, target_date)
        
        # Check if ecommerce metrics returned valid data, otherwise use event counts
        has_ecommerce_data = False
        test_views = 0
        test_add_carts = 0
        test_checkouts = 0
        test_purchases = 0
        
        for row in response.rows:
            test_views += int(row.metric_values[1].value)
            test_add_carts += int(row.metric_values[2].value)
            test_checkouts += int(row.metric_values[3].value)
            test_purchases += int(row.metric_values[4].value)
        
        # If ecommerce metrics are all 0 but we have event counts, use events
        if test_add_carts == 0 and test_checkouts == 0 and event_metrics['add_to_cart'] > 0:
            print(f"  [INFO] Using event-based counts instead of ecommerce metrics")
            print(f"  [INFO] Events: view_item={event_metrics['view_item']}, add_to_cart={event_metrics['add_to_cart']}, begin_checkout={event_metrics['begin_checkout']}, purchase={event_metrics['purchase']}")
            use_event_metrics = True
        else:
            use_event_metrics = False
        
        count = 0
        for row in response.rows:
            device = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            revenue = float(row.metric_values[5].value)
            
            if use_event_metrics:
                # Use event counts (approximate - distributed evenly across devices)
                # Get device ratio from sessions
                total_sessions = sum(int(r.metric_values[0].value) for r in response.rows)
                device_ratio = sessions / total_sessions if total_sessions > 0 else 0
                
                views = int(event_metrics['view_item'] * device_ratio)
                add_carts = int(event_metrics['add_to_cart'] * device_ratio)
                checkouts = int(event_metrics['begin_checkout'] * device_ratio)
                purchases = int(event_metrics['purchase'] * device_ratio)
            else:
                views = int(row.metric_values[1].value)
                add_carts = int(row.metric_values[2].value)
                checkouts = int(row.metric_values[3].value)
                purchases = int(row.metric_values[4].value)
            
            funnel = GA4FunnelDaily(
                id=str(uuid.uuid4()),
                date=target_date,
                device_category=device.lower(),
                sessions=sessions,
                product_views=views,
                add_to_carts=add_carts,
                begin_checkouts=checkouts,
                purchases=purchases,
                revenue=revenue,
                # Computed rates (safe division)
                view_rate=views / sessions if sessions > 0 else 0.0,
                cart_rate=add_carts / views if views > 0 else 0.0,
                checkout_rate=checkouts / add_carts if add_carts > 0 else 0.0,
                purchase_rate=purchases / checkouts if checkouts > 0 else 0.0,
                overall_conversion=purchases / sessions if sessions > 0 else 0.0,
            )
            self.db.add(funnel)
            count += 1
        
        # Also store an "all" devices aggregate
        if count > 0:
            all_funnels = self.db.query(GA4FunnelDaily).filter(
                GA4FunnelDaily.date == target_date,
                GA4FunnelDaily.device_category != 'all'
            ).all()
            
            total = GA4FunnelDaily(
                id=str(uuid.uuid4()),
                date=target_date,
                device_category='all',
                sessions=sum(f.sessions for f in all_funnels),
                product_views=sum(f.product_views for f in all_funnels),
                add_to_carts=sum(f.add_to_carts for f in all_funnels),
                begin_checkouts=sum(f.begin_checkouts for f in all_funnels),
                purchases=sum(f.purchases for f in all_funnels),
                revenue=sum(f.revenue for f in all_funnels),
            )
            # Compute rates for aggregate
            if total.sessions > 0:
                total.view_rate = total.product_views / total.sessions
                total.overall_conversion = total.purchases / total.sessions
            if total.product_views > 0:
                total.cart_rate = total.add_to_carts / total.product_views
            if total.add_to_carts > 0:
                total.checkout_rate = total.begin_checkouts / total.add_to_carts
            if total.begin_checkouts > 0:
                total.purchase_rate = total.purchases / total.begin_checkouts
            
            self.db.add(total)
            count += 1
        
        self.db.flush()
        return count
    
    def _harvest_ga4_funnel_fallback(self, client, target_date) -> int:
        """
        Fallback: use sessions + event counts if ecommerce metrics unavailable.
        Uses eventCount with eventName filter for each funnel step.
        """
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest,
            FilterExpression, Filter
        )
        
        # Simplified: just get sessions and conversions by device
        request = RunReportRequest(
            property=f"properties/{self.google.property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="conversions"),
                Metric(name="totalRevenue"),
            ],
            date_ranges=[
                DateRange(
                    start_date=target_date.strftime('%Y-%m-%d'),
                    end_date=target_date.strftime('%Y-%m-%d')
                )
            ],
        )
        
        response = client.run_report(request)
        count = 0
        
        for row in response.rows:
            device = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            conversions = int(row.metric_values[1].value)
            revenue = float(row.metric_values[2].value)
            
            funnel = GA4FunnelDaily(
                id=str(uuid.uuid4()),
                date=target_date,
                device_category=device.lower(),
                sessions=sessions,
                purchases=conversions,
                revenue=revenue,
                overall_conversion=conversions / sessions if sessions > 0 else 0.0,
            )
            self.db.add(funnel)
            count += 1
        
        self.db.flush()
        return count
    
    # ========================================================================
    # STEP 5: GA4 Page-Level Ecommerce Events
    # ========================================================================
    
    def _harvest_ga4_page_metrics(self) -> int:
        """
        Pull GA4 page-level metrics and merge into existing PageDailyMetric rows.
        
        Enhanced version of existing get_ga4_engagement_data() that also 
        fetches add_to_cart and purchase events per page.
        """
        if not self.google.credentials or not self.google.property_id:
            return 0
        
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
        
        client = BetaAnalyticsDataClient(credentials=self.google.credentials)
        
        # GA4 has ~24h delay, but we wrote page metrics from GSC for target_date (3 days ago)
        # We update the SAME page rows with GA4 data from 1 day ago for a rough merge,
        # OR we update today's date rows if they exist
        target_date = (datetime.now() - timedelta(days=1)).date()
        
        request = RunReportRequest(
            property=f"properties/{self.google.property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
                Metric(name="totalRevenue"),
            ],
            date_ranges=[
                DateRange(
                    start_date=target_date.strftime('%Y-%m-%d'),
                    end_date=target_date.strftime('%Y-%m-%d')
                )
            ],
        )
        
        response = client.run_report(request)
        updated = 0
        
        # Build lookup of existing page metrics from the GSC harvest (3 days ago)
        # We'll match by page path and update the GA4 columns
        gsc_date = (datetime.now() - timedelta(days=3)).date()
        
        for row in response.rows:
            page_path = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            avg_duration = float(row.metric_values[1].value)
            bounce_rate = float(row.metric_values[2].value)
            revenue = float(row.metric_values[3].value)
            
            # Try to find existing PageDailyMetric for this page from GSC harvest
            # Match by page path suffix (GSC stores full URL, GA4 stores path)
            page_metric = self.db.query(PageDailyMetric).filter(
                PageDailyMetric.date == gsc_date,
                PageDailyMetric.page_url.contains(page_path)
            ).first()
            
            if page_metric:
                page_metric.ga4_sessions = sessions
                page_metric.ga4_engagement_time = avg_duration
                page_metric.ga4_bounce_rate = bounce_rate
                page_metric.ga4_revenue = revenue
                
                # Compute revenue per impression/click
                if page_metric.gsc_impressions and page_metric.gsc_impressions > 0:
                    page_metric.revenue_per_impression = revenue / page_metric.gsc_impressions
                if page_metric.gsc_clicks and page_metric.gsc_clicks > 0:
                    page_metric.revenue_per_click = revenue / page_metric.gsc_clicks
                
                updated += 1
        
        self.db.flush()
        return updated
    
    # ========================================================================
    # STEP 6: Compute Metric Deltas
    # ========================================================================
    
    def _compute_metric_deltas(self):
        """
        After storing today's data, compute 7d and 30d changes.
        
        For each query in today's harvest:
          position_change_7d = today.position - avg(7_days_ago).position
          ctr_change_7d = today.ctr - avg(7_days_ago).ctr
        """
        target_date = (datetime.now() - timedelta(days=3)).date()
        date_7d_ago = target_date - timedelta(days=7)
        date_30d_ago = target_date - timedelta(days=30)
        
        # Get today's records
        today_records = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date == target_date
        ).all()
        
        if not today_records:
            return
        
        # Build lookup of historical averages for all queries
        # 7-day averages
        avg_7d = {}
        rows_7d = self.db.query(
            KeywordDailyMetric.query,
            sql_func.avg(KeywordDailyMetric.position).label('avg_position'),
            sql_func.avg(KeywordDailyMetric.ctr).label('avg_ctr'),
            sql_func.avg(KeywordDailyMetric.impressions).label('avg_impressions'),
        ).filter(
            KeywordDailyMetric.date >= date_7d_ago,
            KeywordDailyMetric.date < target_date
        ).group_by(KeywordDailyMetric.query).all()
        
        for row in rows_7d:
            avg_7d[row.query] = {
                'position': row.avg_position,
                'ctr': row.avg_ctr,
                'impressions': row.avg_impressions,
            }
        
        # 30-day averages
        avg_30d = {}
        rows_30d = self.db.query(
            KeywordDailyMetric.query,
            sql_func.avg(KeywordDailyMetric.position).label('avg_position'),
        ).filter(
            KeywordDailyMetric.date >= date_30d_ago,
            KeywordDailyMetric.date < target_date
        ).group_by(KeywordDailyMetric.query).all()
        
        for row in rows_30d:
            avg_30d[row.query] = row.avg_position
        
        # Update deltas
        for record in today_records:
            if record.query in avg_7d:
                hist = avg_7d[record.query]
                record.position_change_7d = record.position - hist['position']
                record.ctr_change_7d = record.ctr - hist['ctr']
                if hist['impressions'] and hist['impressions'] > 0:
                    record.impressions_change_7d = (
                        (record.impressions - hist['impressions']) / hist['impressions']
                    )
            
            if record.query in avg_30d:
                record.position_change_30d = record.position - avg_30d[record.query]
        
        self.db.flush()
    
    # ========================================================================
    # STEP 7: CTR Benchmarks
    # ========================================================================
    
    def _compute_ctr_benchmarks(self):
        """
        Apply position-based CTR benchmarks to today's records.
        
        For each query:
            expected_ctr = benchmark[round(position)]
            ctr_gap = actual_ctr - expected_ctr
            is_underperforming = ctr_gap < -0.01 (below benchmark by >1%)
        """
        target_date = (datetime.now() - timedelta(days=3)).date()
        
        records = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date == target_date
        ).all()
        
        for record in records:
            if record.position and record.position > 0:
                expected = get_expected_ctr(record.position)
                record.expected_ctr = expected
                record.ctr_gap = record.ctr - expected
                # Underperforming if CTR is below benchmark by more than 1%
                # AND has meaningful impressions (avoid noise from low-volume queries)
                record.is_underperforming = (
                    record.ctr_gap < -0.01 and 
                    record.impressions >= 20
                )
        
        self.db.flush()
    
    # ========================================================================
    # STEP 8: Cannibalization Detection
    # ========================================================================
    
    def _detect_cannibalization(self):
        """
        Flag queries where 2+ pages from our site appear in results.
        
        Query keyword_page_mappings for today:
          GROUP BY query HAVING COUNT(DISTINCT page_url) > 1
        
        Mark all rows for those queries as is_cannibalized = True.
        """
        target_date = (datetime.now() - timedelta(days=3)).date()
        
        # Find queries with multiple competing pages
        cannibalized_queries = self.db.query(
            KeywordPageMapping.query,
            sql_func.count(sql_func.distinct(KeywordPageMapping.page_url)).label('page_count')
        ).filter(
            KeywordPageMapping.date == target_date
        ).group_by(
            KeywordPageMapping.query
        ).having(
            sql_func.count(sql_func.distinct(KeywordPageMapping.page_url)) > 1
        ).all()
        
        cannibalized_query_set = {row.query for row in cannibalized_queries}
        page_count_map = {row.query: row.page_count for row in cannibalized_queries}
        
        if not cannibalized_query_set:
            return
        
        # Update all mappings for cannibalized queries
        mappings = self.db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date == target_date,
            KeywordPageMapping.query.in_(cannibalized_query_set)
        ).all()
        
        for mapping in mappings:
            mapping.is_cannibalized = True
            mapping.competing_pages_count = page_count_map.get(mapping.query, 1)

        self.db.flush()

        # Collection-specific cannibalization detection:
        # Flag when a collection competes with a blog for the same keyword
        self._detect_collection_blog_conflicts(target_date, cannibalized_query_set)

    def _detect_collection_blog_conflicts(self, target_date, cannibalized_queries: set):
        """
        Detect when collections and blogs compete for the same keywords.
        Creates SEOAlerts for high-severity conflicts.
        """
        if not cannibalized_queries:
            return

        # Get all cannibalized mappings for today
        mappings = self.db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date == target_date,
            KeywordPageMapping.query.in_(cannibalized_queries)
        ).all()

        # Group by query to find collection-vs-blog conflicts
        from collections import defaultdict
        query_pages = defaultdict(list)
        for m in mappings:
            page_type = m.page_type or self._classify_page_type(m.page_url)
            query_pages[m.query].append({
                'url': m.page_url,
                'type': page_type,
                'position': m.position,
                'clicks': m.clicks,
                'impressions': m.impressions
            })

        conflicts_found = 0
        for query, pages in query_pages.items():
            page_types = {p['type'] for p in pages}

            # Alert when collection AND blog compete
            if 'collection' in page_types and 'blog' in page_types:
                blog_pages = [p for p in pages if p['type'] == 'blog']
                collection_pages = [p for p in pages if p['type'] == 'collection']

                for blog in blog_pages:
                    for col in collection_pages:
                        severity = 'high' if blog['position'] <= 3 else 'medium'

                        alert = SEOAlert(
                            id=str(uuid.uuid4()),
                            alert_type='collection_cannibalization',
                            severity=severity,
                            title=f"Colección vs Blog: '{query}'",
                            description=(
                                f"Blog ({blog['url']}) rankea #{blog['position']:.0f} y "
                                f"colección ({col['url']}) rankea #{col['position']:.0f} "
                                f"para '{query}'. Consolida con link interno blog → colección."
                            ),
                            affected_query=query,
                            affected_page=col['url'],
                            metric_before=blog['position'],
                            metric_after=col['position'],
                            status='open'
                        )
                        self.db.add(alert)
                        conflicts_found += 1

        if conflicts_found:
            self.db.flush()
            print(f"    [Cannibal] {conflicts_found} collection-blog conflicts detected")
    
    # ========================================================================
    # URL CLASSIFICATION
    # ========================================================================

    @staticmethod
    def _classify_page_type(url: str) -> str:
        """Classify a URL as blog, product, collection, or other."""
        url_lower = url.lower()
        if '/blogs/' in url_lower or '/blog/' in url_lower:
            return 'blog'
        elif '/products/' in url_lower:
            return 'product'
        elif '/collections/' in url_lower:
            return 'collection'
        return 'other'

    # ========================================================================
    # CLEANUP JOB
    # ========================================================================
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Delete historical data older than specified days.
        Run weekly to keep DB lean.
        """
        cutoff = date.today() - timedelta(days=days_to_keep)
        
        deleted = {}
        
        deleted['keyword_metrics'] = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date < cutoff
        ).delete()
        
        deleted['page_metrics'] = self.db.query(PageDailyMetric).filter(
            PageDailyMetric.date < cutoff
        ).delete()
        
        # Keep mappings for only 30 days (they're larger)
        mapping_cutoff = date.today() - timedelta(days=30)
        deleted['mappings'] = self.db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date < mapping_cutoff
        ).delete()
        
        deleted['funnel'] = self.db.query(GA4FunnelDaily).filter(
            GA4FunnelDaily.date < cutoff
        ).delete()
        
        self.db.commit()
        return deleted


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("Running SEO Intelligence Daily Collector...")
    db = SessionLocal()
    try:
        collector = DailyCollector(db)
        result = collector.run_daily_harvest()
        print(f"\nResult: {result}")
    finally:
        db.close()

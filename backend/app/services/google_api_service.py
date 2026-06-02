import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy,
    FilterExpression,
    FilterExpressionList,
    Filter
)
from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.core.config import settings
from app.services.redis_service import cached

# GSC has 2-3 day lag; GA4 has same-day lag. 30 min is a good balance
# between dashboard freshness and API-quota friendliness.
_GOOGLE_API_CACHE_TTL = 1800

class GoogleApiService:
    def __init__(self):
        self.credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        self.property_id = settings.GOOGLE_GA4_PROPERTY_ID
        self.site_url = settings.GOOGLE_SEARCH_CONSOLE_SITE_URL
        self.credentials = None
        
        # 1. Try explicit service account file
        if self.credentials_path and os.path.exists(self.credentials_path):
            try:
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=[
                        'https://www.googleapis.com/auth/analytics.readonly',
                        'https://www.googleapis.com/auth/webmasters.readonly'
                    ]
                )
                print(f"[OK] Service account credentials loaded: {self.credentials.project_id}")
            except Exception as e:
                print(f"[WARN] Failed to load service account file: {e}")

        # 2. Fallback to Application Default Credentials (via gcloud CLI)
        if not self.credentials:
            try:
                import google.auth
                self.credentials, project = google.auth.default(
                    scopes=[
                        'https://www.googleapis.com/auth/analytics.readonly',
                        'https://www.googleapis.com/auth/webmasters.readonly'
                    ]
                )
                print(f"[OK] Using Application Default Credentials for project: {project}")
            except Exception as e:
                print(f"[ERROR] No valid Google credentials found: {e}")

        self.AI_REFERRER_PATTERNS = [
            "perplexity.ai",
            "chatgpt.com", 
            "claude.ai",
            "copilot.microsoft.com",
            "you.com",
            "phind.com"
        ]

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_search_console_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch search query performance from Google Search Console."""
        if not self.credentials or not self.site_url:
            return []

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3) # GSC data usually has 2-3 days delay
            start_date = end_date - timedelta(days=days)

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['query'],
                'rowLimit': 500
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            queries = []
            if 'rows' in response:
                for row in response['rows']:
                    queries.append({
                        'query': row['keys'][0],
                        'clicks': row['clicks'],
                        'impressions': row['impressions'],
                        'ctr': row['ctr'],
                        'position': row['position']
                    })

            return queries
        except Exception as e:
            print(f"❌ Error fetching GSC data: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_search_console_product_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch page-level Search Console data for product pages.
        Filters to only include /products/ URLs.
        """
        if not self.credentials or not self.site_url:
            return []

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['page'],
                'rowLimit': 5000
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            pages = []
            if 'rows' in response:
                for row in response['rows']:
                    page_url = row['keys'][0]
                    # Only include product pages
                    if '/products/' in page_url:
                        pages.append({
                            'page': page_url,
                            'clicks': row['clicks'],
                            'impressions': row['impressions'],
                            'ctr': row['ctr'],
                            'position': row['position']
                        })

            return pages
        except Exception as e:
            print(f"❌ Error fetching GSC product data: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_search_console_blog_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch page-level Search Console data for blog article pages.
        Filters to only include /blogs/ URLs. One batched call — caller maps
        results to articles by URL.
        """
        if not self.credentials or not self.site_url:
            return []

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['page'],
                'rowLimit': 5000
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            pages = []
            if 'rows' in response:
                for row in response['rows']:
                    page_url = row['keys'][0]
                    if '/blogs/' in page_url:
                        pages.append({
                            'page': page_url,
                            'clicks': row['clicks'],
                            'impressions': row['impressions'],
                            'ctr': row['ctr'],
                            'position': row['position']
                        })

            return pages
        except Exception as e:
            print(f"[ERROR] Fetching GSC blog data: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_ga4_engagement_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch page-level engagement data from GA4 including revenue and bounce rate."""
        if not self.credentials or not self.property_id:
            print("[WARN] GA4 Property ID or credentials missing")
            return []

        try:
            client = BetaAnalyticsDataClient(credentials=self.credentials)

            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                    Metric(name="sessions"),
                    Metric(name="purchaseRevenue"),
                    Metric(name="bounceRate"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            )

            response = client.run_report(request)

            results = []
            for row in response.rows:
                results.append({
                    'page_path': row.dimension_values[0].value,
                    'active_users': int(row.metric_values[0].value),
                    'avg_duration': float(row.metric_values[1].value),
                    'conversions': int(row.metric_values[2].value),
                    'sessions': int(row.metric_values[3].value),
                    'revenue': float(row.metric_values[4].value),
                    'bounce_rate': float(row.metric_values[5].value),
                })

            return results
        except Exception as e:
            print(f"[ERROR] Fetching GA4 data: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_product_gsc_live(self, handle: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Fetch GSC page-level data for a single product (live API call)."""
        if not self.credentials or not self.site_url:
            return None

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            # Use exact URL match for this product page
            product_url = f"{self.site_url.rstrip('/')}/products/{handle}"

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['page'],
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals',
                        'expression': product_url
                    }]
                }],
                'rowLimit': 1
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            if 'rows' in response and response['rows']:
                row = response['rows'][0]
                return {
                    'impressions': row['impressions'],
                    'clicks': row['clicks'],
                    'ctr': row['ctr'],
                    'position': row['position']
                }

            return None
        except Exception as e:
            print(f"[ERROR] Fetching GSC data for {handle}: {e}")
            return None

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_product_gsc_queries(self, handle: str, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch GSC queries that ACTUALLY lead to this product page.
        Uses both 'page' and 'query' dimensions with a page URL filter,
        so only queries where THIS product is the landing page are returned.
        """
        if not self.credentials or not self.site_url:
            return []

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            product_url = f"{self.site_url.rstrip('/')}/products/{handle}"

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['query'],
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals',
                        'expression': product_url
                    }]
                }],
                'rowLimit': limit
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            queries = []
            if 'rows' in response:
                for row in response['rows']:
                    queries.append({
                        'query': row['keys'][0],
                        'clicks': row['clicks'],
                        'impressions': row['impressions'],
                        'ctr': row['ctr'],
                        'position': row['position']
                    })

            return queries
        except Exception as e:
            print(f"[ERROR] Fetching GSC queries for {handle}: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_search_console_queries_for_url(self, url_path: str, days: int = 90, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch GSC queries that ACTUALLY landed users on a given URL path.

        Generic variant of get_product_gsc_queries — accepts any path on the
        site (`/blogs/...`, `/pages/...`, etc.), not just /products/.

        Args:
            url_path: Relative path starting with '/' (e.g. '/blogs/diagnostico/p0700').
            days: Lookback window in days. Default 90 for richer signal on
                article pages, which typically have lower query volume than
                product pages.
            limit: Max queries to return.
        """
        if not self.credentials or not self.site_url:
            return []

        try:
            service = build('webmasters', 'v3', credentials=self.credentials)

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            if not url_path.startswith('/'):
                url_path = '/' + url_path
            full_url = f"{self.site_url.rstrip('/')}{url_path}"

            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['query'],
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals',
                        'expression': full_url
                    }]
                }],
                'rowLimit': limit
            }

            response = service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

            queries = []
            if 'rows' in response:
                for row in response['rows']:
                    queries.append({
                        'query': row['keys'][0],
                        'clicks': row['clicks'],
                        'impressions': row['impressions'],
                        'ctr': row['ctr'],
                        'position': row['position']
                    })

            return queries
        except Exception as e:
            print(f"[ERROR] Fetching GSC queries for {url_path}: {e}")
            return []

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_product_ga4_live(self, handle: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Fetch GA4 data for a single product page by handle (live API call)."""
        if not self.credentials or not self.property_id:
            return None

        try:
            client = BetaAnalyticsDataClient(credentials=self.credentials)

            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                    Metric(name="sessions"),
                    Metric(name="purchaseRevenue"),
                    Metric(name="bounceRate"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="pagePath",
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.CONTAINS,
                            value=f"/products/{handle}"
                        )
                    )
                ),
            )

            response = client.run_report(request)

            if response.rows:
                # Sum across all matching rows
                total_sessions = 0
                total_revenue = 0.0
                total_users = 0
                weighted_duration = 0.0
                weighted_bounce = 0.0

                for row in response.rows:
                    sessions = int(row.metric_values[3].value)
                    total_users += int(row.metric_values[0].value)
                    weighted_duration += float(row.metric_values[1].value) * sessions
                    total_sessions += sessions
                    total_revenue += float(row.metric_values[4].value)
                    weighted_bounce += float(row.metric_values[5].value) * sessions

                avg_duration = (weighted_duration / total_sessions) if total_sessions > 0 else 0
                avg_bounce = (weighted_bounce / total_sessions) if total_sessions > 0 else 0

                return {
                    'sessions': total_sessions,
                    'active_users': total_users,
                    'avg_duration': avg_duration,
                    'revenue': total_revenue,
                    'bounce_rate': avg_bounce,
                }

            return None
        except Exception as e:
            print(f"[ERROR] Fetching GA4 data for {handle}: {e}")
            return None

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_llm_txt_traffic(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch specialized report for LLMS.txt initiated traffic."""
        if not self.credentials or not self.property_id:
            return []
            
        try:
            client = BetaAnalyticsDataClient(credentials=self.credentials)
            
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[
                    Dimension(name="sessionSource"), 
                    Dimension(name="pagePath"),
                    Dimension(name="pageReferrer")
                ],
                metrics=[
                    Metric(name="sessions"), 
                    Metric(name="activeUsers")
                ],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="sessionSource",
                        string_filter=Filter.StringFilter(value="llms.txt")
                    )
                ),
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            )
            
            response = client.run_report(request)
            
            results = []
            for row in response.rows:
                results.append({
                    'source': row.dimension_values[0].value,
                    'page_path': row.dimension_values[1].value,
                    'referrer': row.dimension_values[2].value,
                    'sessions': int(row.metric_values[0].value),
                    'active_users': int(row.metric_values[1].value)
                })
            
            return results
        except Exception as e:
            print(f"❌ Error fetching LLMS.txt traffic data: {e}")
            return []

    # ---- Traffic Spike Diagnostic Methods ----

    def diagnose_traffic_spike(self, days: int = 7) -> Dict[str, Any]:
        """
        Full diagnostic report for traffic spikes.
        Breaks down sessions by source/medium, country, channel, and engagement.
        Returns everything needed to identify bots, LLM crawlers, or real traffic.
        """
        if not self.credentials or not self.property_id:
            return {"error": "GA4 credentials not configured"}

        client = BetaAnalyticsDataClient(credentials=self.credentials)
        results = {}

        # 1. Sessions by source/medium (top 25)
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[
                    Dimension(name="sessionSource"),
                    Dimension(name="sessionMedium"),
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=25,
            ))
            results["by_source_medium"] = [
                {
                    "source": row.dimension_values[0].value,
                    "medium": row.dimension_values[1].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "bounce_rate": round(float(row.metric_values[2].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[3].value), 1),
                    "conversions": int(row.metric_values[4].value),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["by_source_medium"] = {"error": str(e)}

        # 2. Sessions by country (top 15)
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="country")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=15,
            ))
            results["by_country"] = [
                {
                    "country": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "bounce_rate": round(float(row.metric_values[1].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[2].value), 1),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["by_country"] = {"error": str(e)}

        # 3. Sessions by default channel group
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="sessionDefaultChannelGroup")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
            ))
            results["by_channel"] = [
                {
                    "channel": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "bounce_rate": round(float(row.metric_values[2].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[3].value), 1),
                    "conversions": int(row.metric_values[4].value),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["by_channel"] = {"error": str(e)}

        # 4. Daily sessions trend (to see the exact spike day)
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="newUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
            ))
            results["daily_trend"] = [
                {
                    "date": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "new_users": int(row.metric_values[2].value),
                    "bounce_rate": round(float(row.metric_values[3].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[4].value), 1),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["daily_trend"] = {"error": str(e)}

        # 5. Top landing pages during spike (which pages are being hit)
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="landingPagePlusQueryString")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=20,
            ))
            results["top_landing_pages"] = [
                {
                    "page": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "bounce_rate": round(float(row.metric_values[1].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[2].value), 1),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["top_landing_pages"] = {"error": str(e)}

        # 6. Device category breakdown (bots often show as desktop with 0 engagement)
        try:
            resp = client.run_report(RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="deviceCategory")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                ],
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            ))
            results["by_device"] = [
                {
                    "device": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "bounce_rate": round(float(row.metric_values[1].value), 1),
                    "avg_duration_sec": round(float(row.metric_values[2].value), 1),
                }
                for row in resp.rows
            ]
        except Exception as e:
            results["by_device"] = {"error": str(e)}

        # 7. Bot signals analysis
        results["bot_signals"] = self._analyze_bot_signals(results)

        return results

    def _analyze_bot_signals(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Analyze traffic data for bot/crawler indicators."""
        signals = []

        # Check source/medium for suspicious patterns
        sources = data.get("by_source_medium", [])
        if isinstance(sources, list):
            for s in sources:
                bounce = s.get("bounce_rate", 0)
                duration = s.get("avg_duration_sec", 0)
                sessions = s.get("sessions", 0)
                conversions = s.get("conversions", 0)
                source = s.get("source", "")

                # High sessions + high bounce + near-zero duration = bot
                if sessions > 100 and bounce > 90 and duration < 3:
                    signals.append({
                        "severity": "HIGH",
                        "source": f"{source}/{s.get('medium', '')}",
                        "signal": f"{sessions} sessions, {bounce}% bounce, {duration}s avg duration — likely bot traffic",
                    })

                # Known AI crawlers
                ai_sources = ["chatgpt", "perplexity", "claude", "copilot", "openai", "anthropic", "you.com", "phind"]
                if any(ai in source.lower() for ai in ai_sources):
                    signals.append({
                        "severity": "INFO",
                        "source": f"{source}/{s.get('medium', '')}",
                        "signal": f"AI engine traffic: {sessions} sessions",
                    })

                # (not set) / (not set) with high volume = often bots
                if source == "(not set)" and sessions > 200:
                    signals.append({
                        "severity": "MEDIUM",
                        "source": "(not set)/(not set)",
                        "signal": f"{sessions} unattributed sessions — possible bot or misconfigured tracking",
                    })

        # Check country for geographic anomalies
        countries = data.get("by_country", [])
        if isinstance(countries, list) and len(countries) >= 2:
            top = countries[0]
            if top.get("country", "").lower() not in ["mexico", "united states", "estados unidos"]:
                signals.append({
                    "severity": "HIGH",
                    "source": f"Country: {top['country']}",
                    "signal": f"Top traffic country is {top['country']} ({top['sessions']} sessions) — unexpected for a Mexico-based store",
                })

        # Check daily trend for single-day spikes
        daily = data.get("daily_trend", [])
        if isinstance(daily, list) and len(daily) >= 3:
            sessions_list = [d.get("sessions", 0) for d in daily]
            avg = sum(sessions_list) / len(sessions_list)
            for d in daily:
                if d["sessions"] > avg * 3 and d["sessions"] > 500:
                    signals.append({
                        "severity": "HIGH",
                        "source": f"Date: {d['date']}",
                        "signal": f"Single-day spike: {d['sessions']} sessions (avg: {avg:.0f}) — {d['sessions']/avg:.1f}x normal",
                    })

        if not signals:
            signals.append({"severity": "OK", "source": "all", "signal": "No obvious bot signals detected"})

        return signals

    @cached(ttl=_GOOGLE_API_CACHE_TTL)
    def get_ai_referral_traffic(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch general AI engine referral traffic based on known patterns."""
        if not self.credentials or not self.property_id:
            return []
            
        try:
            client = BetaAnalyticsDataClient(credentials=self.credentials)
            
            # Use OR filter for multiple referrers
            filter_expressions = [
                FilterExpression(
                    filter=Filter(
                        field_name="pageReferrer",
                        string_filter=Filter.StringFilter(match_type=Filter.StringFilter.MatchType.CONTAINS, value=pattern)
                    )
                ) for pattern in self.AI_REFERRER_PATTERNS
            ]
            
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="pageReferrer"), Dimension(name="pagePath")],
                metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
                dimension_filter=FilterExpression(
                    or_group=FilterExpressionList(expressions=filter_expressions)
                ),
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            )
            
            response = client.run_report(request)
            
            results = []
            for row in response.rows:
                results.append({
                    'referrer': row.dimension_values[0].value,
                    'page_path': row.dimension_values[1].value,
                    'sessions': int(row.metric_values[0].value),
                    'active_users': int(row.metric_values[1].value)
                })
            
            return results
        except Exception as e:
            print(f"❌ Error fetching AI referral data: {e}")
            return []

    def sync_performance_data(self, db_session):
        """Orchestrate sync between Google APIs and local Database."""
        from app.models.aeo_models import FaultCode, DiagnosticContent
        
        print(f"🔄 Starting Search Performance Sync for {self.site_url}...")
        
        # 1. Sync Search Console (Queries -> FaultCodes)
        gsc_data = self.get_search_console_data()
        updated_codes = 0

        # Bulk-load fault codes matching any GSC query in one IN-query, then
        # index by code for O(1) lookup inside the loop.
        gsc_query_codes = {item['query'].upper() for item in gsc_data}
        fault_codes_by_code = {
            fc.code: fc
            for fc in db_session.query(FaultCode).filter(FaultCode.code.in_(gsc_query_codes)).all()
        }

        for item in gsc_data:
            fault_code = fault_codes_by_code.get(item['query'].upper())

            if fault_code:
                fault_code.monthly_clicks = item['clicks']
                fault_code.monthly_impressions = item['impressions']
                fault_code.current_ctr = item['ctr']
                fault_code.avg_position = item['position']
                fault_code.updated_at = datetime.now()
                updated_codes += 1

        # 2. Sync GA4 (Pages -> DiagnosticContent)
        ga4_data = self.get_ga4_engagement_data()
        updated_pages = 0

        # NOTE: DiagnosticContent.page_url uses a CONTAINS match, so we can't
        # use a simple IN-query. Load all diagnostic pages once and match in
        # Python — still 1 query instead of N.
        all_diagnostic_pages = db_session.query(DiagnosticContent).all()

        for item in ga4_data:
            page_path = item['page_path']
            # Match by URL/Path (contains semantics preserved)
            page = next((p for p in all_diagnostic_pages if p.page_url and page_path in p.page_url), None)

            if page:
                page.active_users = item['active_users']
                page.avg_engagement_seconds = int(item['avg_duration'])
                page.key_events = item['conversions']
                page.last_synced = datetime.now()
                updated_pages += 1
        
        db_session.commit()
        
        # 3. Handle specific AI tracking
        llm_traffic = self.get_llm_txt_traffic()
        ai_referrals = self.get_ai_referral_traffic()
        
        # LOG AI TRAFFIC FOR DASHBOARD (This would normally go to a geo_metrics table)
        # For now, we print it - in a full implementation we'd save it to the DB
        print(f"📊 Tracking: {len(llm_traffic)} LLMS.txt entries, {len(ai_referrals)} general AI referrals detected.")
        
        print(f"✅ Sync complete. Updated {updated_codes} fault codes and {updated_pages} diagnostic pages.")
        return {
            "updated_fault_codes": updated_codes,
            "updated_pages": updated_pages,
            "llm_traffic_count": len(llm_traffic),
            "ai_referral_count": len(ai_referrals)
        }

    # Fault code pattern: OBD-II codes — Powertrain (P), Body (B), Chassis (C),
    # Network (U). First digit is 0-3 (generic/manufacturer/reserved).
    _FAULT_CODE_RE = re.compile(r"\b([PBCU][0-3]\d{3})\b", re.IGNORECASE)

    def refresh_fault_codes_from_gsc(
        self,
        db_session,
        days: int = 30,
        min_impressions: int = 10,
    ) -> Dict[str, Any]:
        """Extract fault codes from current GSC queries and upsert FaultCode rows.

        Replaces the hardcoded PRIORITY_FAULT_CODES list as the source of truth.
        Aggregates clicks/impressions across all queries containing a given code
        so "P0700 chevrolet" and "codigo p0700" both contribute to that code's
        metrics. Skips codes with fewer than `min_impressions` impressions to
        avoid cluttering the DB with long-tail noise.

        Returns a summary dict with counts and the top codes by clicks.
        """
        from app.models.aeo_models import FaultCode

        gsc_data = self.get_search_console_data(days=days)
        if not gsc_data:
            return {
                "status": "no_data",
                "created": 0,
                "updated": 0,
                "qualifying_codes": 0,
                "queries_scanned": 0,
            }

        # Aggregate metrics per code across all queries that mention it.
        agg: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"clicks": 0, "impressions": 0, "pos_sum": 0.0, "n": 0, "sample_queries": []}
        )
        for item in gsc_data:
            q = item.get("query", "") or ""
            codes_in_query = {m.upper() for m in self._FAULT_CODE_RE.findall(q)}
            for code in codes_in_query:
                stats = agg[code]
                stats["clicks"] += int(item.get("clicks", 0) or 0)
                stats["impressions"] += int(item.get("impressions", 0) or 0)
                stats["pos_sum"] += float(item.get("position", 0) or 0)
                stats["n"] += 1
                if len(stats["sample_queries"]) < 3:
                    stats["sample_queries"].append(q)

        # Drop long-tail codes below the impression floor.
        qualified = {c: s for c, s in agg.items() if s["impressions"] >= min_impressions}

        if not qualified:
            return {
                "status": "no_qualifying_codes",
                "created": 0,
                "updated": 0,
                "qualifying_codes": 0,
                "queries_scanned": len(gsc_data),
            }

        # Bulk-load existing rows in one IN-query.
        existing = {
            fc.code: fc
            for fc in db_session.query(FaultCode)
            .filter(FaultCode.code.in_(list(qualified.keys())))
            .all()
        }

        created = 0
        updated = 0
        now = datetime.now()

        for code, stats in qualified.items():
            clicks = stats["clicks"]
            impressions = stats["impressions"]
            ctr = clicks / impressions if impressions else 0.0
            avg_pos = stats["pos_sum"] / stats["n"] if stats["n"] else 0.0

            fc = existing.get(code)
            if fc is not None:
                fc.monthly_clicks = clicks
                fc.monthly_impressions = impressions
                fc.current_ctr = ctr
                fc.avg_position = avg_pos
                fc.updated_at = now
                updated += 1
            else:
                fc = FaultCode(
                    code=code,
                    name=f"Código {code}",  # placeholder; enrich later
                    monthly_clicks=clicks,
                    monthly_impressions=impressions,
                    current_ctr=ctr,
                    avg_position=avg_pos,
                    is_priority=(clicks >= 300),
                    include_in_llms_txt=True,
                    severity=("high" if clicks >= 300 else "medium"),
                    transmissions=[],
                    vehicles=[],
                    common_causes=[],
                    symptoms_text=[],
                )
                db_session.add(fc)
                created += 1

        db_session.commit()

        top_codes = sorted(qualified.items(), key=lambda kv: kv[1]["clicks"], reverse=True)[:10]

        return {
            "status": "completed",
            "created": created,
            "updated": updated,
            "qualifying_codes": len(qualified),
            "queries_scanned": len(gsc_data),
            "top_codes": [
                {"code": c, "clicks": s["clicks"], "impressions": s["impressions"]}
                for c, s in top_codes
            ],
        }

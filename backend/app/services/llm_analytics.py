"""
Enhanced LLM Sales Analytics Module

Provides advanced metrics for LLM attribution analysis:
- Conversion funnel tracking
- Time-to-conversion analysis
- Assisted conversions (multi-touch attribution)
- Geographic analysis
- Cohort retention analysis
- Category performance
- Predictive alerts
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict
import statistics
from dataclasses import dataclass, field
from enum import Enum


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertType(Enum):
    TREND_DOWN = "trend_down"
    TREND_UP = "trend_up"
    ANOMALY = "anomaly"
    OPPORTUNITY = "opportunity"
    INSIGHT = "insight"


@dataclass
class LLMAttributionAlert:
    type: AlertType
    severity: AlertSeverity
    source: str
    metric: str
    current_value: float
    previous_value: float
    change_pct: float
    message: str
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversionFunnel:
    impressions: int = 0
    traffic: int = 0
    product_views: int = 0
    add_to_carts: int = 0
    checkouts: int = 0
    purchases: int = 0
    revenue: float = 0.0
    
    @property
    def traffic_rate(self) -> float:
        return (self.traffic / self.impressions * 100) if self.impressions > 0 else 0
    
    @property
    def view_rate(self) -> float:
        return (self.product_views / self.traffic * 100) if self.traffic > 0 else 0
    
    @property
    def cart_rate(self) -> float:
        return (self.add_to_carts / self.product_views * 100) if self.product_views > 0 else 0
    
    @property
    def checkout_rate(self) -> float:
        return (self.checkouts / self.add_to_carts * 100) if self.add_to_carts > 0 else 0
    
    @property
    def purchase_rate(self) -> float:
        return (self.purchases / self.checkouts * 100) if self.checkouts > 0 else 0
    
    @property
    def overall_conversion(self) -> float:
        return (self.purchases / self.traffic * 100) if self.traffic > 0 else 0


@dataclass
class TimeToConversion:
    source: str
    avg_hours: float
    median_hours: float
    min_hours: float
    max_hours: float
    percentile_25: float
    percentile_75: float
    distribution: Dict[str, int]  # Hour buckets


@dataclass
class CohortMetrics:
    cohort_date: str  # YYYY-MM
    source: str
    initial_customers: int
    retention_30d: float
    retention_60d: float
    retention_90d: float
    avg_orders_per_customer: float
    total_revenue: float
    ltv: float


@dataclass
class GeoMetrics:
    country: str
    region: Optional[str]
    sales: float
    orders: int
    customers: int
    avg_order_value: float
    sources: Dict[str, int]  # Source breakdown


@dataclass
class CategoryPerformance:
    category: str
    llm_sales: float
    llm_orders: int
    total_sales: float
    total_orders: int
    llm_penetration_pct: float  # % of total sales from LLMs
    avg_order_value: float
    top_sources: List[Tuple[str, int]]
    growth_pct: float


@dataclass
class AssistedConversion:
    source: str
    touchpoint_position: str  # 'first', 'middle', 'last'
    orders: int
    sales: float
    days_to_conversion: float


class LLMAnalyticsEnhancer:
    """
    Enhances basic LLM sales data with advanced analytics.
    
    This class wraps around the existing ShopifyService LLM attribution
    methods and adds:
    - Multi-touch attribution
    - Time-to-conversion analysis
    - Geographic breakdown
    - Cohort analysis
    - Category performance
    - Predictive alerts
    """
    
    # Class-level cache removed - now using SQLite via CacheEntry model
    
    def __init__(self, shopify_service):
        self.shopify = shopify_service
        self._alert_thresholds = {
            'sales_drop_pct': 15.0,      # Alert if sales drop > 15%
            'aov_drop_pct': 10.0,        # Alert if AOV drops > 10%
            'conversion_drop_pct': 20.0,  # Alert if conversion drops > 20%
            'trend_window_days': 7,       # Compare vs last 7 days
        }
    
    @classmethod
    def clear_cache(cls, db=None):
        """Clear the enhanced analytics cache from SQLite."""
        if db is None:
            from app.db.session import SessionLocal
            db = SessionLocal()
            close_after = True
        else:
            close_after = False
        
        try:
            from app.models.aeo_models import CacheEntry
            CacheEntry.clear(db, pattern="enhanced_llm_sales:")
            print("[LLMAnalytics] SQLite cache cleared")
        finally:
            if close_after:
                db.close()
    
    def get_enhanced_llm_sales(
        self,
        days: int = 365,
        include_funnel: bool = True,
        include_assisted: bool = True,
        include_geo: bool = True,
        include_time_to_conversion: bool = True,
        include_cohorts: bool = True,
        include_categories: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive LLM sales analytics with all enhanced metrics.
        Uses caching to avoid re-fetching orders on every page reload.
        Cache key includes all parameters to ensure cache invalidation when settings change.
        
        Returns:
            Dict containing:
            - basic: Original sales data (summary, by_source, monthly_trend)
            - funnel: Conversion funnel metrics (if requested)
            - assisted: Multi-touch attribution data (if requested)
            - geo: Geographic breakdown (if requested)
            - time_to_conversion: Time analysis (if requested)
            - cohorts: Retention analysis (if requested)
            - categories: Category performance (if requested)
            - alerts: Automated insights and warnings
        """
        from app.db.session import SessionLocal
        from app.models.aeo_models import CacheEntry
        
        # Create cache key based on all parameters
        cache_key = f"enhanced_llm_sales:{days}:{include_funnel}:{include_assisted}:{include_geo}:{include_time_to_conversion}:{include_cohorts}:{include_categories}"
        
        # Check SQLite cache first (persists across restarts!)
        db = SessionLocal()
        try:
            cached = CacheEntry.get(db, cache_key)
            if cached:
                print(f"[LLMAnalytics] SQLite Cache HIT for {cache_key}")
                return cached
            
            print(f"[LLMAnalytics] Cache MISS - fetching fresh data for {cache_key}")
            
            # Get base data from existing service (this already uses cache)
            base_data = self.shopify.get_llm_attributed_sales(days=days, compare=True)
            
            result = {
                "basic": base_data,
                "enhanced": {}
            }
            
            # Fetch orders with full details for analysis
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            orders = self.shopify._fetch_orders_with_utm(start_date, end_date)
            
            # Core metrics (Overview + Attribution tabs)
            if include_assisted:
                result["enhanced"]["assisted_conversions"] = self._calculate_assisted_conversions(orders)
            
            # Fetch orders with line items for product/category analysis
            orders_with_products = self.shopify._fetch_orders_with_products(days)
            
            # Time-to-conversion (uses order createdAt since visit timestamp not always available)
            if include_time_to_conversion:
                result["enhanced"]["time_to_conversion"] = self._analyze_time_to_conversion(orders)
            
            # Category performance (requires lineItems with productType)
            if include_categories:
                result["enhanced"]["category_performance"] = self._analyze_categories(orders_with_products)
            
            # Cohort analysis (requires customer ID)
            if include_cohorts:
                result["enhanced"]["cohort_analysis"] = self._calculate_cohorts(orders)
            
            # Geographic breakdown (requires shippingAddress)
            if include_geo:
                result["enhanced"]["geographic"] = self._analyze_geography(orders)
            
            # Always generate alerts based on available data
            result["alerts"] = self._generate_alerts(base_data, result["enhanced"])
            
            # Store in SQLite cache with no TTL (persists until manual refresh)
            CacheEntry.set(db, cache_key, result, ttl_hours=0)
            print(f"[LLMAnalytics] Cached result in SQLite (no expiry - use refresh=true to update)")

            
            return result
        finally:
            db.close()
    
    def _calculate_assisted_conversions(self, orders: List[Dict]) -> Dict[str, Any]:
        """
        Calculate multi-touch attribution across the customer journey.
        
        Tracks:
        - Direct: LLM was first AND last touch
        - First-touch: LLM started the journey
        - Middle-touch: LLM influenced mid-journey
        - Last-touch: LLM closed (current default)
        """
        direct = defaultdict(lambda: {"orders": 0, "sales": 0.0})
        first_touch = defaultdict(lambda: {"orders": 0, "sales": 0.0})
        middle_touch = defaultdict(lambda: {"orders": 0, "sales": 0.0})
        last_touch = defaultdict(lambda: {"orders": 0, "sales": 0.0})
        
        # Track unique customers for overlap analysis
        customer_touchpoints = defaultdict(set)
        
        for order in orders:
            journey = order.get('customerJourneySummary', {})
            first_visit = journey.get('firstVisit', {})
            last_visit = journey.get('lastVisit', {})
            
            # Get LLM source at each touchpoint
            first_source = self._identify_llm_source_from_visit(first_visit)
            last_source = self.shopify._identify_llm_source(order)
            
            # Get total order value
            total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0)
            
            # Track customer
            customer_id = order.get('customer', {}).get('id', order.get('id'))
            
            if first_source and last_source:
                if first_source == last_source:
                    # Direct conversion - same source start to finish
                    direct[first_source]["orders"] += 1
                    direct[first_source]["sales"] += total
                    customer_touchpoints[customer_id].add(f"direct:{first_source}")
                else:
                    # First touch was LLM, but different source closed
                    first_touch[first_source]["orders"] += 1
                    first_touch[first_source]["sales"] += total
                    customer_touchpoints[customer_id].add(f"first:{first_source}")
                    
                    # Last touch was also LLM (different one)
                    last_touch[last_source]["orders"] += 1
                    last_touch[last_source]["sales"] += total
                    customer_touchpoints[customer_id].add(f"last:{last_source}")
            elif first_source:
                # Only first touch was LLM
                first_touch[first_source]["orders"] += 1
                first_touch[first_source]["sales"] += total
                customer_touchpoints[customer_id].add(f"first:{first_source}")
            elif last_source:
                # Only last touch was LLM (current default attribution)
                last_touch[last_source]["orders"] += 1
                last_touch[last_source]["sales"] += total
                customer_touchpoints[customer_id].add(f"last:{last_source}")
        
        # Calculate overlap - customers touched by multiple LLM sources
        multi_source_customers = sum(
            1 for touchpoints in customer_touchpoints.values()
            if len(set(t.split(':')[1] for t in touchpoints)) > 1
        )
        
        return {
            "direct": dict(direct),
            "first_touch": dict(first_touch),
            "middle_touch": dict(middle_touch),
            "last_touch": dict(last_touch),
            "total_influenced": sum(
                sum(s["orders"] for s in data.values())
                for data in [direct, first_touch, middle_touch, last_touch]
            ),
            "multi_source_customers": multi_source_customers,
            "attribution_model": {
                "last_touch_total": sum(s["sales"] for s in last_touch.values()),
                "first_touch_total": sum(s["sales"] for s in first_touch.values()),
                "direct_total": sum(s["sales"] for s in direct.values()),
                "total_assisted": sum(s["sales"] for s in first_touch.values()) + sum(s["sales"] for s in middle_touch.values())
            }
        }
    
    def _analyze_time_to_conversion(self, orders: List[Dict]) -> Dict[str, Any]:
        """
        Analyze how long it takes from first LLM visit to purchase.
        
        Returns per-source breakdown with statistical analysis.
        """
        source_times = defaultdict(list)
        
        for order in orders:
            source = self.shopify._identify_llm_source(order)
            if not source:
                continue

            journey = order.get('customerJourneySummary', {})
            first_visit = journey.get('firstVisit', {}) or {}
            order_time = order.get('createdAt') or order.get('created_at')

            # Shopify GraphQL exposes visitToken.landingPage but not occurredAt.
            # Use the customerJourney daysSinceFirstInteraction as a proxy when
            # available — it's the gap from first touch to purchase in whole days.
            days_gap = journey.get('daysSinceFirstInteraction')
            if days_gap is not None:
                try:
                    hours = float(days_gap) * 24.0
                    if 0 <= hours <= 2160:  # within 90 days
                        source_times[source].append(hours)
                except (ValueError, TypeError):
                    pass
                continue

            # Fallback: if no journey data, try explicit timestamp fields that
            # some Shopify plan tiers do expose.
            first_visit_time = (
                first_visit.get('occurredAt')
                or first_visit.get('landingPage', {}).get('occurredAt') if isinstance(first_visit.get('landingPage'), dict) else None
            )
            if first_visit_time and order_time:
                try:
                    first_dt = datetime.fromisoformat(first_visit_time.replace('Z', '+00:00'))
                    order_dt = datetime.fromisoformat(order_time.replace('Z', '+00:00'))
                    hours = (order_dt - first_dt).total_seconds() / 3600
                    if 0 <= hours <= 2160:
                        source_times[source].append(hours)
                except (ValueError, TypeError):
                    pass
        
        results = {}
        for source, times in source_times.items():
            if len(times) < 2:
                continue
                
            times_sorted = sorted(times)
            n = len(times_sorted)
            
            # Calculate percentiles
            p25_idx = int(n * 0.25)
            p75_idx = int(n * 0.75)
            
            # Distribution buckets
            distribution = {
                "0-1h": sum(1 for t in times if t <= 1),
                "1-24h": sum(1 for t in times if 1 < t <= 24),
                "1-7d": sum(1 for t in times if 24 < t <= 168),
                "1-30d": sum(1 for t in times if 168 < t <= 720),
                "30d+": sum(1 for t in times if t > 720)
            }
            
            results[source] = {
                "avg_hours": round(statistics.mean(times), 1),
                "median_hours": round(statistics.median(times), 1),
                "min_hours": round(min(times), 1),
                "max_hours": round(max(times), 1),
                "percentile_25": round(times_sorted[p25_idx], 1),
                "percentile_75": round(times_sorted[p75_idx], 1),
                "distribution": distribution,
                "sample_size": n
            }
        
        return results
    
    def _analyze_categories(self, orders: List[Dict]) -> List[Dict]:
        """
        Analyze sales performance by product category for LLM-attributed orders.
        """
        from app.models.product import Product
        from app.db.session import SessionLocal
        
        category_data = defaultdict(lambda: {
            "llm_sales": 0.0,
            "llm_orders": 0,
            "sources": defaultdict(int),
            "product_ids": set()
        })
        
        # Debug: Track orders processed
        orders_with_source = 0
        line_items_processed = 0
        
        # Process orders
        for order in orders:
            source = self.shopify._identify_llm_source(order)
            if not source:
                continue
            
            orders_with_source += 1
            line_items = order.get('lineItems', {}).get('edges', [])
            for edge in line_items:
                item = edge.get('node', {})
                product = item.get('product') or {}
                product_id = product.get('id', '').split('/')[-1]
                
                if product_id:
                    line_items_processed += 1
                    amount = float(item.get('originalTotalSet', {}).get('shopMoney', {}).get('amount', 0))
                    category_data[product_id]["llm_sales"] += amount
                    category_data[product_id]["llm_orders"] += 1
                    category_data[product_id]["sources"][source] += 1
                    category_data[product_id]["product_ids"].add(product_id)
        
        print(f"[Categories] Orders with LLM source: {orders_with_source}")
        print(f"[Categories] Line items processed: {line_items_processed}")
        print(f"[Categories] Unique products found: {len(category_data)}")
        
        # Query database for product categories and total sales
        db = SessionLocal()
        try:
            product_ids = list(category_data.keys())
            products = db.query(Product).filter(
                Product.shopify_id.in_(product_ids)
            ).all()
            
            print(f"[Categories] Products matched in DB: {len(products)}")
            
            # Aggregate by category
            category_summary = defaultdict(lambda: {
                "llm_sales": 0.0,
                "llm_orders": 0,
                "total_sales": 0.0,
                "total_orders": 0,
                "sources": defaultdict(int),
                "count": 0
            })
            
            for product in products:
                shopify_id = str(product.shopify_id)
                category = product.product_type or "Uncategorized"
                
                if shopify_id in category_data:
                    data = category_data[shopify_id]
                    summary = category_summary[category]
                    
                    summary["llm_sales"] += data["llm_sales"]
                    summary["llm_orders"] += data["llm_orders"]
                    summary["total_sales"] += product.total_revenue or 0
                    summary["total_orders"] += product.total_sold or 0
                    summary["count"] += 1
                    
                    for src, count in data["sources"].items():
                        summary["sources"][src] += count
            
            # Calculate final metrics
            results = []
            for category, data in category_summary.items():
                total_sales = data["total_sales"] or 1  # Avoid div by zero
                penetration = (data["llm_sales"] / total_sales) * 100
                
                results.append({
                    "category": category,
                    "llm_sales": round(data["llm_sales"], 2),
                    "llm_orders": data["llm_orders"],
                    "total_sales": round(data["total_sales"], 2),
                    "total_orders": data["total_orders"],
                    "llm_penetration_pct": round(penetration, 1),
                    "avg_order_value": round(data["llm_sales"] / data["llm_orders"], 2) if data["llm_orders"] > 0 else 0,
                    "top_sources": sorted(data["sources"].items(), key=lambda x: x[1], reverse=True)[:3],
                    "product_count": data["count"]
                })
            
            return sorted(results, key=lambda x: x["llm_sales"], reverse=True)
            
        finally:
            db.close()
    
    def _calculate_cohorts(self, orders: List[Dict]) -> List[Dict]:
        """
        Calculate customer cohort retention analysis.
        
        Groups customers by first purchase month and tracks:
        - Retention at 30, 60, 90 days
        - Lifetime value
        - Average orders per customer
        """
        from collections import defaultdict
        
        # Group orders by customer
        customer_orders = defaultdict(list)
        customer_source = {}
        
        for order in orders:
            customer = order.get('customer', {})
            customer_id = customer.get('id')
            if not customer_id:
                continue
            
            source = self.shopify._identify_llm_source(order)
            if not source:
                continue
            
            created_at = order.get('createdAt', '')
            total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0)
            
            customer_orders[customer_id].append({
                "date": created_at,
                "amount": total,
                "source": source
            })
            customer_source[customer_id] = source
        
        # Group customers by cohort (first purchase month)
        cohorts = defaultdict(lambda: defaultdict(lambda: {
            "customers": set(),
            "orders": [],
            "revenue": 0.0
        }))
        
        for customer_id, orders_list in customer_orders.items():
            if not orders_list:
                continue
            
            # Sort by date
            orders_list.sort(key=lambda x: x["date"])
            first_order = orders_list[0]
            cohort_key = first_order["date"][:7]  # YYYY-MM
            source = customer_source.get(customer_id, "unknown")
            
            cohorts[cohort_key][source]["customers"].add(customer_id)
            for order in orders_list:
                cohorts[cohort_key][source]["orders"].append(order)
                cohorts[cohort_key][source]["revenue"] += order["amount"]
        
        # Calculate retention metrics
        results = []
        for cohort_month, sources in sorted(cohorts.items()):
            for source, data in sources.items():
                customers = data["customers"]
                orders_list = data["orders"]
                
                if not customers:
                    continue
                
                # Calculate retention
                initial_count = len(customers)
                
                # Track who came back
                returned_30d = set()
                returned_60d = set()
                returned_90d = set()
                
                for customer_id in customers:
                    customer_order_list = [o for o in orders_list if o["date"][:7] == cohort_month]
                    if len(customer_order_list) > 1:
                        returned_30d.add(customer_id)
                    # Note: For accurate retention, we'd need orders beyond the cohort month
                    # This is a simplified version
                
                avg_orders = len(orders_list) / initial_count
                ltv = data["revenue"] / initial_count
                
                results.append({
                    "cohort_month": cohort_month,
                    "source": source,
                    "initial_customers": initial_count,
                    "total_orders": len(orders_list),
                    "retention_30d": round(len(returned_30d) / initial_count * 100, 1),
                    "avg_orders_per_customer": round(avg_orders, 2),
                    "total_revenue": round(data["revenue"], 2),
                    "ltv": round(ltv, 2)
                })
        
        return sorted(results, key=lambda x: (x["cohort_month"], x["source"]))
    
    def _analyze_geography(self, orders: List[Dict]) -> List[Dict]:
        """
        Analyze geographic distribution of LLM-attributed sales.
        """
        geo_data = defaultdict(lambda: {
            "sales": 0.0,
            "orders": 0,
            "customers": set(),
            "sources": defaultdict(int)
        })
        
        for order in orders:
            source = self.shopify._identify_llm_source(order)
            if not source:
                continue
            
            customer = order.get('customer', {})
            customer_id = customer.get('id', order.get('id'))
            
            # Get shipping/billing address
            address = order.get('shippingAddress') or order.get('billingAddress') or {}
            country = address.get('country', 'Unknown')
            region = address.get('province') or address.get('region')
            
            key = (country, region)
            total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0)
            
            geo_data[key]["sales"] += total
            geo_data[key]["orders"] += 1
            geo_data[key]["customers"].add(customer_id)
            geo_data[key]["sources"][source] += 1
        
        results = []
        for (country, region), data in geo_data.items():
            results.append({
                "country": country,
                "region": region,
                "sales": round(data["sales"], 2),
                "orders": data["orders"],
                "customers": len(data["customers"]),
                "avg_order_value": round(data["sales"] / data["orders"], 2) if data["orders"] > 0 else 0,
                "sources": dict(data["sources"])
            })
        
        return sorted(results, key=lambda x: x["sales"], reverse=True)
    
    def _generate_alerts(
        self,
        base_data: Dict[str, Any],
        enhanced_data: Dict[str, Any]
    ) -> List[Dict]:
        """
        Generate automated alerts and insights based on data analysis.
        """
        alerts = []
        
        # Check comparison data
        comparison = base_data.get("comparison")
        by_source = base_data.get("by_source", [])
        
        if comparison:
            # Sales trend alerts
            sales_change = comparison.get("sales_change_pct", 0)
            if sales_change < -self._alert_thresholds['sales_drop_pct']:
                alerts.append({
                    "type": AlertType.TREND_DOWN.value,
                    "severity": AlertSeverity.HIGH.value if sales_change < -25 else AlertSeverity.MEDIUM.value,
                    "metric": "sales",
                    "change_pct": sales_change,
                    "message": f"LLM-attributed sales are down {abs(sales_change):.1f}% vs previous period",
                    "recommendation": "Check UTM tracking implementation and recent changes to llms.txt content"
                })
            elif sales_change > 25:
                alerts.append({
                    "type": AlertType.TREND_UP.value,
                    "severity": AlertSeverity.LOW.value,
                    "metric": "sales",
                    "change_pct": sales_change,
                    "message": f"LLM-attributed sales are up {sales_change:.1f}% vs previous period",
                    "recommendation": "Analyze which content changes drove this growth and replicate"
                })
            
            # AOV alerts
            aov_change = comparison.get("aov_change_pct", 0)
            if aov_change < -self._alert_thresholds['aov_drop_pct']:
                alerts.append({
                    "type": AlertType.ANOMALY.value,
                    "severity": AlertSeverity.MEDIUM.value,
                    "metric": "aov",
                    "change_pct": aov_change,
                    "message": f"Average order value from LLMs dropped {abs(aov_change):.1f}%",
                    "recommendation": "Review product bundling recommendations in LLM citations"
                })
        
        # Source-specific alerts
        for source_data in by_source:
            source = source_data.get("source", "unknown")
            aov = source_data.get("aov", 0)
            
            # Identify high-AOV opportunities
            if aov > 400:  # Adjust threshold as needed
                alerts.append({
                    "type": AlertType.OPPORTUNITY.value,
                    "severity": AlertSeverity.LOW.value,
                    "source": source,
                    "metric": "aov",
                    "current_value": aov,
                    "message": f"{source} has high AOV (${aov:.2f}) - opportunity to expand",
                    "recommendation": f"Increase {source} visibility in llms.txt and optimize for this audience"
                })
        
        # Assisted conversion insights
        assisted = enhanced_data.get("assisted_conversions", {})
        first_touch = assisted.get("first_touch", {})
        if first_touch:
            total_first_touch = sum(s["sales"] for s in first_touch.values())
            total_last_touch = base_data.get("summary", {}).get("total_sales", 0)
            
            if total_first_touch > total_last_touch * 0.2:  # >20% assisted
                alerts.append({
                    "type": AlertType.INSIGHT.value,
                    "severity": AlertSeverity.LOW.value,
                    "metric": "assisted_conversions",
                    "message": f"{len(first_touch)} LLM sources are influencing but not closing sales",
                    "recommendation": "Consider multi-touch attribution model - LLMs may be undervalued"
                })
        
        return alerts
    
    def _identify_llm_source_from_visit(self, visit: Dict) -> Optional[str]:
        """Helper to identify LLM source from a visit object."""
        if not visit:
            return None
        
        referrer_url = (visit.get('referrerUrl') or '').lower()
        source_name = (visit.get('source') or '').lower()
        
        utm = visit.get('utmParameters') or {}
        utm_source = (utm.get('source') or '').lower()
        utm_medium = (utm.get('medium') or '').lower()
        utm_campaign = (utm.get('campaign') or '').lower()
        
        # Import patterns directly since they're module-level constants
        from app.services.shopify_service import LLM_UTM_SOURCES, LLM_SOURCE_PATTERNS
        
        # Check UTM first (most reliable)
        utm_combined = f"{utm_source} {utm_medium} {utm_campaign}"
        for source, patterns in LLM_UTM_SOURCES.items():
            for pattern in patterns:
                if pattern in utm_combined:
                    return source
        
        # Check referrer
        referrer_combined = f"{referrer_url} {source_name}"
        for source, patterns in LLM_SOURCE_PATTERNS.items():
            for pattern in patterns:
                if pattern in referrer_combined:
                    return source
        
        return None
    
    def get_conversion_funnel(self, days: int = 30, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Get conversion funnel metrics by combining GA4 traffic with Shopify orders.
        
        Note: This requires GA4 integration with custom dimensions for LLM source.
        """
        funnel = ConversionFunnel()
        
        # Get traffic data from Google Analytics (if available)
        try:
            from app.services.google_api_service import GoogleApiService
            ga = GoogleApiService()
            
            # Get LLM traffic data
            llm_traffic = ga.get_llm_txt_traffic(days=days)
            ai_referrals = ga.get_ai_referral_traffic(days=days)
            
            # Calculate impressions (approximate from traffic)
            funnel.impressions = sum(t.get('sessions', 0) for t in llm_traffic) * 3  # Estimate
            funnel.traffic = sum(t.get('sessions', 0) for t in llm_traffic + ai_referrals)
            
        except Exception as e:
            print(f"[LLMAnalytics] Could not fetch GA4 data: {e}")
            funnel.impressions = 0
            funnel.traffic = 0
        
        # Get conversion data from Shopify
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        orders = self.shopify._fetch_orders_with_utm(start_date, end_date)
        
        # Filter by source if specified
        if source:
            orders = [o for o in orders if self.shopify._identify_llm_source(o) == source]
        
        funnel.purchases = len(orders)
        funnel.revenue = sum(
            float(o.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0)
            for o in orders
        )
        
        # Note: product_views, add_to_carts, checkouts would need
        # Shopify Pixel or GA4 e-commerce tracking with LLM attribution
        
        return {
            "impressions": funnel.impressions,
            "traffic": funnel.traffic,
            "product_views": funnel.product_views,
            "add_to_carts": funnel.add_to_carts,
            "checkouts": funnel.checkouts,
            "purchases": funnel.purchases,
            "revenue": round(funnel.revenue, 2),
            "conversion_rates": {
                "traffic_to_view": round(funnel.view_rate, 2),
                "view_to_cart": round(funnel.cart_rate, 2),
                "cart_to_checkout": round(funnel.checkout_rate, 2),
                "checkout_to_purchase": round(funnel.purchase_rate, 2),
                "overall": round(funnel.overall_conversion, 2)
            },
            "period_days": days
        }

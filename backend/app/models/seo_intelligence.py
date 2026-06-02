"""
SEO Intelligence Models
Historical data tables for Semrush-level keyword tracking, CTR optimization,
cannibalization detection, funnel analytics, content gap analysis, and alerts.

All tables are ADDITIVE — zero changes to existing models.
Written by: DailyCollector job (daily at 06:00 UTC)
Read by: CTROptimizer, PositionTracker, CannibalizationDetector, AlertService, ProductRevenueRanker
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Text, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.session import Base
from datetime import datetime, date as date_type
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============================================================================
# DATABASE MODELS
# ============================================================================


class KeywordDailyMetric(Base):
    """
    Daily GSC data per query for position/CTR tracking.
    
    WRITE: DailyCollector job (06:00 UTC)
    READ: PositionTracker, CTROptimizer, AlertService
    RETENTION: 90 days (cleanup job)
    VOLUME: ~500 rows/day = ~45K rows in 90 days
    """
    __tablename__ = "keyword_daily_metrics"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    query = Column(String(500), nullable=False, index=True)

    # GSC raw data
    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)              # 0.034 = 3.4%
    position = Column(Float, default=0.0)          # 8.3

    # Computed deltas (filled by DailyCollector._compute_metric_deltas)
    position_change_7d = Column(Float)             # -2.1 means improved by 2 spots
    position_change_30d = Column(Float)
    ctr_change_7d = Column(Float)
    impressions_change_7d = Column(Float)

    # CTR benchmarking (filled by DailyCollector._compute_ctr_benchmarks)
    expected_ctr = Column(Float)                   # benchmark CTR for this position
    ctr_gap = Column(Float)                        # actual - expected (negative = underperforming)
    is_underperforming = Column(Boolean, default=False)

    __table_args__ = (
        Index('ix_keyword_date_query', 'date', 'query', unique=True),
    )


class PageDailyMetric(Base):
    """
    Daily GSC + GA4 data per page (product-level).
    
    WRITE: DailyCollector job
    READ: ProductRevenueRanker, CannibalizationDetector
    RETENTION: 90 days
    """
    __tablename__ = "page_daily_metrics"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    page_url = Column(String(500), nullable=False, index=True)
    product_id = Column(String, ForeignKey('products.id'), index=True, nullable=True)

    # GSC data
    gsc_clicks = Column(Integer, default=0)
    gsc_impressions = Column(Integer, default=0)
    gsc_ctr = Column(Float, default=0.0)
    gsc_position = Column(Float, default=0.0)

    # GA4 data (real funnel — fills the gap in CROAnalyticsService)
    ga4_sessions = Column(Integer, default=0)
    ga4_add_to_cart = Column(Integer, default=0)
    ga4_begin_checkout = Column(Integer, default=0)
    ga4_purchases = Column(Integer, default=0)
    ga4_revenue = Column(Float, default=0.0)
    ga4_engagement_time = Column(Float, default=0.0)
    ga4_bounce_rate = Column(Float, default=0.0)

    # Computed: Revenue per impression (key Semrush-like metric)
    revenue_per_impression = Column(Float, default=0.0)
    revenue_per_click = Column(Float, default=0.0)

    __table_args__ = (
        Index('ix_page_date_url', 'date', 'page_url', unique=True),
    )


class KeywordPageMapping(Base):
    """
    Tracks which pages rank for which queries (for cannibalization detection).
    
    WRITE: DailyCollector (from GSC query+page dimension)
    READ: CannibalizationDetector
    RETENTION: 30 days
    """
    __tablename__ = "keyword_page_mappings"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    query = Column(String(500), nullable=False, index=True)
    page_url = Column(String(500), nullable=False)

    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    position = Column(Float, default=0.0)

    # How many pages compete for this query on this day
    competing_pages_count = Column(Integer, default=1)
    is_cannibalized = Column(Boolean, default=False)

    # Page type classification (for collection cannibalization detection)
    page_type = Column(String(20), nullable=True)  # 'blog', 'product', 'collection', 'other'

    __table_args__ = (
        Index('ix_mapping_date_query_page', 'date', 'query', 'page_url', unique=True),
    )


class GA4FunnelDaily(Base):
    """
    Daily GA4 ecommerce funnel metrics (currently MISSING from the system).
    
    WRITE: DailyCollector (GA4 API)
    READ: CRO Analytics, Data Hub, Frontend funnel chart
    """
    __tablename__ = "ga4_funnel_daily"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    device_category = Column(String(20), index=True)  # 'mobile', 'desktop', 'tablet', 'all'

    # Funnel steps
    sessions = Column(Integer, default=0)
    product_views = Column(Integer, default=0)       # view_item events
    add_to_carts = Column(Integer, default=0)        # add_to_cart events
    begin_checkouts = Column(Integer, default=0)     # begin_checkout events
    purchases = Column(Integer, default=0)           # purchase events
    revenue = Column(Float, default=0.0)

    # Computed rates
    view_rate = Column(Float, default=0.0)           # product_views / sessions
    cart_rate = Column(Float, default=0.0)           # add_to_carts / product_views
    checkout_rate = Column(Float, default=0.0)       # begin_checkouts / add_to_carts
    purchase_rate = Column(Float, default=0.0)       # purchases / begin_checkouts
    overall_conversion = Column(Float, default=0.0)  # purchases / sessions

    __table_args__ = (
        Index('ix_funnel_date_device', 'date', 'device_category', unique=True),
    )


class ContentGapResult(Base):
    """
    Content gap analysis results from Grok web search.
    
    WRITE: ContentGapAnalyzer (weekly)
    READ: IntelligenceEngine, Frontend
    RETENTION: Keep latest per competitor+query
    """
    __tablename__ = "content_gap_results"

    id = Column(String, primary_key=True)
    analyzed_at = Column(DateTime, server_default=func.now())
    competitor_domain = Column(String(200), index=True)

    query = Column(String(500), nullable=False)
    competitor_position = Column(Float)          # Their estimated rank
    our_position = Column(Float)                 # Our rank (null = not ranking)
    search_volume_estimate = Column(Integer)     # From impression data
    difficulty_estimate = Column(String(20))     # easy, medium, hard

    # Content recommendation
    recommended_content_type = Column(String(50))   # blog_post, product_page, collection_page
    recommended_title = Column(String(300))
    priority_score = Column(Float, default=0.0)

    status = Column(String(20), default='open')  # open, in_progress, completed, dismissed


class SEOAlert(Base):
    """
    Triggered alerts for position drops, traffic anomalies, etc.
    
    WRITE: AlertService
    READ: Frontend alert feed, IntelligenceEngine
    """
    __tablename__ = "seo_alerts"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    alert_type = Column(String(50), nullable=False, index=True)
    # Types: position_drop, traffic_drop, ctr_drop, new_opportunity,
    #        cannibalization, competitor_movement, algorithm_update

    severity = Column(String(20), nullable=False)  # critical, high, medium, low
    title = Column(String(300), nullable=False)
    description = Column(Text)

    # Context
    affected_query = Column(String(500))
    affected_page = Column(String(500))
    metric_before = Column(Float)
    metric_after = Column(Float)
    metric_change = Column(Float)

    # Resolution
    status = Column(String(20), default='open')  # open, acknowledged, resolved, dismissed
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)


# ============================================================================
# PYDANTIC SCHEMAS (for API responses)
# ============================================================================


class KeywordMetricResponse(BaseModel):
    """Single keyword with all metrics for a given day."""
    query: str
    date: date_type
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    position_change_7d: Optional[float] = None
    position_change_30d: Optional[float] = None
    ctr_change_7d: Optional[float] = None
    impressions_change_7d: Optional[float] = None
    expected_ctr: Optional[float] = None
    ctr_gap: Optional[float] = None
    is_underperforming: bool = False

    class Config:
        from_attributes = True


class KeywordTrendResponse(BaseModel):
    """Keyword with historical trend data (for sparklines)."""
    query: str
    current_position: float
    position_7d_ago: Optional[float] = None
    position_30d_ago: Optional[float] = None
    trend: str = "stable"  # improving, stable, declining
    change_7d: Optional[float] = None
    change_30d: Optional[float] = None
    current_clicks: int = 0
    current_impressions: int = 0
    current_ctr: float = 0.0
    daily_positions: List[Dict[str, Any]] = []  # [{date, position}]

    class Config:
        from_attributes = True


class CTRUnderperformerResponse(BaseModel):
    """Query where actual CTR is below position-based benchmark."""
    query: str
    position: float
    actual_ctr: float
    expected_ctr: float
    ctr_gap: float
    impressions: int
    potential_extra_clicks: int  # if we hit benchmark
    page_url: Optional[str] = None

    class Config:
        from_attributes = True


class CTRSummaryResponse(BaseModel):
    """Dashboard summary for CTR optimization."""
    total_underperforming: int = 0
    total_potential_clicks: int = 0
    avg_ctr_gap: float = 0.0
    top_opportunities: List[CTRUnderperformerResponse] = []
    by_position_bucket: Dict[str, Dict[str, Any]] = {}

    class Config:
        from_attributes = True


class MetaSuggestionResponse(BaseModel):
    """AI-generated meta title/description alternatives."""
    alternatives: List[Dict[str, str]] = []  # [{title, description, rationale}]
    estimated_ctr_improvement: str = ""


class PositionSummaryResponse(BaseModel):
    """Summary of all tracked keyword positions."""
    total_tracked: int = 0
    improving: int = 0
    stable: int = 0
    declining: int = 0
    new_in_top_10: int = 0
    lost_from_top_10: int = 0


class MoversAndShakersResponse(BaseModel):
    """Biggest position changes."""
    biggest_gains: List[Dict[str, Any]] = []
    biggest_losses: List[Dict[str, Any]] = []


class CannibalizationResponse(BaseModel):
    """Cannibalized query with competing pages."""
    query: str
    pages: List[Dict[str, Any]] = []  # [{page_url, clicks, impressions, ctr, position}]
    total_impressions: int = 0
    recommendation: str = ""


class GA4FunnelResponse(BaseModel):
    """GA4 ecommerce funnel for a given period."""
    date: date_type
    device_category: str
    sessions: int = 0
    product_views: int = 0
    add_to_carts: int = 0
    begin_checkouts: int = 0
    purchases: int = 0
    revenue: float = 0.0
    view_rate: float = 0.0
    cart_rate: float = 0.0
    checkout_rate: float = 0.0
    purchase_rate: float = 0.0
    overall_conversion: float = 0.0

    class Config:
        from_attributes = True


class ContentGapResponse(BaseModel):
    """Content gap opportunity."""
    id: str
    competitor_domain: str
    query: str
    competitor_position: Optional[float] = None
    our_position: Optional[float] = None
    search_volume_estimate: Optional[int] = None
    difficulty_estimate: Optional[str] = None
    recommended_content_type: Optional[str] = None
    recommended_title: Optional[str] = None
    priority_score: float = 0.0
    status: str = "open"

    class Config:
        from_attributes = True


class SEOAlertResponse(BaseModel):
    """SEO alert event."""
    id: str
    created_at: datetime
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    affected_query: Optional[str] = None
    affected_page: Optional[str] = None
    metric_before: Optional[float] = None
    metric_after: Optional[float] = None
    metric_change: Optional[float] = None
    status: str = "open"

    class Config:
        from_attributes = True


class AlertSummaryResponse(BaseModel):
    """Alert dashboard summary."""
    open_alerts: int = 0
    by_severity: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    recent: List[SEOAlertResponse] = []


class CollectionStatusResponse(BaseModel):
    """Status of the last daily collection run."""
    queries_stored: int = 0
    mappings_stored: int = 0
    funnel_days_stored: int = 0
    pages_stored: int = 0
    alerts_generated: int = 0
    harvested_at: str = ""
    status: str = "unknown"
    error: Optional[str] = None


class ProductROIResponse(BaseModel):
    """Product ranked by revenue per impression."""
    product_id: Optional[str] = None
    page_url: str
    title: Optional[str] = None
    gsc_impressions: int = 0
    gsc_clicks: int = 0
    ga4_revenue: float = 0.0
    revenue_per_impression: float = 0.0
    revenue_per_click: float = 0.0
    ga4_sessions: int = 0
    ga4_purchases: int = 0

    class Config:
        from_attributes = True

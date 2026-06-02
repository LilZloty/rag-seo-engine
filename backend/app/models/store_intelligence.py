"""
Store Intelligence Models
Data structures for the unified store analytics system.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============================================================================
# DATABASE MODELS
# ============================================================================

class StoreSnapshot(Base):
    """
    Comprehensive snapshot of store health across all channels.
    Captured every 6 hours for trend analysis.
    """
    __tablename__ = "store_snapshots"
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Commerce Data
    commerce_data = Column(JSON, default=dict)
    
    # Traffic Data
    traffic_data = Column(JSON, default=dict)
    
    # SEO Data
    seo_data = Column(JSON, default=dict)
    
    # GEO (AI Visibility) Data
    geo_data = Column(JSON, default=dict)
    
    # Content Data
    content_data = Column(JSON, default=dict)
    
    # Technical Data
    technical_data = Column(JSON, default=dict)
    
    # B2B Customer Data
    b2b_data = Column(JSON, default=dict)
    
    # Aggregated Health Score (0-100)
    overall_health_score = Column(Integer, default=0)
    commerce_health = Column(Integer, default=0)
    cro_health = Column(Integer, default=0)
    seo_health = Column(Integer, default=0)
    geo_health = Column(Integer, default=0)
    technical_health = Column(Integer, default=0)
    
    # Trend indicators
    trend_direction = Column(String(20), default='stable')  # improving, stable, declining


class IntelligenceReport(Base):
    """
    AI-generated intelligence report with issues, opportunities, and insights.
    """
    __tablename__ = "intelligence_reports"
    
    id = Column(String, primary_key=True)
    snapshot_id = Column(String, ForeignKey('store_snapshots.id'), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Critical issues requiring immediate attention
    critical_issues = Column(JSON, default=list)
    
    # Growth opportunities
    opportunities = Column(JSON, default=list)
    
    # Trending metrics
    trends = Column(JSON, default=dict)
    
    # Anomalies detected
    anomalies = Column(JSON, default=list)
    
    # Cross-channel correlations
    correlations = Column(JSON, default=list)
    
    # AI-generated summary
    executive_summary = Column(Text)
    
    # This week's focus areas
    weekly_focus = Column(JSON, default=list)
    
    # Strategic initiatives (3-month view)
    strategic_initiatives = Column(JSON, default=list)


class AIRecommendation(Base):
    """
    Individual AI-generated recommendation with tracking.
    """
    __tablename__ = "ai_recommendations"
    
    id = Column(String, primary_key=True)
    report_id = Column(String, ForeignKey('intelligence_reports.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Categorization
    category = Column(String(50), index=True)  # CRO, SEO, GEO, CONTENT, TECHNICAL, INVENTORY
    priority = Column(String(20), index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    
    # Content
    title = Column(String(255), nullable=False)
    description = Column(Text)
    action_steps = Column(JSON, default=list)
    
    # Impact prediction
    revenue_impact = Column(String(100))  # e.g., "+$500/month"
    traffic_impact = Column(String(100))   # e.g., "+200 sessions/month"
    effort_required = Column(String(50))   # e.g., "1 hour", "1 day", "1 week"
    confidence_score = Column(Float, default=0.0)  # 0-1
    
    # Status tracking
    status = Column(String(20), default='pending')  # pending, in_progress, completed, dismissed
    implemented_at = Column(DateTime(timezone=True))
    actual_impact = Column(JSON, default=dict)  # Track actual vs predicted
    
    # Auto-implementation
    can_auto_implement = Column(Boolean, default=False)
    auto_implement_endpoint = Column(String(255))  # API endpoint if applicable


class MetricTrend(Base):
    """
    Historical trends for key metrics.
    """
    __tablename__ = "metric_trends"
    
    id = Column(String, primary_key=True)
    metric_name = Column(String(100), index=True)  # e.g., "conversion_rate", "organic_traffic"
    metric_category = Column(String(50), index=True)  # commerce, seo, cro, geo, technical
    
    timestamp = Column(DateTime(timezone=True), index=True)
    value = Column(Float)
    
    # Change tracking
    change_7d = Column(Float)  # 7-day change
    change_30d = Column(Float)  # 30-day change
    
    # Thresholds
    is_above_target = Column(Boolean)
    is_critical = Column(Boolean)


# ============================================================================
# PYDANTIC SCHEMAS (for API)
# ============================================================================

class CommerceData(BaseModel):
    """E-commerce metrics snapshot."""
    total_revenue_30d: float = 0.0
    total_orders_30d: int = 0
    total_sessions_30d: int = 0
    aov: float = 0.0
    conversion_rate: float = 0.0
    
    # Product performance
    top_products: List[Dict[str, Any]] = []
    slow_movers: List[Dict[str, Any]] = []
    out_of_stock_count: int = 0
    low_stock_count: int = 0
    
    # Category breakdown
    category_performance: List[Dict[str, Any]] = []
    
    # Customer metrics
    new_customers_30d: int = 0
    returning_customers_30d: int = 0
    customer_ltv_avg: float = 0.0


class TrafficData(BaseModel):
    """Traffic and CRO metrics snapshot."""
    total_sessions: int = 0
    unique_users: int = 0
    
    # Funnel metrics
    add_to_cart_rate: float = 0.0
    checkout_rate: float = 0.0
    purchase_rate: float = 0.0
    cart_abandonment_rate: float = 0.0
    
    # Channel breakdown
    channel_performance: Dict[str, Dict[str, Any]] = {}
    
    # Page performance
    top_landing_pages: List[Dict[str, Any]] = []
    high_exit_pages: List[Dict[str, Any]] = []
    
    # Behavior
    avg_session_duration: float = 0.0
    bounce_rate: float = 0.0
    pages_per_session: float = 0.0
    
    # Device
    mobile_percentage: float = 0.0
    desktop_percentage: float = 0.0


class SEOData(BaseModel):
    """Search performance metrics."""
    total_clicks: int = 0
    total_impressions: int = 0
    avg_ctr: float = 0.0
    avg_position: float = 0.0
    
    # Query analysis
    top_queries: List[Dict[str, Any]] = []
    declining_queries: List[Dict[str, Any]] = []
    opportunity_queries: List[Dict[str, Any]] = []
    
    # Page-level
    indexed_pages: int = 0
    products_optimized: int = 0
    products_needing_seo: int = 0
    
    # Competitor tracking
    competitor_mentions: int = 0
    your_mentions: int = 0


class GEOData(BaseModel):
    """AI/LLM visibility metrics."""
    grok_score: int = 0
    openai_score: int = 0
    perplexity_score: int = 0
    overall_visibility: int = 0
    
    # Citation tracking
    total_citations: int = 0
    citations_by_source: Dict[str, int] = {}
    
    # Traffic
    llm_referral_sessions: int = 0
    llm_conversions: int = 0
    llm_conversion_rate: float = 0.0
    
    # Competitive
    vs_competitors: Dict[str, Any] = {}


class ContentData(BaseModel):
    """Content quality and coverage metrics."""
    products_with_content: int = 0
    products_needing_content: int = 0
    avg_content_score: float = 0.0
    
    # Collection content
    collections_optimized: int = 0
    collections_needing_work: int = 0
    
    # Blog/Authority
    blog_posts_30d: int = 0
    total_blog_posts: int = 0
    
    # Content gaps
    missing_topics: List[str] = []
    outdated_content: List[Dict[str, Any]] = []


class B2BData(BaseModel):
    """B2B customer tier intelligence."""
    # Tier member counts
    total_b2b_customers: int = 0
    tier_breakdown: Dict[str, int] = {}  # {"Platino B2B": 8, "Oro B2B": 20, ...}
    
    # Tag health
    correctly_tagged: int = 0
    missing_tags: int = 0
    tag_health_pct: float = 0.0
    
    # Revenue concentration  
    tier_revenue: Dict[str, float] = {}  # Revenue per tier
    top_client_revenue_pct: float = 0.0  # % of revenue from top 10 clients
    
    # Customer health
    active_last_30d: int = 0
    active_last_90d: int = 0
    at_risk_clients: int = 0  # Haven't ordered in 60+ days
    churned_clients: int = 0  # Haven't ordered in 120+ days


class TechnicalData(BaseModel):
    """Technical SEO and performance metrics."""
    # Core Web Vitals
    lcp: float = 0.0  # Largest Contentful Paint
    fid: float = 0.0  # First Input Delay
    cls: float = 0.0  # Cumulative Layout Shift
    
    cwv_status: str = "unknown"  # good, needs_improvement, poor
    
    # Site health
    broken_links_count: int = 0
    redirect_chains_count: int = 0
    
    # Schema
    schema_coverage_pct: float = 0.0
    schema_errors_count: int = 0
    
    # Mobile
    mobile_usability_issues: int = 0
    
    # Security
    ssl_valid: bool = True
    security_issues: List[str] = []


class StoreSnapshotResponse(BaseModel):
    """API response for store snapshot."""
    id: str
    timestamp: datetime
    
    commerce: CommerceData
    traffic: TrafficData
    seo: SEOData
    geo: GEOData
    content: ContentData
    technical: TechnicalData
    
    health_scores: Dict[str, int]
    trend: str
    
    class Config:
        from_attributes = True


class CriticalIssue(BaseModel):
    """Critical issue requiring immediate attention."""
    category: str
    severity: str
    title: str
    description: str
    impact: str
    action: str
    estimated_revenue_loss: Optional[str] = None


class Opportunity(BaseModel):
    """Growth opportunity."""
    category: str
    title: str
    description: str
    potential_impact: str
    effort: str
    action: str
    priority_score: float = 0.0  # Calculated impact/effort ratio


class CorrelationInsight(BaseModel):
    """Cross-channel correlation insight."""
    insight: str
    metric_1: str
    metric_2: str
    correlation: float
    recommendation: str


class IntelligenceReportResponse(BaseModel):
    """API response for intelligence report."""
    id: str
    snapshot_id: str
    generated_at: datetime
    
    executive_summary: str
    store_health: Dict[str, Any]
    
    critical_issues: List[CriticalIssue]
    opportunities: List[Opportunity]
    correlations: List[CorrelationInsight]
    
    weekly_focus: List[Dict[str, Any]]
    strategic_initiatives: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class AIRecommendationResponse(BaseModel):
    """API response for AI recommendation."""
    id: str
    category: str
    priority: str
    title: str
    description: str
    action_steps: List[str]
    
    revenue_impact: str
    traffic_impact: str
    effort_required: str
    confidence_score: float
    
    status: str
    can_auto_implement: bool
    
    class Config:
        from_attributes = True


class StoreHealthGauge(BaseModel):
    """Simplified health score for dashboard."""
    overall: int
    trend: str
    breakdown: Dict[str, int]
    last_updated: datetime

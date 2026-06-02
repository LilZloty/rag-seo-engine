from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, JSON, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Product(Base):
    __tablename__ = "products"
    
    id = Column(String, primary_key=True)
    shopify_id = Column(String(50), unique=True, nullable=False, index=True)
    sku = Column(String(100))
    title = Column(Text, nullable=False)
    handle = Column(String(255))
    current_description_html = Column(Text)
    image_count = Column(Integer, default=0)
    image_filenames = Column(JSON)
    needs_seo = Column(Boolean, default=False, index=True)
    seo_status = Column(String(20), default='none')
    total_sold = Column(Integer, default=0, index=True)  # Total units sold (legacy - keeps 90d data)
    total_revenue = Column(Float, default=0.0)  # Total revenue from sales (legacy - keeps 90d data)
    
    # Time-based sales data
    sold_30d = Column(Integer, default=0)  # Units sold in last 30 days
    revenue_30d = Column(Float, default=0.0)  # Revenue in last 30 days
    sold_90d = Column(Integer, default=0)  # Units sold in last 90 days
    revenue_90d = Column(Float, default=0.0)  # Revenue in last 90 days
    sold_365d = Column(Integer, default=0)  # Units sold in last 365 days
    revenue_365d = Column(Float, default=0.0)  # Revenue in last 365 days
    sold_all_time = Column(Integer, default=0)  # All-time units sold
    revenue_all_time = Column(Float, default=0.0)  # All-time revenue
    cached_vehicle_fitments = Column(JSON)  # Local cache of vehicle fitments (avoids slow Shopify API)
    transmission_code = Column(String(30), index=True)  # Computed: DQ200, 4L60E, etc. for AEO chunking
    transmission_codes = Column(JSON, nullable=True)  # Multi-code array (Phase 1.2): ['VW095','VW096','01M'] — cross-reference emission
    product_type = Column(String(100), index=True)  # From Shopify: Filtros, Partes Electrizas, etc.
    vendor = Column(String(100))  # Cached vendor for Schema.org
    price = Column(String(20))  # Cached price for Schema.org
    last_scraped_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Shopify timestamps (when product was created/updated in Shopify)
    shopify_created_at = Column(DateTime(timezone=True), nullable=True)
    shopify_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # GA4 Analytics Fields
    ga4_sessions = Column(Integer, default=0, index=True)
    ga4_engagement_time = Column(Float, default=0.0)  # avg seconds
    ga4_bounce_rate = Column(Float, default=0.0)  # percentage
    ga4_revenue = Column(Float, default=0.0)

    # Search Console Fields
    gsc_impressions = Column(Integer, default=0, index=True)
    gsc_clicks = Column(Integer, default=0)
    gsc_ctr = Column(Float, default=0.0)
    gsc_position = Column(Float, default=0.0)

    # Calculated Fields
    performance_score = Column(Integer, default=0, index=True)  # 0-100 combined score
    opportunity_level = Column(String(20), default='low', index=True)  # high/medium/low
    seo_score = Column(Integer, default=0, index=True)  # 0-100 SEO optimization score
    
    # Inventory Fields
    inventory_quantity = Column(Integer, default=None, nullable=True)  # Total inventory across all locations
    inventory_by_location = Column(JSON, nullable=True)  # {"Location Name": qty, ...} per-sucursal breakdown
    inventory_status = Column(String(20), default=None, nullable=True)  # in_stock, out_of_stock, low_stock
    last_inventory_sync = Column(DateTime(timezone=True), nullable=True)
    
    # Inventory Intelligence Fields (Phase 1)
    inventory_velocity = Column(Float, nullable=True)          # Units sold per day (30d avg)
    days_of_supply = Column(Float, nullable=True)              # Current stock / velocity
    demand_score = Column(Integer, default=0)                  # 0-100 composite score
    stock_health = Column(String(20), nullable=True)           # healthy, warning, critical, dead
    dead_stock_tier = Column(String(20), nullable=True, index=True)  # slow, stale, dead, obsolete (NULL if not applicable)
    last_sold_at = Column(DateTime(timezone=True), nullable=True)    # Date of most recent sale (from Shopify orders)
    low_stock_threshold = Column(Integer, default=5)           # Per-product dynamic threshold
    last_stockout_date = Column(DateTime(timezone=True), nullable=True)
    stockout_frequency_90d = Column(Integer, default=0)        # Times OOS in 90 days
    active_subscribers = Column(Integer, default=0)            # Waitlist size (Phase 2)

    # Action Center computed fields
    urgency_score = Column(Integer, default=0)                   # 0-100, -1 for dead stock
    revenue_lost_est = Column(Float, default=0.0)                # Estimated revenue lost while OOS
    suggested_reorder_qty = Column(Integer, default=0)           # Suggested units to reorder

    # Anchor Product / Co-purchase fields
    co_purchase_count = Column(Integer, default=0)               # Times bought with other products (multi-item orders)
    avg_cart_companions = Column(Float, default=0.0)             # Avg # of other products in same cart
    cart_revenue_multiplier = Column(Float, default=1.0)         # Avg total cart value / this product's price
    anchor_score = Column(Integer, default=0)                    # 0-100: how much this product drives multi-product sales
    top_companions = Column(JSON, nullable=True)                 # Top 5 products frequently bought with this one

    # Timestamps
    last_analytics_sync = Column(DateTime(timezone=True))

    # Priority Score — composite ranking that drives the Optimization Queue.
    # Computed nightly by `recompute_product_priority_scores`. Components stored
    # alongside so the UI can show why a product made the queue without recomputing.
    # See backend/app/services/priority_score.py for the formula.
    priority_score = Column(Float, default=0.0, index=True)
    priority_components = Column(JSON, nullable=True)
    priority_computed_at = Column(DateTime(timezone=True), nullable=True)

    content_drafts = relationship("ContentDraft", back_populates="product", cascade="all, delete-orphan")
    ai_analysis_cache = relationship("AIAnalysisCache", back_populates="product", uselist=False, cascade="all, delete-orphan")

    @property
    def description_length(self) -> int:
        """Returns the length of the current description HTML."""
        desc = self.current_description_html
        return len(desc) if desc else 0


class ContentDraft(Base):
    __tablename__ = "content_drafts"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey('products.id'))
    h1_title = Column(String(100))
    hook_html = Column(Text)
    technical_specs = Column(JSON)
    installation_guide = Column(Text)
    faq_items = Column(JSON)
    compatible_vehicles = Column(JSON)
    alt_tags = Column(JSON)
    short_description = Column(String(160))
    meta_title = Column(String(70))
    meta_description = Column(String(160))
    url_handle = Column(String(255))
    llm_used = Column(String(50))

    product = relationship("Product", back_populates="content_drafts")


class AIAnalysisCache(Base):
    """Cache for AI-powered SEO/AEO/GEO analysis results to reduce API costs"""
    __tablename__ = "ai_analysis_cache"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False, index=True)

    # Analysis scores
    seo_score = Column(Integer, default=0)
    aeo_score = Column(Integer, default=0)
    geo_score = Column(Integer, default=0)

    # Full analysis results stored as JSON
    seo_analysis = Column(JSON, default=dict)
    aeo_analysis = Column(JSON, default=dict)
    geo_analysis = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)
    priority_actions = Column(JSON, default=list)
    expected_impact = Column(JSON, default=dict)

    # v2 Enhanced fields (stored as JSON)
    primary_issue = Column(JSON, nullable=True)
    performance_vs_benchmark = Column(JSON, nullable=True)
    ai_visibility_scores = Column(JSON, nullable=True)
    top_opportunity_queries = Column(JSON, nullable=True)
    trend_indicators = Column(JSON, nullable=True)
    estimated_revenue_opportunity = Column(Float, nullable=True)
    performance_tier = Column(String(20), nullable=True)

    # Analytics snapshot (to know if data changed)
    ga4_sessions_snapshot = Column(Integer, default=0)
    gsc_impressions_snapshot = Column(Integer, default=0)
    sold_30d_snapshot = Column(Integer, default=0)
    seo_score_snapshot = Column(Integer, default=0)

    # Cache metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_stale = Column(Boolean, default=False)  # Marked stale when product data changes significantly

    # Relationship to Product
    product = relationship("Product", back_populates="ai_analysis_cache")


class SupplierPart(Base):
    __tablename__ = "supplier_parts"
    
    id = Column(String, primary_key=True)
    supplier_name = Column(String(50), nullable=False, index=True)
    part_number = Column(String(100), index=True)
    product_name = Column(Text)
    transmission_code = Column(String(20), index=True)
    part_type = Column(String(50), index=True)
    specifications = Column(JSON)
    compatible_vehicles = Column(JSON)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    source_url = Column(Text)
    qdrant_id = Column(String)


class ProductAnalyticsSnapshot(Base):
    """Historical snapshots of product analytics for trend tracking"""
    __tablename__ = "product_analytics_snapshots"
    __table_args__ = (
        Index('ix_snapshots_product_date', 'product_id', 'snapshot_date'),
    )

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False, index=True)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Sales metrics — multiple windows to distinguish signal from noise.
    # 30d is noisy for slow-moving transmission parts; 90d/365d show the real trend.
    sold_30d = Column(Integer, default=0)
    revenue_30d = Column(Float, default=0.0)
    sold_90d = Column(Integer, default=0)
    revenue_90d = Column(Float, default=0.0)
    sold_365d = Column(Integer, default=0)
    revenue_365d = Column(Float, default=0.0)
    
    # GA4 metrics
    ga4_sessions = Column(Integer, default=0)
    ga4_engagement_time = Column(Float, default=0.0)
    ga4_bounce_rate = Column(Float, default=0.0)
    ga4_revenue = Column(Float, default=0.0)
    
    # Search Console metrics
    gsc_impressions = Column(Integer, default=0)
    gsc_clicks = Column(Integer, default=0)
    gsc_ctr = Column(Float, default=0.0)
    gsc_position = Column(Float, default=0.0)
    gsc_top_queries = Column(JSON, default=list)  # Top 10 queries with metrics
    
    # AI Visibility (from ProductVisibilitySnapshot)
    ai_visibility_score = Column(Integer, default=0)
    ai_visibility_by_llm = Column(JSON, default=dict)
    
    # Calculated scores
    performance_score = Column(Integer, default=0)
    seo_score = Column(Integer, default=0)

    # Shopify product state (for overlap detection — what else changed besides content?)
    price = Column(String(20), default=None, nullable=True)
    inventory_quantity = Column(Integer, default=None, nullable=True)
    image_count = Column(Integer, default=0)
    description_length = Column(Integer, default=0)

    # Snapshot type (daily, weekly, monthly)
    snapshot_type = Column(String(20), default='daily')


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"
    
    id = Column(String, primary_key=True)
    supplier_name = Column(String(50))
    status = Column(String(20))
    parts_found = Column(Integer, default=0)
    errors = Column(JSON)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

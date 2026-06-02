"""
Collection Optimizer Models
Database models for tracking collection optimization workflow
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import Base


class CollectionOptimizer(Base):
    """
    Tracks Shopify collections and their optimization status
    """
    __tablename__ = "collection_optimizer"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Shopify Collection Info
    shopify_collection_id = Column(String, unique=True, index=True)
    collection_handle = Column(String, index=True)
    collection_title = Column(String)
    collection_url = Column(String)
    
    # Collection Type/Category
    category = Column(String, index=True)  # 'transmission', 'direccion', 'frenos', etc.
    
    # Current Content Status
    has_educational_content = Column(Boolean, default=False)
    has_faq_section = Column(Boolean, default=False)
    has_schema_markup = Column(Boolean, default=False)
    
    # Metafield Status
    metafield_description = Column(Text)  # Current content in metafield
    metafield_faq = Column(Text)  # Current FAQ content
    metafield_updated_at = Column(DateTime)
    
    # Analytics Baseline (before optimization)
    baseline_impressions = Column(Integer, default=0)
    baseline_clicks = Column(Integer, default=0)
    baseline_ctr = Column(Float, default=0.0)
    baseline_position = Column(Float, default=0.0)
    baseline_date = Column(DateTime)
    
    # Current Performance
    current_impressions = Column(Integer, default=0)
    current_clicks = Column(Integer, default=0)
    current_ctr = Column(Float, default=0.0)
    current_position = Column(Float, default=0.0)
    last_analytics_sync = Column(DateTime)
    
    # Optimization Status
    optimization_status = Column(String, default="pending")  # pending, analyzing, generating, ready, published, tracking
    optimization_priority = Column(Integer, default=0)  # 1-10, higher = more important
    
    # Content Generation
    generated_content = Column(Text)  # AI-generated educational content
    generated_faq = Column(JSON)  # List of FAQ items
    generated_schema = Column(Text)  # JSON-LD schema markup
    content_generated_at = Column(DateTime)
    
    # A/B Testing
    ab_test_enabled = Column(Boolean, default=False)
    ab_test_variant = Column(String)  # 'control', 'optimized'
    ab_test_start_date = Column(DateTime)
    ab_test_results = Column(JSON)
    
    # GA4 Engagement Metrics
    ga4_sessions = Column(Integer, default=0)
    ga4_bounce_rate = Column(Float, default=0.0)  # Percentage (0-100)
    ga4_avg_engagement_time = Column(Float, default=0.0)  # Seconds
    
    # GA4 Conversion Metrics
    ga4_conversions = Column(Integer, default=0)
    ga4_conversion_rate = Column(Float, default=0.0)  # Percentage (0-100)
    ga4_revenue = Column(Float, default=0.0)  # Revenue in local currency
    
    # AI/GEO Tracking
    ga4_ai_referral_sessions = Column(Integer, default=0)
    ga4_ai_referral_conversions = Column(Integer, default=0)
    
    # GA4 Baseline (before optimization)
    baseline_ga4_sessions = Column(Integer, default=0)
    baseline_ga4_conversions = Column(Integer, default=0)
    baseline_ga4_revenue = Column(Float, default=0.0)
    baseline_ga4_date = Column(DateTime)
    
    # GA4 Sync Tracking
    last_ga4_sync = Column(DateTime)

    # Shopify Direct Attribution
    shopify_attributed_revenue = Column(Float, default=0.0)
    shopify_attributed_orders = Column(Integer, default=0)
    shopify_llm_revenue = Column(Float, default=0.0)
    shopify_llm_orders = Column(Integer, default=0)
    last_shopify_sync = Column(DateTime)

    # DataForSEO
    dataforseo_primary_keyword = Column(String)
    dataforseo_volume = Column(Integer, default=0)
    dataforseo_competition = Column(String)  # 'LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'
    dataforseo_cpc = Column(Float, default=0.0)
    dataforseo_top_competitor = Column(String)
    dataforseo_serp_features = Column(JSON)
    dataforseo_people_also_ask = Column(JSON)
    dataforseo_organic_results = Column(JSON)  # Top 10 organic SERP results (cached permanently)
    dataforseo_last_sync = Column(DateTime)

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    search_queries = relationship("CollectionSearchQuery", back_populates="collection", cascade="all, delete-orphan")
    optimization_history = relationship("CollectionOptimizationHistory", back_populates="collection", cascade="all, delete-orphan")
    analytics_snapshots = relationship("CollectionAnalyticsSnapshot", back_populates="collection", cascade="all, delete-orphan")
    content_drafts = relationship("CollectionContentDraft", back_populates="collection", cascade="all, delete-orphan")
    cannibalization_results = relationship("CollectionCannibalizationResult", back_populates="collection", cascade="all, delete-orphan")


class CollectionSearchQuery(Base):
    """
    Stores Search Console queries related to each collection
    """
    __tablename__ = "collection_search_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collection_optimizer.id"))
    
    # Query Data
    query = Column(String, index=True)
    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    position = Column(Float, default=0.0)
    
    # Classification
    query_type = Column(String)  # 'question', 'product', 'brand', 'comparison'
    intent = Column(String)  # 'informational', 'transactional', 'navigational'
    priority_score = Column(Float, default=0.0)  # Calculated opportunity score
    
    # Date
    date_recorded = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    collection = relationship("CollectionOptimizer", back_populates="search_queries")


class CollectionOptimizationHistory(Base):
    """
    Tracks all optimization actions performed on collections
    """
    __tablename__ = "collection_optimization_history"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collection_optimizer.id"))
    
    # Action Details
    action_type = Column(String)  # 'sync', 'analyze', 'generate', 'deploy', 'track'
    action_status = Column(String)  # 'success', 'failed', 'in_progress'
    action_details = Column(JSON)  # Additional context
    
    # Content Changes
    content_before = Column(Text)
    content_after = Column(Text)
    
    # Performance Impact
    impressions_change = Column(Integer)
    clicks_change = Column(Integer)
    ctr_change = Column(Float)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    collection = relationship("CollectionOptimizer", back_populates="optimization_history")


class CollectionContentTemplate(Base):
    """
    Reusable content templates for different collection types
    """
    __tablename__ = "collection_content_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template Info
    template_name = Column(String, unique=True)
    category = Column(String, index=True)  # 'transmission', 'direccion', 'general'
    content_type = Column(String)  # 'educational', 'faq', 'schema'
    
    # Template Content
    template_structure = Column(Text)  # HTML/Markdown template with placeholders
    example_content = Column(Text)  # Example of filled template
    
    # Placeholders
    placeholders = Column(JSON)  # ['{product_name}', '{symptoms}', '{benefits}']
    
    # Usage
    usage_count = Column(Integer, default=0)
    avg_performance_score = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

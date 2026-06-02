"""
Collection Intelligence Models
Database models for collection analytics snapshots, content drafts,
and cannibalization detection results.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class CollectionAnalyticsSnapshot(Base):
    """
    Historical snapshots of collection analytics for trend tracking.
    Mirrors ProductAnalyticsSnapshot pattern.

    WRITE: Snapshot job (daily)
    READ: Trend charts, before/after optimization analysis
    RETENTION: 90 days
    """
    __tablename__ = "collection_analytics_snapshots"
    __table_args__ = (
        Index('ix_col_snapshots_collection_date', 'collection_id', 'snapshot_date'),
    )

    id = Column(String, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collection_optimizer.id'), nullable=False, index=True)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # GSC metrics
    gsc_impressions = Column(Integer, default=0)
    gsc_clicks = Column(Integer, default=0)
    gsc_ctr = Column(Float, default=0.0)
    gsc_position = Column(Float, default=0.0)
    gsc_top_queries = Column(JSON, default=list)

    # GA4 metrics
    ga4_sessions = Column(Integer, default=0)
    ga4_bounce_rate = Column(Float, default=0.0)
    ga4_engagement_time = Column(Float, default=0.0)
    ga4_conversions = Column(Integer, default=0)
    ga4_conversion_rate = Column(Float, default=0.0)
    ga4_revenue = Column(Float, default=0.0)
    ga4_ai_referral_sessions = Column(Integer, default=0)

    # Shopify attribution
    shopify_attributed_revenue = Column(Float, default=0.0)
    shopify_attributed_orders = Column(Integer, default=0)
    shopify_llm_revenue = Column(Float, default=0.0)
    shopify_llm_orders = Column(Integer, default=0)

    # DataForSEO
    dataforseo_volume = Column(Integer, default=0)
    dataforseo_competition = Column(String)

    # Optimization status at snapshot time
    optimization_status = Column(String)
    has_content = Column(Boolean, default=False)

    # Snapshot type
    snapshot_type = Column(String(20), default='daily')

    # Relationship
    collection = relationship("CollectionOptimizer", back_populates="analytics_snapshots")


class CollectionContentDraft(Base):
    """
    Content versioning for collections. Allows multiple drafts before deploying.

    WRITE: Content generation pipeline
    READ: Draft review UI, deploy workflow
    """
    __tablename__ = "collection_content_drafts"

    id = Column(String, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collection_optimizer.id'), nullable=False, index=True)

    # Version tracking
    version = Column(Integer, default=1)
    draft_status = Column(String, default='draft')  # draft, approved, deployed, archived

    # Generated content
    educational_content = Column(Text)
    faq_content = Column(JSON)
    schema_markup = Column(Text)

    # Meta fields
    meta_title = Column(String)
    meta_description = Column(Text)

    # Cannibalization context
    cannibalization_check = Column(JSON)  # Stores CannibalizationCheckResult at generation time
    safe_keywords_used = Column(JSON)  # Keywords targeted in this draft
    blocked_keywords_avoided = Column(JSON)  # Keywords excluded from this draft

    # Generation metadata
    generation_provider = Column(String)  # Which LLM was used
    generation_prompt_hash = Column(String)  # Hash of prompt for reproducibility
    multi_agent = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    collection = relationship("CollectionOptimizer", back_populates="content_drafts")


class CollectionCannibalizationResult(Base):
    """
    Persistent cannibalization analysis results per collection.
    Stores which keywords are safe/blocked/warning for content generation.

    WRITE: CannibalizationGuard service
    READ: Content generation guard, dashboard warnings, recommendations
    """
    __tablename__ = "collection_cannibalization_results"

    id = Column(String, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collection_optimizer.id'), nullable=False, index=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Keyword analysis
    target_keywords = Column(JSON)  # All keywords considered
    safe_keywords = Column(JSON)  # [{keyword, intent, volume_estimate}]
    blocked_keywords = Column(JSON)  # [{keyword, conflicting_url, page_type, position, severity, recommendation}]
    warning_keywords = Column(JSON)  # Same structure as blocked

    # Conflict details
    conflicts = Column(JSON)  # Full list of KeywordConflict objects

    # Scoring
    risk_score = Column(Float, default=0.0)  # 0-100 (0 = all safe, 100 = all blocked)
    status = Column(String, default='safe')  # safe, warning, blocked
    can_generate = Column(Boolean, default=True)
    generation_guidance = Column(Text)  # AI-ready summary of what to include/exclude

    # Relationship
    collection = relationship("CollectionOptimizer", back_populates="cannibalization_results")

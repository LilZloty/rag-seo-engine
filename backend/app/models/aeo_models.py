"""
AEO (Answer Engine Optimization) Database Models

Phase 1: ChunkApprovalStatus, TransmissionPattern, AEOConfig, BlogCache
Phase 2: Knowledge Graph entities for GEO (FaultCode, Symptom, Solution)
"""

from typing import Optional
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.core.config import settings


class ChunkApprovalStatus(Base):
    """Tracks approval status per product_type for AEO inclusion."""
    __tablename__ = "chunk_approval_status"
    
    product_type = Column(String(100), primary_key=True)
    approved = Column(Boolean, default=False, index=True)
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TransmissionPattern(Base):
    """Configurable transmission code patterns for chunk extraction."""
    __tablename__ = "transmission_patterns"
    
    code = Column(String(30), primary_key=True)
    category = Column(String(50), nullable=False, index=True)
    description = Column(String(200))
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AEOConfig(Base):
    """Global AEO configuration settings."""
    __tablename__ = "aeo_config"
    
    id = Column(String(50), primary_key=True, default="default")
    llms_txt_version = Column(String(20), default="1.0.0")
    include_blogs = Column(Boolean, default=True)
    include_collections = Column(Boolean, default=True)
    include_fault_codes = Column(Boolean, default=True)  # NEW: GEO diagnostic content
    max_products_per_category = Column(String(10), default="50")
    store_name = Column(String(200), default=f"{settings.STORE_NAME} - Especialistas en Transmisiones Automaticas")
    store_description = Column(Text, default="La fuente lider en Mexico para diagnostico y reparacion de transmisiones automaticas. Soluciones expertas para codigos P0700, P0841, P0706 y mas de 50 codigos de falla.")
    authority_statement = Column(Text, default="Mas de 10,000 lectores ayudados. Confianza de 10,000+ mecanicos en Latinoamerica.")  # NEW
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BlogCache(Base):
    """Cache for Shopify blog articles."""
    __tablename__ = "blog_cache"
    
    id = Column(String(50), primary_key=True)
    blog_handle = Column(String(100), index=True)
    title = Column(String(300))
    handle = Column(String(200))
    summary = Column(Text)
    tags = Column(Text)
    published_at = Column(DateTime(timezone=True))
    include_in_llms_txt = Column(Boolean, default=True)
    cached_at = Column(DateTime(timezone=True), server_default=func.now())


# ============ GEO Knowledge Graph Entities ============

class FaultCode(Base):
    """
    Fault code entity for Knowledge Graph.
    
    Example: P0700 (General Transmission Fault)
    Based on GA data: P0700 is #1 traffic driver with 1,500+ monthly clicks
    """
    __tablename__ = "fault_codes"
    
    code = Column(String(20), primary_key=True)  # P0700, P0841, etc.
    name = Column(String(200))  # "General Transmission Fault"
    description = Column(Text)  # Full explanation
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    monthly_clicks = Column(Integer, default=0)  # From GA data
    monthly_impressions = Column(Integer, default=0)
    current_ctr = Column(Float, default=0.0)
    avg_position = Column(Float, default=0.0)  # Average position in GSC
    query_type = Column(String(50), default="direct_fault")  # direct_fault, informational, product_search
    
    # Relationships
    transmissions = Column(JSON)  # ["4L60E", "A604", "RE5R05A"]
    vehicles = Column(JSON)  # ["Chrysler 300", "Silverado", "Dodge Ram"]
    common_causes = Column(JSON)  # ["Solenoid failure", "Wiring issue"]
    symptoms_text = Column(JSON)  # ["Check engine light", "Harsh shifting"]
    
    # Content URLs
    blog_url = Column(String(300))  # /blogs/news/que-es-p0700
    collection_url = Column(String(300))  # /collections/p0700-solutions
    
    # Status
    is_priority = Column(Boolean, default=False, index=True)  # Top 10 from GA
    include_in_llms_txt = Column(Boolean, default=True)
    has_faq_schema = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    solutions = relationship("Solution", back_populates="fault_code", cascade="all, delete-orphan")
    blog_solutions = relationship("BlogSolution", back_populates="fault_code")


class Solution(Base):
    """
    Solution entity linking FaultCode to Products.
    
    Example: "Solenoid Kit" fixes P0700 with 65% success rate
    """
    __tablename__ = "solutions"
    
    id = Column(String(50), primary_key=True)
    fault_code_id = Column(String(20), ForeignKey("fault_codes.code"), nullable=False, index=True)
    
    title = Column(String(200)) # NEW: Friendly name for the solution
    solution_type = Column(String(50))  # part_replacement, adjustment, software, service
    description = Column(Text)
    success_rate = Column(Float)  # 0.0 to 1.0 (65% = 0.65)
    difficulty_level = Column(String(20))  # easy, medium, hard, professional
    estimated_cost = Column(String(50))  # "$50-150"
    
    # Linked products
    product_ids = Column(JSON)  # ["prod-123", "prod-456"]
    recommended_skus = Column(JSON) # NEW: List of recommended SKUs
    collection_url = Column(String(300)) # NEW: Linked collection for the solution
    
    # Display order
    priority = Column(Integer, default=100)
    is_recommended = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    fault_code = relationship("FaultCode", back_populates="solutions")


class DiagnosticContent(Base):
    """
    Content statistics for diagnostic pages (from GA data).
    
    Tracks: "10,000+ readers helped" type stats for authority signals
    """
    __tablename__ = "diagnostic_content"
    
    id = Column(String(50), primary_key=True)
    page_type = Column(String(50), index=True)  # fault_code, symptom, how_to
    page_url = Column(String(300))
    title = Column(String(300))
    
    # GA Metrics
    active_users = Column(Integer, default=0)
    avg_engagement_seconds = Column(Integer, default=0)
    key_events = Column(Integer, default=0)  # Conversions
    
    # Authority signals for GEO
    readers_helped_text = Column(String(100))  # "10,000+ readers helped"
    
    last_synced = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GEOMetric(Base):
    """Tracks GEO/AEO performance metrics over time."""
    __tablename__ = "geo_metrics"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False, index=True)  # 'ai_referral', 'rich_result', 'citation'
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PerplexityCitation(Base):
    """Logs manual or automated checks of Perplexity citations."""
    __tablename__ = "perplexity_citations"
    
    id = Column(Integer, primary_key=True)
    check_date = Column(DateTime(timezone=True), nullable=False, index=True)
    query = Column(String(500), nullable=False)
    cited = Column(Boolean, nullable=False)
    cited_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============ AI Visibility Tracker Models ============

class PromptPanelItem(Base):
    """
    A prompt in the AI Visibility prompt panel.
    
    Each prompt is a query we send to LLMs to check if Example Store is cited.
    Example: "¿Dónde comprar kit de reparación 4L60E en México?"
    """
    __tablename__ = "prompt_panel_items"
    
    id = Column(Integer, primary_key=True)
    prompt_text = Column(Text, nullable=False)  # The actual prompt
    category = Column(String(50), index=True)  # fault_code, product, competitor, general
    priority = Column(Integer, default=50)  # Higher = more important (0-100)
    
    # Optional: link to fault code or product
    linked_fault_code = Column(String(20), ForeignKey("fault_codes.code"))
    linked_transmission = Column(String(30))  # e.g., "4L60E"
    
    # Tracking
    is_active = Column(Boolean, default=True, index=True)
    last_checked = Column(DateTime(timezone=True))
    check_count = Column(Integer, default=0)
    
    # Source (e.g., from GSC top queries, manual, etc.)
    source = Column(String(50), default="manual")  # manual, gsc_import, competitor
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AIVisibilityResult(Base):
    """
    Result of a single LLM query for visibility checking.
    
    Stores whether Example Store was mentioned/cited in the response.
    """
    __tablename__ = "ai_visibility_results"
    
    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("prompt_panel_items.id"), nullable=False, index=True)
    
    # LLM Info
    llm_provider = Column(String(30), nullable=False)  # grok, openai, gemini, perplexity
    llm_model = Column(String(100))  # grok-4-1-fast-reasoning, gpt-4o-mini, etc.
    
    # Response analysis
    response_text = Column(Text)  # Full LLM response (optional, can be truncated)
    
    # Citation Detection
    brand_mentioned = Column(Boolean, default=False)  # "Example Store" or "example-store" mentioned
    url_cited = Column(Boolean, default=False)  # example-store.com URL found
    product_mentioned = Column(Boolean, default=False)  # Specific product name found
    competitor_mentioned = Column(Boolean, default=False)  # Competitor brand found
    
    # Detected entities (JSON arrays)
    mentioned_brands = Column(JSON)  # ["Example Store", "TSS", "TransGo"]
    mentioned_urls = Column(JSON)  # ["example-store.com/collections/4l60e"]
    mentioned_products = Column(JSON)  # ["Kit de Reparación 4L60E"]
    
    # Sentiment (optional, future feature)
    sentiment = Column(String(20))  # positive, neutral, negative
    
    # Timing
    query_time_ms = Column(Integer)  # How long the LLM took to respond
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Error handling
    error = Column(Text)  # If the query failed
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VisibilitySnapshot(Base):
    """
    Aggregated daily visibility metrics.
    
    Provides a "score" for how visible Example Store is across AI engines on a given day.
    """
    __tablename__ = "visibility_snapshots"
    
    id = Column(Integer, primary_key=True)
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True, unique=True)
    
    # Aggregated metrics
    total_prompts_checked = Column(Integer, default=0)
    brand_mentions = Column(Integer, default=0)  # Times "Example Store" was mentioned
    url_citations = Column(Integer, default=0)  # Times example-store.com was cited
    product_mentions = Column(Integer, default=0)  # Times specific products were mentioned
    competitor_mentions = Column(Integer, default=0)  # Times competitors were mentioned
    
    # Calculated scores (0-100)
    visibility_score = Column(Float, default=0.0)  # Overall visibility (% of prompts with brand mention)
    citation_score = Column(Float, default=0.0)  # URL citation rate
    share_of_voice = Column(Float, default=0.0)  # Example Store mentions / (Example Store + Competitors)

    # Per-competitor breakdown: {"transgo": 12, "sonnax": 3, ...}. Lets the
    # dashboard show *which* competitors are catching up, not just that
    # "some competitor" was mentioned. Excludes Example Store.
    competitor_breakdown = Column(JSON)

    # Breakdown by LLM
    metrics_by_llm = Column(JSON)  # {"grok": {"mentions": 10, "citations": 5}, ...}
    
    # Top performing prompts
    top_prompts = Column(JSON)  # [{"prompt_id": 1, "mentions": 5}, ...]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ============ Product AI Visibility Models ============

class AEOEvent(Base):
    """
    Tracks AEO/GEO improvement actions for timeline visualization.

    Each row is a meaningful change (llms.txt deployed, schema added, content published)
    that can be overlaid on the monthly-trend charts to answer:
    'Are our improvements doing something?'
    """
    __tablename__ = "aeo_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)
    # llms_txt_deployed | schema_added | content_updated | visibility_check
    # keyword_published | other
    event_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProductVisibilityResult(Base):
    """
    Individual visibility check result for a specific product on an LLM.
    
    This extends AIVisibilityResult to track product-level visibility,
    similar to SEMrush's per-domain AI visibility tracking.
    """
    __tablename__ = "product_visibility_results"
    
    id = Column(Integer, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)

    # Prompt used for the check (can be auto-generated from product attributes)
    prompt_text = Column(Text, nullable=False)
    prompt_type = Column(String(50))  # fitment_query, competitor_compare, feature_query, diagnostic

    # LLM Info
    llm_provider = Column(String(30), nullable=False)  # grok, openai, perplexity, gemini
    llm_model = Column(String(100))

    # Response analysis
    response_text = Column(Text)  # Full or truncated response

    # Product-specific visibility signals
    was_mentioned = Column(Boolean, default=False)  # Was this specific product mentioned?
    position_in_response = Column(Integer)  # 1st, 2nd, 3rd recommendation (null = not mentioned)
    mention_context = Column(String(100))  # recommended, compared, mentioned, not_found

    # Brand detection (inherited from brand-level tracking)
    brand_mentioned = Column(Boolean, default=False)
    brand_url_cited = Column(Boolean, default=False)

    # Competitor analysis for this prompt
    competitors_mentioned = Column(JSON)  # ["transgo", "sonnax"] - products mentioned instead
    competitor_urls_cited = Column(JSON)  # URLs of competitors cited

    # Sentiment and quality
    sentiment = Column(String(20))  # positive, neutral, negative
    recommendation_strength = Column(String(20))  # strong, moderate, weak, none

    # Timing
    query_time_ms = Column(Integer)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Error handling
    error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProductVisibilitySnapshot(Base):
    """
    Aggregated daily visibility scores per product.

    Like SEMrush's "48/100 Medium" visibility score, but for each product.
    Enables tracking trends and improvement over time.
    """
    __tablename__ = "product_visibility_snapshots"

    id = Column(Integer, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Overall visibility score (0-100, like SEMrush)
    visibility_score = Column(Float, default=0.0)  # Aggregated score
    visibility_level = Column(String(10))  # low (0-33), medium (34-66), high (67-100)
    
    # Breakdowns
    scores_by_llm = Column(JSON)  # {"grok": 85, "perplexity": 62, "chatgpt": 45}
    
    # Raw counts
    total_checks = Column(Integer, default=0)
    mention_count = Column(Integer, default=0)
    first_position_count = Column(Integer, default=0)  # Times mentioned 1st
    url_citation_count = Column(Integer, default=0)
    
    # Competitor analysis
    competitor_share = Column(Float, default=0.0)  # % of prompts where competitors were mentioned
    top_competitors = Column(JSON)  # [{"name": "transgo", "mentions": 5}]
    
    # Change tracking
    score_change_7d = Column(Float)  # Change vs 7 days ago
    score_change_30d = Column(Float)  # Change vs 30 days ago
    
    # Metadata
    prompts_used = Column(JSON)  # IDs of prompts used in this snapshot
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Unique constraint: one snapshot per product per day
    __table_args__ = (
        # SQLAlchemy composite unique constraint
        {'sqlite_autoincrement': True},
    )


class CacheEntry(Base):
    """
    SQLite-based persistent cache for expensive API calls.
    
    Stores JSON-serialized results with TTL support.
    Used by ShopifyService and LLMAnalyticsEnhancer to persist data across restarts.
    """
    __tablename__ = "cache_entries"
    
    cache_key = Column(String(255), primary_key=True)  # e.g., "llm_sales:365:true"
    cache_value = Column(Text, nullable=False)  # JSON serialized data
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional TTL
    
    @classmethod
    def get(cls, db, key: str, default=None, allow_stale: bool = False):
        """Get cached value if not expired.
        
        Args:
            db: Database session
            key: Cache key to look up
            default: Value to return if key not found (or expired and allow_stale=False)
            allow_stale: If True, return expired data with '_stale: True' flag
                         instead of deleting it. Useful for fallback when APIs fail.
        """
        import json
        from datetime import datetime, timezone
        
        entry = db.query(cls).filter(cls.cache_key == key).first()
        if not entry:
            return default
        
        # Check if expired
        is_expired = False
        if entry.expires_at:
            now = datetime.now(timezone.utc)
            exp = entry.expires_at if entry.expires_at.tzinfo else entry.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                is_expired = True
        
        if is_expired and not allow_stale:
            # Original behavior — delete expired entry
            db.delete(entry)
            db.commit()
            return default
        
        try:
            data = json.loads(entry.cache_value)
            if is_expired and allow_stale:
                # Mark as stale so caller knows it's outdated
                if isinstance(data, dict):
                    data['_stale'] = True
                    data['_cached_at'] = str(entry.cached_at)
            return data
        except json.JSONDecodeError:
            return default
    
    @classmethod
    def set(cls, db, key: str, value, ttl_hours: int = 4):
        """Set cache value with optional TTL (default 4 hours)."""
        import json
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours) if ttl_hours else None
        
        # Upsert
        entry = db.query(cls).filter(cls.cache_key == key).first()
        if entry:
            entry.cache_value = json.dumps(value, default=str)
            entry.cached_at = now
            entry.expires_at = expires_at
        else:
            entry = cls(
                cache_key=key,
                cache_value=json.dumps(value, default=str),
                cached_at=now,
                expires_at=expires_at
            )
            db.add(entry)
        
        db.commit()
        return entry
    
    @classmethod
    def clear(cls, db, pattern: Optional[str] = None):
        """Clear cache entries matching pattern (or all if no pattern)."""
        if pattern:
            db.query(cls).filter(cls.cache_key.like(f"{pattern}%")).delete(synchronize_session=False)
        else:
            db.query(cls).delete(synchronize_session=False)
        db.commit()

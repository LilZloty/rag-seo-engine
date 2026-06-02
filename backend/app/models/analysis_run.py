"""
Analysis Run Model

Stores the full context of each AI content analysis run — all input data,
prompts, and results — so nothing is lost and runs can be compared/reused.
"""

from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Integer, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base


class AnalysisRun(Base):
    """
    Full audit trail for each AI content analysis.
    
    Stores all input data snapshots, the enriched prompt sent to Grok,
    both pass results, and metadata (cost, timing, model versions).
    
    Used to:
    - Avoid re-running analysis when source data hasn't changed
    - Compare analysis versions over time
    - Debug what data Grok received
    - Track API costs per product
    """
    __tablename__ = "analysis_runs"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False, index=True)

    # ---- Input data snapshots (frozen at analysis time) ----
    gsc_queries_snapshot = Column(JSON)           # GSC queries list
    serp_data_snapshot = Column(JSON)             # DataForSEO SERP results
    competitor_pages_snapshot = Column(JSON)       # Competitor page analysis
    keyword_volumes_snapshot = Column(JSON)        # Search volumes dict
    historical_trends_snapshot = Column(JSON)      # Trend data
    competitor_analysis_snapshot = Column(JSON)     # AI-mentioned competitors
    benchmarks_snapshot = Column(JSON)             # Category benchmarks

    # ---- Prompt ----
    enriched_prompt = Column(Text)                # Full prompt sent to Grok
    system_prompt = Column(Text)                  # System prompt (Pass 2)

    # ---- Pass 1: Fact verification ----
    pass1_analysis = Column(JSON)                 # Verified facts, issues, gaps
    pass1_model = Column(String(60))              # e.g. "grok-3-mini-fast"
    pass1_duration_ms = Column(Integer)

    # ---- Pass 2: Full recommendations ----
    pass2_analysis = Column(JSON)                 # Final analysis JSON
    pass2_model = Column(String(60))              # e.g. "grok-3"
    pass2_duration_ms = Column(Integer)

    # ---- Scores (denormalized for quick queries) ----
    seo_score = Column(Integer, default=0)
    aeo_score = Column(Integer, default=0)
    geo_score = Column(Integer, default=0)

    # ---- Metadata ----
    total_duration_seconds = Column(Float)
    data_hash = Column(String(64), index=True)    # SHA-256 of key inputs → skip if same
    is_latest = Column(Boolean, default=True, index=True)  # Only latest run per product
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    product = relationship("Product", backref="analysis_runs")

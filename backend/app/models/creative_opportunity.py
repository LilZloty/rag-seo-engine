"""
Creative Opportunity models.

Extends the Creative Intelligence layer with persistent, actionable
opportunity rows: transmissions in demand we don't sell, products we
sell but get no traffic, products that get impressions but don't
convert clicks. Status-tracked so resolved/dismissed items don't keep
re-surfacing each detection run.
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, Text, ForeignKey, Index
)
from sqlalchemy.sql import func
from app.db.session import Base


class CreativeOpportunity(Base):
    """A detected gap or under-leveraged asset surfaced from creative intelligence signals.

    One row per (opportunity_type, target) pair. Re-detection of the same
    signal updates `last_seen_at` and metrics instead of creating duplicates
    (see `signal_hash`). Resolved/dismissed rows are kept for audit + to
    prevent re-surfacing during their cooldown.
    """
    __tablename__ = "creative_opportunities"
    __table_args__ = (
        Index("ix_creative_opp_type_status", "opportunity_type", "status"),
        Index("ix_creative_opp_score_status", "opportunity_score", "status"),
    )

    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Classification
    # opportunity_type:
    #   transmission_demand_gap → search demand for a transmission code we don't sell
    #   query_demand_gap        → high-impression GSC query with no semantic match in catalog
    #   latent_inventory        → product matches demand signal but gets ~0 sessions
    #   marketing_gap           → product has impressions but CTR <2% (under-clicked listing)
    opportunity_type = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), nullable=False, default="medium", index=True)  # high|medium|low

    # Target — what the opportunity is about. Exactly one of these is populated
    # depending on opportunity_type.
    target_type = Column(String(20), nullable=False)  # transmission|product|query
    target_transmission_code = Column(String(30), nullable=True, index=True)
    target_vehicle_brand = Column(String(50), nullable=True, index=True)
    target_product_id = Column(String, ForeignKey("products.id"), nullable=True, index=True)
    target_query = Column(String(255), nullable=True)

    # Signal payload — the evidence backing the opportunity. Schema varies by type:
    #   transmission_demand_gap: {matched_queries: [...], total_impressions, total_clicks}
    #   query_demand_gap:        {impressions, clicks, ctr, position, top_match_similarity}
    #   latent_inventory:        {expected_sessions, actual_sessions, matched_queries: [...]}
    #   marketing_gap:           {impressions, clicks, ctr, position}
    signal_data = Column(JSON, default=dict)

    # Scoring + impact estimate (used to rank the opportunities list)
    opportunity_score = Column(Float, default=0.0, index=True)
    estimated_monthly_sessions = Column(Integer, nullable=True)
    estimated_monthly_revenue = Column(Float, nullable=True)

    # Human-readable summary + suggested action
    title = Column(String(255), nullable=False)
    description = Column(Text)
    recommended_action = Column(Text)
    action_steps = Column(JSON, default=list)

    # Status workflow
    # open → investigating → in_progress → resolved
    #                                   ↘ dismissed (won't fix / not a real gap)
    status = Column(String(20), nullable=False, default="open", index=True)
    notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # Deduplication: SHA256(opportunity_type + canonical target id).
    # Detection runs upsert on this; one row per real-world gap.
    signal_hash = Column(String(64), unique=True, nullable=False, index=True)

"""
Supervisor Agent Models

Three tables:
- news_items: deduped + summarized SEO/AEO/GEO news
- supervisor_proposals: actions proposed by the agent (Phase 4+)
- supervisor_runs: log of every daily/weekly/evaluator run with token cost
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.session import Base


class NewsItem(Base):
    """
    A single SEO/AEO/GEO news item ingested from RSS.

    Dedup is by (source, guid) when guid is present, else (source, url).
    Summary + tag are filled by the LLM summarizer; raw fields are kept
    so we can re-summarize if the prompt changes.
    """
    __tablename__ = "supervisor_news_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(80), nullable=False, index=True)  # e.g., "search-engine-land"
    source_kind = Column(String(20), default="rss")          # rss | atom | manual

    # Identity
    guid = Column(String(500), nullable=True)                # feed-provided GUID if any
    url = Column(String(1000), nullable=False)
    title = Column(String(500), nullable=False)

    # Raw content
    raw_summary = Column(Text, nullable=True)                # feed-provided summary/description
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # LLM-derived
    summary_bullets = Column(JSON, default=list)             # list[str], 3-5 bullets
    tag = Column(String(20), nullable=True, index=True)      # algo|aeo|geo|tooling|policy|market|other
    relevance = Column(String(10), nullable=True)            # high|medium|low|skip
    summarized_at = Column(DateTime(timezone=True), nullable=True)
    summary_model = Column(String(60), nullable=True)        # which model wrote the summary

    # Bookkeeping
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        # Dedup: never store the same (source, url) twice
        UniqueConstraint("source", "url", name="uq_news_source_url"),
        # Common query: "latest items, optionally filtered by tag"
        Index("ix_news_published_tag", "published_at", "tag"),
    )


class SupervisorProposal(Base):
    """
    An action proposed by the supervisor for Theo's review.

    Reserved for Phase 4. Migration creates the table now so we don't
    block ourselves later, but no writer exists yet.
    """
    __tablename__ = "supervisor_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    kind = Column(String(40), nullable=False, index=True)
    target = Column(String(500), nullable=True)              # url|product_id|collection_id|fault_code
    rationale = Column(Text, nullable=False)
    expected_impact = Column(Text, nullable=True)
    confidence = Column(String(10), nullable=False, default="low")  # low|medium|high
    tool_citations = Column(JSON, default=list)
    proposed_action = Column(Text, nullable=True)

    # Status lifecycle: pending -> approved|rejected -> shipped -> evaluated
    status = Column(String(20), nullable=False, default="pending", index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True, index=True)
    human_notes = Column(Text, nullable=True)

    # Outcome attribution (Phase 5)
    outcome_metric_t14 = Column(JSON, default=dict)          # {gsc_impressions_pct, position_delta, ...}
    outcome_verdict = Column(String(20), nullable=True)       # positive|neutral|negative|ambiguous
    evaluated_at = Column(DateTime(timezone=True), nullable=True)

    # Provenance
    run_id = Column(Integer, nullable=True, index=True)      # FK-shaped, no constraint to keep migration simple


class SupervisorRun(Base):
    """
    One row per supervisor invocation. Tracks cost, mode, output summary,
    and whether the run succeeded. Cheap insurance against silent failures.
    """
    __tablename__ = "supervisor_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    mode = Column(String(20), nullable=False, index=True)    # daily_pulse|weekly_brief|investigate|news_ingest|evaluator
    status = Column(String(20), nullable=False, default="running")  # running|ok|error

    # Cost + model
    model = Column(String(60), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)

    # Output
    summary = Column(Text, nullable=True)                    # human-readable digest
    artifacts = Column(JSON, default=dict)                   # e.g., {proposals_written: 4, news_added: 17}
    error = Column(Text, nullable=True)

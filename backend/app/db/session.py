from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.POSTGRES_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.LOG_LEVEL == "DEBUG"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI endpoints to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    from app.models import (
        Product, ContentDraft, SupplierPart, ScrapingJob, AIAnalysisCache,
        Library, Document, DocumentChunk, PromptTemplate, GenerationHistory,
        StoreSnapshot, IntelligenceReport, AIRecommendation, MetricTrend,
        KeywordDailyMetric, PageDailyMetric, KeywordPageMapping,
        GA4FunnelDaily, ContentGapResult, SEOAlert
    )
    from app.models.inventory_models import InventorySnapshot, InventoryAlert, RestockEvent
    from app.models.collection_optimizer_models import (
        CollectionOptimizer, CollectionSearchQuery, CollectionOptimizationHistory, CollectionContentTemplate
    )
    from app.models.collection_intelligence_models import (
        CollectionAnalyticsSnapshot, CollectionContentDraft, CollectionCannibalizationResult
    )
    from app.models.supervisor_models import (
        NewsItem, SupervisorProposal, SupervisorRun
    )
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE store_snapshots ADD COLUMN IF NOT EXISTS b2b_data JSON DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS inventory_velocity FLOAT DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS days_of_supply FLOAT DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS demand_score INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_health VARCHAR(20) DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER DEFAULT 5",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS last_stockout_date TIMESTAMP WITH TIME ZONE DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS stockout_frequency_90d INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS active_subscribers INTEGER DEFAULT 0",
            "ALTER TABLE keyword_page_mappings ADD COLUMN IF NOT EXISTS page_type VARCHAR(20) DEFAULT NULL",
            "ALTER TABLE visibility_snapshots ADD COLUMN IF NOT EXISTS competitor_breakdown JSON DEFAULT NULL",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS transmission_codes JSON DEFAULT NULL",
        ]
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

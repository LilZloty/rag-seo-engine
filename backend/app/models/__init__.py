# Models package
# Export all models for easy importing

from app.models.product import Product, ContentDraft, SupplierPart, ScrapingJob, AIAnalysisCache
from app.models.analysis_run import AnalysisRun
from app.models.library import (
    Library,
    Document,
    DocumentChunk,
    PromptTemplate,
    GenerationHistory,
    document_library_association
)
from app.models.aeo_models import (
    ChunkApprovalStatus, AEOConfig, TransmissionPattern, BlogCache,
    FaultCode, Solution, DiagnosticContent,
    # AI Visibility models
    PromptPanelItem, AIVisibilityResult, VisibilitySnapshot,
    # Product AI Visibility models
    ProductVisibilityResult, ProductVisibilitySnapshot,
    # GEO & Cache models
    GEOMetric, PerplexityCitation, CacheEntry
)
from app.models.store_intelligence import (
    StoreSnapshot, IntelligenceReport, AIRecommendation, MetricTrend
)
from app.models.seo_intelligence import (
    KeywordDailyMetric, PageDailyMetric, KeywordPageMapping,
    GA4FunnelDaily, ContentGapResult, SEOAlert
)
from app.models.solution_graph import (
    BlogSolution, SolutionPath, ProductRecommendationEngine,
    QueryProductAffinity, SmartSnippet
)
from app.models.inventory_models import (
    InventorySnapshot, InventoryAlert, RestockEvent, OrderLineItem
)
from app.models.collection_optimizer_models import (
    CollectionOptimizer, CollectionSearchQuery, CollectionOptimizationHistory, CollectionContentTemplate
)
from app.models.collection_intelligence_models import (
    CollectionAnalyticsSnapshot, CollectionContentDraft, CollectionCannibalizationResult
)
from app.models.supervisor_models import (
    NewsItem, SupervisorProposal, SupervisorRun
)
from app.models.creative_opportunity import CreativeOpportunity

# Register SQLAlchemy event listeners (manual edit tracking, etc.)
from app.models import listeners  # noqa: F401

__all__ = [
    # Original models
    "Product",
    "ContentDraft",
    "SupplierPart",
    "ScrapingJob",
    "AIAnalysisCache",
    "AnalysisRun",
    # Knowledge Library models
    "Library",
    "Document",
    "DocumentChunk",
    "PromptTemplate",
    "GenerationHistory",
    "document_library_association",
    # AEO models
    "ChunkApprovalStatus",
    "AEOConfig",
    "TransmissionPattern",
    "BlogCache",
    # GEO Knowledge Graph models
    "FaultCode",
    "Solution",
    "DiagnosticContent",
    # AI Visibility models (brand-level)
    "PromptPanelItem",
    "AIVisibilityResult",
    "VisibilitySnapshot",
    # Product AI Visibility models
    "ProductVisibilityResult",
    "ProductVisibilitySnapshot",
    # GEO & Cache models
    "GEOMetric",
    "PerplexityCitation",
    "CacheEntry",
    # Store Intelligence models
    "StoreSnapshot",
    "IntelligenceReport",
    "AIRecommendation",
    "MetricTrend",
    # SEO Intelligence models (Advanced Intelligence System)
    "KeywordDailyMetric",
    "PageDailyMetric",
    "KeywordPageMapping",
    "GA4FunnelDaily",
    "ContentGapResult",
    "SEOAlert",
    # Solution Engine models
    "BlogSolution",
    "SolutionPath",
    "ProductRecommendationEngine",
    "QueryProductAffinity",
    "SmartSnippet",
    # Analysis Run audit trail
    "AnalysisRun",
    # Inventory Intelligence models
    "InventorySnapshot",
    "InventoryAlert",
    "RestockEvent",
    "OrderLineItem",
    # Collection Optimizer models
    "CollectionOptimizer",
    "CollectionSearchQuery",
    "CollectionOptimizationHistory",
    "CollectionContentTemplate",
    # Collection Intelligence models
    "CollectionAnalyticsSnapshot",
    "CollectionContentDraft",
    "CollectionCannibalizationResult",
    # Supervisor agent models
    "NewsItem",
    "SupervisorProposal",
    "SupervisorRun",
    # Creative intelligence opportunities
    "CreativeOpportunity",
]

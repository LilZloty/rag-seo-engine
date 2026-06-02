"""
AEO (Answer Engine Optimization) Pydantic Schemas

Request/Response models for AEO API endpoints.
Phase 2: Added GEO schemas for FaultCode, Solution, FAQPage, HowTo
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Chunk Schemas ============

class ProductChunkBase(BaseModel):
    """Base schema for a product chunk (computed from product_type)"""
    product_type: str
    product_count: int
    approved: bool = False
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None


class ProductChunkResponse(ProductChunkBase):
    """Response schema with sample products"""
    sample_products: List[dict] = Field(default_factory=list)
    category: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class ChunkApprovalRequest(BaseModel):
    """Request to approve/reject a chunk"""
    approved: bool
    notes: Optional[str] = None
    approved_by: Optional[str] = "admin"


# ============ llms.txt Schemas ============

class LLMSTxtPreviewResponse(BaseModel):
    """Response for llms.txt preview"""
    content: str
    token_estimate: int
    byte_size: int
    approved_chunks: int
    total_chunks: int
    last_generated: Optional[datetime] = None


class LLMSTxtGenerateRequest(BaseModel):
    """Request to regenerate llms.txt"""
    force_rebuild: bool = False
    include_blogs: bool = True
    include_collections: bool = True
    include_fault_codes: bool = True


# ============ Schema.org Schemas ============

class VehiclePartSchemaResponse(BaseModel):
    """JSON-LD VehiclePart schema for a product"""
    product_id: str
    json_ld: dict
    validation_status: str = "valid"


class BulkSchemaRequest(BaseModel):
    """Request for bulk schema generation"""
    product_ids: Optional[List[str]] = None
    chunk_id: Optional[str] = None


# ============ Blog Schemas ============

class BlogArticleResponse(BaseModel):
    """Blog article for AEO inclusion"""
    id: str
    title: str
    handle: str
    url: Optional[str] = None
    blog_handle: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    include_in_llms_txt: bool = True


# ============ Config Schemas ============

class AEOConfigResponse(BaseModel):
    """AEO configuration settings"""
    llms_txt_version: str
    include_blogs: bool
    include_collections: bool
    include_fault_codes: Optional[bool] = True
    max_products_per_category: int
    store_name: str
    store_description: str
    authority_statement: Optional[str] = None
    
    class Config:
        from_attributes = True


class AEOConfigUpdateRequest(BaseModel):
    """Request to update AEO config"""
    include_blogs: Optional[bool] = None
    include_collections: Optional[bool] = None
    include_fault_codes: Optional[bool] = None
    max_products_per_category: Optional[int] = None
    store_name: Optional[str] = None
    store_description: Optional[str] = None
    authority_statement: Optional[str] = None


# ============ GEO Fault Code Schemas ============

class SolutionBase(BaseModel):
    """Solution for a fault code"""
    solution_type: str  # part_replacement, adjustment, software, service
    description: str
    success_rate: Optional[float] = None  # 0.0 to 1.0
    difficulty_level: Optional[str] = None  # easy, medium, hard, professional
    estimated_cost: Optional[str] = None
    product_ids: List[str] = Field(default_factory=list)
    is_recommended: bool = False


class SolutionResponse(SolutionBase):
    id: str
    fault_code_id: str
    priority: int = 100
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FaultCodeBase(BaseModel):
    """Fault code for Knowledge Graph"""
    code: str  # P0700, P0841, etc.
    name: str  # "General Transmission Fault"
    description: Optional[str] = None
    severity: str = "medium"


class FaultCodeCreate(FaultCodeBase):
    """Request to create a fault code"""
    transmissions: List[str] = Field(default_factory=list)
    vehicles: List[str] = Field(default_factory=list)
    common_causes: List[str] = Field(default_factory=list)
    symptoms_text: List[str] = Field(default_factory=list)
    blog_url: Optional[str] = None
    collection_url: Optional[str] = None
    monthly_clicks: int = 0
    monthly_impressions: int = 0
    is_priority: bool = False


class FaultCodeResponse(FaultCodeBase):
    """Full fault code response with solutions"""
    transmissions: List[str] = Field(default_factory=list)
    vehicles: List[str] = Field(default_factory=list)
    common_causes: List[str] = Field(default_factory=list)
    symptoms_text: List[str] = Field(default_factory=list)
    blog_url: Optional[str] = None
    collection_url: Optional[str] = None
    monthly_clicks: int = 0
    monthly_impressions: int = 0
    current_ctr: float = 0.0
    is_priority: bool = False
    include_in_llms_txt: bool = True
    has_faq_schema: bool = False
    solutions: List[SolutionResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Schema.org GEO Schemas ============

class FAQItem(BaseModel):
    """Single FAQ question/answer pair"""
    question: str
    answer: str


class FAQPageSchemaResponse(BaseModel):
    """FAQPage JSON-LD schema"""
    fault_code: str
    json_ld: Dict[str, Any]
    validation_status: str = "valid"


class HowToStep(BaseModel):
    """Single step in a HowTo guide"""
    step_number: int
    name: str
    text: str
    image_url: Optional[str] = None


class HowToSchemaResponse(BaseModel):
    """HowTo JSON-LD schema"""
    content_id: str
    json_ld: Dict[str, Any]
    validation_status: str = "valid"


# ============ Diagnostic Content Schemas ============

class DiagnosticContentResponse(BaseModel):
    """Content statistics for authority signals"""
    id: str
    page_type: str
    page_url: str
    title: str
    active_users: int = 0
    avg_engagement_seconds: int = 0
    key_events: int = 0
    readers_helped_text: Optional[str] = None
    last_synced: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ AI Visibility Tracker Schemas ============

class PromptPanelItemCreate(BaseModel):
    """Request to create a new prompt"""
    prompt_text: str
    category: str = "general"  # fault_code, product, competitor, general
    priority: int = Field(default=50, ge=0, le=100)
    linked_fault_code: Optional[str] = None
    linked_transmission: Optional[str] = None
    source: str = "manual"  # manual, gsc_import, competitor


class PromptPanelItemResponse(BaseModel):
    """Prompt panel item response"""
    id: int
    prompt_text: str
    category: str
    priority: int
    linked_fault_code: Optional[str] = None
    linked_transmission: Optional[str] = None
    source: str
    is_active: bool
    last_checked: Optional[datetime] = None
    check_count: int = 0
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AIVisibilityResultResponse(BaseModel):
    """Single visibility check result"""
    id: int
    prompt_id: int
    llm_provider: str
    llm_model: Optional[str] = None
    brand_mentioned: bool = False
    url_cited: bool = False
    product_mentioned: bool = False
    competitor_mentioned: bool = False
    mentioned_brands: List[str] = Field(default_factory=list)
    mentioned_urls: List[str] = Field(default_factory=list)
    mentioned_products: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None  # positive, neutral, negative
    query_time_ms: Optional[int] = None
    checked_at: Optional[datetime] = None
    error: Optional[str] = None
    
    class Config:
        from_attributes = True


class VisibilitySnapshotResponse(BaseModel):
    """Daily visibility snapshot"""
    id: int
    snapshot_date: datetime
    total_prompts_checked: int = 0
    brand_mentions: int = 0
    url_citations: int = 0
    product_mentions: int = 0
    competitor_mentions: int = 0
    visibility_score: float = 0.0  # 0-100
    citation_score: float = 0.0  # 0-100
    share_of_voice: float = 0.0  # 0-100
    metrics_by_llm: Optional[Dict[str, Any]] = None
    top_prompts: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True


class VisibilityCheckRequest(BaseModel):
    """Request to run visibility checks"""
    prompt_ids: Optional[List[int]] = None  # None = all active prompts
    providers: List[str] = Field(default=["grok"])  # LLM providers to use
    limit: int = Field(default=20, le=50)  # Max prompts per run
    max_concurrent: int = Field(default=3, ge=1, le=10)  # Max concurrent LLM calls
    timeout_per_check: int = Field(default=60, ge=10, le=300)  # Timeout per check in seconds


class VisibilityDashboardResponse(BaseModel):
    """Dashboard aggregated metrics"""
    current: Dict[str, Any]  # visibility_score, citation_score, share_of_voice
    trends: Dict[str, float]  # week_avg_visibility, week_avg_share
    totals: Dict[str, int]  # active_prompts, total_checks
    by_llm: Dict[str, Any]  # Metrics broken down by LLM provider
    top_prompts: List[Dict[str, Any]]  # Top performing prompts


# ============ LLM Sales Attribution Schemas ============

class LLMSalesBySource(BaseModel):
    """Sales metrics for a single LLM source"""
    source: str  # chatgpt, gemini, perplexity, claude
    sales: float
    orders: int
    aov: float  # Average order value
    percent_of_total: float
    new_customers: int
    returning_customers: int


class LLMSalesSummary(BaseModel):
    """Aggregated sales summary across all LLM sources"""
    total_sales: float
    total_orders: int
    average_order_value: float
    new_customers: int
    returning_customers: int
    gross_sales: float
    net_sales: float


class LLMSalesComparison(BaseModel):
    """Period-over-period comparison metrics"""
    sales_change_pct: float
    orders_change_pct: float
    aov_change_pct: float


class LLMSalesPeriod(BaseModel):
    """Date range for the sales query"""
    start: str  # ISO date
    end: str  # ISO date


class LLMSalesResponse(BaseModel):
    """
    Full LLM sales attribution response.
    
    Returns aggregated sales data for orders attributed to LLM sources
    (ChatGPT, Gemini, Perplexity, Claude) via UTM tracking.
    """
    status: str  # 'success' or 'no_data'
    message: Optional[str] = None
    summary: LLMSalesSummary
    by_source: List[LLMSalesBySource]
    comparison: Optional[LLMSalesComparison] = None
    period: Optional[LLMSalesPeriod] = None


# ============ LLM Product Intelligence Schemas ============

class ProductContentAttributes(BaseModel):
    """Content attributes that contribute to LLM discoverability"""
    description_length: int
    has_aeo_chunks: bool
    chunk_count: int
    in_llms_txt: bool
    has_images: bool
    image_count: int


class LLMReferencedProduct(BaseModel):
    """Product that has been referenced by LLMs"""
    id: str  # Changed from int to str to match database
    shopify_id: str
    title: str
    sku: str
    handle: str
    product_type: str
    orders_from_llm: int
    revenue_from_llm: float
    sources: List[str]  # chatgpt, gemini, etc.
    content_attributes: ProductContentAttributes


class OptimizationOpportunity(BaseModel):
    """High-selling product not getting LLM traffic"""
    id: str  # Changed from int to str to match database
    shopify_id: str
    title: str
    sku: str
    handle: str
    product_type: str
    total_sold: int
    total_revenue: float
    current_attributes: ProductContentAttributes
    issues: List[str]  # "Not in llms.txt", "Short description", etc.
    recommendation: str


class SuccessPatterns(BaseModel):
    """Patterns found in products that get LLM references"""
    avg_description_length: int
    products_with_aeo_chunks_pct: float
    total_products_referenced: int
    most_common_sources: List[Dict[str, Any]]


class ProductIntelligenceResponse(BaseModel):
    """Full product intelligence response"""
    status: str
    message: Optional[str] = None
    products_from_llm: List[LLMReferencedProduct] = Field(default_factory=list)
    optimization_opportunities: List[OptimizationOpportunity] = Field(default_factory=list)
    success_patterns: Optional[SuccessPatterns] = None
    sync_needed: Optional[bool] = False
    missing_product_count: Optional[int] = 0



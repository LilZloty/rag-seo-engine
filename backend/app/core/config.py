from pydantic_settings import BaseSettings
from typing import Optional, List, Literal
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG SEO Engine"
    VERSION: str = "1.0.0"

    # Environment: development | staging | production
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    API_V1_STR: str = "/api/v1"
    
    # PostgreSQL via Cloudflare tunnel (appsdb.internal.example → localhost:5432)
    # Start tunnel first: .\start-tunnel.ps1
    POSTGRES_URL: str = "postgresql://USER:PASS@localhost:5432/rag_seo"
    
    # Vector Database (Qdrant)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "documents"
    
    # Redis (optional for MVP)
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_REDIS: bool = False  # Disabled for MVP
    
    # LLM Configuration
    LLM_PROVIDER: str = "ollama"  # Options: "ollama", "openai", "anthropic", "grok", "minimax"
    
    # Ollama (local, free)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:latest"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-5"
    
    # Anthropic (Claude)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
    
    # X.AI (Grok)
    XAI_API_KEY: Optional[str] = None
    XAI_MODEL: str = "grok-4.3"

    # X.AI (Grok 4.20) — legacy multi-agent model
    XAI_GROK420_MODEL: str = "grok-4.3"
    MULTI_AGENT_ENABLED: bool = False

    # Supervisor agent — triage tasks like news summarization don't need
    # reasoning depth. Override XAI_MODEL with a faster model just for the
    # supervisor. Set to empty/None to fall back to XAI_MODEL.
    SUPERVISOR_SUMMARIZE_MODEL: str = "grok-4.3"
    
    # MiniMax
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_MODEL: str = "MiniMax-M2.1"
    
    # Mistral
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-large-latest"
    
    # Kimi (Moonshot AI)
    KIMI_API_KEY: Optional[str] = None
    KIMI_MODEL: str = "kimi-k2.5"
    

    # Web Search (Serper) - Fallback when RAG has sparse results
    SERPER_API_KEY: Optional[str] = None
    WEB_SEARCH_FALLBACK: bool = True  # Enable web search when RAG has < 3 chunks
    WEB_SEARCH_MIN_RAG_CHUNKS: int = 3  # Trigger web search if RAG returns fewer chunks

    # DataForSEO - Real SERP data for content analysis
    DATAFORSEO_LOGIN: str = ""
    DATAFORSEO_PASSWORD: str = ""
    USE_DATAFORSEO: bool = False  # Master toggle — enables SERP search + keyword volumes (cheap API calls)
    # Sub-toggle for the expensive part: Playwright-driven scraping of competitor
    # product pages found in SERP results. This is what costs real money/time
    # (multi-page fetches per analysis). Default off — enable only when you need
    # competitor content gap analysis. Requires USE_DATAFORSEO=true.
    DATAFORSEO_SCRAPE_COMPETITORS: bool = False
    # Skip DataForSEO for products below this GSC impression floor. The 500-floor
    # used to make sense for pre-Grok analysis; with the keyword-data gate now in
    # place (returns [] when no signal exists), low-impression products still
    # benefit from Related Searches data. 50 strikes a balance — products with
    # zero traction stay free, anything with even modest visibility gets analyzed.
    DATAFORSEO_MIN_IMPRESSIONS: int = 50
    # When True, use the async task-based endpoint ($0.06/1000) instead of the
    # live endpoint ($0.60/1000). Results take 30-60s; trade latency for cost.
    # Only enable for batch/scheduled analysis, not user-blocking paths.
    DATAFORSEO_USE_STANDARD: bool = False

    # SERP provider switch. "dataforseo" uses the DataForSEO API (requires $50
    # deposit). "serpapi" uses the SerpAPI free tier (100 SERPs/month, no card).
    # Both providers return the same response shape — downstream consumers
    # (content_generator, article_enrichment, etc.) don't change.
    SERP_PROVIDER: Literal["dataforseo", "serpapi"] = "dataforseo"
    SERPAPI_KEY: str = ""

    # Legacy settings (for backwards compatibility)
    USE_LOCAL_LLM: bool = False
    DEFAULT_LLM: str = "claude-3-5-sonnet-20241022"
    
    # Embedding Model
    EMBEDDING_PROVIDER: str = "openai"  # Options: "openai", "ollama"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Shopify Integration
    SHOPIFY_STORE: str = "your-store.myshopify.com"
    SHOPIFY_ACCESS_TOKEN: str = ""
    SHOPIFY_API_VERSION: str = "2025-01"
    
    # Inventory Intelligence
    INVENTORY_DEFAULT_LOW_STOCK: int = 5       # Default low-stock threshold
    INVENTORY_DEAD_STOCK_DAYS: int = 90        # Days with no sales = dead stock
    INVENTORY_SYNC_INTERVAL_HOURS: int = 6     # Auto-sync interval
    SHOPIFY_WEBHOOK_SECRET: str = ""           # For HMAC validation

    # Celery (disabled for MVP)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    
    LOG_LEVEL: str = "INFO"
    
    MAX_CONTENT_LENGTH: int = 5242880
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://frontend:3000"]
    
    # RAG Configuration
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5  # Number of chunks to retrieve
    MAX_PROMPT_TOKENS: int = 4000  # Token limit for merged prompt templates
    
    # Google Analytics & Search Console
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_GA4_PROPERTY_ID: Optional[str] = None
    GOOGLE_SEARCH_CONSOLE_SITE_URL: Optional[str] = "https://www.your-domain.com"

    # Sucursales — Internal Store Sales Endpoints (m107/m207/m407/m507.internal.example)
    # These are variable DECLARATIONS only. Pydantic-settings reads the real
    # values from backend/.env at startup. Do NOT hardcode credentials here —
    # config.py is tracked by git; .env is gitignored.
    SUCURSAL_BASIC_USER: str = ""
    SUCURSAL_BASIC_TOKEN: str = ""
    SUCURSAL_FETCH_TIMEOUT: int = 15  # seconds per node
    SUCURSAL_DETAILS_BATCH_SIZE: int = 50  # /Apps/Products/Details limit per request
    SUCURSAL_COUNTRY_CODE: str = "MEX"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def effective_log_level(self) -> str:
        """WARNING in production, DEBUG in dev, INFO otherwise."""
        if self.LOG_LEVEL != "INFO":
            return self.LOG_LEVEL  # explicit override wins
        return {"development": "DEBUG", "staging": "INFO", "production": "WARNING"}[self.ENVIRONMENT]

    @property
    def effective_cache_ttl(self) -> int:
        """Redis cache TTL in seconds — shorter in dev for faster iteration."""
        return {"development": 60, "staging": 300, "production": 600}[self.ENVIRONMENT]

    @property
    def effective_workers(self) -> int:
        """Uvicorn worker count."""
        return {"development": 1, "staging": 2, "production": 4}[self.ENVIRONMENT]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


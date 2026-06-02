# Pydantic schemas for Library, Document, and PromptTemplate
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class LibraryType(str, Enum):
    BRAND = "brand"
    PRODUCT_TYPE = "product_type"
    TRANSMISSION = "transmission"


class SourceType(str, Enum):
    SCRAPED = "scraped"
    UPLOADED_PDF = "uploaded_pdf"
    MANUAL = "manual"


class GenerationStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"


# Library Schemas
class LibraryBase(BaseModel):
    name: str = Field(..., max_length=100)
    name_es: Optional[str] = Field(None, max_length=100)
    library_type: LibraryType
    filter_value: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    scrape_url: Optional[str] = None


class LibraryCreate(LibraryBase):
    id: str = Field(..., pattern=r'^lib_[a-z0-9_]+$')


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    name_es: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    scrape_url: Optional[str] = None


class LibraryResponse(LibraryBase):
    id: str
    document_count: Optional[int] = 0
    is_active: bool = True
    prompt_template_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('document_count', pre=True, always=True)
    def set_document_count(cls, v):
        return v if v is not None else 0

    class Config:
        from_attributes = True


class LibraryWithDocuments(LibraryResponse):
    documents: List["DocumentResponse"] = []


# Document Schemas
class DocumentBase(BaseModel):
    title: str = Field(..., max_length=500)
    content: str
    source_type: SourceType
    source_url: Optional[str] = None
    source_filename: Optional[str] = None


class DocumentCreate(DocumentBase):
    brands: List[str] = []
    product_types: List[str] = []
    transmission_codes: List[str] = []
    part_numbers: List[str] = []
    tags: List[str] = []


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    brands: Optional[List[str]] = None
    product_types: Optional[List[str]] = None
    transmission_codes: Optional[List[str]] = None
    part_numbers: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    verified: Optional[bool] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    content_preview: Optional[str] = None
    source_type: SourceType
    source_url: Optional[str] = None
    source_filename: Optional[str] = None
    brands: List[str] = []
    product_types: List[str] = []
    transmission_codes: List[str] = []
    part_numbers: List[str] = []
    tags: List[str] = []
    chunk_count: int = 0
    verified: bool = False
    quality_score: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentWithContent(DocumentResponse):
    content: str
    qdrant_ids: List[str] = []


# PromptTemplate Schemas
class PromptTemplateBase(BaseModel):
    name: str = Field(..., max_length=100)
    template_type: str
    system_instructions: str
    example_output: Optional[str] = None


class PromptTemplateCreate(PromptTemplateBase):
    id: str
    product_type_filter: Optional[str] = None
    brand_filter: Optional[str] = None
    transmission_filter: Optional[str] = None
    priority: int = 0


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    system_instructions: Optional[str] = None
    example_output: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class PromptTemplateResponse(PromptTemplateBase):
    id: str
    is_active: bool = True
    is_readonly: Optional[bool] = False
    priority: int = 0
    product_type_filter: Optional[str] = None
    brand_filter: Optional[str] = None
    transmission_filter: Optional[str] = None
    usage_count: Optional[int] = 0
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Generation/Content Schemas
class ImageConfig(BaseModel):
    count: int = Field(..., ge=1, le=20)
    types: List[str] = []


class GenerateContentRequest(BaseModel):
    product_id: str
    library_ids: Optional[List[str]] = []  # Libraries to use for RAG
    template_id: Optional[str] = None  # Specific prompt template to use
    image_config: Optional[ImageConfig] = None
    use_local_llm: bool = True  # Default to True as we use Ollama
    provider: Optional[str] = None  # Specific LLM provider (grok, openai, anthropic, ollama)
    model_name: Optional[str] = None  # Specific model name for the provider
    # Analysis insights for context-aware generation
    analysis_insights: Optional[Dict[str, Any]] = None  # Grok analysis data to enhance content


class RAGSource(BaseModel):
    document_id: str
    document_title: str
    chunk_id: str
    score: float
    content_preview: str


class GeneratedContent(BaseModel):
    h1_title: str = Field(..., max_length=100)
    description_html: str
    alt_tags: List[str]
    compatible_vehicles: str
    short_description: str = Field(..., max_length=160)
    meta_title: str = Field(..., max_length=70)
    meta_description: str = Field(..., max_length=160)
    url_handle: str
    resumen: Optional[str] = None
    hashtags: Optional[str] = None


class GenerateContentResponse(BaseModel):
    id: str
    product_id: str
    content: GeneratedContent
    rag_sources: List[RAGSource]
    libraries_used: List[str]
    prompts_used: List[str]
    llm_used: str
    generation_time_ms: int
    status: GenerationStatus = GenerationStatus.DRAFT
    generated_at: datetime

    class Config:
        from_attributes = True


# Forward reference update
LibraryWithDocuments.model_rebuild()

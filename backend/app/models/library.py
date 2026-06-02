# Knowledge Library Models
# These extend the existing models to support multi-library tagged documents

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, JSON, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

# Association table for many-to-many relationship between documents and libraries
document_library_association = Table(
    'document_library',
    Base.metadata,
    Column('document_id', String, ForeignKey('documents.id'), primary_key=True),
    Column('library_id', String, ForeignKey('libraries.id'), primary_key=True)
)


class Library(Base):
    """Knowledge Library - a filtered collection of documents by type"""
    __tablename__ = "libraries"
    
    id = Column(String, primary_key=True)  # e.g., "lib_tss", "lib_valve_bodies"
    name = Column(String(100), nullable=False)  # e.g., "TSS", "Cuerpos de Válvulas"
    name_es = Column(String(100))  # Spanish name for UI
    library_type = Column(String(50), nullable=False, index=True)  # "brand", "product_type", "transmission"
    filter_value = Column(String(100))  # Value used for filtering documents
    description = Column(Text)
    icon = Column(String(50))  # Emoji or icon identifier
    color = Column(String(20))  # Hex color for UI
    
    # Associated prompt override
    prompt_template_id = Column(String, ForeignKey('prompt_templates.id'))
    prompt_template = relationship("PromptTemplate", back_populates="library")
    
    # Computed fields (updated on document changes)
    document_count = Column(Integer, default=0)
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Status
    is_active = Column(Boolean, default=True)
    scrape_url = Column(Text)  # Source URL for scraping this library
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    documents = relationship(
        "Document",
        secondary=document_library_association,
        back_populates="libraries"
    )


class Document(Base):
    """RAG Source Document - can belong to multiple libraries via tags"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # Full text content
    content_preview = Column(String(500))  # First 500 chars for UI display
    
    # Source information
    source_type = Column(String(50), nullable=False, index=True)  # "scraped", "uploaded_pdf", "manual"
    source_url = Column(Text)  # URL if scraped
    source_filename = Column(String(255))  # Filename if uploaded
    
    # Multi-library tags (JSON arrays for flexible filtering)
    brands = Column(JSON, default=list)  # ["TSS", "Sonnax"]
    product_types = Column(JSON, default=list)  # ["cuerpo_de_valvulas"]
    transmission_codes = Column(JSON, default=list)  # ["4L60E", "4L65E"]
    part_numbers = Column(JSON, default=list)  # ["TSS-VB-001"]
    tags = Column(JSON, default=list)  # Additional custom tags
    
    # RAG metadata
    chunk_count = Column(Integer, default=0)
    qdrant_ids = Column(JSON, default=list)  # IDs in vector database
    embedding_model = Column(String(100))
    
    # Quality/verification
    verified = Column(Boolean, default=False)
    verified_by = Column(String(100))
    verified_at = Column(DateTime(timezone=True))
    quality_score = Column(Integer)  # 1-10 quality rating
    
    # Timestamps
    scraped_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    libraries = relationship(
        "Library",
        secondary=document_library_association,
        back_populates="documents"
    )
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Individual chunk of a document stored in vector DB"""
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey('documents.id'), nullable=False, index=True)
    
    chunk_index = Column(Integer, nullable=False)  # Order in document
    content = Column(Text, nullable=False)  # Chunk text content
    token_count = Column(Integer)
    
    # Vector DB reference
    qdrant_id = Column(String, unique=True)
    
    # Metadata for retrieval
    chunk_metadata = Column(JSON, default=dict)  # Additional metadata
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    document = relationship("Document", back_populates="chunks")


class PromptTemplate(Base):
    """Prompt template for content generation - can be linked to a library"""
    __tablename__ = "prompt_templates"
    
    id = Column(String, primary_key=True)  # e.g., "prompt_base", "prompt_tss"
    name = Column(String(100), nullable=False)
    template_type = Column(String(50), nullable=False, index=True)  # "base", "brand", "product_type", "transmission"
    
    # Template content
    system_instructions = Column(Text, nullable=False)  # The actual prompt instructions
    example_output = Column(Text)  # Example of desired output
    
    # Configuration
    is_active = Column(Boolean, default=True)
    is_readonly = Column(Boolean, default=False)  # For base prompt
    priority = Column(Integer, default=0)  # Order when combining prompts (higher = applied later)
    version = Column(Integer, default=1)  # Version number for A/B testing and rollback
    
    # Filters for when to auto-apply this template
    product_type_filter = Column(String(50))  # Auto-apply when product type matches
    brand_filter = Column(String(50))  # Auto-apply when brand matches
    transmission_filter = Column(String(50))  # Auto-apply when transmission matches
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    library = relationship("Library", back_populates="prompt_template", uselist=False)


class GenerationHistory(Base):
    """Track all content generations for history and audit"""
    __tablename__ = "generation_history"
    
    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey('products.id'), index=True)
    
    # Input configuration
    libraries_used = Column(JSON, default=list)  # IDs of libraries used
    prompts_used = Column(JSON, default=list)  # IDs of prompts used
    image_count = Column(Integer)
    image_types = Column(JSON, default=list)
    
    # RAG context
    documents_retrieved = Column(JSON, default=list)  # Document IDs used
    chunks_retrieved = Column(JSON, default=list)  # Chunk IDs with scores
    
    # Generated output (8-point SEO format)
    h1_title = Column(String(255))
    description_html = Column(Text)
    alt_tags = Column(JSON)
    compatible_vehicles = Column(Text)
    short_description = Column(Text)
    meta_title = Column(String(255))
    meta_description = Column(Text)
    url_handle = Column(String(255))
    hashtags = Column(Text)
    
    # LLM details
    llm_used = Column(String(50))  # "claude-3-5-sonnet", "llama3.1:8b"
    llm_tokens_input = Column(Integer)
    llm_tokens_output = Column(Integer)
    generation_time_ms = Column(Integer)
    
    # Status
    status = Column(String(20), default='draft')  # "draft", "approved", "published"
    approved_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    published_to_shopify = Column(Boolean, default=False)
    
    # Timestamps
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Note: No relationship to Product here to keep models separate
    # Can be joined via product_id when needed

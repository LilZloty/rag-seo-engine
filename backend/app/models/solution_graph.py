"""
SOLUTION GRAPH MODELS
=====================

These models create intelligent connections between:
- Search queries (what users ask)
- Blog content (educational answers)
- Products (solutions to buy)
- Fault codes (diagnostic context)
"""

from sqlalchemy import Column, String, Integer, Float, Text, Boolean, JSON, ForeignKey, Table, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


# Association table: Blog ↔ Products (many-to-many)
blog_product_recommendations = Table(
    'blog_product_recommendations',
    Base.metadata,
    Column('blog_id', String, ForeignKey('blog_solutions.id')),
    Column('product_id', String, ForeignKey('products.id')),
    Column('recommendation_type', String(50)),  # primary, secondary, alternative
    Column('match_score', Float),  # 0-100 AI match score
    Column('conversion_rate', Float),  # Historical conversion %
)


class BlogSolution(Base):
    """
    Enhanced blog content optimized for Solution Engine.
    
    Every blog article becomes a "Solution Hub" that:
    - Answers the query (AEO)
    - Shows authority (GEO)
    - Recommends products (Commerce)
    """
    __tablename__ = 'blog_solutions'
    
    id = Column(String, primary_key=True)
    shopify_blog_id = Column(String(50), index=True)
    title = Column(String(300))
    handle = Column(String(200))
    blog_handle = Column(String(100))
    url = Column(String(500))
    
    # Content classification
    content_type = Column(String(50))  # fault_code, symptom, how_to, comparison
    target_keywords = Column(JSON)  # ["p0700", "código p0700 chevrolet"]
    
    # Fault code linkage
    primary_fault_code = Column(String(20), ForeignKey('fault_codes.code'))
    related_fault_codes = Column(JSON)  # ["P0706", "P0868"]
    
    # Transmission coverage
    applicable_transmissions = Column(JSON)  # ["4L60E", "6L80"]
    applicable_vehicles = Column(JSON)  # [{"make": "Chevrolet", "model": "Silverado"}]
    
    # AEO/GEO Signals
    faq_schema = Column(JSON)  # FAQPage structured data
    howto_schema = Column(JSON)  # HowTo structured data
    authority_signals = Column(JSON)  # {"readers_helped": 10000, "expert_verified": true}
    
    # Commerce integration
    recommended_products = relationship("Product", secondary=blog_product_recommendations)
    
    # Performance metrics (from GA4/GSC)
    monthly_clicks = Column(Integer, default=0)
    monthly_impressions = Column(Integer, default=0)
    avg_position = Column(Float, default=0.0)
    avg_time_on_page = Column(Integer, default=0)  # seconds
    conversion_rate = Column(Float, default=0.0)  # Blog → Purchase %
    
    # AI-generated metadata
    content_summary = Column(Text)  # Grok-generated summary
    key_entities = Column(JSON)  # ["solenoid", "TCM", "transmission fluid"]
    difficulty_level = Column(String(20))  # beginner, intermediate, advanced
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    fault_code = relationship("FaultCode", back_populates="blog_solutions")


class SolutionPath(Base):
    """
    Pre-computed "solution paths" for common query patterns.
    
    Example: "P0700 Chevrolet" → Read Blog → Check Solenoid → Buy Kit
    """
    __tablename__ = 'solution_paths'
    
    id = Column(String, primary_key=True)
    
    # Query pattern matching
    query_pattern = Column(String(200), index=True)  # "p0700 chevrolet"
    query_intent = Column(String(50))  # diagnostic, repair, purchase, comparison
    
    # Solution steps (ordered)
    steps = Column(JSON)  # [
                          #   {"type": "blog", "id": "blog-123", "title": "Qué es P0700"},
                          #   {"type": "product", "id": "prod-456", "title": "Kit Solenoide 4L60E"}
                          # ]
    
    # Performance
    click_through_rate = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    avg_revenue_per_path = Column(Float, default=0.0)
    
    # AI optimization
    grok_optimized = Column(Boolean, default=False)
    optimization_date = Column(DateTime(timezone=True))
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProductRecommendationEngine(Base):
    """
    AI-generated product recommendations with reasoning.
    """
    __tablename__ = 'product_recommendations'
    
    id = Column(String, primary_key=True)
    
    # Context
    context_type = Column(String(50))  # fault_code, blog_article, search_query
    context_id = Column(String(100))  # ID of the context (fault code, blog ID, etc.)
    
    # Recommended products (ordered by relevance)
    recommendations = Column(JSON)  # [
                                   #   {
                                   #     "product_id": "prod-123",
                                   #     "sku": "KIT-4L60E-P0700",
                                   #     "match_score": 95,
                                   #     "reasoning": "This kit fixes P0700 in 4L60E transmissions",
                                   #     "position": 1
                                   #   }
                                   # ]
    
    # AI metadata
    generated_by = Column(String(50))  # grok, manual, algorithm
    generation_prompt = Column(Text)  # The prompt used to generate
    confidence_score = Column(Float)  # 0-100
    
    # Performance tracking
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    purchases = Column(Integer, default=0)
    revenue_generated = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())


class QueryProductAffinity(Base):
    """
    Machine learning model: Which products convert for which queries?
    
    This is the "secret sauce" - learned from your actual data.
    """
    __tablename__ = 'query_product_affinity'
    
    id = Column(Integer, primary_key=True)
    
    query_pattern = Column(String(200), index=True)  # "p0700 chevrolet silverado"
    product_id = Column(String, ForeignKey('products.id'), index=True)
    
    # Affinity scores
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    
    # Calculated scores
    click_through_rate = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)  # Click → Purchase
    revenue_per_impression = Column(Float, default=0.0)
    
    # AI prediction
    predicted_conversion_rate = Column(Float, default=0.0)  # Grok prediction
    confidence = Column(Float, default=0.0)
    
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('query_pattern', 'product_id', name='unique_query_product'),
    )


class SmartSnippet(Base):
    """
    AI-optimized featured snippets for AEO/GEO.
    
    Pre-generated answers optimized for AI engines.
    """
    __tablename__ = 'smart_snippets'
    
    id = Column(String, primary_key=True)
    
    # Target query
    query = Column(String(300), index=True)
    query_variations = Column(JSON)  # ["código p0700", "que significa p0700"]
    
    # Optimized answer
    short_answer = Column(String(300))  # For featured snippets
    detailed_answer = Column(Text)  # For AI responses
    
    # Structured data
    schema_type = Column(String(50))  # FAQPage, HowTo, Article
    schema_json = Column(JSON)
    
    # Product connection
    related_products = Column(JSON)  # ["prod-123", "prod-456"]
    
    # Performance
    ai_citation_count = Column(Integer, default=0)  # Times cited by Grok/Perplexity
    position_0_count = Column(Integer, default=0)  # Featured snippet captures
    
    # AEO signals
    authority_quote = Column(String(500))  # E-E-A-T statement
    statistic_claims = Column(JSON)  # ["Fixes 87% of P0700 cases"]
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

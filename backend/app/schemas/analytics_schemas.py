from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class TopicMetrics(BaseModel):
    """Metrics for a specific topic (transmission or fault code)"""
    topic: str
    category: str  # 'transmission', 'fault_code', 'general'
    
    # Visibility Metrics
    checks: int = 0
    mentions: int = 0
    citations: int = 0
    competitor_mentions: int = 0
    visibility_score: float = 0.0  # % of checks with mention
    
    # Sales Metrics
    orders: int = 0
    revenue: float = 0.0
    
    # Correlation Metrics
    revenue_per_mention: float = 0.0
    conversion_efficiency: float = 0.0  # score 0-100
    status: str = "neutral"  # 'star', 'underperformer', 'potential', 'low_interest'
    original_name: Optional[str] = None

class CorrelationSummary(BaseModel):
    """Summary metrics for the correlation analysis"""
    total_mentions: int
    total_revenue: float
    avg_revenue_per_mention: float
    top_performing_topic: Optional[str] = None
    most_cited_topic: Optional[str] = None

class VisibilitySalesCorrelation(BaseModel):
    """Full correlation report"""
    status: str
    days: int
    summary: CorrelationSummary
    topics: List[TopicMetrics]
    last_updated: datetime = Field(default_factory=datetime.utcnow)

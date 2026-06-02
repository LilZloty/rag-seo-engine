"""
Solution Engine API Endpoints - Phase 1
========================================

REST API for the Solution Engine.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.services.solution_engine import SolutionEngine, get_solution_engine

router = APIRouter(prefix="/solution-engine", tags=["Solution Engine"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ProductRecommendation(BaseModel):
    rank: int
    product_id: str
    sku: Optional[str]
    title: str
    handle: Optional[str]
    price: Optional[str]
    transmission_code: Optional[str]
    product_type: Optional[str]
    total_sold: int
    url: Optional[str]
    match_score: int
    reasoning: str
    fix_probability: str


class FaultCodeAnalysisResponse(BaseModel):
    fault_code: str
    products: List[ProductRecommendation]


class SolutionStep(BaseModel):
    step: int
    type: str
    title: str
    content: str


class SolutionPathResponse(BaseModel):
    query: str
    fault_code: Optional[str]
    intent: str
    steps: List[SolutionStep]
    products: List[ProductRecommendation]


class SmartSnippetResponse(BaseModel):
    query: str
    fault_code: Optional[str]
    short_answer: str
    detailed_answer: str
    authority_quote: str
    statistic_claims: List[str]
    related_products: List[str]


class DashboardStats(BaseModel):
    fault_codes_total: int
    fault_codes_with_products: int
    coverage_percentage: float
    total_product_matches: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/fault-code/{fault_code}/products", response_model=FaultCodeAnalysisResponse)
def get_fault_code_products(
    fault_code: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get product recommendations for a specific fault code.
    
    Returns products sorted by relevance with match scores and reasoning.
    """
    engine = get_solution_engine(db)
    products = engine.get_products_for_fault_code(fault_code, limit)
    
    return {
        "fault_code": fault_code,
        "products": products
    }


@router.get("/solution-path")
def get_solution_path(
    query: str = Query(..., description="Search query, e.g., 'p0700 chevrolet'"),
    db: Session = Depends(get_db)
):
    """
    Generate a solution path for a search query.
    
    Creates step-by-step journey from query to purchase.
    """
    engine = get_solution_engine(db)
    path = engine.generate_solution_path(query)
    
    return path


@router.get("/smart-snippet")
def get_smart_snippet(
    query: str = Query(..., description="Search query to optimize for"),
    db: Session = Depends(get_db)
):
    """
    Generate an optimized answer for a search query.
    
    Creates content optimized for AEO/GEO (featured snippets, AI citations).
    """
    engine = get_solution_engine(db)
    snippet = engine.generate_smart_snippet(query)
    
    return snippet


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get Solution Engine dashboard statistics.
    
    Shows coverage of fault codes with product recommendations.
    """
    engine = get_solution_engine(db)
    stats = engine.get_stats()
    
    return stats


@router.get("/top-fault-codes")
def get_top_fault_codes(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get top fault codes by search volume with product availability.
    """
    from app.models.aeo_models import FaultCode
    
    fault_codes = db.query(FaultCode).order_by(
        FaultCode.monthly_clicks.desc()
    ).limit(limit).all()
    
    engine = get_solution_engine(db)
    
    return {
        "fault_codes": [
            {
                "code": fc.code,
                "name": fc.name,
                "monthly_clicks": fc.monthly_clicks or 0,
                "monthly_impressions": fc.monthly_impressions or 0,
                "avg_position": fc.avg_position or 0,
                "products_available": len(engine.get_products_for_fault_code(fc.code, 100))
            }
            for fc in fault_codes
        ]
    }

"""
Content Analyzer API - Grok-Powered SEO/AEO/GEO Analysis (v2 Enhanced)

Provides comprehensive content analysis by aggregating data from:
- Shopify (product data, sales, inventory)
- GA4 (traffic, conversions, engagement)
- Search Console (impressions, clicks, rankings)
- AI Visibility tracking (Grok/GPT/Perplexity scores)
- Category benchmarks (conversion rates, prices, etc.)

Enhanced with:
- Primary Issue Diagnosis (NEW_PRODUCT | VISIBILITY | RELEVANCE | CONVERSION | STALLED)
- "Why This Matters" revenue context
- Cross-product intelligence
- Actionable recommendations with auto-generation hints

And analyzing with Grok AI for actionable recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional, Any
import re
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
import os
import json
import uuid
import hashlib
import time

from app.core.config import settings
from app.db.session import get_db
from app.models.product import Product, AIAnalysisCache
from app.models.analysis_run import AnalysisRun
from app.services.shopify_service import ShopifyService
from app.services.google_api_service import GoogleApiService
from app.services.dataforseo_service import dataforseo_service, format_volumes_for_gsc_table
from app.services.competitor_page_scraper import competitor_scraper, format_competitor_pages_for_prompt

router = APIRouter()


class ProductAnalyticsRequest(BaseModel):
    days: int = 30


class ProductAnalyticsResponse(BaseModel):
    # Product Info
    product_id: str
    title: str
    handle: str
    sku: Optional[str]
    
    # Shopify Data
    price: float
    compare_at_price: Optional[float]
    inventory_quantity: int
    product_type: Optional[str]
    vendor: Optional[str]
    tags: List[str]
    
    # Sales Metrics (Time-based)
    sold_30d: int
    revenue_30d: float
    sold_90d: int
    revenue_90d: float
    sold_365d: int
    revenue_365d: float
    
    # GA4 Metrics (if available)
    ga4_sessions: int
    ga4_engagement_time: float
    ga4_bounce_rate: float
    ga4_revenue: float
    
    # Search Console Metrics (if available)
    gsc_impressions: int
    gsc_clicks: int
    gsc_ctr: float
    gsc_position: float
    
    # Content Quality
    seo_score: int
    description_length: int
    image_count: int
    needs_seo: bool
    
    # Opportunity
    opportunity_level: str
    performance_score: int

    # Data freshness
    data_stale: bool = False
    last_sync_hours_ago: Optional[float] = None

    # Gap #4: where GSC numbers came from. "snapshot" = fresh daily snapshot used
    # without a live API call; "live" = GSC API queried this request; "snapshot_stale"
    # = no fresh snapshot AND live returned empty/errored, served the last known snapshot
    # instead of fake zeros; "not_measured" = no snapshot and no live data — frontend
    # should hide or label the numbers rather than render real-looking zeros.
    analytics_source: Optional[str] = None
    gsc_snapshot_age_hours: Optional[float] = None


class AIAnalysisRequest(BaseModel):
    product_id: str
    title: str
    description: str
    meta_title: Optional[str]
    meta_description: Optional[str]
    price: float
    product_type: Optional[str]
    
    # Analytics Data
    sold_30d: int
    sold_90d: int = 0
    sold_365d: int = 0
    revenue_30d: float
    revenue_90d: float = 0.0
    ga4_sessions: int
    ga4_engagement_time: float
    gsc_impressions: int
    gsc_clicks: int
    gsc_position: float
    
    # Content Metrics
    seo_score: int
    description_length: int
    image_count: int
    
    # Context
    top_keywords: List[str] = []
    vehicle_fitments: List[str] = []


class AIAnalysisResponse(BaseModel):
    seo_analysis: Dict
    aeo_analysis: Dict
    geo_analysis: Dict
    recommendations: List[Dict]
    priority_actions: List[str]
    expected_impact: Dict
    cached: bool = False  # Whether this was served from cache
    cache_age_hours: Optional[float] = None  # How old the cache is
    
    # ENHANCED v2 Fields
    primary_issue: Optional[Dict[str, Any]] = None  # {"type": "CONVERSION", "description": "...", "why": "..."}
    performance_vs_benchmark: Optional[Dict[str, Any]] = None  # Comparison vs category
    ai_visibility_scores: Optional[Dict[str, int]] = None  # {"grok": 85, "openai": 62, "perplexity": 45}
    # Gap #6: freshness of the visibility row. "fresh" / "stale" mean the
    # scores above were measured recently enough to render; "not_measured" /
    # "unknown" tell the frontend to suppress the 0/0/0 placeholders and
    # offer a "Medir ahora" CTA instead of misleading the user with a real-
    # looking zero. Comes from the latest ProductVisibilitySnapshot, NOT
    # from when the cached Grok analysis ran.
    ai_visibility_status: Optional[str] = None
    ai_visibility_age_days: Optional[int] = None
    ai_visibility_snapshot_date: Optional[str] = None
    top_opportunity_queries: Optional[List[Dict[str, Any]]] = None  # GSC queries with opportunity
    trend_indicators: Optional[Dict[str, Any]] = None  # {"traffic": "+5%", "position": "-2", "ai_visibility": "+8%"}
    estimated_revenue_opportunity: Optional[float] = None  # $ potential from implementing recommendations
    performance_tier: Optional[str] = None  # "HIGH" | "ESTABLISHED" | "DEVELOPING" — computed from actual metrics
    competitor_snippets: Optional[List[Dict[str, Any]]] = None  # Top organic SERP results: [{title, snippet, url, keyword, rank}]


class CategoryBenchmarksResponse(BaseModel):
    """Category benchmark data for comparison."""
    product_type: str
    product_count: int
    avg_conversion_rate: float
    avg_sessions: float
    avg_ctr: float
    avg_position: float
    avg_price: float
    avg_description_length: int
    top_performers: List[Dict[str, Any]]  # Top 3 products in category
    common_winning_features: List[str]  # Features that correlate with success


class CachedAnalysisRequest(BaseModel):
    force_refresh: bool = False  # If True, ignore cache and call API


# ============ HELPER FUNCTIONS FOR ENRICHED DATA ============

def get_category_benchmarks(db: Session, product_type: str) -> Dict[str, Any]:
    """
    Calculate category benchmarks from all products in the same category.
    Used to compare product performance vs peers.
    """
    if not product_type:
        return _get_default_benchmarks()
    
    # Get all products in same category
    products = db.query(Product).filter(
        Product.product_type == product_type
    ).all()
    
    if len(products) < 3:
        # Not enough data for meaningful benchmarks
        return _get_default_benchmarks()
    
    # Calculate aggregates using TOTALS (not average-of-percentages)
    total_sessions = 0
    total_sold = 0
    total_clicks = 0
    total_impressions = 0
    total_position = 0
    total_price = 0
    total_desc_len = 0
    products_with_position = 0

    for p in products:
        sessions = p.ga4_sessions or 0
        sold = p.sold_30d or 0
        impressions = p.gsc_impressions or 0
        clicks = p.gsc_clicks or 0
        position = p.gsc_position or 0

        total_sessions += sessions
        total_sold += sold
        total_impressions += impressions
        total_clicks += clicks

        if position > 0:
            total_position += position
            products_with_position += 1

        try:
            total_price += float(p.price) if p.price else 0
        except:
            pass

        total_desc_len += p.description_length or 0

    n = len(products)

    # Conversion rate: total sold / total sessions (not average of individual rates)
    avg_conversion_rate = round((total_sold / total_sessions) * 100, 2) if total_sessions > 0 else 2.1
    # CTR: total clicks / total impressions
    avg_ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions > 0 else 3.5
    # Position: average only across products that have a position
    avg_position = round(total_position / products_with_position, 1) if products_with_position > 0 else 15.0

    # Find top performers (by revenue)
    top_performers = sorted(
        [
            {
                "title": p.title[:50],
                "revenue_30d": p.revenue_30d or 0,
                "sold_30d": p.sold_30d or 0,
                "sessions": p.ga4_sessions or 0
            }
            for p in products if p.revenue_30d and p.revenue_30d > 0
        ],
        key=lambda x: x["revenue_30d"],
        reverse=True
    )[:3]

    return {
        "product_type": product_type,
        "product_count": n,
        "avg_conversion_rate": avg_conversion_rate,
        "avg_sessions": round(total_sessions / n, 1) if n > 0 else 150,
        "avg_ctr": avg_ctr,
        "avg_position": avg_position,
        "avg_price": round(total_price / n, 2) if n > 0 else 85.0,
        "avg_description_length": int(total_desc_len / n) if n > 0 else 1200,
        "top_performers": top_performers,
        "common_winning_features": [
            "comparison_table",
            "installation_guide",
            "video_content",
            "faq_section",
            "vehicle_fitment_table"
        ]
    }


def _get_default_benchmarks() -> Dict[str, Any]:
    """Default benchmarks when not enough data available."""
    return {
        "product_type": "unknown",
        "product_count": 0,
        "avg_conversion_rate": 2.1,
        "avg_sessions": 150,
        "avg_ctr": 3.5,
        "avg_position": 15.0,
        "avg_price": 85.0,
        "avg_description_length": 1200,
        "top_performers": [],
        "common_winning_features": [
            "comparison_table",
            "installation_guide",
            "faq_section"
        ]
    }


def get_product_gsc_queries(db: Session, product_handle: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top Search Console queries for a product.
    TODO: Integrate with actual GSC API for query-level data.
    """
    # For now, return placeholder - in production would query GSC API
    # filtered by product URL
    return []


def get_product_gsc_queries_with_opportunity(
    google_service: GoogleApiService,
    product_handle: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Fetch GSC queries that ACTUALLY lead to this product page and identify opportunities.
    Uses page-filtered GSC API (dimensions: query, filter: page=product_url).
    Only returns queries where this product is the landing page in Google Search.
    """
    try:
        # Fetch queries filtered by this product's landing page URL
        product_queries = google_service.get_product_gsc_queries(product_handle, days=30, limit=20)

        if not product_queries:
            return []

        opportunities = []
        for query_data in product_queries:
            impressions = query_data.get('impressions', 0)
            clicks = query_data.get('clicks', 0)
            position = query_data.get('position', 100)
            ctr = (clicks / impressions * 100) if impressions > 0 else 0

            # Identify opportunity: good impressions but low CTR or improvable position
            is_opportunity = (
                impressions > 10 and
                (ctr < 5.0 or (3 <= position <= 20))
            )

            opportunities.append({
                "query": query_data.get('query'),
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr, 2),
                "position": round(position, 1),
                "opportunity": "HIGH" if is_opportunity and impressions > 100 else "MEDIUM" if is_opportunity else "LOW",
                "potential_traffic": int(impressions * (0.05 - ctr/100)) if ctr < 5 else 0
            })

        # Sort by impressions (highest first)
        opportunities.sort(key=lambda x: x['impressions'], reverse=True)

        return opportunities[:limit]

    except Exception as e:
        print(f"[GSC Queries] Error fetching: {e}")
        return []


def get_historical_trends(db: Session, product_id: str) -> Dict[str, Any]:
    """
    Get historical trend data comparing current vs 7d/30d ago.
    Returns trend indicators and percentage changes.
    """
    try:
        from app.models.product import ProductAnalyticsSnapshot
        
        # Get current product data
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}
        
        # Get snapshots from 7d and 30d ago
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        snapshot_7d = db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.product_id == product_id,
            ProductAnalyticsSnapshot.snapshot_date <= seven_days_ago
        ).order_by(ProductAnalyticsSnapshot.snapshot_date.desc()).first()
        
        snapshot_30d = db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.product_id == product_id,
            ProductAnalyticsSnapshot.snapshot_date <= thirty_days_ago
        ).order_by(ProductAnalyticsSnapshot.snapshot_date.desc()).first()
        
        trends = {
            "current": {
                "sessions": product.ga4_sessions or 0,
                "sold_30d": product.sold_30d or 0,
                "revenue_30d": product.revenue_30d or 0,
                "gsc_impressions": product.gsc_impressions or 0,
                "gsc_clicks": product.gsc_clicks or 0,
                "gsc_position": product.gsc_position or 0,
            },
            "vs_7d": {},
            "vs_30d": {},
            "trend_indicators": {}
        }
        
        # Calculate 7d changes
        if snapshot_7d:
            trends["vs_7d"] = {
                "sessions": _calc_change(product.ga4_sessions or 0, snapshot_7d.ga4_sessions or 0),
                "sold": _calc_change(product.sold_30d or 0, snapshot_7d.sold_30d or 0),
                "impressions": _calc_change(product.gsc_impressions or 0, snapshot_7d.gsc_impressions or 0),
                "position": _calc_change(product.gsc_position or 0, snapshot_7d.gsc_position or 0, inverse=True),
            }
        
        # Calculate 30d changes
        if snapshot_30d:
            trends["vs_30d"] = {
                "sessions": _calc_change(product.ga4_sessions or 0, snapshot_30d.ga4_sessions or 0),
                "sold": _calc_change(product.sold_30d or 0, snapshot_30d.sold_30d or 0),
                "impressions": _calc_change(product.gsc_impressions or 0, snapshot_30d.gsc_impressions or 0),
                "position": _calc_change(product.gsc_position or 0, snapshot_30d.gsc_position or 0, inverse=True),
            }
        
        # Generate trend indicators
        trends["trend_indicators"] = {
            "traffic": _format_trend(trends["vs_7d"].get("sessions")),
            "sales": _format_trend(trends["vs_7d"].get("sold")),
            "position": _format_trend(trends["vs_7d"].get("position")),
            "impressions": _format_trend(trends["vs_7d"].get("impressions")),
        }
        
        return trends
        
    except Exception as e:
        print(f"[Historical Trends] Error: {e}")
        db.rollback()
        return {"error": str(e), "trend_indicators": {}}


def _calc_change(current: float, previous: float, inverse: bool = False) -> Dict[str, Any]:
    """Calculate percentage change between two values."""
    if previous == 0:
        return {"change": 0, "percent": "N/A", "direction": "neutral"}
    
    change = current - previous
    percent = (change / previous) * 100
    
    if inverse:
        percent = -percent
        direction = "up" if percent > 0 else "down" if percent < 0 else "stable"
    else:
        direction = "up" if percent > 0 else "down" if percent < 0 else "stable"
    
    return {
        "change": round(change, 2),
        "percent": round(percent, 1),
        "direction": direction
    }


def _format_trend(change_data: Dict[str, Any] | None) -> str:
    """Format trend data into a readable string."""
    if not change_data:
        return "N/A"
    
    percent = change_data.get("percent", "N/A")
    direction = change_data.get("direction", "neutral")
    
    if percent == "N/A":
        return "N/A"
    
    arrow = "↗" if direction == "up" else "↘" if direction == "down" else "→"
    return f"{arrow} {percent:+.1f}%"


def _run_content_audit(description: str) -> str:
    """
    Server-side content audit: parse HTML to detect existing elements.
    Returns a formatted string for inclusion in the Grok analysis prompt.
    """
    import re as _re
    
    if not description:
        return """- **FAQ Section**: NOT FOUND (0 questions)
- **Vehicle Table**: NOT FOUND (0 rows)
- **Technical Specs List**: NOT FOUND
- **Installation Guide**: NOT FOUND
- **Proper Heading Structure (h2/h3/h4)**: NOT FOUND

**⚠️ ALL content elements are MISSING. Recommend adding all from scratch.**"""
    
    lines = []
    
    # 1. FAQ Detection
    faq_match = _re.search(
        r'<h3[^>]*>\s*Preguntas\s+Frecuentes\s*</h3>(.*?)(?=<h[23]|$)',
        description, _re.IGNORECASE | _re.DOTALL
    )
    if faq_match:
        faq_section = faq_match.group(1)
        questions = _re.findall(r'<strong>([^<]*\?)\s*</strong>', faq_section)
        q_list = ', '.join([f'"{q[:60]}"' for q in questions[:5]])
        lines.append(f"- **FAQ Section**: FOUND ({len(questions)} questions): {q_list}")
        if len(questions) >= 5:
            lines.append("  → FAQ is COMPLETE (5+ questions). Do NOT recommend 'add FAQ'. Suggest improvements to EXISTING questions only if needed.")
        else:
            lines.append(f"  → FAQ is INCOMPLETE ({len(questions)}/5 minimum). Recommend EXPANDING with {5 - len(questions)} more questions.")
    else:
        lines.append("- **FAQ Section**: NOT FOUND (0 questions)")
        lines.append("  → Recommend ADDING a FAQ section with 5+ voice-search questions.")
    
    # 2. Vehicle Table Detection
    table_match = _re.search(r'<table[^>]*>(.*?)</table>', description, _re.IGNORECASE | _re.DOTALL)
    if table_match:
        rows = _re.findall(r'<tr[^>]*>', table_match.group(1), _re.IGNORECASE)
        row_count = max(0, len(rows) - 1)  # minus header
        lines.append(f"- **Vehicle Table**: FOUND ({row_count} vehicle rows in HTML table)")
        lines.append(f"  → Table EXISTS. Do NOT recommend 'add vehicle table'. Verify it includes ALL {row_count} vehicles from fitments data. Only suggest 'complete table with missing vehicles' if needed.")
    else:
        # Check for non-table vehicle listing
        has_vehicles_section = bool(_re.search(r'<h4[^>]*>\s*Veh', description, _re.IGNORECASE))
        if has_vehicles_section:
            lines.append("- **Vehicle Table**: PARTIAL - Vehicle section found but NOT in proper <table> format")
            lines.append("  → Recommend CONVERTING existing vehicle listing to proper HTML table with Marca/Modelo/Años/Motor columns.")
        else:
            lines.append("- **Vehicle Table**: NOT FOUND")
            lines.append("  → Recommend ADDING a vehicle compatibility table.")
    
    # 3. Technical Specs
    has_specs = bool(_re.search(r'<li>\s*<strong>(SKU|Tipo|Compatibilidad|OEM|Ubicaci)', description, _re.IGNORECASE))
    if has_specs:
        lines.append("- **Technical Specs List**: FOUND (structured <ul> with product details)")
        lines.append("  → Specs section EXISTS. Only suggest additions for MISSING specs.")
    else:
        lines.append("- **Technical Specs List**: NOT FOUND")
        lines.append("  → Recommend ADDING a specs list with SKU, OEM, compatibility, etc.")
    
    # 4. Installation Guide
    has_guide = bool(_re.search(r'<h3[^>]*>\s*Gu.{1,5}a\s+de\s+Instalaci', description, _re.IGNORECASE))
    if has_guide:
        lines.append("- **Installation Guide**: FOUND")
        lines.append("  → Guide EXISTS. Do NOT recommend adding one.")
    else:
        lines.append("- **Installation Guide**: NOT FOUND")
        lines.append("  → Recommend ADDING a brief installation guide.")
    
    # 5. Heading Structure
    has_h2 = bool(_re.search(r'<h2', description, _re.IGNORECASE))
    has_h3 = bool(_re.search(r'<h3', description, _re.IGNORECASE))
    has_h4 = bool(_re.search(r'<h4', description, _re.IGNORECASE))
    heading_parts = []
    if has_h2: heading_parts.append('h2')
    if has_h3: heading_parts.append('h3')
    if has_h4: heading_parts.append('h4')
    if heading_parts:
        lines.append(f"- **Heading Structure**: FOUND ({', '.join(heading_parts)})")
    else:
        lines.append("- **Heading Structure**: NOT FOUND (no h2/h3/h4 tags)")
    
    lines.append("")
    lines.append("**⚠️ CRITICAL: Use the audit above to guide your recommendations. NEVER recommend adding content that already EXISTS.**")
    
    return "\n".join(lines)


def _format_gsc_queries(queries: List[Dict[str, Any]]) -> str:
    """Format GSC queries into a readable table."""
    if not queries:
        return "No query data available for this product."
    
    lines = ["| Query | Impressions | CTR | Position | Opportunity |"]
    lines.append("|-------|-------------|-----|----------|-------------|")
    
    for q in queries[:8]:
        lines.append(
            f"| {q.get('query', 'N/A')[:30]} | {q.get('impressions', 0):,} | "
            f"{q.get('ctr', 0):.1f}% | {q.get('position', 0):.1f} | "
            f"{q.get('opportunity', 'LOW')} |"
        )
    
    if len(queries) > 8:
        lines.append(f"| ... and {len(queries) - 8} more queries | | | | |")
    
    return "\n".join(lines)


def _format_competitor_analysis(analysis: Dict[str, Any]) -> str:
    """Format competitor analysis into readable sections with actual LLM quotes."""
    if not analysis:
        return "No competitor data available."
    
    sections = []
    
    # AI-mentioned competitors
    ai_competitors = analysis.get("ai_mentioned_competitors", [])
    if ai_competitors:
        sections.append("### Competitors Mentioned in AI Responses:")
        for comp in ai_competitors[:5]:
            sections.append(f"- **{comp.get('name', 'Unknown')}**: Mentioned {comp.get('mention_count', 0)} times")
    
    # NEW: Actual LLM response quotes about competitors
    competitor_quotes = analysis.get("competitor_quotes", [])
    if competitor_quotes:
        sections.append("\n### What LLMs Say About Competitors (Actual Quotes):")
        for quote_data in competitor_quotes[:5]:
            competitor = quote_data.get("competitor", "Unknown")
            quote = quote_data.get("quote", "")
            provider = quote_data.get("provider", "")
            if quote:
                sections.append(f"- **{competitor}** ({provider}): \"{quote[:200]}\"")
    
    # NEW: Content gaps from LLM responses
    content_gaps = analysis.get("content_gaps", [])
    if content_gaps:
        sections.append("\n### Content Gaps (What Competitors Mention That Your Product Doesn't):")
        for gap in content_gaps[:5]:
            sections.append(f"- {gap}")
    
    # NEW: Prompts where competitors beat you
    losing_prompts = analysis.get("losing_prompts", [])
    if losing_prompts:
        sections.append("\n### Prompts Where Competitors Are Recommended Instead of You:")
        for prompt_data in losing_prompts[:3]:
            prompt = prompt_data.get("prompt", "")
            winners = prompt_data.get("competitors", [])
            sections.append(f"- Query: \"{prompt[:100]}\" → LLM recommended: {', '.join(winners)}")
    
    # Category top performers
    top_performers = analysis.get("category_top_performers", [])
    if top_performers:
        sections.append("\n### Top Performers in Category (Your Store):")
        for perf in top_performers[:3]:
            sections.append(
                f"- **{perf.get('name', 'Unknown')[:35]}**: "
                f"${perf.get('revenue_30d', 0):,.0f}/mo, "
                f"{perf.get('estimated_conversion', 0):.1f}% conversion"
            )
    
    # Gap analysis features
    gap_analysis = analysis.get("gap_analysis", {})
    if gap_analysis:
        features = gap_analysis.get("features_you_lack", [])
        if features:
            sections.append("\n### Features Common in Top Performers:")
            sections.append(", ".join(features[:5]))
    
    # Recommendations
    recommendations = analysis.get("recommendations", [])
    if recommendations:
        sections.append("\n### Competitor-Based Recommendations:")
        for rec in recommendations[:3]:
            sections.append(f"- {rec}")
    
    return "\n".join(sections) if sections else "No competitor data available."


def _format_serp_data(serp_data: Dict[str, Any]) -> str:
    """Format SERP data for the Grok prompt using the service's formatter."""
    if not serp_data:
        return "SERP data not available."
    return dataforseo_service.format_for_prompt(serp_data)


def _format_historical_trends(trends: Dict[str, Any]) -> str:
    """Format historical trend data into a readable trajectory for Grok."""
    if not trends or trends.get("error"):
        return "No historical trend data available."
    
    current = trends.get("current", {})
    vs_7d = trends.get("vs_7d", {})
    vs_30d = trends.get("vs_30d", {})
    
    def _arrow(change_data):
        if not change_data:
            return "—"
        pct = change_data.get("pct_change", 0)
        prev = change_data.get("previous", 0)
        curr = change_data.get("current", 0)
        if pct > 10:
            return f"{prev} → {curr} (↑ +{pct:.0f}%)"
        elif pct < -10:
            return f"{prev} → {curr} (↓ {pct:.0f}%)"
        else:
            return f"{prev} → {curr} (→ stable)"
    
    lines = []
    lines.append("| Metric | 30d Ago → Now | 7d Ago → Now |")
    lines.append("|--------|---------------|--------------|")
    
    metrics = [
        ("Sessions", "sessions"),
        ("Sales (30d)", "sold"),
        ("Impressions", "impressions"),
        ("GSC Position", "position"),
    ]
    
    for label, key in metrics:
        col_30d = _arrow(vs_30d.get(key)) if vs_30d else "—"
        col_7d = _arrow(vs_7d.get(key)) if vs_7d else "—"
        lines.append(f"| {label} | {col_30d} | {col_7d} |")
    
    # Add trajectory summary
    indicators = trends.get("trend_indicators", {})
    if indicators:
        summary_parts = []
        for metric, indicator in indicators.items():
            if indicator and indicator != "—":
                summary_parts.append(f"{metric}: {indicator}")
        if summary_parts:
            lines.append(f"\n**Overall Trajectory:** {' | '.join(summary_parts)}")
    
    return "\n".join(lines)


def get_competitor_analysis(
    db: Session,
    product_id: str,
    product_type: str,
    ai_visibility: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze competitors mentioned in AI responses.
    Enhanced: now fetches actual stored LLM responses for competitor quotes and content gaps.
    """
    try:
        # Get competitors from AI visibility data
        top_competitors = ai_visibility.get("top_competitors", [])
        
        # Get category top performers as competitors
        benchmarks = get_category_benchmarks(db, product_type)
        top_performers = benchmarks.get("top_performers", [])
        
        # Analyze what makes top performers successful
        competitor_insights = []
        for performer in top_performers[:3]:
            competitor_insights.append({
                "name": performer.get("title", "Unknown")[:40],
                "revenue_30d": performer.get("revenue_30d", 0),
                "sold_30d": performer.get("sold_30d", 0),
                "sessions": performer.get("sessions", 0),
                "estimated_conversion": round(
                    (performer.get("sold_30d", 0) / performer.get("sessions", 1)) * 100, 2
                ) if performer.get("sessions", 0) > 0 else 0,
            })
        
        # Get AI-mentioned competitors (from snapshot)
        ai_competitors = []
        for comp in top_competitors[:5]:
            if isinstance(comp, dict):
                ai_competitors.append({
                    "name": comp.get("name", "Unknown"),
                    "mention_count": comp.get("mentions", comp.get("mention_count", 0)),
                    "avg_position": comp.get("avg_position", 0),
                    "mentioned_in": comp.get("llms", [])
                })
            elif isinstance(comp, str):
                ai_competitors.append({
                    "name": comp, "mention_count": 1, "avg_position": 0, "mentioned_in": []
                })
        
        # NEW: Fetch actual stored LLM responses for rich competitive intelligence
        competitor_quotes, content_gaps, losing_prompts = _extract_competitor_intelligence(
            db, product_id, ai_competitors
        )
        
        return {
            "category_top_performers": competitor_insights,
            "ai_mentioned_competitors": ai_competitors,
            "competitor_quotes": competitor_quotes,
            "content_gaps": content_gaps,
            "losing_prompts": losing_prompts,
            "gap_analysis": {
                "features_you_lack": benchmarks.get("common_winning_features", []),
            },
            "recommendations": _generate_competitor_recommendations(
                competitor_insights, ai_competitors, content_gaps
            )
        }
        
    except Exception as e:
        print(f"[Competitor Analysis] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {
            "category_top_performers": [],
            "ai_mentioned_competitors": [],
            "competitor_quotes": [],
            "content_gaps": [],
            "losing_prompts": [],
            "gap_analysis": {},
            "recommendations": []
        }


def _extract_competitor_intelligence(
    db: Session,
    product_id: str,
    ai_competitors: List[Dict]
) -> tuple:
    """
    Extract rich competitive intelligence from stored ProductVisibilityResult records.
    Returns: (competitor_quotes, content_gaps, losing_prompts)
    """
    import re
    
    competitor_quotes = []
    content_gaps = []
    losing_prompts = []
    
    try:
        from app.models.aeo_models import ProductVisibilityResult
        
        # Fetch recent visibility check results with actual LLM responses
        results = db.query(ProductVisibilityResult).filter(
            ProductVisibilityResult.product_id == str(product_id),
            ProductVisibilityResult.error.is_(None),
            ProductVisibilityResult.response_text.isnot(None)
        ).order_by(ProductVisibilityResult.checked_at.desc()).limit(10).all()
        
        if not results:
            print(f"[Competitor Intel] No visibility results found for product {product_id}")
            return competitor_quotes, content_gaps, losing_prompts
        
        print(f"[Competitor Intel] Analyzing {len(results)} stored LLM responses")
        
        competitor_names = {c.get("name", "").lower() for c in ai_competitors if c.get("name")}
        keyword_counter = {}
        
        for result in results:
            response = result.response_text or ""
            competitors_in_response = result.competitors_mentioned or []
            
            # Extract quotes about each competitor
            if response and competitors_in_response:
                sentences = re.split(r'[.!?]\s+', response)
                
                for comp_name in competitors_in_response:
                    comp_lower = comp_name.lower()
                    # Find sentences mentioning this competitor
                    comp_sentences = [
                        s.strip() for s in sentences
                        if comp_lower in s.lower() and len(s.strip()) > 20
                    ]
                    
                    if comp_sentences:
                        # Take the most informative sentence (longest)
                        best_quote = max(comp_sentences, key=len)
                        competitor_quotes.append({
                            "competitor": comp_name,
                            "quote": best_quote[:300],
                            "provider": result.llm_provider,
                            "prompt": result.prompt_text[:100] if result.prompt_text else ""
                        })
                        
                        # Extract keywords from competitor mentions for gap analysis
                        for sentence in comp_sentences:
                            words = re.findall(r'\b[a-záéíóúñ]{4,}\b', sentence.lower())
                            for word in words:
                                if word not in competitor_names and word not in {
                                    'para', 'como', 'este', 'esta', 'estos', 'estas',
                                    'mejor', 'mejores', 'marca', 'marcas', 'producto',
                                    'productos', 'puede', 'pueden', 'también', 'tiene',
                                    'tienen', 'donde', 'cuando', 'porque', 'sobre',
                                    'entre', 'desde', 'hacia', 'cada', 'todo', 'toda',
                                    'todos', 'todas', 'otro', 'otra', 'otros', 'otras',
                                    'hola', 'entiendo', 'buscar', 'buscando', 'contexto',
                                    'refiere', 'comúnmente', 'usado', 'usados', 'incluyen',
                                }:
                                    keyword_counter[word] = keyword_counter.get(word, 0) + 1
            
            # Track prompts where your product was NOT mentioned but competitors were
            if not result.was_mentioned and competitors_in_response:
                losing_prompts.append({
                    "prompt": result.prompt_text or "",
                    "competitors": competitors_in_response[:3],
                    "provider": result.llm_provider
                })
        
        # Generate content gaps from competitor keyword frequency
        sorted_keywords = sorted(keyword_counter.items(), key=lambda x: x[1], reverse=True)
        for keyword, count in sorted_keywords[:8]:
            if count >= 2:
                content_gaps.append(
                    f"Competitors mention '{keyword}' ({count}x in LLM responses) — consider adding this to your product content"
                )
        
        # Dedup competitor quotes (keep best per competitor)
        seen_competitors = set()
        unique_quotes = []
        for q in competitor_quotes:
            if q["competitor"] not in seen_competitors:
                seen_competitors.add(q["competitor"])
                unique_quotes.append(q)
        competitor_quotes = unique_quotes[:5]
        
        print(f"[Competitor Intel] Found {len(competitor_quotes)} quotes, {len(content_gaps)} gaps, {len(losing_prompts)} losing prompts")
        
    except Exception as e:
        print(f"[Competitor Intel] Error extracting intelligence: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    return competitor_quotes, content_gaps, losing_prompts


def _generate_competitor_recommendations(
    top_performers: List[Dict],
    ai_competitors: List[Dict],
    content_gaps: List[str] = None  # noqa: Optional not needed, None handled below
) -> List[str]:
    """Generate actionable recommendations based on competitor analysis."""
    content_gaps = content_gaps or []
    recommendations = []
    
    if ai_competitors:
        top_ai_comp = ai_competitors[0] if ai_competitors else None
        if top_ai_comp and top_ai_comp.get("mention_count", 0) > 0:
            recommendations.append(
                f"Competidor '{top_ai_comp['name']}' aparece {top_ai_comp['mention_count']}x en respuestas de IA. "
                f"Tu contenido debe posicionar tu producto como mejor alternativa."
            )
    
    if content_gaps:
        recommendations.append(
            f"Los LLMs mencionan {len(content_gaps)} puntos clave sobre competidores que tu producto no cubre. "
            f"Agrega estos temas a tu descripción para competir en respuestas de IA."
        )
    
    if top_performers:
        top_performer = top_performers[0] if top_performers else None
        if top_performer and top_performer.get("estimated_conversion", 0) > 2:
            recommendations.append(
                f"Top performer '{top_performer['name'][:30]}' convierte al "
                f"{top_performer['estimated_conversion']:.1f}%. "
                f"Revisar su descripción para aprender de su contenido."
            )
    
    if not recommendations:
        recommendations.append("Sin suficientes datos de competidores para análisis.")
    
    return recommendations


def get_product_ai_visibility(db: Session, product_id: str) -> Dict[str, Any]:
    """
    Get AI visibility scores from ProductVisibilitySnapshot.

    Returns scores for Grok/OpenAI/Perplexity together with a freshness status
    (Gap #6) so the frontend can distinguish "no measurement yet" from a real
    0% reading. Status values:
        fresh        — snapshot ≤ 7 days old
        stale        — snapshot 7–30 days old (still surface scores, warn user)
        not_measured — no snapshot OR snapshot > 30 days old → frontend should
                       suppress the 0/0/0 row and offer "Medir ahora"
        unknown      — DB query errored
    """
    FRESH_DAYS = 7
    STALE_DAYS = 30

    try:
        from app.models.aeo_models import ProductVisibilitySnapshot

        snapshot = db.query(ProductVisibilitySnapshot).filter(
            ProductVisibilitySnapshot.product_id == str(product_id)
        ).order_by(ProductVisibilitySnapshot.snapshot_date.desc()).first()

        if snapshot and snapshot.scores_by_llm and snapshot.snapshot_date:
            snap_dt = snapshot.snapshot_date
            if snap_dt.tzinfo is None:
                snap_dt = snap_dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - snap_dt).total_seconds() / 86400

            if age_days <= FRESH_DAYS:
                status = "fresh"
            elif age_days <= STALE_DAYS:
                status = "stale"
            else:
                # Old enough that the 0/0/0 row would mislead more than help.
                # Tell the frontend it's not measured so it offers a re-probe.
                status = "not_measured"

            if status in ("fresh", "stale"):
                return {
                    "scores": snapshot.scores_by_llm,
                    "overall_score": snapshot.visibility_score,
                    "level": snapshot.visibility_level,
                    "top_competitors": snapshot.top_competitors or [],
                    "status": status,
                    "age_days": int(age_days),
                    "snapshot_date": snap_dt.isoformat(),
                }

            # status == "not_measured" because age > 30 days. Keep the legacy
            # zero-shaped dict so callers that iterate scores/overall_score
            # don't break (e.g. trend_indicators string formatting), but
            # signal not_measured so the frontend gates rendering.
            return {
                "scores": {"grok": 0, "openai": 0, "perplexity": 0},
                "overall_score": 0,
                "level": "unknown",
                "top_competitors": [],
                "status": "not_measured",
                "age_days": int(age_days),
                "snapshot_date": snap_dt.isoformat(),
            }
    except Exception as e:
        print(f"[AI Visibility] Could not fetch: {e}")
        db.rollback()  # Recover session so subsequent queries work
        return {
            "scores": {"grok": 0, "openai": 0, "perplexity": 0},
            "overall_score": 0,
            "level": "unknown",
            "top_competitors": [],
            "status": "unknown",
            "age_days": None,
            "snapshot_date": None,
        }

    # No snapshot row at all → never measured.
    return {
        "scores": {"grok": 0, "openai": 0, "perplexity": 0},
        "overall_score": 0,
        "level": "unknown",
        "top_competitors": [],
        "status": "not_measured",
        "age_days": None,
        "snapshot_date": None,
    }


def diagnose_primary_issue(
    sessions: int,
    impressions: int,
    clicks: int,
    sold: int,
    position: float,
    benchmarks: Dict[str, Any],
    sold_90d: int = 0,
    sold_365d: int = 0
) -> Dict[str, Any]:
    """
    Diagnose the PRIMARY issue affecting this product.

    Framework:
    - NEW_PRODUCT: Very low sessions + No sales (any period) = Product just launched, needs indexing
    - VISIBILITY: Low sessions + Low impressions = Content/SEO problem
    - RELEVANCE: High impressions + Low CTR = Meta/description problem
    - CONVERSION: High sessions + Low sales = Pricing/trust problem
    - STALLED: High position + Low growth = Differentiation problem

    Uses sold_90d/sold_365d as fallback: if 30d sales are 0 but 90d/365d show sales,
    the product is NOT new — it's selling through non-Google channels or had recent sales.
    """
    avg_sessions = benchmarks.get("avg_sessions", 150)
    avg_ctr = benchmarks.get("avg_ctr", 3.5)
    avg_conversion = benchmarks.get("avg_conversion_rate", 2.1)

    # Calculate actual metrics
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    conversion_rate = (sold / sessions * 100) if sessions > 0 else 0

    # Check if product has ANY sales across all periods (Shopify data = all channels)
    has_any_sales = sold > 0 or sold_90d > 0 or sold_365d > 0
    total_known_sales = max(sold, sold_90d, sold_365d)

    # Determine Performance Tier
    if impressions >= 1000 and position > 0 and position < 10:
        performance_tier = "HIGH"
    elif impressions >= 200:
        performance_tier = "ESTABLISHED"
    else:
        performance_tier = "DEVELOPING"

    # NEW_PRODUCT: Very few sessions and zero sales across ALL periods = truly new
    if sessions < 10 and not has_any_sales:
        return {
            "type": "NEW_PRODUCT",
            "severity": "info",
            "description": "Producto nuevo — aún sin datos suficientes para diagnóstico completo",
            "why": f"Este producto tiene solo {sessions} sesiones y 0 ventas en todos los períodos. Es un producto nuevo que aún no acumula datos suficientes de rendimiento. Las recomendaciones deben enfocarse en optimización de contenido para indexación inicial.",
            "solution_category": "content",
            "impact_if_fixed": "Optimizar contenido ahora acelerará la indexación y primeras ventas",
            "performance_tier": performance_tier
        }

    # CHANNEL_BLIND: Has Shopify sales but no Google visibility — selling via non-Google channels
    if has_any_sales and impressions == 0 and sessions < 10:
        sales_detail = f"{sold} en 30d" if sold > 0 else f"{sold_90d} en 90d" if sold_90d > 0 else f"{sold_365d} en 365d"
        return {
            "type": "VISIBILITY",
            "severity": "high",
            "description": f"Producto con ventas ({sales_detail}) pero invisible en Google",
            "why": f"Este producto tiene {total_known_sales} ventas (Shopify, todos los canales) pero 0 impresiones en Google Search Console y {sessions} sesiones GA4. Las ventas llegan por canales no-Google (directo, redes sociales, Mercado Libre, WhatsApp). Hay oportunidad de capturar tráfico orgánico adicional.",
            "solution_category": "seo",
            "impact_if_fixed": f"Capturar tráfico orgánico de Google para un producto que ya convierte — alto potencial de ROI",
            "performance_tier": performance_tier
        }
    
    # VISIBILITY issue: Below average traffic
    if sessions < avg_sessions * 0.5 and impressions < 1000:
        return {
            "type": "VISIBILITY",
            "severity": "high" if sessions < avg_sessions * 0.25 else "medium",
            "description": "Bajo tráfico y pocas impresiones",
            "why": f"Este producto tiene {sessions} sesiones vs promedio de {avg_sessions:.0f}. Las impresiones ({impressions}) son muy bajas.",
            "solution_category": "seo",
            "impact_if_fixed": f"Potencial +{int((avg_sessions - sessions) / avg_sessions * 100)}% tráfico",
            "performance_tier": performance_tier
        }
    
    # RELEVANCE issue: Good impressions but low CTR
    if impressions > 1000 and ctr < avg_ctr * 0.7:
        return {
            "type": "RELEVANCE",
            "severity": "high" if ctr < avg_ctr * 0.5 else "medium",
            "description": "Buenas impresiones pero bajo CTR",
            "why": f"El producto aparece en búsquedas ({impressions} impresiones) pero el CTR es {ctr:.1f}% vs promedio {avg_ctr:.1f}%.",
            "solution_category": "meta",
            "impact_if_fixed": f"Potencial +{int((avg_ctr - ctr) / avg_ctr * 100)}% clics",
            "performance_tier": performance_tier
        }
    
    # CONVERSION issue: Good traffic but low sales
    if sessions > avg_sessions * 0.7 and conversion_rate < avg_conversion * 0.5:
        return {
            "type": "CONVERSION",
            "severity": "high" if conversion_rate < avg_conversion * 0.3 else "medium",
            "description": "Buen tráfico pero bajas ventas",
            "why": f"El producto recibe {sessions} sesiones pero convierte al {conversion_rate:.1f}% vs promedio {avg_conversion:.1f}%.",
            "solution_category": "conversion",
            "impact_if_fixed": f"Potencial +{int((avg_conversion - conversion_rate) / avg_conversion * 100)}% ventas",
            "performance_tier": performance_tier
        }
    
    # STALLED issue: Good position but not growing
    if position < 10 and sessions > 0:
        return {
            "type": "STALLED",
            "severity": "medium",
            "description": "Buena posición pero estancado",
            "why": f"El producto está en posición {position:.1f} pero podría capturar más tráfico con mejor contenido.",
            "solution_category": "differentiation",
            "impact_if_fixed": "Potencial +20-30% tráfico con contenido diferenciado",
            "performance_tier": performance_tier
        }
    
    # Default: General optimization
    return {
        "type": "OPTIMIZATION",
        "severity": "low",
        "description": "Oportunidad de mejora general",
        "why": "El producto tiene rendimiento moderado con oportunidades de mejora en múltiples áreas.",
        "solution_category": "general",
        "impact_if_fixed": "Potencial +10-20% rendimiento general",
        "performance_tier": performance_tier
    }


def get_shopify_service():
    return ShopifyService()


def get_google_service():
    return GoogleApiService()


# ============ CATEGORY BENCHMARKS ENDPOINT ============

@router.get("/analyze/category-benchmarks/{product_type}", response_model=CategoryBenchmarksResponse)
async def get_category_benchmarks_endpoint(
    product_type: str,
    db: Session = Depends(get_db)
):
    """
    Get category benchmarks for comparison.
    
    Returns average metrics for all products in the same category,
    enabling comparison of product performance vs peers.
    """
    try:
        benchmarks = get_category_benchmarks(db, product_type)
        return CategoryBenchmarksResponse(**benchmarks)
    except Exception as e:
        print(f"Error fetching benchmarks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/product-analytics/{product_id}", response_model=ProductAnalyticsResponse)
async def get_product_analytics(
    product_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Aggregate all analytics data for a product from Shopify, GA4, and Search Console.

    Fetches LIVE data from GSC and GA4 APIs for this specific product,
    then persists it to the DB. Sales data comes from the DB (synced from Shopify orders).
    """
    try:
        # Get product from database
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        shopify_service = get_shopify_service()
        google_service = get_google_service()

        # Calculate SEO score
        seo_score = shopify_service.get_seo_score(product.current_description_html or "")

        # ---- GSC data: snapshot-first with live fallback (Gap #4) ----
        # Previous behavior was "always live, wipe to 0 if empty" — that destroyed
        # historical snapshot data whenever GSC returned an empty row (rate limits,
        # index flux, brand-new products not yet crawled, …). New behavior:
        #   1. Fresh snapshot (<25h, i.e. taken by today's 06:30 cron) wins — no API call
        #   2. Otherwise hit live GSC. On success, persist it back to Product.
        #   3. On live-empty or live-error AND we have an older snapshot, serve that as
        #      "snapshot_stale" rather than overwriting with zeros.
        #   4. Only return zeros when there genuinely is no snapshot and live has nothing.
        from app.models.product import ProductAnalyticsSnapshot
        SNAP_FRESH_HOURS = 25  # 06:30 cron + 1h buffer; anything older is "stale"

        gsc_live = None
        analytics_source: Optional[str] = None
        gsc_snapshot_age_hours: Optional[float] = None

        latest_snap = db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.product_id == product_id
        ).order_by(ProductAnalyticsSnapshot.snapshot_date.desc()).first()
        if latest_snap and latest_snap.snapshot_date:
            snap_dt = latest_snap.snapshot_date
            if snap_dt.tzinfo is None:
                snap_dt = snap_dt.replace(tzinfo=timezone.utc)
            gsc_snapshot_age_hours = (datetime.now(timezone.utc) - snap_dt).total_seconds() / 3600

        snap_is_fresh = (
            latest_snap is not None
            and gsc_snapshot_age_hours is not None
            and gsc_snapshot_age_hours < SNAP_FRESH_HOURS
        )

        def _apply_snapshot(snap):
            product.gsc_impressions = snap.gsc_impressions or 0
            product.gsc_clicks = snap.gsc_clicks or 0
            product.gsc_ctr = snap.gsc_ctr or 0.0
            product.gsc_position = snap.gsc_position or 0.0

        if snap_is_fresh:
            _apply_snapshot(latest_snap)
            analytics_source = "snapshot"
            print(f"[Analytics] GSC snapshot (fresh, {gsc_snapshot_age_hours:.1f}h old): "
                  f"{latest_snap.gsc_impressions} impressions, pos {(latest_snap.gsc_position or 0):.1f}")
        elif product.handle and google_service.credentials:
            try:
                gsc_live = google_service.get_product_gsc_live(product.handle, days=days)
                if gsc_live:
                    product.gsc_impressions = gsc_live['impressions']
                    product.gsc_clicks = gsc_live['clicks']
                    product.gsc_ctr = gsc_live['ctr']
                    product.gsc_position = gsc_live['position']
                    analytics_source = "live"
                    print(f"[Analytics] GSC live: {gsc_live['impressions']} impressions, "
                          f"pos {gsc_live['position']:.1f}")
                elif latest_snap:
                    # Live returned nothing but we have an older snapshot — serve it
                    # rather than wiping to 0. Frontend can warn via analytics_source.
                    _apply_snapshot(latest_snap)
                    analytics_source = "snapshot_stale"
                    print(f"[Analytics] GSC live: empty, falling back to stale snapshot "
                          f"({gsc_snapshot_age_hours:.1f}h old)")
                else:
                    analytics_source = "not_measured"
                    print(f"[Analytics] GSC: no live data and no snapshot for /products/{product.handle}")
            except Exception as e:
                if latest_snap:
                    _apply_snapshot(latest_snap)
                    analytics_source = "snapshot_stale"
                    print(f"[Analytics] GSC live errored ({e}); using stale snapshot")
                else:
                    analytics_source = "unknown"
                    print(f"[Analytics] GSC live errored ({e}); no snapshot either")
        elif latest_snap:
            # No GSC creds wired up but we still have a snapshot — use it.
            _apply_snapshot(latest_snap)
            analytics_source = "snapshot_stale"
        else:
            analytics_source = "not_measured"

        # ---- LIVE FETCH: GA4 data for this product ----
        ga4_live = None
        if product.handle and google_service.credentials:
            try:
                ga4_live = google_service.get_product_ga4_live(product.handle, days=days)
                if ga4_live:
                    product.ga4_sessions = ga4_live['sessions']
                    product.ga4_engagement_time = ga4_live['avg_duration']
                    product.ga4_revenue = ga4_live['revenue']
                    product.ga4_bounce_rate = ga4_live['bounce_rate']
                    print(f"[Analytics] GA4 live: {ga4_live['sessions']} sessions, ${ga4_live['revenue']:.2f} revenue")
                else:
                    product.ga4_sessions = 0
                    product.ga4_engagement_time = 0.0
                    product.ga4_revenue = 0.0
                    product.ga4_bounce_rate = 0.0
                    print(f"[Analytics] GA4 live: no data for /products/{product.handle}")
            except Exception as e:
                print(f"[Analytics] GA4 live fetch failed (using DB fallback): {e}")

        # ---- LIVE FETCH: Shopify sales for this product ----
        sales_live = None
        if product.shopify_id:
            try:
                sales_live = shopify_service.get_single_product_sales(product.shopify_id)
                if sales_live:
                    product.sold_30d = sales_live['30d']['total_sold']
                    product.revenue_30d = sales_live['30d']['total_revenue']
                    product.sold_90d = sales_live['90d']['total_sold']
                    product.revenue_90d = sales_live['90d']['total_revenue']
                    product.sold_365d = sales_live['365d']['total_sold']
                    product.revenue_365d = sales_live['365d']['total_revenue']
                    product.total_sold = sales_live['90d']['total_sold']
                    product.total_revenue = sales_live['90d']['total_revenue']
                    print(f"[Analytics] Shopify live: 30d={sales_live['30d']['total_sold']}, 90d={sales_live['90d']['total_sold']}, 365d={sales_live['365d']['total_sold']}")
            except Exception as e:
                print(f"[Analytics] Shopify sales fetch failed (using DB fallback): {e}")

        # Persist live data back to DB + update sync timestamp
        product.last_analytics_sync = datetime.now(timezone.utc)
        db.commit()

        # Extract tags
        tags = []
        if hasattr(product, 'tags') and product.tags:
            if isinstance(product.tags, str):
                tags = [t.strip() for t in product.tags.split(',')]
            elif isinstance(product.tags, list):
                tags = product.tags

        return ProductAnalyticsResponse(
            product_id=str(product.id),
            title=product.title,
            handle=product.handle,
            sku=product.sku,

            # Shopify data
            price=float(product.price or 0),
            compare_at_price=None,
            inventory_quantity=product.inventory_quantity or 0,
            product_type=product.product_type,
            vendor=product.vendor,
            tags=tags,

            # Sales metrics (live from Shopify or DB fallback)
            sold_30d=product.sold_30d or 0,
            revenue_30d=product.revenue_30d or 0.0,
            sold_90d=product.sold_90d or 0,
            revenue_90d=product.revenue_90d or 0.0,
            sold_365d=product.sold_365d or 0,
            revenue_365d=product.revenue_365d or 0.0,

            # GA4 metrics (live or DB fallback)
            ga4_sessions=product.ga4_sessions or 0,
            ga4_engagement_time=product.ga4_engagement_time or 0.0,
            ga4_bounce_rate=product.ga4_bounce_rate or 0.0,
            ga4_revenue=product.ga4_revenue or 0.0,

            # Search Console metrics (live or DB fallback)
            gsc_impressions=product.gsc_impressions or 0,
            gsc_clicks=product.gsc_clicks or 0,
            gsc_ctr=product.gsc_ctr or 0.0,
            gsc_position=product.gsc_position or 0.0,

            # Content quality
            seo_score=seo_score,
            description_length=product.description_length or 0,
            image_count=product.image_count or 0,
            needs_seo=product.needs_seo or False,

            # Opportunity
            opportunity_level=product.opportunity_level or 'low',
            performance_score=product.performance_score or 0,

            # Data freshness — gsc=snapshot now also counts as fresh enough to dodge
            # the "stale" banner since a same-day snapshot is what other dashboards use.
            data_stale=not (
                analytics_source in ("live", "snapshot")
                or ga4_live is not None
                or sales_live is not None
            ),
            last_sync_hours_ago=0.0 if (
                analytics_source in ("live", "snapshot")
                or ga4_live is not None
                or sales_live is not None
            ) else None,
            analytics_source=analytics_source,
            gsc_snapshot_age_hours=gsc_snapshot_age_hours,
        )

    except Exception as e:
        print(f"Error fetching product analytics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/cached/{product_id}")
async def get_cached_analysis(product_id: str, db: Session = Depends(get_db)):
    """
    Lightweight cache-only lookup. Returns cached analysis if available, 404 if not.
    Never triggers a Grok API call.
    """
    cache = db.query(AIAnalysisCache).filter(
        AIAnalysisCache.product_id == product_id
    ).first()

    if not cache or cache.is_stale:
        raise HTTPException(status_code=404, detail="No cached analysis")

    # Ensure updated_at is timezone-aware for comparison
    updated_at = cache.updated_at
    if updated_at and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    if not updated_at:
        raise HTTPException(status_code=404, detail="No cached analysis")

    cache_age = datetime.now(timezone.utc) - updated_at
    if cache_age > timedelta(hours=72):
        raise HTTPException(status_code=404, detail="Cache too old")

    # Sanitize legacy caches written before the keyword-data gate existed.
    # Those entries can carry hallucinated keyword_opportunities pattern-matched
    # from titles. If the cache lacks the new `keyword_opportunities_status`
    # field, treat its keywords as untrusted and clear them — fresh analyses
    # will repopulate with grounded data (or stay empty if no data exists).
    seo_cache = dict(cache.seo_analysis or {})
    if 'keyword_opportunities_status' not in seo_cache:
        seo_cache['keyword_opportunities'] = []
        seo_cache['keyword_opportunities_status'] = 'no_data'

    # Gap #6: surface CURRENT visibility freshness (not the cache's snapshot of
    # it). If the latest ProductVisibilitySnapshot is older than the staleness
    # threshold, the cached scores are returned but the status flag tells the
    # frontend to render "Aún no se ha medido" instead of the 0/0/0 row that
    # used to fool users into thinking 0% was a real measurement.
    visibility = get_product_ai_visibility(db, product_id)

    return AIAnalysisResponse(
        seo_analysis=seo_cache,
        aeo_analysis=cache.aeo_analysis or {},
        geo_analysis=cache.geo_analysis or {},
        recommendations=cache.recommendations or [],
        priority_actions=cache.priority_actions or [],
        expected_impact=cache.expected_impact or {},
        cached=True,
        cache_age_hours=cache_age.total_seconds() / 3600,
        primary_issue=cache.primary_issue,
        performance_vs_benchmark=cache.performance_vs_benchmark,
        ai_visibility_scores=cache.ai_visibility_scores,
        ai_visibility_status=visibility.get("status"),
        ai_visibility_age_days=visibility.get("age_days"),
        ai_visibility_snapshot_date=visibility.get("snapshot_date"),
        top_opportunity_queries=cache.top_opportunity_queries,
        trend_indicators=cache.trend_indicators,
        estimated_revenue_opportunity=cache.estimated_revenue_opportunity,
        performance_tier=cache.performance_tier,
    )


@router.post("/analyze/ai-content-review", response_model=AIAnalysisResponse)
async def analyze_content_with_ai(
    request: AIAnalysisRequest,
    force_refresh: bool = False,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Analyze product content with Grok AI for comprehensive SEO/AEO/GEO recommendations.
    
    This endpoint checks for cached analysis first to save API costs.
    Set force_refresh=True to get a fresh analysis.
    
    Returns:
    - SEO analysis and recommendations
    - AEO (Answer Engine Optimization) insights  
    - GEO (Generative Engine Optimization) guidance
    - Prioritized action items
    - cached: True if served from cache
    - cache_age_hours: How old the cached analysis is
    """
    from datetime import datetime, timedelta, timezone
    import uuid

    try:
        # Gap #5 — Pre-analysis Shopify sales sync check.
        # The request body carries whatever the frontend snapshot had (often from
        # an /analyze/product-analytics call earlier in the session). If the user
        # has been on the page for a while, or arrives here from a non-refreshing
        # path, those numbers can be hours old. Grok will then base
        # recommendations on stale sales — and the cache will record the stale
        # snapshot as the analysis input, defeating the drift-detection that
        # protects subsequent calls. So before we touch the cache, if Product's
        # last_analytics_sync is older than 6h (or never set), fetch fresh sales
        # inline and mutate BOTH the DB row AND the request object so the cache
        # snapshot we eventually persist reflects current truth.
        SALES_FRESH_HOURS = 6
        product_row = db.query(Product).filter(Product.id == request.product_id).first()
        if product_row is not None and product_row.shopify_id:
            last_sync = product_row.last_analytics_sync
            sales_are_stale = last_sync is None
            if last_sync is not None:
                if last_sync.tzinfo is None:
                    last_sync = last_sync.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - last_sync).total_seconds() / 3600
                sales_are_stale = age_hours > SALES_FRESH_HOURS

            if sales_are_stale:
                try:
                    from app.services.shopify_service import shopify_service
                    sales_live = shopify_service.get_single_product_sales(product_row.shopify_id)
                    if sales_live:
                        product_row.sold_30d = sales_live['30d']['total_sold']
                        product_row.revenue_30d = sales_live['30d']['total_revenue']
                        product_row.sold_90d = sales_live['90d']['total_sold']
                        product_row.revenue_90d = sales_live['90d']['total_revenue']
                        product_row.sold_365d = sales_live['365d']['total_sold']
                        product_row.revenue_365d = sales_live['365d']['total_revenue']
                        product_row.total_sold = sales_live['90d']['total_sold']
                        product_row.total_revenue = sales_live['90d']['total_revenue']
                        product_row.last_analytics_sync = datetime.now(timezone.utc)
                        db.commit()
                        # Also overwrite the request body so the drift check + the
                        # cache snapshot use fresh numbers (drift would otherwise
                        # incorrectly bust the cache on every stale-input request).
                        request.sold_30d = product_row.sold_30d
                        request.sold_90d = product_row.sold_90d
                        request.sold_365d = product_row.sold_365d
                        request.revenue_30d = float(product_row.revenue_30d or 0.0)
                        request.revenue_90d = float(product_row.revenue_90d or 0.0)
                        print(f"[AI Analysis] Gap #5 sales pre-sync: "
                              f"sold_30d={product_row.sold_30d}, "
                              f"sold_90d={product_row.sold_90d}, "
                              f"sold_365d={product_row.sold_365d}")
                except Exception as e:
                    # Non-blocking — proceed with whatever the request body had.
                    # Grok will see slightly old numbers but the analysis still runs.
                    print(f"[AI Analysis] Gap #5 sales pre-sync failed (non-blocking): {e}")

        # Check for cached analysis first (unless force_refresh is True).
        # IMPORTANT: the cache stores snapshots of the inputs (gsc_impressions,
        # seo_score, sold_30d, …) at analysis time. If ANY of those changed
        # since the cache was written, we MUST invalidate — otherwise the cache
        # can return recommendations about a different version of the product
        # (e.g. referencing a meta_title that no longer exists, which is how we
        # got the "Frmtoyta52" hallucination).
        if not force_refresh:
            cache = db.query(AIAnalysisCache).filter(
                AIAnalysisCache.product_id == request.product_id
            ).first()

            if cache and not cache.is_stale:
                cache_age = datetime.now(timezone.utc) - cache.updated_at

                # Input snapshot comparison — if any input moved, bust the cache.
                # Use small tolerances because analytics fields wobble by 1-2
                # units between syncs for reasons that don't invalidate advice.
                def _drift(snap, live, tol):
                    s = snap or 0
                    l = live or 0
                    return abs(s - l) > tol

                inputs_drifted = (
                    _drift(cache.seo_score_snapshot, request.seo_score, 2) or
                    _drift(cache.gsc_impressions_snapshot, request.gsc_impressions, 50) or
                    _drift(cache.ga4_sessions_snapshot, request.ga4_sessions, 10) or
                    _drift(cache.sold_30d_snapshot, request.sold_30d, 1)
                )

                if inputs_drifted:
                    print(f"[AI Analysis] Cache INVALIDATED — input data drifted since last analysis (product {request.product_id})")
                    cache.is_stale = True
                    db.commit()
                elif cache_age < timedelta(hours=24):
                    print(f"[AI Analysis] Cache HIT for product {request.product_id} (age: {cache_age.total_seconds()/3600:.1f} hours)")
                    # Gap #6: cache-hit shortcut still needs to surface CURRENT
                    # visibility freshness so the frontend gates rendering on the
                    # latest snapshot, not on whatever was true when Grok ran.
                    _vis_hit = get_product_ai_visibility(db, request.product_id)
                    return AIAnalysisResponse(
                        seo_analysis=cache.seo_analysis,
                        aeo_analysis=cache.aeo_analysis,
                        geo_analysis=cache.geo_analysis,
                        recommendations=cache.recommendations,
                        priority_actions=cache.priority_actions,
                        expected_impact=cache.expected_impact,
                        cached=True,
                        cache_age_hours=cache_age.total_seconds() / 3600,
                        primary_issue=cache.primary_issue,
                        performance_vs_benchmark=cache.performance_vs_benchmark,
                        ai_visibility_scores=cache.ai_visibility_scores,
                        ai_visibility_status=_vis_hit.get("status"),
                        ai_visibility_age_days=_vis_hit.get("age_days"),
                        ai_visibility_snapshot_date=_vis_hit.get("snapshot_date"),
                        top_opportunity_queries=cache.top_opportunity_queries,
                        trend_indicators=cache.trend_indicators,
                        estimated_revenue_opportunity=cache.estimated_revenue_opportunity,
                        performance_tier=cache.performance_tier,
                    )
                else:
                    print(f"[AI Analysis] Cache STALE for product {request.product_id} (age: {cache_age.total_seconds()/3600:.1f} hours)")
        
        print(f"[AI Analysis] Cache MISS for product {request.product_id} - calling Grok API...")
        
        # ============ FETCH FRESH DATA FROM SHOPIFY IF FORCE_REFRESH ============
        fresh_shopify_data = None
        if force_refresh:
            print(f"[AI Analysis] Force refresh enabled - fetching fresh Shopify data...")
            try:
                from app.services.shopify_service import shopify_service
                # Use raw SQL to avoid ORM model/column mismatch issues
                from sqlalchemy import text
                result = db.execute(text("SELECT shopify_id FROM products WHERE id = :pid"), {"pid": str(request.product_id)}).fetchone()
                shopify_id = result[0] if result else str(request.product_id)
                print(f"[AI Analysis] Fetching Shopify data for shopify_id={shopify_id}...")
                fresh_shopify_data = shopify_service.get_product_full_details(shopify_id, bypass_cache=True)
                if fresh_shopify_data:
                    desc_len = len(fresh_shopify_data.get('body_html', '') or '')
                    vehicle_count = len(fresh_shopify_data.get('vehicle_fitments', []))
                    print(f"[AI Analysis] Fresh data loaded: title='{fresh_shopify_data.get('title', '')[:50]}...', desc_len={desc_len}, vehicles={vehicle_count}")
                else:
                    print(f"[AI Analysis] Warning: get_product_full_details returned None")
            except Exception as e:
                import traceback
                print(f"[AI Analysis] Warning: Could not fetch fresh Shopify data: {e}")
                traceback.print_exc()
        
        from app.services.llm_providers.base import LLMProviderFactory

        # Initialize LLM provider (use selected or default to Grok)
        target_provider = (provider or 'grok').lower()

        # Auto-route multi-agent model to grok420 provider (requires Responses API)
        if model_name and 'multi-agent' in model_name:
            target_provider = 'grok420'
            print(f"[AI Analysis] Auto-routing multi-agent model to grok420 provider")

        grok = LLMProviderFactory.create(target_provider, model=model_name)
        effective_model = model_name or grok.model or settings.XAI_MODEL
        print(f"[AI Analysis] Using provider={target_provider}, model={effective_model}")
        
        # ============ ENRICHED DATA GATHERING (v2) ============
        print(f"[AI Analysis v2] Gathering enriched context...")
        
        # 1. Get category benchmarks
        benchmarks = get_category_benchmarks(db, request.product_type)
        print(f"[AI Analysis v2] Benchmarks: {benchmarks.get('product_count', 0)} products in category")
        
        # 2. Get AI Visibility scores
        ai_visibility = get_product_ai_visibility(db, request.product_id)
        print(f"[AI Analysis v2] AI Visibility: {ai_visibility.get('overall_score', 0)}/100")
        
        # 3. Diagnose primary issue
        primary_issue = diagnose_primary_issue(
            sessions=request.ga4_sessions,
            impressions=request.gsc_impressions,
            clicks=request.gsc_clicks,
            sold=request.sold_30d,
            position=request.gsc_position,
            benchmarks=benchmarks,
            sold_90d=request.sold_90d,
            sold_365d=request.sold_365d
        )
        print(f"[AI Analysis v2] Primary Issue: {primary_issue.get('type')} ({primary_issue.get('severity')})")
        
        # 4. Get GSC top queries with opportunities (v2.1)
        # Look up actual handle from DB instead of approximating from title
        product_record = db.query(Product).filter(Product.id == request.product_id).first()
        product_handle = product_record.handle if product_record and product_record.handle else request.title.lower().replace(' ', '-')
        print(f"[AI Analysis v2.1] Using handle: '{product_handle}' (from {'DB' if product_record and product_record.handle else 'title fallback'})")

        google_service = get_google_service()
        gsc_queries = get_product_gsc_queries_with_opportunity(
            google_service,
            product_handle,
            limit=10
        )
        print(f"[AI Analysis v2.1] GSC Queries: {len(gsc_queries)} opportunities found")
        
        # 5. Get historical trends (v2.1)
        historical_trends = get_historical_trends(db, request.product_id)
        print(f"[AI Analysis v2.1] Trends: {historical_trends.get('trend_indicators', {})}")
        
        # 6. Get competitor analysis (v2.1)
        competitor_analysis = get_competitor_analysis(
            db, 
            request.product_id, 
            request.product_type or "",
            ai_visibility
        )
        print(f"[AI Analysis v2.1] Competitors: {len(competitor_analysis.get('ai_mentioned_competitors', []))} AI-mentioned")

        # 6.5-6.7. DataForSEO (SERP landscape, competitor pages, keyword volumes)
        #
        # COST GATE: DataForSEO is paid per call. For products with <500 GSC
        # impressions there's no meaningful competitive landscape to analyze —
        # they're not competing for any visible slice of the SERP. Skipping
        # these products cuts ~80% of API volume with no intelligence loss.
        # The threshold can be tuned via settings.DATAFORSEO_MIN_IMPRESSIONS.
        serp_data = {}
        competitor_pages = []
        keyword_volumes = {}

        _min_impr_gate = getattr(settings, 'DATAFORSEO_MIN_IMPRESSIONS', 500)
        _skip_dataforseo = (request.gsc_impressions or 0) < _min_impr_gate
        if _skip_dataforseo:
            print(
                f"[AI Analysis v2.2] DataForSEO SKIPPED for product {request.product_id} — "
                f"only {request.gsc_impressions or 0} impressions (< {_min_impr_gate} threshold). "
                f"Cost-saving gate in effect."
            )

        if settings.USE_DATAFORSEO and not _skip_dataforseo:
            print(f"[AI Analysis v2.2] Fetching SERP landscape from DataForSEO...")
            serp_data = await dataforseo_service.get_serp_data_for_product(
                product_title=request.title,
                gsc_queries=gsc_queries,
                db=db,
                max_keywords=3
            )
            print(
                f"[AI Analysis v2.2] SERP: {serp_data.get('total_organic', 0)} organic, "
                f"{serp_data.get('total_paa', 0)} PAA, "
                f"cached={any(r.get('cached') for r in serp_data.get('results', []))}"
            )

            # Scrape top competitor pages from SERP results.
            # Gated behind a separate flag because Playwright multi-page scraping
            # is the expensive piece of the DataForSEO pipeline (CPU + time).
            # Set DATAFORSEO_SCRAPE_COMPETITORS=true to enable.
            if getattr(settings, 'DATAFORSEO_SCRAPE_COMPETITORS', False):
                try:
                    competitor_pages = await competitor_scraper.analyze_competitor_pages(
                        serp_data=serp_data, db=db, max_pages=3
                    )
                    print(f"[AI Analysis v2.2] Competitor pages: {len(competitor_pages)} analyzed")
                except Exception as e:
                    print(f"[AI Analysis v2.2] Competitor scraping failed (non-fatal): {e}")
            else:
                print(f"[AI Analysis v2.2] Competitor scraping skipped (DATAFORSEO_SCRAPE_COMPETITORS=false)")

            # Fetch keyword search volumes
            try:
                volume_keywords = [q.get('query', '') for q in gsc_queries[:10] if q.get('query')]
                keyword_volumes = await dataforseo_service.fetch_keyword_volumes(
                    keywords=volume_keywords, db=db
                )
                print(f"[AI Analysis v2.2] Keyword volumes: {len(keyword_volumes)} fetched")
            except Exception as e:
                print(f"[AI Analysis v2.2] Keyword volume fetch failed (non-fatal): {e}")
        else:
            print(f"[AI Analysis v2.2] DataForSEO disabled (USE_DATAFORSEO=false) — using GSC data only")

        # Keyword-opportunity data availability gate.
        # Without DataForSEO related searches AND without GSC queries that have
        # meaningful impressions, Grok has nothing to ground keyword opportunities
        # in — it pattern-matches the title and produces hallucinations like
        # "31508-41X00 Nissan" that don't exist on Google Trends. Compute this
        # once here so we can both (a) tell the LLM to return [] and (b) defensively
        # force [] after the response if the LLM ignores the instruction.
        _has_serp_related = bool((serp_data or {}).get('all_related'))
        _has_gsc_queries = any(
            (q.get('impressions') or 0) >= 10
            for q in (gsc_queries or [])
        )
        keyword_data_available = _has_serp_related or _has_gsc_queries
        print(
            f"[AI Analysis] keyword_data_available={keyword_data_available} "
            f"(serp_related={_has_serp_related}, gsc_queries_with_impressions={_has_gsc_queries})"
        )

        # Extract top organic snippets — the actual SERP competitors the product
        # needs to out-rank. We surface these to the content generator so it can
        # DIFFERENTIATE, not just regurgitate category-standard copy.
        competitor_snippets: List[Dict[str, Any]] = []
        for r in (serp_data.get('results') or [])[:3]:
            kw = r.get('keyword', '') or ''
            for organic in (r.get('organic_results') or [])[:2]:
                if not isinstance(organic, dict):
                    continue
                competitor_snippets.append({
                    'keyword': kw,
                    'rank': organic.get('rank_group') or organic.get('rank_absolute'),
                    'title': (organic.get('title') or '')[:140],
                    'snippet': (organic.get('description') or '')[:240],
                    'url': organic.get('url') or '',
                    'domain': organic.get('domain') or '',
                })
                if len(competitor_snippets) >= 6:
                    break
            if len(competitor_snippets) >= 6:
                break
        if competitor_snippets:
            print(f"[AI Analysis v2.2] Extracted {len(competitor_snippets)} competitor snippets for content pipeline")

        # 7. Build data hash to check if we can skip re-analysis
        data_hash_input = json.dumps({
            'gsc': [q.get('query', '') for q in gsc_queries[:10]],
            'sessions': request.ga4_sessions,
            'impressions': request.gsc_impressions,
            'sold': request.sold_30d,
            'sold_90d': request.sold_90d,
            'seo': request.seo_score,
        }, sort_keys=True)
        data_hash = hashlib.sha256(data_hash_input.encode()).hexdigest()
        
        # Check if a recent analysis with same data exists (skip-if-recent)
        recent_run = db.query(AnalysisRun).filter(
            AnalysisRun.product_id == request.product_id,
            AnalysisRun.data_hash == data_hash,
            AnalysisRun.is_latest == True,
            AnalysisRun.created_at > datetime.now(timezone.utc) - timedelta(hours=24)
        ).first()
        
        if recent_run and recent_run.pass2_analysis and not force_refresh:
            print(f"[AI Analysis v2.2] Skipping re-analysis — recent run found (hash={data_hash[:12]}...)")
            cached_analysis = recent_run.pass2_analysis
            # Apply the keyword-data gate to cached responses too — older cached
            # runs may carry hallucinated keyword_opportunities from before this gate
            # existed. Re-enforce the contract so the UI never shows them.
            _cached_seo = cached_analysis.setdefault('seo', {}) if isinstance(cached_analysis, dict) else {}
            if not keyword_data_available:
                _cached_seo['keyword_opportunities'] = []
                _cached_seo['keyword_opportunities_status'] = 'no_data'
            else:
                _cached_seo.setdefault('keyword_opportunities', [])
                _cached_seo.setdefault('keyword_opportunities_status', 'real')
            return AIAnalysisResponse(
                seo_analysis=cached_analysis.get('seo', {}),
                aeo_analysis=cached_analysis.get('aeo', {}),
                geo_analysis=cached_analysis.get('geo', {}),
                recommendations=cached_analysis.get('recommendations', []),
                priority_actions=cached_analysis.get('priority_actions', []),
                expected_impact=cached_analysis.get('expected_impact', {}),
                cached=True,
                cache_age_hours=(datetime.now(timezone.utc) - recent_run.created_at).total_seconds() / 3600,
                primary_issue=cached_analysis.get('primary_issue_confirmed', primary_issue),
                performance_vs_benchmark={
                    "category": benchmarks.get('product_type'),
                    "product_count": benchmarks.get('product_count', 0),
                    "metrics": {
                        "sessions": {"product": request.ga4_sessions, "category_avg": benchmarks.get('avg_sessions')},
                        "impressions": {"product": request.gsc_impressions},
                        "sold_30d": {"product": request.sold_30d},
                        "sold_90d": {"product": request.sold_90d},
                        "conversion": {"product": (request.sold_30d / request.ga4_sessions * 100) if request.ga4_sessions > 0 else 0, "category_avg": benchmarks.get('avg_conversion_rate')},
                        "ctr": {"product": (request.gsc_clicks / request.gsc_impressions * 100) if request.gsc_impressions > 0 else 0, "category_avg": benchmarks.get('avg_ctr')},
                        "position": {"product": request.gsc_position, "category_avg": benchmarks.get('avg_position')},
                    },
                    "top_performers": benchmarks.get('top_performers', [])
                },
                ai_visibility_scores=ai_visibility.get('scores', {}),
                ai_visibility_status=ai_visibility.get('status'),
                ai_visibility_age_days=ai_visibility.get('age_days'),
                ai_visibility_snapshot_date=ai_visibility.get('snapshot_date'),
                top_opportunity_queries=gsc_queries,
                trend_indicators=historical_trends.get('trend_indicators', {
                    "traffic": "N/A",
                    "position": "N/A",
                    "ai_visibility": f"{ai_visibility.get('overall_score', 0)}/100"
                }),
                estimated_revenue_opportunity=recent_run.revenue_opportunity if hasattr(recent_run, 'revenue_opportunity') else None
            )
        
        analysis_start_time = time.time()

        # Compute performance tier from actual metrics — injected into response for the generator to use
        _is_high_performer = request.gsc_impressions >= 1000 and 0 < request.gsc_position < 10
        computed_performance_tier = (
            "HIGH" if _is_high_performer
            else "ESTABLISHED" if request.gsc_impressions >= 200
            else "DEVELOPING"
        )
        print(f"[AI Analysis] Performance tier: {computed_performance_tier} (impressions={request.gsc_impressions}, position={request.gsc_position:.1f})")

        # 7b. Build ENRICHED prompt (now includes GSC queries + competitor data + SERP landscape + trends)
        # Use fresh Shopify data if available (force_refresh)
        user_prompt = build_enriched_analysis_prompt(
            request=request,
            benchmarks=benchmarks,
            ai_visibility=ai_visibility,
            primary_issue=primary_issue,
            gsc_queries=gsc_queries,
            competitor_analysis=competitor_analysis,
            fresh_shopify_data=fresh_shopify_data,
            serp_data=serp_data,
            historical_trends=historical_trends,
            competitor_pages=competitor_pages,
            keyword_volumes=keyword_volumes,
            keyword_data_available=keyword_data_available
        )
        # ========== MULTI-PASS ANALYSIS (Chain of Thought) ==========
        
        # Pass 1: Fact verification & issue identification
        print(f"[AI Analysis v2.2] Pass 1: Fact verification with {effective_model}...")
        pass1_system = """You are an expert automotive parts SEO analyst. 
Analyze the data provided and return ONLY a JSON object with your factual analysis.
Do NOT generate content or recommendations. Only analyze what IS and what IS NOT.

Return JSON with these exact keys:
{
    "verified_facts": ["list of confirmed facts from the data"],
    "data_gaps": ["what information is missing or uncertain"],
    "real_issues": [
        {"issue": "description", "evidence": "specific data point", "severity": "critical|high|medium|low"}
    ],
    "competitor_advantages": ["specific advantages competitors have based on SERP/page data"],
    "content_vs_competitors": {
        "your_word_count": 0,
        "competitor_avg_word_count": 0,
        "your_faq_count": 0,
        "competitor_avg_faq_count": 0,
        "missing_content_types": ["what competitors have that you don't"]
    },
    "priority_keywords": [
        {"keyword": "...", "volume": 0, "current_position": 0, "difficulty": "easy|medium|hard", "reason": "why prioritize"}
    ]
}"""
        
        pass1_prompt = f"""Analyze this product data. Identify VERIFIED facts, real issues, and data gaps.
DO NOT invent data. Only report what the numbers actually show.

{user_prompt}"""
        
        try:
            pass1_response = await grok.generate(
                system_prompt=pass1_system,
                user_prompt=pass1_prompt,
                temperature=0.1,
                json_mode=True,
                model=effective_model
            )
            
            # Parse Pass 1 response
            if isinstance(pass1_response, dict):
                pass1_analysis = pass1_response
            elif isinstance(pass1_response, str):
                import re
                json_match = re.search(r'\{.*\}', pass1_response, re.DOTALL)
                pass1_analysis = json.loads(json_match.group()) if json_match else {}
            else:
                pass1_analysis = {}
            
            print(f"[AI Analysis v2.2] Pass 1 complete: {len(pass1_analysis.get('real_issues', []))} issues, "
                  f"{len(pass1_analysis.get('verified_facts', []))} facts verified")
        except Exception as e:
            print(f"[AI Analysis v2.2] Pass 1 failed (non-fatal, proceeding without): {e}")
            pass1_analysis = {}
        
        # Pass 2: Full recommendation generation with verified analysis
        print(f"[AI Analysis v2.2] Pass 2: Generating recommendations with {effective_model}...")
        
        # Inject Pass 1 analysis into the system prompt
        pass1_context = ""
        if pass1_analysis:
            pass1_context = f"""

## PRE-ANALYSIS (Verified by fact-checking pass):
**Verified Facts:** {json.dumps(pass1_analysis.get('verified_facts', []), ensure_ascii=False)[:500]}
**Real Issues (evidence-based):** {json.dumps(pass1_analysis.get('real_issues', []), ensure_ascii=False)[:500]}
**Competitor Advantages:** {json.dumps(pass1_analysis.get('competitor_advantages', []), ensure_ascii=False)[:300]}
**Content Gap vs Competitors:** {json.dumps(pass1_analysis.get('content_vs_competitors', {}), ensure_ascii=False)[:300]}
**Priority Keywords:** {json.dumps(pass1_analysis.get('priority_keywords', []), ensure_ascii=False)[:300]}

IMPORTANT: Base your recommendations ONLY on these verified issues. Do NOT invent new problems."""
        
        system_prompt = f"""You are an expert SEO, AEO, and GEO analyst for automotive parts e-commerce in Mexico.

CRITICAL: Return ONLY valid JSON. No markdown, no explanations outside JSON.

Your analysis must be:
1. SPECIFIC - Not "mejorar descripción" but "agregar tabla de especificaciones con X columnas"
2. DATA-DRIVEN - Reference the benchmarks and metrics provided
3. ACTIONABLE - Include actual content that can be copied
4. REVENUE-FOCUSED - Estimate $ impact where possible

## SCORING RUBRIC — anchor your scores to the CONTENT AUDIT results, not vibes

**SEO score (0-100)** — on-page + ranking signals:
  + 40 if meta_title present, under 60 chars, and contains the transmission code
  + 20 if meta_description 140-160 chars with benefit + SKU
  + 15 if description_html > 800 chars with structured headings
  + 15 if vehicle compatibility is explicit (table or structured list)
  + 10 if H1 title matches product + transmission code
  Subtract 20 if meta_title contains SKU (violates best practice).
  Subtract 15 if URL handle changed recently on a high-impression product.

**AEO score (0-100)** — answer-engine readiness:
  + 30 if FAQ section exists with >= 5 questions (from content audit)
  + 20 if technical specs are structured (list or table)
  + 20 if installation guide present
  + 15 if JSON-LD schema types include FAQPage, Product, and VehiclePart
  + 15 if at least 3 questions target voice-search phrasing ("¿Cómo…", "¿Qué…")
  If the audit shows FAQ WITH >= 5 questions, AEO score MUST be at least 60.
  If schema is present (structured_data), AEO score MUST be at least 70.

**GEO score (0-100)** — generative-engine visibility:
  + 25 if brand/vendor is clearly stated with authority context
  + 25 if product type, transmission code, AND vehicle applications are all named
  + 20 if competitor differentiation is explicit (why this over brand X)
  + 15 if content references external authority (OEM numbers, manufacturer spec)
  + 15 if year ranges and alternate transmission codes are mentioned

When the content audit shows an element is ALREADY PRESENT, you MUST reflect that
in the score. Do not score 25/100 for AEO when the audit shows 5 FAQs + a full
vehicle table + install guide — that's a 70+ AEO configuration by the rubric.

{pass1_context}"""
        
        # Call Grok API (Pass 2 — full model)
        response = await grok.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            json_mode=True
        )
        
        # Parse the response (expecting JSON)
        # Grok returns dict when json_mode=True, string otherwise
        if isinstance(response, dict):
            analysis = response
        elif isinstance(response, str):
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                # Fallback structured response if JSON parsing fails
                analysis = parse_text_response(response)
        else:
            analysis = parse_text_response(str(response))
        
        # Extract revenue estimate from analysis (before cache save)
        revenue_opportunity = None
        try:
            impact = analysis.get('expected_impact', {})
            if isinstance(impact, dict):
                rev_str = impact.get('revenue_potential', '')
                if rev_str:
                    import re
                    match = re.search(r'\$?([\d,]+)', str(rev_str))
                    if match:
                        revenue_opportunity = float(match.group(1).replace(',', ''))
        except:
            pass

        # ─────────────────────────────────────────────────────────────
        # POST-GROK VALIDATION: drop recommendations that are already satisfied
        # by the current product content, and drop any that reference strings
        # Grok invented (hallucinations). This runs BEFORE caching so bad advice
        # doesn't get stored for 24h.
        # ─────────────────────────────────────────────────────────────
        def _is_recommendation_redundant(rec_text: str) -> Optional[str]:
            """If the recommendation asks for something already present, return
            the reason. Otherwise return None (keep the recommendation)."""
            t = (rec_text or "").lower()
            desc = (request.description or "").lower()
            meta_t = (request.meta_title or "").lower()
            meta_d = (request.meta_description or "").lower()

            # FAQ already present
            if any(k in t for k in ['agregar faq', 'add faq', 'añadir faq', 'incluir faq', 'crear faq', 'sección faq', 'seccion faq']):
                if 'preguntas frecuentes' in desc or '<details' in desc or 'faqpage' in desc:
                    return "FAQ already present in description"

            # Vehicle table — if desc has <table> inside a Vehiculos block, a "convert list to table" recommendation is stale
            if any(k in t for k in ['tabla html', 'tabla de', 'tabla completa', 'convertir.*tabla', 'reemplazar.*tabla']) and 'vehic' in t:
                if '<table' in desc and ('vehic' in desc or 'fitment' in desc):
                    return "Vehicle table already rendered as HTML"

            # Technical specs table
            if any(k in t for k in ['tabla de especificaciones', 'especificaciones técnicas', 'ficha técnica']):
                if 'ficha técnica' in desc or ('<table' in desc and 'sku' in desc and 'transmis' in desc):
                    return "Technical spec table already present"

            # Install guide
            if any(k in t for k in ['guía de instalación', 'guia de instalacion', 'install guide']):
                if 'guía de instalación' in desc or 'guia de instalacion' in desc:
                    return "Install guide already present"

            # Hallucination filter — recommendations claiming a string is in meta/title/desc
            # but the string is not actually present there. Pattern: "'XXX' en meta", "contiene 'XXX'"
            m = re.search(r"['\"`]([A-Z][A-Za-z0-9_\-]{4,})['\"`]", rec_text or "")
            if m:
                suspect = m.group(1)
                # Drop common legitimate cases (transmission codes, product codes) from the hallucination check
                lookups = (meta_t + ' ' + meta_d + ' ' + desc + ' ' + (request.title or '').lower())
                if suspect.lower() not in lookups:
                    # Grok referenced a string that doesn't exist in any product field
                    return f"References '{suspect}' which is not in any product field (likely hallucination)"

            return None

        def _filter_recommendations(items):
            if not isinstance(items, list):
                return items
            filtered = []
            dropped = 0
            for item in items:
                text = ''
                if isinstance(item, dict):
                    text = ' '.join([
                        str(item.get('action', '')),
                        str(item.get('description', '')),
                        str(item.get('title', '')),
                    ])
                elif isinstance(item, str):
                    text = item
                reason = _is_recommendation_redundant(text)
                if reason:
                    dropped += 1
                    print(f"[AI Analysis] Dropped stale recommendation — {reason}: {text[:100]}")
                    continue
                filtered.append(item)
            if dropped:
                print(f"[AI Analysis] Filtered out {dropped} stale/hallucinated recommendations")
            return filtered

        # Apply the filter to all recommendation surfaces before they get cached
        if isinstance(analysis, dict):
            if 'recommendations' in analysis:
                analysis['recommendations'] = _filter_recommendations(analysis['recommendations'])
            if 'priority_actions' in analysis:
                analysis['priority_actions'] = _filter_recommendations(analysis['priority_actions'])

        # AI visibility loop check — when overall score is low we asked Grok
        # for at least 2 recommendations flagged ai_visibility_target=true.
        # This is observability only (not a block) — false negatives make us
        # tighten the prompt; we don't want to silently regenerate.
        try:
            _av_score = (ai_visibility or {}).get('overall_score') or 0
            if _av_score < 50 and isinstance(analysis, dict):
                _recs = analysis.get('recommendations') or []
                _ai_targeted = [
                    r for r in _recs
                    if isinstance(r, dict) and (
                        r.get('ai_visibility_target') is True
                        or str(r.get('ai_visibility_target', '')).lower() == 'true'
                    )
                ]
                if len(_ai_targeted) < 2:
                    print(
                        f"[AI Analysis] AI visibility loop gap: overall_score={_av_score}, "
                        f"got {len(_ai_targeted)} ai_visibility_target recs (asked for ≥2). "
                        f"Recommendations may not be closing the AI mention gap."
                    )
                else:
                    print(
                        f"[AI Analysis] AI visibility loop closed: {len(_ai_targeted)} "
                        f"ai_visibility_target recommendations generated for score {_av_score}."
                    )
        except Exception as _av_err:
            print(f"[AI Analysis] AI visibility loop check failed (non-fatal): {_av_err}")

        # Defensive enforcement of the keyword_opportunities data gate.
        # The prompt instructs Grok to return [] when no real data exists, but
        # LLM compliance with negative instructions is probabilistic — force
        # the contract here so the UI never receives hallucinated keywords.
        if isinstance(analysis, dict):
            seo_section = analysis.setdefault('seo', {})
            if not keyword_data_available:
                if seo_section.get('keyword_opportunities'):
                    print(
                        f"[AI Analysis] Dropping {len(seo_section.get('keyword_opportunities', []))} "
                        f"keyword_opportunities — no GSC queries and no DataForSEO data to ground them in."
                    )
                seo_section['keyword_opportunities'] = []
                seo_section['keyword_opportunities_status'] = 'no_data'
            else:
                seo_section.setdefault('keyword_opportunities', [])
                seo_section['keyword_opportunities_status'] = 'real'

        # Save to cache
        try:
            cache_entry = db.query(AIAnalysisCache).filter(
                AIAnalysisCache.product_id == request.product_id
            ).first()
            
            if not cache_entry:
                cache_entry = AIAnalysisCache(
                    id=str(uuid.uuid4()),
                    product_id=request.product_id
                )
                db.add(cache_entry)
            
            # Update cache with new analysis (basic + v2 fields)
            cache_entry.seo_score = analysis.get('seo', {}).get('score', 0)
            cache_entry.aeo_score = analysis.get('aeo', {}).get('score', 0)
            cache_entry.geo_score = analysis.get('geo', {}).get('score', 0)
            cache_entry.seo_analysis = analysis.get('seo', {})
            cache_entry.aeo_analysis = analysis.get('aeo', {})
            cache_entry.geo_analysis = analysis.get('geo', {})
            cache_entry.recommendations = analysis.get('recommendations', [])
            cache_entry.priority_actions = analysis.get('priority_actions', [])
            cache_entry.expected_impact = analysis.get('expected_impact', {})
            # v2 enhanced fields
            cache_entry.primary_issue = analysis.get('primary_issue_confirmed', primary_issue)
            cache_entry.performance_vs_benchmark = {
                "category": benchmarks.get('product_type'),
                "product_count": benchmarks.get('product_count', 0),
                "metrics": {
                    "sessions": {"product": request.ga4_sessions, "category_avg": benchmarks.get('avg_sessions')},
                    "conversion": {"product": (request.sold_30d / request.ga4_sessions * 100) if request.ga4_sessions > 0 else 0, "category_avg": benchmarks.get('avg_conversion_rate')},
                    "ctr": {"product": (request.gsc_clicks / request.gsc_impressions * 100) if request.gsc_impressions > 0 else 0, "category_avg": benchmarks.get('avg_ctr')},
                    "position": {"product": request.gsc_position, "category_avg": benchmarks.get('avg_position')},
                },
                "top_performers": benchmarks.get('top_performers', [])
            }
            cache_entry.ai_visibility_scores = ai_visibility.get('scores', {})
            cache_entry.top_opportunity_queries = gsc_queries
            cache_entry.trend_indicators = historical_trends.get('trend_indicators', {
                "traffic": "N/A", "position": "N/A",
                "ai_visibility": f"{ai_visibility.get('overall_score', 0)}/100"
            })
            cache_entry.performance_tier = computed_performance_tier
            cache_entry.estimated_revenue_opportunity = revenue_opportunity

            # Save analytics snapshot for cache invalidation
            cache_entry.ga4_sessions_snapshot = request.ga4_sessions
            cache_entry.gsc_impressions_snapshot = request.gsc_impressions
            cache_entry.sold_30d_snapshot = request.sold_30d
            cache_entry.seo_score_snapshot = request.seo_score
            cache_entry.is_stale = False
            cache_entry.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            print(f"[AI Analysis] Cached results for product {request.product_id}")
        except Exception as cache_error:
            print(f"[AI Analysis] Failed to cache results: {cache_error}")
            db.rollback()
        
        # ========== SAVE FULL ANALYSIS RUN ==========
        total_duration = time.time() - analysis_start_time
        try:
            # Mark previous runs as not latest
            db.query(AnalysisRun).filter(
                AnalysisRun.product_id == request.product_id,
                AnalysisRun.is_latest == True
            ).update({'is_latest': False})
            
            run = AnalysisRun(
                id=str(uuid.uuid4()),
                product_id=request.product_id,
                # Input snapshots
                gsc_queries_snapshot=gsc_queries,
                serp_data_snapshot=serp_data,
                competitor_pages_snapshot=competitor_pages if competitor_pages else None,
                keyword_volumes_snapshot=keyword_volumes if keyword_volumes else None,
                historical_trends_snapshot=historical_trends,
                competitor_analysis_snapshot=competitor_analysis,
                benchmarks_snapshot=benchmarks,
                # Prompt
                enriched_prompt=user_prompt[:50000] if user_prompt else None,  # Cap at 50k chars
                system_prompt=system_prompt[:10000] if system_prompt else None,
                # Pass 1
                pass1_analysis=pass1_analysis if pass1_analysis else None,
                pass1_model=effective_model,
                # Pass 2
                pass2_analysis=analysis,
                pass2_model=effective_model,
                # Scores
                seo_score=analysis.get('seo', {}).get('score', 0),
                aeo_score=analysis.get('aeo', {}).get('score', 0),
                geo_score=analysis.get('geo', {}).get('score', 0),
                # Metadata
                total_duration_seconds=round(total_duration, 2),
                data_hash=data_hash,
                is_latest=True
            )
            db.add(run)
            db.commit()
            print(f"[AI Analysis] Saved AnalysisRun {run.id[:8]}... (duration={total_duration:.1f}s, hash={data_hash[:12]})")
        except Exception as run_error:
            print(f"[AI Analysis] Failed to save AnalysisRun: {run_error}")
            db.rollback()
        
        return AIAnalysisResponse(
            seo_analysis=analysis.get('seo', {}),
            aeo_analysis=analysis.get('aeo', {}),
            geo_analysis=analysis.get('geo', {}),
            recommendations=analysis.get('recommendations', []),
            priority_actions=analysis.get('priority_actions', []),
            expected_impact=analysis.get('expected_impact', {}),
            cached=False,
            cache_age_hours=0,
            # ENHANCED v2 fields
            primary_issue=analysis.get('primary_issue_confirmed', primary_issue),
            performance_vs_benchmark={
                "category": benchmarks.get('product_type'),
                "product_count": benchmarks.get('product_count', 0),
                "metrics": {
                    "sessions": {"product": request.ga4_sessions, "category_avg": benchmarks.get('avg_sessions')},
                    "conversion": {"product": (request.sold_30d / request.ga4_sessions * 100) if request.ga4_sessions > 0 else 0, "category_avg": benchmarks.get('avg_conversion_rate')},
                    "ctr": {"product": (request.gsc_clicks / request.gsc_impressions * 100) if request.gsc_impressions > 0 else 0, "category_avg": benchmarks.get('avg_ctr')},
                    "position": {"product": request.gsc_position, "category_avg": benchmarks.get('avg_position')},
                },
                "top_performers": benchmarks.get('top_performers', [])
            },
            ai_visibility_scores=ai_visibility.get('scores', {}),
            ai_visibility_status=ai_visibility.get('status'),
            ai_visibility_age_days=ai_visibility.get('age_days'),
            ai_visibility_snapshot_date=ai_visibility.get('snapshot_date'),
            top_opportunity_queries=gsc_queries,  # v2.1: Now populated
            trend_indicators=historical_trends.get('trend_indicators', {  # v2.1: Now populated
                "traffic": "N/A",
                "position": "N/A",
                "ai_visibility": f"{ai_visibility.get('overall_score', 0)}/100"
            }),
            estimated_revenue_opportunity=revenue_opportunity,
            performance_tier=computed_performance_tier,
            competitor_snippets=competitor_snippets,
        )

    except Exception as e:
        print(f"AI analysis error: {e}")
        import traceback
        traceback.print_exc()
        # Return fallback response with enriched context
        return AIAnalysisResponse(
            seo_analysis={"score": request.seo_score, "issues": [], "opportunities": []},
            aeo_analysis={"score": 50, "snippet_opportunities": [], "questions": []},
            geo_analysis={"score": 50, "entity_clarity": "medium", "gaps": []},
            recommendations=[
                {
                    "priority": "high",
                    "category": "seo",
                    "action": "Mejorar la descripción del producto",
                    "expected_impact": "Aumentar tráfico orgánico",
                    "implementation": "Agregar más detalles técnicos y especificaciones"
                }
            ],
            priority_actions=["Mejorar descripción del producto", "Agregar FAQ", "Optimizar meta tags"],
            expected_impact={
                "traffic_increase": "20-30%",
                "conversion_increase": "10-15%",
                "timeline": "4-8 semanas"
            },
            # Include enriched context even in fallback
            primary_issue=primary_issue if 'primary_issue' in dir() else {"type": "UNKNOWN", "description": "Error en análisis"},
            performance_vs_benchmark={"category": request.product_type, "error": "Analysis failed"},
            ai_visibility_scores={"grok": 0, "openai": 0, "perplexity": 0},
            # Gap #6: in the fallback path we never reached the snapshot query, so
            # flag status as "unknown" rather than letting it default to undefined.
            # Frontend treats unknown like not_measured (suppresses the 0/0/0 row)
            # but the label tells the user it was a backend error, not absence of data.
            ai_visibility_status="unknown",
            ai_visibility_age_days=None,
            ai_visibility_snapshot_date=None,
            estimated_revenue_opportunity=None
        )


def build_enriched_analysis_prompt(
    request: AIAnalysisRequest,
    benchmarks: Dict[str, Any],
    ai_visibility: Dict[str, Any],
    primary_issue: Dict[str, Any],
    gsc_queries: List[Dict[str, Any]] = None,
    competitor_analysis: Dict[str, Any] = None,
    fresh_shopify_data: Dict[str, Any] = None,
    serp_data: Dict[str, Any] = None,
    historical_trends: Optional[Dict[str, Any]] = None,
    competitor_pages: Optional[List[Dict[str, Any]]] = None,
    keyword_volumes: Optional[Dict[str, Dict[str, Any]]] = None,
    keyword_data_available: bool = False
) -> str:
    """
    Build ENHANCED comprehensive prompt for Grok analysis v2.2.
    
    Includes:
    - Primary Issue Diagnosis (NEW_PRODUCT | VISIBILITY | RELEVANCE | CONVERSION | STALLED)
    - AI Visibility scores (Grok/GPT/Perplexity)
    - Category benchmarks comparison
    - Historical trends (sessions, sales, position trajectory)
    - GSC top queries with opportunities (v2.1)
    - Competitor analysis (v2.1)
    - "Why This Matters" revenue context
    - Actionable recommendations with auto-generation hints
    """
    gsc_queries = gsc_queries or []
    competitor_analysis = competitor_analysis or {}
    serp_data = serp_data or {}
    historical_trends = historical_trends or {}
    competitor_pages = competitor_pages or []
    keyword_volumes = keyword_volumes or {}

    import re as _re
    
    # Use fresh Shopify data when available (force_refresh), otherwise use request data
    if fresh_shopify_data:
        print(f"[AI Analysis Prompt] Using FRESH Shopify data with {len(fresh_shopify_data.get('vehicle_fitments', []))} vehicles")
        title = fresh_shopify_data.get('title', request.title)
        description = fresh_shopify_data.get('body_html', request.description)
        meta_title = fresh_shopify_data.get('meta_title', request.meta_title)
        meta_description = fresh_shopify_data.get('meta_description', request.meta_description)
        image_count = len(fresh_shopify_data.get('images', []))
        vehicle_fitments = fresh_shopify_data.get('vehicle_fitments', [])
        vehicle_count = len(vehicle_fitments)
        # Calculate fresh SEO score
        from app.services.shopify_service import shopify_service
        seo_score = shopify_service.get_seo_score(description or '')
        description_length = len(description or '')
    else:
        print(f"[AI Analysis Prompt] Using REQUEST data (no fresh data available)")
        desc_len = len(request.description or '')
        print(f"[AI Analysis Prompt] Request description length: {desc_len} chars (expected: {request.description_length})")
        if desc_len < 100 and request.description_length > 500:
            print(f"[AI Analysis Prompt] WARNING: Description seems truncated or empty! Frontend sent {desc_len} chars but product has {request.description_length} chars. Content audit will be inaccurate.")
        title = request.title
        description = request.description
        meta_title = request.meta_title
        meta_description = request.meta_description
        image_count = request.image_count
        vehicle_count = len(request.vehicle_fitments)
        seo_score = request.seo_score
        description_length = request.description_length
    
    # Calculate conversion rate
    conversion_rate = (request.sold_30d / request.ga4_sessions * 100) if request.ga4_sessions > 0 else 0
    ctr = (request.gsc_clicks / request.gsc_impressions * 100) if request.gsc_impressions > 0 else 0
    
    # Determine status vs benchmark
    def get_status(value: float, benchmark: float, inverse: bool = False) -> str:
        if inverse:
            return "✅ Better" if value < benchmark else "⚠️ Worse"
        return "✅ Above" if value > benchmark else "⚠️ Below"

    # Performance tier detection — classify product to protect high-ranking organic assets
    is_high_performer = (
        request.gsc_impressions >= 1000 and
        0 < request.gsc_position < 10
    )
    # Build a hard-rule block for keyword_opportunities when no real data exists.
    # Without this, Grok pattern-matches the title/URL and produces fake "opportunities"
    # like "31508-41X00 Nissan" that don't appear in Google Trends or anywhere else.
    if keyword_data_available:
        keyword_opps_rule = (
            "**KEYWORD OPPORTUNITIES — DATA AVAILABLE**: Real GSC queries or DataForSEO Related Searches "
            "are present in the prompt. Source `keyword_opportunities` ONLY from those — "
            "specifically: GSC queries with impressions where the product ranks at position 11+ "
            "(close-but-not-ranking), or items from the Related Searches list. "
            "Set `keyword_opportunities_status` to 'real'."
        )
    else:
        keyword_opps_rule = (
            "**KEYWORD OPPORTUNITIES — NO DATA AVAILABLE (HARD RULE)**: This product has NO GSC queries "
            "with meaningful impressions AND no DataForSEO Related Searches. "
            "You MUST return `keyword_opportunities: []` and `keyword_opportunities_status: 'no_data'`. "
            "DO NOT pattern-match the product title, URL handle, OEM numbers, or transmission codes "
            "to invent keywords. Strings like '31508-41X00 Nissan' or 'rondana porta planetario' that "
            "are already in the title are NOT opportunities — they're descriptors. "
            "Returning fake keywords here misleads the user into chasing nothing."
        )

    performance_tier = (
        "HIGH" if is_high_performer
        else "ESTABLISHED" if request.gsc_impressions >= 200
        else "DEVELOPING"
    )

    return f"""You are an expert SEO, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) analyst specializing in automotive parts e-commerce for the Mexican market.

Analyze this product's content and performance data, then provide DETAILED, SPECIFIC, ACTIONABLE recommendations in Spanish.

    ## 📊 PRODUCT PERFORMANCE SNAPSHOT
- **Title:** {title}
- **Category:** {request.product_type or 'Not specified'}
- **Price:** ${request.price} (Category avg: ${benchmarks.get('avg_price', 85):.2f})
- **30d Sales:** {request.sold_30d} units | ${request.revenue_30d:.2f} revenue
- **90d Sales:** {request.sold_90d} units | ${request.revenue_90d:.2f} revenue
- **Note:** Sales data comes from Shopify (ALL channels: Google, direct, social, Mercado Libre, WhatsApp). GSC only tracks Google Search.
- **Vehicle Fitments:** {vehicle_count} vehicles (check if table present in description)

## 📈 METRICS vs CATEGORY BENCHMARK
| Metric | This Product | Category Avg | Status |
|--------|--------------|--------------|--------|
| Sessions | {request.ga4_sessions} | {benchmarks.get('avg_sessions', 150):.0f} | {get_status(request.ga4_sessions, benchmarks.get('avg_sessions', 150))} |
| Conversion | {conversion_rate:.1f}% | {benchmarks.get('avg_conversion_rate', 2.1):.1f}% | {get_status(conversion_rate, benchmarks.get('avg_conversion_rate', 2.1))} |
| CTR | {ctr:.1f}% | {benchmarks.get('avg_ctr', 3.5):.1f}% | {get_status(ctr, benchmarks.get('avg_ctr', 3.5))} |
| Position | {request.gsc_position:.1f} | {benchmarks.get('avg_position', 15):.1f} | {get_status(request.gsc_position, benchmarks.get('avg_position', 15), inverse=True)} |
| GSC Impressions | {request.gsc_impressions:,} | — | — |

## 📐 HOW TO INTERPRET THESE METRICS (SEO First Principles)
GSC impressions and organic position are the strongest signal of keyword-to-content alignment available.

**Ranking asset hierarchy (most to least critical to preserve):**
1. **URL/handle** — the most destructive change possible. The URL is what Google indexes, what builds link equity, and what the ranking algorithm has learned to associate with search queries. Changing a ranking URL, even with redirects, causes ranking collapse and takes months to recover. NEVER recommend changing the URL for a product with established traffic.
2. **Meta title** — Google's primary on-page ranking signal. It determines which queries the page appears for in SERPs. More important than H1 for ranking. If a product is ranking at position < 10, the meta title keywords are working — do not recommend replacing them.
3. **H1 title** — on-page content signal. Less critical than meta title for ranking but part of the semantic structure Google has indexed.

**The Preservation Principle:** A high impression count combined with a strong organic position (< 10) means the URL, meta title, and H1 keywords are **already succeeding** at matching Google's understanding of this page. The algorithm has learned to associate those exact keywords with this URL. Recommending changes to these in this situation is not optimization — it breaks validated semantic signals and can cause a ranking collapse (sometimes of 90%+) that takes months to recover.

**The Inverse:** A product with near-zero impressions has no validated keyword signal. The current meta title and H1 are failing to communicate relevance to Google. In this case, rewriting them is the highest-leverage action available.

**Apply this proportionally to the data above:**
- This product has **{request.gsc_impressions:,} impressions** at position **{request.gsc_position:.1f}** (category avg: {benchmarks.get('avg_position', 15):.1f})
- The stronger these numbers, the more your recommendations should ENRICH rather than REPLACE: add FAQ, tables, specs, AEO snippets — without touching URL, meta title, or H1 keywords that are already ranking
- The weaker these numbers, the more freely you can recommend structural changes including meta title and H1 rewrites

## 📊 HISTORICAL TRENDS (Is this product growing or stagnating?)
{_format_historical_trends(historical_trends)}

## 🤖 AI VISIBILITY SCORES (How visible is this product in AI responses?)
- **Grok/X.AI:** {ai_visibility.get('scores', {}).get('grok', 0)}/100
- **ChatGPT:** {ai_visibility.get('scores', {}).get('openai', 0)}/100
- **Perplexity:** {ai_visibility.get('scores', {}).get('perplexity', 0)}/100
- **Overall:** {ai_visibility.get('overall_score', 0)}/100 ({ai_visibility.get('level', 'unknown')})
- **Competitors mentioned in AI:** {', '.join([c.get('name', '') for c in ai_visibility.get('top_competitors', [])[:3]]) or 'None detected'}

### 🎯 AI VISIBILITY ACTION RULE (HARD REQUIREMENT)
{(
    "**This product is INVISIBLE or weak in AI engines (overall <50/100).** Your recommendations "
    "MUST include AT LEAST 2 entries with `ai_visibility_target: true` that specifically address "
    "this gap — NOT generic SEO advice. Concrete examples of qualifying recommendations: "
    "(1) add explicit comparison content versus the competitors listed above (\"a diferencia de "
    "[Competitor], este producto…\"), since AI engines cite products that explicitly differentiate themselves; "
    "(2) add a structured spec table with verifiable numbers (viscosity cSt, capacity L, OEM refs) — "
    "AI engines preferentially quote pages with citable specs; "
    "(3) add a 'Why this product over [alternative]' section that names alternatives directly; "
    "(4) add explicit authority signals (years in business, units sold, certifications) since AI engines "
    "weight authority heavily when choosing what to mention. "
    "Each AI-targeted recommendation should name the specific provider and competitor it addresses "
    "(\"For ChatGPT, where [Competitor] is mentioned 3x more often, add…\"). "
    "Skip generic SEO advice for these slots — focus exclusively on closing the visibility gap."
) if (ai_visibility.get('overall_score') or 0) < 50 else (
    "**AI visibility is healthy (overall ≥50/100).** Recommendations may include AI-visibility "
    "enhancements but they are not mandatory. Mark any AI-targeted suggestions with "
    "`ai_visibility_target: true` so they can be tracked separately from general SEO work."
)}

## 🔍 PRIMARY ISSUE DIAGNOSED
**Type:** {primary_issue.get('type', 'UNKNOWN')}
**Severity:** {primary_issue.get('severity', 'medium')}
**Description:** {primary_issue.get('description', 'Not diagnosed')}
**Why:** {primary_issue.get('why', 'Not specified')}
**Impact if fixed:** {primary_issue.get('impact_if_fixed', 'Unknown')}

## 🔎 TOP SEARCH QUERIES WITH OPPORTUNITY (from Google Search Console)
{format_volumes_for_gsc_table(gsc_queries, keyword_volumes) if keyword_volumes else _format_gsc_queries(gsc_queries)}

## 🏆 COMPETITOR ANALYSIS
{_format_competitor_analysis(competitor_analysis)}

## 🌐 REAL SERP LANDSCAPE (DataForSEO - Mexico, Google, Desktop)
{_format_serp_data(serp_data)}

## 🔬 COMPETITOR PAGE ANALYSIS (Actual Content From Top Ranking Pages)
{format_competitor_pages_for_prompt(competitor_pages)}

## 📝 CONTENT QUALITY
- **SEO Score:** {seo_score}/100
- **Description Length:** {description_length} chars (Category avg: {benchmarks.get('avg_description_length', 1200)})
- **Images:** {image_count}

## Current Content Preview
**Meta Title:** {meta_title or 'Not set'}
**Meta Description:** {meta_description or 'Not set'}
**Full Product Description (HTML):**
{description if description else 'No description'}

## 🔍 CONTENT AUDIT - EXISTING ELEMENTS DETECTED (SERVER-SIDE SCAN)
The following content elements were **already detected** in the current product description by automated scanning:

{_run_content_audit(description)}

## ✅ YOUR TASK

### 1. Confirm or Refine Primary Issue
Based on your analysis, confirm if the diagnosed issue is correct or identify a different primary issue.

### 2. COMPETITIVE CONTENT STRATEGY (Use Competitor Quotes Above)
The COMPETITOR ANALYSIS section contains ACTUAL quotes from LLM responses about competitors.
- Use these quotes to identify SPECIFIC claims your product must counter
- For each competitor advantage mentioned by LLMs, suggest content that positions YOUR product favorably
- If LLMs recommend competitors because of specific features (e.g., "garantía extendida", "kit completo"), recommend adding those features or explicitly addressing why your product is better
- The "Content Gaps" list shows keywords competitors use that YOUR product doesn't mention — address each gap
- The "Losing Prompts" show exact user queries where LLMs chose competitors over you — tailor FAQ and description to win these queries
- Generate comparison table data based on ACTUAL competitor claims from the quotes, not invented specs

### 3. Provide SPECIFIC, VERIFIED Recommendations (Use Content Audit)
Based on your CONTENT AUDIT above, provide recommendations ONLY for MISSING content:
- If FAQ exists with 5+ questions → Suggest "Expandir FAQ con preguntas sobre [tema específico]" NOT "Agregar FAQ"
- If vehicle table exists → Verify it includes ALL vehicles from fitments, suggest "Completar tabla con vehículos faltantes: [list]"
- If no FAQ exists → Recommend adding FAQ with specific questions based on search queries AND the "Losing Prompts" above
- If no vehicle table → Recommend adding complete vehicle compatibility table
- Be SPECIFIC (not "mejorar descripción" but "agregar tabla de especificaciones con columnas: OEM, Año, Modelo")
- Include CONSERVATIVE impact estimates (e.g., "+10-20% tráfico" not "+340% CTR")
- Mark EASY TO IMPLEMENT items with [AUTO-GENERATE] tag
- VERIFY all technical specs (OEM numbers, viscosity, compatibility) are accurate
- Use PRECISE language: "compatible con" NOT "soluciona"
- **Respect Organic Signals:** Before recommending a title change, evaluate the GSC impressions and position data in the metrics table. If that product already has meaningful impressions and a strong position, those metrics prove the current keywords are working for Google. In that case, focus recommendations on ENRICHING the page (FAQ, tables, technical specs, AEO structured data) rather than replacing the title or core keywords. If impressions are near zero and position is weak or absent, a title rewrite is the right call. Use `OPTIMIZATION_ONLY` as the issue type when the product is already ranking well and the goal is conversion/enrichment, not visibility.

### 3. Generate Ready-to-Use Content (FACTUALLY ACCURATE)
For high-priority items, provide actual content that can be copied:
- All specs must be VERIFIABLE from product data
- NO invented OEM numbers or specifications
- Meta title under 60 characters
- Use conservative, accurate claims only

## OUTPUT FORMAT - Return ONLY valid JSON:
{{
    "primary_issue_confirmed": {{
        "type": "NEW_PRODUCT|VISIBILITY|RELEVANCE|CONVERSION|STALLED|OPTIMIZATION|OPTIMIZATION_ONLY",
        "description": "Brief description in Spanish",
        "why": "Explanation in Spanish with data points",
        "estimated_revenue_impact": 1234.56,
        "performance_tier": "HIGH|ESTABLISHED|DEVELOPING"
    }},
    "seo": {{
        "score": number (0-100),
        "critical_issues": ["specific issue 1", "specific issue 2"],
        "improvements": ["specific improvement 1", "specific improvement 2"],
        "keyword_opportunities": ["ONLY keywords sourced from REAL data: GSC queries with impressions (currently ranking poorly) OR DataForSEO Related Searches. NEVER pattern-match the product title or URL handle. If neither source provides data, return []."],
        "keyword_opportunities_status": "'real' if keywords are grounded in GSC/DataForSEO data, 'no_data' if neither source had data and the array is empty"
    }},
    "aeo": {{
        "score": number (0-100),
        "snippet_opportunities": ["specific opportunity with example"],
        "question_targets": ["¿Specific question 1?", "¿Question 2?"],
        "structured_data_recommendations": ["specific schema type to add"]
    }},
    "geo": {{
        "score": number (0-100),
        "entity_clarity": "good|medium|poor",
        "context_gaps": ["specific gap 1", "gap 2"],
        "authority_signals": ["specific signal to add 1", "signal 2"]
    }},
    "recommendations": [
        {{
            "priority": "high|medium|low",
            "category": "seo|aeo|geo|conversion",
            "action": "VERY SPECIFIC action in Spanish with PRECISE language (compatible/recomendado, NOT soluciona/corrige)",
            "why_it_matters": "Explanation with CONSERVATIVE data/revenue impact (be realistic, not exaggerated)",
            "expected_impact": "Realistic % or $ estimate (e.g., '+10-20% tráfico', not '+340%')",
            "implementation": "Step-by-step in Spanish with verification steps",
            "auto_generate": true|false,
            "generated_content": "Actual HTML/text to copy if auto_generate is true - MUST use precise language and verified specs only",
            "ai_visibility_target": "true if this recommendation specifically addresses the AI visibility gap (closing the mention-rate delta with competitors named in the AI VISIBILITY section). false otherwise. Required when AI visibility overall <50."
        }}
    ],
    "priority_actions": ["Top 3 MOST IMPACTFUL specific actions"],
    "expected_impact": {{
        "traffic_increase": "X%",
        "conversion_increase": "Y%",
        "revenue_potential": "$Z/month",
        "timeline": "X weeks"
    }},
    "generated_content": {{
        "suggested_meta_title": "50-60 char title (Google truncates after ~60)",
        "suggested_meta_description": "150-160 char description",
        "faq_questions": ["¿Q1 from PAA?", "¿Q2 from PAA?", "¿Q3?", "¿Q4?", "¿Q5?"],
        "faq_source": "Use 'People Also Ask' from REAL SERP LANDSCAPE as primary FAQ source — these are actual user questions",
        "comparison_table_html": "<table>...</table> or null"
    }}
}}

CRITICAL GUIDELINES FOR ACCURACY AND PRECISION:

### 1. META TITLE LENGTH - STRICT 60 CHAR LIMIT
- Google truncates titles after ~60 characters
- ✅ GOOD: "Aceite ZF LifeguardFluid 8 ZF8HP | Example Store" (46 chars)
- ❌ BAD: "Aceite Transmisión ZF LifeguardFluid 8 1L para ZF8HP ZF9HP | Soluciona P0868 Nissan" (75+ chars)

### 2. LANGUAGE PRECISION - NO OVERPROMISING
- ✅ USE: "compatible con", "recomendado para", "ayuda a mantener", "especificación OEM"
- ❌ AVOID: "soluciona", "corrige", "elimina", "repara" (unless product specifically does this)
- Example: "Este aceite es compatible con sistemas que muestran error P0868" (NOT "Este aceite corrige P0868")

### 3. RAG CONTEXT VERIFICATION
- ONLY recommend specifications that can be verified from the product data provided above
- If unsure about a spec, DON'T include it in recommendations
- Vehicle compatibility ONLY from the product description HTML or vehicle fitments data provided — NEVER invent vehicles
- All OEM numbers, SKUs, and transmission codes MUST come from the product data above

### 4. REALISTIC IMPACT ESTIMATES
- Be conservative with revenue projections
- "+10-30% tráfico" is realistic, "+340% CTR" is likely exaggerated
- If the product has 0 sales or very few sessions (<10), mark all revenue estimates as "PROJECTION" and explain they are based on category benchmarks, not actual product data

### 5. SEARCH VOLUME DATA - NOT AVAILABLE
- You do NOT have access to keyword monthly search volume data (e.g. from SEMrush or Ahrefs)
- The GSC data above provides impressions, CTR, and position ONLY
- Do NOT estimate or invent monthly search volumes (e.g. "20-50 búsquedas/mes")
- Instead, reference GSC impressions as the traffic indicator: "31 impresiones en GSC" NOT "20-50 búsquedas/mes"

### 5b. KEYWORD OPPORTUNITIES - GROUND IN REAL DATA OR RETURN EMPTY
{keyword_opps_rule}

### 6. NEW PRODUCTS (PRIMARY ISSUE = NEW_PRODUCT)
- If the primary issue is NEW_PRODUCT, focus recommendations on content quality for INITIAL INDEXING
- Do NOT diagnose conversion or traffic problems — the product simply hasn't accumulated data yet
- Revenue estimates should be clearly marked as category-based projections
- Focus on actionable improvements, not hype

### 5. PRODUCT TYPE RELEVANCE
- For oil products: focus on fluid specs, viscosity, OEM compatibility
- For solenoids: focus on valve body, TCM, pressure
- NEVER mix component terms (e.g., don't mention "oil cooler" for an oil bottle product)

### 7. REAL SERP LANDSCAPE - HOW TO USE IT
- The "REAL SERP LANDSCAPE" section shows ACTUAL competitors ranking in Mexico for this product's keywords
- Use competitor titles and descriptions to understand what search intent signals Google rewards
- The "People Also Ask" questions are REAL user questions — use them as FAQ questions verbatim or adapted
- Do NOT invent FAQs when PAA questions are available — prefer real PAA questions
- If "featured_snippet" is detected, structure your content recommendation to target that snippet format (paragraph, table, or list)
- Related searches reveal keyword expansion opportunities — flag the most relevant ones in your keyword_opportunities

IMPORTANT: 
- Every recommendation must be SPECIFIC, ACTIONABLE, and FACTUALLY ACCURATE
- Include revenue estimates where possible (be conservative: "+10-30% tráfico" not "+340%")
- For [AUTO-GENERATE] items, provide actual content in generated_content field
- Think like a consultant: "Here's exactly what to do, why, and what to expect"
- QUALITY and TRUTH over aggressive optimization
"""


def parse_text_response(text: str) -> Dict:
    """Fallback parser for non-JSON responses."""
    return {
        "seo": {
            "score": 50,
            "critical_issues": ["Response parsing failed"],
            "improvements": ["Check API response format"],
            "keyword_opportunities": []
        },
        "aeo": {
            "score": 50,
            "snippet_opportunities": [],
            "question_targets": [],
            "structured_data_recommendations": []
        },
        "geo": {
            "score": 50,
            "entity_clarity": "medium",
            "context_gaps": [],
            "authority_signals": []
        },
        "recommendations": [
            {
                "priority": "high",
                "category": "seo",
                "action": "Revisar formato de respuesta de IA",
                "expected_impact": "Mejorar análisis automático",
                "implementation": "Contactar soporte técnico"
            }
        ],
        "priority_actions": ["Verificar conexión con Grok API"],
        "expected_impact": {
            "traffic_increase": "N/A",
            "conversion_increase": "N/A",
            "timeline": "N/A"
        }
    }

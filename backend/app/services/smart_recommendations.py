"""
Smart Recommendations Service
==============================

AI-powered recommendation system using multi-agent consensus for
intelligent product recommendations, SEO improvements, and content optimization.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from app.models.product import Product
from app.models.aeo_models import FaultCode
from app.services.llm_service import llm_service
from app.services.multi_agent import TaskRouter
from app.core.config import settings

logger = logging.getLogger("smart_recommendations")


# ============================================================================
# Pydantic Models for Type Safety
# ============================================================================

from pydantic import BaseModel, Field
from enum import Enum


class RecommendationCategory(str, Enum):
    SEO = "seo"
    AEO = "aeo"
    GEO = "geo"
    CONVERSION = "conversion"


class RecommendationPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationContext(BaseModel):
    fault_codes: List[str] = []
    transmission_codes: List[str] = []
    customer_segment: Optional[str] = None
    current_issues: List[str] = []


class RecommendationFilters(BaseModel):
    min_confidence: int = Field(default=60, ge=0, le=100)
    categories: List[RecommendationCategory] = [RecommendationCategory.SEO, RecommendationCategory.AEO, RecommendationCategory.GEO, RecommendationCategory.CONVERSION]
    max_results: int = Field(default=10, ge=1, le=50)
    sort_by: str = "impact"  # impact, confidence, effort


class AgentBreakdown(BaseModel):
    harper: Dict[str, Any] = {}
    benjamin: Dict[str, Any] = {}
    lucas: Dict[str, Any] = {}


class Recommendation(BaseModel):
    id: str
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    action: str
    expected_impact: str
    confidence: int
    auto_applicable: bool = False
    generated_content: Optional[str] = None
    implementation_steps: List[str] = []
    agent_breakdown: Optional[AgentBreakdown] = None


class SmartRecommendationsResponse(BaseModel):
    product_id: str
    product_title: str
    recommendations: List[Recommendation]
    total_opportunities: int
    estimated_impact: Dict[str, str]
    _multi_agent: Optional[Dict[str, Any]] = None


# ============================================================================
# Smart Recommendations Service
# ============================================================================

class SmartRecommendationsService:
    """
    AI-powered recommendation system using multi-agent consensus.
    
    Provides intelligent recommendations for:
    - SEO improvements (meta, content, keywords)
    - AEO optimization (FAQ, voice search, snippets)
    - GEO enhancement (AI visibility, citations)
    - Conversion optimization (CTAs, product placement)
    """

    def __init__(self, db: Session):
        self.db = db
        self.router = TaskRouter()

    async def get_product_recommendations(
        self,
        product_id: str,
        context: Optional[RecommendationContext] = None,
        filters: Optional[RecommendationFilters] = None,
        multi_agent: bool = False
    ) -> SmartRecommendationsResponse:
        """
        Generate smart product recommendations using multi-agent consensus.
        """
        filters = filters or RecommendationFilters()
        context = context or RecommendationContext()

        # Get product data
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Build analysis prompt
        prompt = self._build_recommendation_prompt(product, context, filters)
        system_prompt = self._get_recommendation_system_prompt()

        # Route to appropriate provider
        provider = self.router.route("recommendation_engine", multi_agent)

        try:
            # Get SEO score from AI cache if available
            seo_score = None
            if product.ai_analysis_cache:
                seo_score = product.ai_analysis_cache.seo_score

            response = await llm_service.generate_content(
                product_info={
                    "product_id": product_id,
                    "title": product.title,
                    "sku": product.sku,
                    "seo_score": seo_score,
                    "performance_score": product.performance_score,
                    "total_sold": product.total_sold,
                    "ga4_sessions": product.ga4_sessions,
                    "gsc_impressions": product.gsc_impressions,
                    "gsc_clicks": product.gsc_clicks,
                },
                context=[],
                system_prompt=system_prompt,
                provider=provider,
            )

            # Parse response
            recommendations = self._parse_recommendations(response, filters)
            
            # Calculate totals
            total_opportunities = len(recommendations)
            estimated_impact = self._calculate_impact(recommendations)

            # Build response
            result = SmartRecommendationsResponse(
                product_id=str(product_id),
                product_title=product.title or "",
                recommendations=recommendations,
                total_opportunities=total_opportunities,
                estimated_impact=estimated_impact,
                _multi_agent=response.get("_multi_agent") if isinstance(response, dict) else None
            )

            return result

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            # Return fallback recommendations
            return self._get_fallback_recommendations(product, filters)

    async def get_multi_product_recommendations(
        self,
        product_ids: List[str],
        filters: Optional[RecommendationFilters] = None,
        multi_agent: bool = False
    ) -> Dict[str, SmartRecommendationsResponse]:
        """
        Generate recommendations for multiple products in batch.
        """
        results = {}
        for product_id in product_ids:
            try:
                result = await self.get_product_recommendations(
                    product_id=product_id,
                    filters=filters,
                    multi_agent=multi_agent
                )
                results[product_id] = result
            except Exception as e:
                logger.error(f"Failed recommendations for {product_id}: {e}")
                results[product_id] = None
        
        return results

    def filter_recommendations(
        self,
        recommendations: List[Recommendation],
        filters: RecommendationFilters
    ) -> List[Recommendation]:
        """
        Apply intelligent filtering to recommendations.
        """
        filtered = []

        for rec in recommendations:
            # Filter by confidence
            if rec.confidence < filters.min_confidence:
                continue

            # Filter by category
            if rec.category not in filters.categories:
                continue

            filtered.append(rec)

        # Sort by specified criteria
        if filters.sort_by == "impact":
            priority_order = {"high": 0, "medium": 1, "low": 2}
            filtered.sort(key=lambda r: priority_order.get(r.priority.value, 3))
        elif filters.sort_by == "confidence":
            filtered.sort(key=lambda r: r.confidence, reverse=True)
        elif filters.sort_by == "effort":
            # Auto-applicable first (lower effort)
            filtered.sort(key=lambda r: not r.auto_applicable)

        return filtered[:filters.max_results]

    def _build_recommendation_prompt(
        self,
        product: Product,
        context: RecommendationContext,
        filters: RecommendationFilters
    ) -> str:
        """Build the prompt for recommendation generation with ALL data sources."""

        # Comprehensive product data from ALL sources
        product_data = {
            # === SHOPIFY DATA ===
            "id": str(product.id),
            "title": product.title,
            "sku": product.sku,
            "handle": product.handle,
            "price": float(product.price or 0),
            "product_type": product.product_type,
            "vendor": product.vendor,
            "description_length": product.description_length,
            "image_count": product.image_count,
            "inventory_quantity": product.inventory_quantity,
            "inventory_status": product.inventory_status,
            
            # === SALES DATA (Shopify Orders) ===
            "sold_30d": product.sold_30d or 0,
            "sold_90d": product.sold_90d or 0,
            "sold_365d": product.sold_365d or 0,
            "sold_all_time": product.sold_all_time or 0,
            "revenue_30d": float(product.revenue_30d or 0),
            "revenue_90d": float(product.revenue_90d or 0),
            "revenue_365d": float(product.revenue_365d or 0),
            "revenue_all_time": float(product.revenue_all_time or 0),
            
            # === GA4 ANALYTICS DATA ===
            "ga4_sessions": product.ga4_sessions or 0,
            "ga4_engagement_time": product.ga4_engagement_time or 0,
            "ga4_bounce_rate": product.ga4_bounce_rate or 0,
            "ga4_revenue": float(product.ga4_revenue or 0),
            
            # === SEARCH CONSOLE DATA ===
            "gsc_impressions": product.gsc_impressions or 0,
            "gsc_clicks": product.gsc_clicks or 0,
            "gsc_ctr": float(product.gsc_ctr or 0),
            "gsc_position": float(product.gsc_position or 0),
            
            # === SEO/AEO/GEO SCORES ===
            "performance_score": product.performance_score or 0,
            "opportunity_level": product.opportunity_level,
            
            # Get SEO score from AI cache if available
            "seo_score": getattr(product.ai_analysis_cache, 'seo_score', None) if product.ai_analysis_cache else None,
            
            # === TRANSMISSION-SPECIFIC ===
            "transmission_code": product.transmission_code,
            
            # === COMPUTED METRICS ===
            "conversion_rate": self._calculate_conversion_rate(product),
            "revenue_per_session": self._calculate_rps(product),
            "engagement_quality": self._calculate_engagement_quality(product),
        }

        # Calculate insights
        insights = self._calculate_insights(product)

        return f"""# SMART RECOMMENDATIONS TASK - MULTI-AGENT ANALYSIS

## Product Data (ALL DATA SOURCES)
```json
{json.dumps(product_data, indent=2, ensure_ascii=False)}
```

## AI-Computed Insights
```json
{json.dumps(insights, indent=2, ensure_ascii=False)}
```

## Context
- Fault Codes: {context.fault_codes or 'None specified'}
- Transmission Codes: {context.transmission_codes or 'None specified'}
- Customer Segment: {context.customer_segment or 'General'}
- Current Issues: {context.current_issues or 'None identified'}

## Filter Criteria
- Minimum Confidence: {filters.min_confidence}%
- Categories: {[c.value for c in filters.categories]}
- Max Results: {filters.max_results}
- Sort By: {filters.sort_by}

## Task - Multi-Agent Analysis
As a team of 4 specialized agents, analyze this product using ALL available data:

**Harper (Research Agent)**: 
- Analyze data accuracy and completeness
- Identify data gaps and anomalies
- Research market positioning

**Benjamin (Logic Agent)**:
- Calculate performance metrics vs benchmarks
- Identify root causes of underperformance
- Prioritize by ROI potential

**Lucas (Creative Agent)**:
- Optimize content for SEO/AEO/GEO
- Generate Mexican Spanish copy
- Create conversion-focused messaging

**Captain (Synthesis Agent)**:
- Merge all agent outputs
- Resolve conflicts
- Provide final consensus score

## Recommendation Categories
1. **SEO** - Search engine optimization improvements
2. **AEO** - Answer engine optimization (voice search, featured snippets)
3. **GEO** - Generative engine optimization (AI visibility)
4. **Conversion** - Conversion rate optimization

## Analysis Focus Areas
Based on the data, prioritize analysis on:
{self._get_priority_focus_areas(product)}

## Response Format
Return JSON with this structure:
{{
  "recommendations": [
    {{
      "id": "rec-001",
      "category": "seo",
      "priority": "high",
      "title": "Optimize Meta Title",
      "action": "Update meta title to include transmission code",
      "expected_impact": "15-20% increase in CTR",
      "confidence": 85,
      "auto_applicable": true,
      "generated_content": "Kit Reparacion 4L60E Chevrolet | Example Store",
      "implementation_steps": ["Copy generated content", "Update in Shopify meta title field"],
      "data_sources_used": ["shopify", "gsc"],
      "agent_breakdown": {{
        "harper": {{"verified": true, "notes": "Technical accuracy confirmed"}},
        "benjamin": {{"logical_valid": true, "score": 85}},
        "lucas": {{"style_score": 90, "suggestions": "Clear and actionable"}}
      }}
    }}
  ],
  "total_opportunities": 5,
  "estimated_impact": {{
    "traffic_increase": "25-35%",
    "conversion_increase": "10-15%",
    "revenue_increase": "$X-X/month",
    "timeline": "2-4 weeks"
  }},
  "data_quality_score": 85,
  "missing_data": ["ga4_events", "gsc_keywords"],
  "product_filter_suggestions": [
    {{
      "filter_type": "opportunity",
      "criteria": "high_revenue_low_seo",
      "count": 12,
      "potential_impact": "$15,000/month"
    }}
  ]
}}

Respond ONLY with valid JSON."""

    def _calculate_conversion_rate(self, product: Product) -> float:
        """Calculate conversion rate from GA4 data."""
        sessions = product.ga4_sessions or 0
        sold = product.sold_90d or 0
        if sessions > 0:
            return round((sold / sessions) * 100, 2)
        return 0.0

    def _calculate_rps(self, product: Product) -> float:
        """Calculate revenue per session."""
        sessions = product.ga4_sessions or 0
        revenue = product.revenue_90d or 0
        if sessions > 0:
            return round(float(revenue) / sessions, 2)
        return 0.0

    def _calculate_engagement_quality(self, product: Product) -> float:
        """Calculate engagement quality score (0-100)."""
        engagement = product.ga4_engagement_time or 0
        bounce = product.ga4_bounce_rate or 0
        # Higher engagement + lower bounce = better quality
        score = min(100, (engagement / 1000) * 20 + (100 - bounce))
        return round(score, 1)

    def _calculate_insights(self, product: Product) -> dict:
        """Calculate AI-driven insights from all data sources."""
        insights = {
            "performance_status": "unknown",
            "opportunity_type": [],
            "data_gaps": [],
            "benchmarks": {},
            "alerts": []
        }

        # Performance status
        score = product.performance_score or 0
        if score >= 80:
            insights["performance_status"] = "excellent"
        elif score >= 60:
            insights["performance_status"] = "good"
        elif score >= 40:
            insights["performance_status"] = "needs_improvement"
        else:
            insights["performance_status"] = "critical"

        # Opportunity types - use performance_score instead of seo_score
        if (product.revenue_90d or 0) > 10000 and (product.performance_score or 0) < 60:
            insights["opportunity_type"].append("high_revenue_low_seo")
        if (product.ga4_sessions or 0) > 500 and (product.ga4_bounce_rate or 0) > 70:
            insights["opportunity_type"].append("high_traffic_high_bounce")
        if (product.gsc_impressions or 0) > 1000 and (product.gsc_clicks or 0) < 10:
            insights["opportunity_type"].append("high_impressions_low_ctr")
        if (product.sold_90d or 0) == 0 and (product.inventory_quantity or 0) > 10:
            insights["opportunity_type"].append("stale_inventory")
        if (product.gsc_position or 0) < 20 and (product.gsc_clicks or 0) > 5:
            insights["opportunity_type"].append("page_2_opportunity")

        # Data gaps
        if not product.ga4_sessions:
            insights["data_gaps"].append("ga4_analytics")
        if not product.gsc_impressions:
            insights["data_gaps"].append("search_console")
        if not product.sold_90d:
            insights["data_gaps"].append("sales_data")

        # Alerts
        if (product.inventory_quantity or 0) < 5:
            insights["alerts"].append("low_inventory")
        if (product.ga4_bounce_rate or 0) > 80:
            insights["alerts"].append("high_bounce_rate")
        if (product.performance_score or 0) < 40:
            insights["alerts"].append("critical_performance_score")

        return insights

    def _get_priority_focus_areas(self, product: Product) -> str:
        """Get priority focus areas based on data analysis."""
        focus_areas = []

        # High traffic but low conversion
        if (product.ga4_sessions or 0) > 100 and self._calculate_conversion_rate(product) < 1:
            focus_areas.append("- HIGH PRIORITY: Traffic exists but conversion is low - focus on CRO")

        # Good impressions but low clicks (CTR issue)
        if (product.gsc_impressions or 0) > 500 and (product.gsc_ctr or 0) < 2:
            focus_areas.append("- HIGH PRIORITY: High impressions but low CTR - optimize titles/meta")

        # High revenue potential with poor performance score
        if (product.revenue_90d or 0) > 5000 and (product.performance_score or 0) < 60:
            focus_areas.append("- HIGH PRIORITY: Revenue driver with low performance - quick win opportunity")

        # Position 11-20 (page 2 opportunity)
        if 11 <= (product.gsc_position or 100) <= 20:
            focus_areas.append("- MEDIUM PRIORITY: Page 2 position - push to page 1 with optimization")

        # Stale inventory
        if (product.sold_90d or 0) == 0 and (product.inventory_quantity or 0) > 0:
            focus_areas.append("- MEDIUM PRIORITY: No recent sales - consider promotion or content refresh")

        if not focus_areas:
            focus_areas.append("- Analyze all categories equally for improvement opportunities")

        return "\n".join(focus_areas)

    def _get_recommendation_system_prompt(self) -> str:
        """System prompt for recommendation generation."""
        return """You are an expert SEO/AEO/GEO consultant for Example Store, a transmission parts e-commerce company.

Your role is to analyze products and provide actionable recommendations that:
1. Improve search visibility (SEO)
2. Optimize for answer engines and voice search (AEO)
3. Increase AI visibility and citations (GEO)
4. Boost conversion rates (Conversion)

Rules:
1. Be specific and actionable - avoid vague recommendations
2. Provide quantified expected impact when possible
3. Generate ready-to-use content for auto-applicable recommendations
4. Consider Mexican Spanish language nuances
5. Focus on high-impact, low-effort improvements first
6. Consider transmission-specific terminology and codes
7. Respond ONLY with valid JSON, no markdown formatting

Priority Guidelines:
- HIGH: Immediate revenue impact, quick fixes, critical SEO issues
- MEDIUM: Important but not urgent, moderate effort required
- LOW: Nice to have, requires significant effort or resources"""

    def _parse_recommendations(
        self,
        response: Dict,
        filters: RecommendationFilters
    ) -> List[Recommendation]:
        """Parse AI response into Recommendation objects."""
        recommendations = []

        try:
            # Handle different response formats
            if isinstance(response, dict):
                content = response.get("content", response)
                if isinstance(content, str):
                    # Try to parse JSON
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
                        # Find JSON in content
                        start = content.find("{")
                        end = content.rfind("}") + 1
                        if start >= 0 and end > start:
                            content = json.loads(content[start:end])
                        else:
                            return self._get_default_recommendations()
                
                recs_data = content.get("recommendations", [])
            else:
                return self._get_default_recommendations()

            for i, rec_data in enumerate(recs_data):
                try:
                    rec = Recommendation(
                        id=rec_data.get("id", f"rec-{i+1:03d}"),
                        category=RecommendationCategory(rec_data.get("category", "seo")),
                        priority=RecommendationPriority(rec_data.get("priority", "medium")),
                        title=rec_data.get("title", "Untitled Recommendation"),
                        action=rec_data.get("action", ""),
                        expected_impact=rec_data.get("expected_impact", "Unknown"),
                        confidence=int(rec_data.get("confidence", 70)),
                        auto_applicable=rec_data.get("auto_applicable", False),
                        generated_content=rec_data.get("generated_content"),
                        implementation_steps=rec_data.get("implementation_steps", []),
                        agent_breakdown=AgentBreakdown(**rec_data.get("agent_breakdown", {})) if rec_data.get("agent_breakdown") else None
                    )
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse recommendation: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse recommendations response: {e}")
            return self._get_default_recommendations()

        return self.filter_recommendations(recommendations, filters)

    def _calculate_impact(self, recommendations: List[Recommendation]) -> Dict[str, str]:
        """Calculate overall estimated impact."""
        high_priority_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.HIGH)
        avg_confidence = sum(r.confidence for r in recommendations) / len(recommendations) if recommendations else 0

        traffic_increase = f"{10 + high_priority_count * 5}-{20 + high_priority_count * 10}%"
        conversion_increase = f"{5 + high_priority_count * 2}-{10 + high_priority_count * 5}%"
        timeline = "2-4 weeks" if high_priority_count > 2 else "1-2 weeks"

        return {
            "traffic_increase": traffic_increase,
            "conversion_increase": conversion_increase,
            "timeline": timeline,
            "confidence_level": f"{avg_confidence:.0f}%"
        }

    def _get_default_recommendations(self) -> List[Recommendation]:
        """Get default recommendations when parsing fails."""
        return [
            Recommendation(
                id="rec-default-001",
                category=RecommendationCategory.SEO,
                priority=RecommendationPriority.HIGH,
                title="Review Product Content",
                action="Analyze product description for SEO improvements",
                expected_impact="10-15% visibility improvement",
                confidence=70,
                auto_applicable=False,
                implementation_steps=["Run AI analysis", "Review suggestions", "Apply changes"]
            )
        ]

    def _get_fallback_recommendations(
        self,
        product: Product,
        filters: RecommendationFilters
    ) -> SmartRecommendationsResponse:
        """Return fallback recommendations when AI fails."""
        recommendations = []

        # Basic SEO recommendation based on performance score
        if product.performance_score and product.performance_score < 80:
            recommendations.append(Recommendation(
                id="rec-seo-001",
                category=RecommendationCategory.SEO,
                priority=RecommendationPriority.HIGH,
                title="Improve Performance Score",
                action="Optimize meta title, description, and content keywords",
                expected_impact="15-25% traffic increase",
                confidence=75,
                auto_applicable=False
            ))

        # AEO recommendation based on description
        if product.description_length and product.description_length < 500:
            recommendations.append(Recommendation(
                id="rec-aeo-001",
                category=RecommendationCategory.AEO,
                priority=RecommendationPriority.MEDIUM,
                title="Expand Content for Voice Search",
                action="Add FAQ section and detailed technical information",
                expected_impact="Better voice search visibility",
                confidence=65,
                auto_applicable=False
            ))

        # Conversion recommendation based on sales
        if product.total_sold and product.total_sold < 10:
            recommendations.append(Recommendation(
                id="rec-conv-001",
                category=RecommendationCategory.CONVERSION,
                priority=RecommendationPriority.HIGH,
                title="Improve Conversion Elements",
                action="Add trust signals, guarantees, and clear CTAs",
                expected_impact="5-10% conversion increase",
                confidence=70,
                auto_applicable=True,
                generated_content="Garantia de 1 ano - Envio express 1-2 dias"
            ))

        return SmartRecommendationsResponse(
            product_id=str(product.id),
            product_title=product.title or "",
            recommendations=self.filter_recommendations(recommendations, filters),
            total_opportunities=len(recommendations),
            estimated_impact={
                "traffic_increase": "10-20%",
                "conversion_increase": "5-10%",
                "timeline": "2-3 weeks"
            },
            _multi_agent=None
        )


# ============================================================================
# Factory Function
# ============================================================================

def get_smart_recommendations_service(db: Session) -> SmartRecommendationsService:
    """Get SmartRecommendationsService instance."""
    return SmartRecommendationsService(db)

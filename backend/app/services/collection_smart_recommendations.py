"""
Collection Smart Recommendations Service
==========================================

AI-powered recommendation system for Shopify collections using
multi-agent consensus. Mirrors SmartRecommendationsService pattern
but adapted for collection-level optimization.

Key difference: All recommendations are cannibalization-aware.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.collection_optimizer_models import CollectionOptimizer, CollectionSearchQuery
from app.services.llm_service import llm_service
from app.services.multi_agent import TaskRouter
from app.services.collection_cannibalization_guard import (
    CollectionCannibalizationGuard, CannibalizationCheckResult
)
from app.core.config import settings

# Reuse product recommendation models (same structure)
from app.services.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationFilters,
    Recommendation,
    AgentBreakdown,
)
from pydantic import BaseModel, Field

logger = logging.getLogger("collection_smart_recommendations")


# ============================================================================
# Collection-Specific Response Model
# ============================================================================

class CollectionRecommendationsResponse(BaseModel):
    collection_id: int
    collection_title: str
    recommendations: List[Recommendation]
    total_opportunities: int
    estimated_impact: Dict[str, str]
    cannibalization_status: str = "unknown"
    cannibalization_risk_score: float = 0.0
    safe_keyword_count: int = 0
    blocked_keyword_count: int = 0
    _multi_agent: Optional[Dict[str, Any]] = None


# ============================================================================
# Collection Smart Recommendations Service
# ============================================================================

class CollectionSmartRecommendationsService:
    """
    AI-powered recommendation system for collections.

    Provides cannibalization-aware recommendations for:
    - SEO: Meta titles, descriptions, internal linking
    - AEO: FAQ optimization, PAA targeting, schema markup
    - GEO: AI visibility, entity clarity, structured data
    - Conversion: CRO, product merchandising, CTAs
    """

    def __init__(self, db: Session):
        self.db = db
        self.router = TaskRouter()
        self.cannibal_guard = CollectionCannibalizationGuard(db)

    async def get_collection_recommendations(
        self,
        collection_id: int,
        filters: Optional[RecommendationFilters] = None,
        multi_agent: bool = False
    ) -> CollectionRecommendationsResponse:
        """Generate smart recommendations for a collection."""
        filters = filters or RecommendationFilters()

        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        # Run cannibalization check first
        cannibal_result = await self.cannibal_guard.check_collection(collection_id)

        # Get search queries
        top_queries = self.db.query(CollectionSearchQuery).filter(
            CollectionSearchQuery.collection_id == collection_id
        ).order_by(CollectionSearchQuery.priority_score.desc()).limit(20).all()

        # Build prompt with all data sources
        prompt = self._build_collection_recommendation_prompt(
            collection, top_queries, cannibal_result, filters
        )
        system_prompt = self._get_collection_system_prompt()

        # Route to appropriate provider
        provider = self.router.route("collection_recommendation_engine", multi_agent)

        try:
            response = await llm_service.generate_content(
                product_info={
                    "collection_id": collection_id,
                    "title": collection.collection_title,
                    "category": collection.category,
                    "impressions": collection.current_impressions,
                    "clicks": collection.current_clicks,
                    "ga4_sessions": collection.ga4_sessions,
                    "ga4_revenue": collection.ga4_revenue,
                    "dataforseo_volume": collection.dataforseo_volume,
                },
                context=[],
                system_prompt=system_prompt,
                provider=provider,
            )

            recommendations = self._parse_recommendations(response, filters)
            total_opportunities = len(recommendations)
            estimated_impact = self._calculate_impact(recommendations)

            return CollectionRecommendationsResponse(
                collection_id=collection_id,
                collection_title=collection.collection_title or "",
                recommendations=recommendations,
                total_opportunities=total_opportunities,
                estimated_impact=estimated_impact,
                cannibalization_status=cannibal_result.status,
                cannibalization_risk_score=cannibal_result.risk_score,
                safe_keyword_count=len(cannibal_result.safe_keywords),
                blocked_keyword_count=len(cannibal_result.blocked_keywords),
                _multi_agent=response.get("_multi_agent") if isinstance(response, dict) else None
            )

        except Exception as e:
            logger.error(f"Failed to generate collection recommendations: {e}")
            return self._get_fallback_recommendations(collection, cannibal_result, filters)

    async def get_batch_recommendations(
        self,
        collection_ids: List[int],
        filters: Optional[RecommendationFilters] = None,
        multi_agent: bool = False
    ) -> Dict[int, CollectionRecommendationsResponse]:
        """Generate recommendations for multiple collections."""
        results = {}
        for cid in collection_ids:
            try:
                results[cid] = await self.get_collection_recommendations(
                    collection_id=cid,
                    filters=filters,
                    multi_agent=multi_agent
                )
            except Exception as e:
                logger.error(f"Failed recommendations for collection {cid}: {e}")
        return results

    async def discover_opportunities(
        self,
        limit: int = 20
    ) -> List[Dict]:
        """
        Find collections with the highest safe optimization potential.
        Cross-references cannibalization to only surface safe opportunities.
        """
        collections = self.db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status.in_(['pending', 'analyzed'])
        ).order_by(
            desc(CollectionOptimizer.dataforseo_volume)
        ).limit(limit * 2).all()  # Fetch extra to filter

        opportunities = []
        for c in collections:
            # Quick cannibalization assessment
            cannibal = await self.cannibal_guard.check_collection(c.id)

            if cannibal.status == "blocked":
                continue  # Skip fully blocked collections

            # Calculate opportunity score — revenue-driven, multi-source
            volume = c.dataforseo_volume or 0
            impressions = c.current_impressions or 0
            sessions = c.ga4_sessions or 0
            revenue = float(c.shopify_attributed_revenue or 0)
            conversions = c.ga4_conversions or 0
            has_content = bool(c.generated_content)
            risk = cannibal.risk_score

            # Revenue-first scoring: Shopify revenue > GA4 conversions > Volume > Impressions
            opp_score = (
                revenue * 0.35 +
                conversions * 50 * 0.25 +
                volume * 0.2 +
                impressions * 0.1 +
                sessions * 0.1
            ) * ((100 - risk) / 100)
            if not has_content:
                opp_score *= 1.5  # Bonus for no existing content

            opportunities.append({
                "collection_id": c.id,
                "collection_title": c.collection_title,
                "category": c.category,
                "handle": c.collection_handle,
                # All 4 data sources
                "dataforseo_volume": volume,
                "impressions": impressions,
                "ga4_sessions": sessions,
                "ga4_conversions": conversions,
                "ga4_conversion_rate": float(c.ga4_conversion_rate or 0),
                "ga4_bounce_rate": float(c.ga4_bounce_rate or 0),
                "shopify_revenue": revenue,
                "shopify_orders": c.shopify_attributed_orders or 0,
                "shopify_llm_revenue": float(c.shopify_llm_revenue or 0),
                "position": float(c.current_position or 0),
                "ctr": float(c.current_ctr or 0),
                "has_content": has_content,
                "cannibalization_status": cannibal.status,
                "risk_score": cannibal.risk_score,
                "safe_keywords": len(cannibal.safe_keywords),
                "blocked_keywords": len(cannibal.blocked_keywords),
                "opportunity_score": round(opp_score, 1),
                # Data freshness
                "last_gsc_sync": c.last_analytics_sync.isoformat() if c.last_analytics_sync else None,
                "last_ga4_sync": c.last_ga4_sync.isoformat() if c.last_ga4_sync else None,
                "last_shopify_sync": c.last_shopify_sync.isoformat() if c.last_shopify_sync else None,
                "last_dataforseo_sync": c.dataforseo_last_sync.isoformat() if c.dataforseo_last_sync else None,
            })

        # Sort by opportunity score and limit
        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities[:limit]

    # ========================================================================
    # Prompt Building
    # ========================================================================

    def _build_collection_recommendation_prompt(
        self,
        collection: CollectionOptimizer,
        queries: List[CollectionSearchQuery],
        cannibal: CannibalizationCheckResult,
        filters: RecommendationFilters
    ) -> str:
        """Build comprehensive prompt with all 4 data sources + cannibalization context."""

        # Collection data from all sources
        collection_data = {
            # Shopify
            "title": collection.collection_title,
            "handle": collection.collection_handle,
            "url": collection.collection_url,
            "category": collection.category,
            "has_content": bool(collection.generated_content),
            "has_faq": bool(collection.generated_faq),
            "has_schema": bool(collection.generated_schema),

            # GSC
            "gsc_impressions": collection.current_impressions or 0,
            "gsc_clicks": collection.current_clicks or 0,
            "gsc_ctr": float(collection.current_ctr or 0),
            "gsc_position": float(collection.current_position or 0),

            # GA4
            "ga4_sessions": collection.ga4_sessions or 0,
            "ga4_bounce_rate": float(collection.ga4_bounce_rate or 0),
            "ga4_engagement_time": float(collection.ga4_avg_engagement_time or 0),
            "ga4_conversions": collection.ga4_conversions or 0,
            "ga4_conversion_rate": float(collection.ga4_conversion_rate or 0),
            "ga4_revenue": float(collection.ga4_revenue or 0),
            "ga4_ai_referral_sessions": collection.ga4_ai_referral_sessions or 0,

            # Shopify Attribution
            "shopify_revenue": float(collection.shopify_attributed_revenue or 0),
            "shopify_orders": collection.shopify_attributed_orders or 0,
            "shopify_llm_revenue": float(collection.shopify_llm_revenue or 0),
            "shopify_llm_orders": collection.shopify_llm_orders or 0,

            # DataForSEO
            "primary_keyword": collection.dataforseo_primary_keyword,
            "monthly_volume": collection.dataforseo_volume or 0,
            "competition": collection.dataforseo_competition,
            "cpc": float(collection.dataforseo_cpc or 0),
            "top_competitor": collection.dataforseo_top_competitor,
            "serp_features": collection.dataforseo_serp_features or [],
        }

        # Top queries with classification
        query_data = []
        for q in queries[:15]:
            query_data.append({
                "query": q.query,
                "clicks": q.clicks,
                "impressions": q.impressions,
                "ctr": float(q.ctr or 0),
                "position": float(q.position or 0),
                "type": q.query_type,
                "intent": q.intent,
                "priority": float(q.priority_score or 0)
            })

        # Cannibalization summary
        cannibal_summary = {
            "status": cannibal.status,
            "risk_score": cannibal.risk_score,
            "safe_keywords": [k.keyword for k in cannibal.safe_keywords[:10]],
            "blocked_keywords": [k.keyword for k in cannibal.blocked_keywords],
            "warning_keywords": [k.keyword for k in cannibal.warning_keywords],
        }

        # Insights
        insights = self._calculate_collection_insights(collection)

        # PAA questions
        paa = collection.dataforseo_people_also_ask or []
        paa_questions = [p.get('question', '') for p in paa[:5] if p.get('question')]

        return f"""# COLLECTION SMART RECOMMENDATIONS - MULTI-AGENT ANALYSIS

## Collection Data (ALL DATA SOURCES)
```json
{json.dumps(collection_data, indent=2, ensure_ascii=False)}
```

## Top Search Queries (GSC)
```json
{json.dumps(query_data, indent=2, ensure_ascii=False)}
```

## Cannibalization Analysis
```json
{json.dumps(cannibal_summary, indent=2, ensure_ascii=False)}
```

## AI-Computed Insights
```json
{json.dumps(insights, indent=2, ensure_ascii=False)}
```

## People Also Ask (DataForSEO)
{chr(10).join([f"- {q}" for q in paa_questions]) if paa_questions else "- No PAA data available"}

## Analysis Focus Areas
{self._get_priority_focus_areas(collection, cannibal)}

## CRITICAL RULE: CANNIBALIZATION AWARENESS
- Keywords marked as BLOCKED must NOT be recommended for collection content
- Keywords marked as WARNING should only be recommended with TRANSACTIONAL framing
- Recommendations should focus on SAFE keywords and transactional intent
- If a blog already ranks for an informational keyword, recommend linking FROM that blog TO this collection instead

## Task - Multi-Agent Analysis
As a team of 4 specialized agents, analyze this COLLECTION:

**Harper (Research)**: Verify data accuracy, identify market gaps, check competitor positioning
**Benjamin (Logic)**: Calculate ROI of each recommendation, identify root causes, prioritize by impact
**Lucas (Creative)**: Generate Spanish copy for titles/descriptions, optimize for Mexican market
**Captain (Synthesis)**: Merge outputs, resolve conflicts, provide consensus score

## Recommendation Categories
1. **SEO** - Meta optimization, internal linking, keyword targeting (SAFE keywords only)
2. **AEO** - FAQ optimization, PAA targeting, schema markup, featured snippets
3. **GEO** - AI visibility, llms.txt optimization, entity structure
4. **Conversion** - CRO, product merchandising, trust signals, CTAs

## Filter Criteria
- Min Confidence: {filters.min_confidence}%
- Categories: {[c.value for c in filters.categories]}
- Max Results: {filters.max_results}

## Response Format
Return JSON:
{{
  "recommendations": [
    {{
      "id": "col-rec-001",
      "category": "seo",
      "priority": "high",
      "title": "Optimizar meta title de la colección",
      "action": "Actualizar meta title con keyword transaccional principal",
      "expected_impact": "15-25% aumento en CTR",
      "confidence": 85,
      "auto_applicable": true,
      "generated_content": "Comprar Convertidores de Torque | Example Store Mexico",
      "implementation_steps": ["Copiar título generado", "Actualizar en Shopify"],
      "agent_breakdown": {{
        "harper": {{"verified": true}},
        "benjamin": {{"score": 85}},
        "lucas": {{"style_score": 90}}
      }}
    }}
  ],
  "total_opportunities": 5,
  "estimated_impact": {{
    "traffic_increase": "20-30%",
    "conversion_increase": "10-15%",
    "revenue_increase": "$X/mes",
    "timeline": "2-4 semanas"
  }}
}}

Respond ONLY with valid JSON."""

    def _calculate_collection_insights(self, collection: CollectionOptimizer) -> dict:
        """Calculate AI-driven insights for a collection."""
        insights = {
            "performance_status": "unknown",
            "opportunity_types": [],
            "data_gaps": [],
            "alerts": []
        }

        # Performance based on available data
        impressions = collection.current_impressions or 0
        clicks = collection.current_clicks or 0
        sessions = collection.ga4_sessions or 0
        conversions = collection.ga4_conversions or 0
        revenue = float(collection.ga4_revenue or 0)
        volume = collection.dataforseo_volume or 0

        if revenue > 10000 or (sessions > 500 and conversions > 10):
            insights["performance_status"] = "excellent"
        elif revenue > 2000 or sessions > 200:
            insights["performance_status"] = "good"
        elif sessions > 50 or impressions > 500:
            insights["performance_status"] = "needs_improvement"
        else:
            insights["performance_status"] = "critical"

        # Opportunity types
        if impressions > 1000 and (collection.current_ctr or 0) < 0.02:
            insights["opportunity_types"].append("high_impressions_low_ctr")
        if sessions > 100 and (collection.ga4_conversion_rate or 0) < 1.0:
            insights["opportunity_types"].append("high_traffic_low_conversion")
        if volume > 500 and not collection.generated_content:
            insights["opportunity_types"].append("high_volume_no_content")
        if 11 <= (collection.current_position or 100) <= 20:
            insights["opportunity_types"].append("page_2_opportunity")
        if (collection.ga4_ai_referral_sessions or 0) == 0 and sessions > 50:
            insights["opportunity_types"].append("no_ai_referrals")
        if (collection.ga4_bounce_rate or 0) > 70:
            insights["opportunity_types"].append("high_bounce_rate")

        # Data gaps
        if not collection.ga4_sessions:
            insights["data_gaps"].append("ga4_analytics")
        if not collection.current_impressions:
            insights["data_gaps"].append("search_console")
        if not collection.dataforseo_volume:
            insights["data_gaps"].append("dataforseo")
        if not collection.shopify_attributed_revenue:
            insights["data_gaps"].append("shopify_attribution")

        # Alerts
        if (collection.ga4_bounce_rate or 0) > 80:
            insights["alerts"].append("critical_bounce_rate")
        if not collection.generated_content and volume > 1000:
            insights["alerts"].append("missing_content_high_volume")
        if not collection.generated_schema:
            insights["alerts"].append("missing_schema_markup")

        return insights

    def _get_priority_focus_areas(
        self, collection: CollectionOptimizer, cannibal: CannibalizationCheckResult
    ) -> str:
        """Get priority focus areas based on data + cannibalization analysis."""
        areas = []

        impressions = collection.current_impressions or 0
        ctr = collection.current_ctr or 0
        sessions = collection.ga4_sessions or 0
        conv_rate = collection.ga4_conversion_rate or 0
        volume = collection.dataforseo_volume or 0
        position = collection.current_position or 100

        if impressions > 500 and ctr < 0.02:
            areas.append("- HIGH: High impressions but low CTR — optimize meta title/description")
        if sessions > 100 and conv_rate < 1.0:
            areas.append("- HIGH: Traffic exists but conversions low — focus on CRO and product merchandising")
        if volume > 500 and not collection.generated_content:
            areas.append("- HIGH: High search volume but no content — generate collection content (transactional)")
        if 11 <= position <= 20:
            areas.append("- MEDIUM: Page 2 position — targeted optimization can push to page 1")
        if cannibal.blocked_keywords:
            areas.append(f"- MEDIUM: {len(cannibal.blocked_keywords)} keywords blocked by cannibalization — recommend internal linking strategy")
        if not collection.generated_schema:
            areas.append("- MEDIUM: Missing FAQ schema markup — add for rich snippet eligibility")
        if (collection.ga4_ai_referral_sessions or 0) == 0:
            areas.append("- LOW: No AI referral traffic — improve GEO signals for LLM visibility")

        if not areas:
            areas.append("- Analyze all categories equally for improvement opportunities")

        return "\n".join(areas)

    def _get_collection_system_prompt(self) -> str:
        """System prompt for collection recommendation generation."""
        return """You are an expert SEO/AEO/GEO consultant for Example Store, a transmission parts e-commerce store in Mexico (5,000+ SKUs).

Your role is to analyze COLLECTIONS (category pages) and provide actionable recommendations that:
1. Improve search visibility (SEO) — targeting TRANSACTIONAL keywords only
2. Optimize for answer engines (AEO) — FAQ schema, PAA targeting, voice search
3. Increase AI visibility (GEO) — structured data, entity clarity for LLMs
4. Boost conversion rates (Conversion) — CRO, product merchandising, trust signals

CRITICAL RULES:
1. NEVER recommend targeting informational keywords that blog articles already rank for
2. Focus on TRANSACTIONAL intent: "comprar", "precio", "kit de", "envío"
3. If a blog ranks for an informational keyword, recommend linking FROM blog TO collection
4. Provide specific, actionable recommendations with Mexican Spanish copy
5. Quantify expected impact when possible
6. Respond ONLY with valid JSON, no markdown formatting

Priority Guidelines:
- HIGH: Immediate revenue impact, quick fixes, critical gaps
- MEDIUM: Important but not urgent, moderate effort
- LOW: Nice to have, requires significant resources"""

    # ========================================================================
    # Response Parsing (reuses product pattern)
    # ========================================================================

    def _parse_recommendations(
        self, response: Dict, filters: RecommendationFilters
    ) -> List[Recommendation]:
        """Parse AI response into Recommendation objects."""
        recommendations = []

        try:
            if isinstance(response, dict):
                content = response.get("content", response)
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
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
                        id=rec_data.get("id", f"col-rec-{i+1:03d}"),
                        category=RecommendationCategory(rec_data.get("category", "seo")),
                        priority=RecommendationPriority(rec_data.get("priority", "medium")),
                        title=rec_data.get("title", ""),
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
                    logger.warning(f"Failed to parse collection recommendation: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse collection recommendations: {e}")
            return self._get_default_recommendations()

        return self._filter_recommendations(recommendations, filters)

    def _filter_recommendations(
        self, recommendations: List[Recommendation], filters: RecommendationFilters
    ) -> List[Recommendation]:
        """Apply filtering and sorting."""
        filtered = []
        for rec in recommendations:
            if rec.confidence < filters.min_confidence:
                continue
            if rec.category not in filters.categories:
                continue
            filtered.append(rec)

        if filters.sort_by == "impact":
            priority_order = {"high": 0, "medium": 1, "low": 2}
            filtered.sort(key=lambda r: priority_order.get(r.priority.value, 3))
        elif filters.sort_by == "confidence":
            filtered.sort(key=lambda r: r.confidence, reverse=True)
        elif filters.sort_by == "effort":
            filtered.sort(key=lambda r: not r.auto_applicable)

        return filtered[:filters.max_results]

    def _calculate_impact(self, recommendations: List[Recommendation]) -> Dict[str, str]:
        """Calculate overall estimated impact."""
        high_count = sum(1 for r in recommendations if r.priority == RecommendationPriority.HIGH)
        avg_conf = sum(r.confidence for r in recommendations) / len(recommendations) if recommendations else 0

        return {
            "traffic_increase": f"{10 + high_count * 5}-{20 + high_count * 10}%",
            "conversion_increase": f"{5 + high_count * 3}-{10 + high_count * 5}%",
            "timeline": "2-4 semanas" if high_count > 2 else "1-2 semanas",
            "confidence_level": f"{avg_conf:.0f}%"
        }

    def _get_default_recommendations(self) -> List[Recommendation]:
        """Default recommendations when parsing fails."""
        return [
            Recommendation(
                id="col-rec-default-001",
                category=RecommendationCategory.SEO,
                priority=RecommendationPriority.HIGH,
                title="Revisar contenido de la colección",
                action="Analizar la colección para mejoras de SEO transaccional",
                expected_impact="10-15% mejora en visibilidad",
                confidence=70,
                auto_applicable=False,
                implementation_steps=["Ejecutar análisis AI", "Revisar sugerencias", "Aplicar cambios"]
            )
        ]

    def _get_fallback_recommendations(
        self,
        collection: CollectionOptimizer,
        cannibal: CannibalizationCheckResult,
        filters: RecommendationFilters
    ) -> CollectionRecommendationsResponse:
        """Return fallback recommendations when AI fails."""
        recommendations = []

        if not collection.generated_content:
            recommendations.append(Recommendation(
                id="col-rec-seo-001",
                category=RecommendationCategory.SEO,
                priority=RecommendationPriority.HIGH,
                title="Generar contenido transaccional para la colección",
                action="Crear contenido optimizado enfocado en intención de compra",
                expected_impact="15-25% aumento en tráfico orgánico",
                confidence=80,
                auto_applicable=False,
                implementation_steps=["Ejecutar generación de contenido", "Revisar draft", "Desplegar a Shopify"]
            ))

        if not collection.generated_schema:
            recommendations.append(Recommendation(
                id="col-rec-aeo-001",
                category=RecommendationCategory.AEO,
                priority=RecommendationPriority.MEDIUM,
                title="Agregar FAQ Schema a la colección",
                action="Generar preguntas frecuentes con schema JSON-LD",
                expected_impact="Elegibilidad para rich snippets en Google",
                confidence=75,
                auto_applicable=False,
                implementation_steps=["Generar FAQ", "Validar schema", "Desplegar a Shopify"]
            ))

        if cannibal.blocked_keywords:
            recommendations.append(Recommendation(
                id="col-rec-seo-002",
                category=RecommendationCategory.SEO,
                priority=RecommendationPriority.HIGH,
                title="Resolver canibalización de keywords",
                action=f"Crear links internos desde {len(cannibal.blocked_keywords)} blogs que compiten por las mismas keywords",
                expected_impact="Eliminar competencia interna, consolidar autoridad",
                confidence=85,
                auto_applicable=False,
                implementation_steps=[
                    "Identificar artículos de blog que compiten",
                    "Agregar links internos blog → colección",
                    "Asegurar que blog mantiene intención informacional"
                ]
            ))

        if (collection.ga4_ai_referral_sessions or 0) == 0:
            recommendations.append(Recommendation(
                id="col-rec-geo-001",
                category=RecommendationCategory.GEO,
                priority=RecommendationPriority.MEDIUM,
                title="Mejorar visibilidad en AI/LLMs",
                action="Agregar datos estructurados y mejorar claridad de entidades para LLMs",
                expected_impact="Aparecer en respuestas de ChatGPT, Gemini, Perplexity",
                confidence=65,
                auto_applicable=False,
                implementation_steps=["Agregar schema completo", "Optimizar llms.txt", "Mejorar estructura de contenido"]
            ))

        return CollectionRecommendationsResponse(
            collection_id=collection.id,
            collection_title=collection.collection_title or "",
            recommendations=self._filter_recommendations(recommendations, filters),
            total_opportunities=len(recommendations),
            estimated_impact={
                "traffic_increase": "10-20%",
                "conversion_increase": "5-10%",
                "timeline": "2-4 semanas"
            },
            cannibalization_status=cannibal.status,
            cannibalization_risk_score=cannibal.risk_score,
            safe_keyword_count=len(cannibal.safe_keywords),
            blocked_keyword_count=len(cannibal.blocked_keywords)
        )


# ============================================================================
# Factory
# ============================================================================

def get_collection_smart_recommendations_service(db: Session) -> CollectionSmartRecommendationsService:
    return CollectionSmartRecommendationsService(db)

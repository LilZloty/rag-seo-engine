"""
Collection Intelligence Service
=================================

Generates intelligence reports for collections:
- Content gap analysis
- Revenue opportunity scoring
- AI visibility gaps
- Cross-collection keyword conflicts
- Store-wide collection health
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc

from app.models.collection_optimizer_models import CollectionOptimizer, CollectionSearchQuery
from app.models.collection_intelligence_models import (
    CollectionAnalyticsSnapshot, CollectionCannibalizationResult
)
from app.models.seo_intelligence import KeywordPageMapping, SEOAlert
from app.services.collection_cannibalization_guard import CollectionCannibalizationGuard

logger = logging.getLogger("collection_intelligence")


class CollectionIntelligenceService:
    """
    Generates intelligence reports for individual collections and
    store-wide collection health assessments.
    """

    def __init__(self, db: Session):
        self.db = db
        self.cannibal_guard = CollectionCannibalizationGuard(db)

    async def generate_collection_report(self, collection_id: int) -> Dict:
        """
        Generate comprehensive intelligence report for a single collection.

        Includes: content gaps, revenue opportunities, AI visibility,
        cannibalization risks, and trend analysis.
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        # Get queries
        queries = self.db.query(CollectionSearchQuery).filter(
            CollectionSearchQuery.collection_id == collection_id
        ).order_by(CollectionSearchQuery.priority_score.desc()).all()

        # Get latest cannibalization result
        cannibal_result = self.db.query(CollectionCannibalizationResult).filter(
            CollectionCannibalizationResult.collection_id == collection_id
        ).order_by(CollectionCannibalizationResult.analyzed_at.desc()).first()

        # Get snapshots for trend analysis
        cutoff = datetime.utcnow() - timedelta(days=30)
        snapshots = self.db.query(CollectionAnalyticsSnapshot).filter(
            CollectionAnalyticsSnapshot.collection_id == collection_id,
            CollectionAnalyticsSnapshot.snapshot_date >= cutoff
        ).order_by(CollectionAnalyticsSnapshot.snapshot_date.asc()).all()

        # Build report sections
        report = {
            "collection_id": collection_id,
            "collection_title": collection.collection_title,
            "category": collection.category,
            "generated_at": datetime.utcnow().isoformat(),

            "status_summary": self._build_status_summary(collection),
            "content_gaps": self._find_content_gaps(collection, queries),
            "revenue_opportunities": self._find_revenue_opportunities(collection),
            "ai_visibility": self._analyze_ai_visibility(collection),
            "cannibalization": self._summarize_cannibalization(cannibal_result),
            "keyword_analysis": self._analyze_keywords(queries),
            "trend_analysis": self._analyze_trends(snapshots),
            "critical_issues": self._find_critical_issues(collection, cannibal_result),
            "quick_wins": self._find_quick_wins(collection, queries),
        }

        return report

    async def get_store_collection_health(self) -> Dict:
        """
        Aggregate health metrics across all collections.
        """
        collections = self.db.query(CollectionOptimizer).all()
        total = len(collections)

        if total == 0:
            return {"total_collections": 0, "message": "No collections found"}

        # Status breakdown
        statuses = {}
        for c in collections:
            status = c.optimization_status or "pending"
            statuses[status] = statuses.get(status, 0) + 1

        # Content metrics
        with_content = sum(1 for c in collections if c.generated_content)
        with_faq = sum(1 for c in collections if c.generated_faq)
        with_schema = sum(1 for c in collections if c.generated_schema)

        # Performance metrics
        total_impressions = sum(c.current_impressions or 0 for c in collections)
        total_clicks = sum(c.current_clicks or 0 for c in collections)
        total_sessions = sum(c.ga4_sessions or 0 for c in collections)
        total_revenue = sum(float(c.shopify_attributed_revenue or 0) for c in collections)
        total_volume = sum(c.dataforseo_volume or 0 for c in collections)

        # AI referral metrics
        total_ai_sessions = sum(c.ga4_ai_referral_sessions or 0 for c in collections)
        total_llm_revenue = sum(float(c.shopify_llm_revenue or 0) for c in collections)

        # Cannibalization alerts
        recent_alerts = self.db.query(SEOAlert).filter(
            SEOAlert.alert_type == 'collection_cannibalization',
            SEOAlert.status == 'open'
        ).count()

        # High-opportunity collections (high volume, no content)
        high_opp = [
            {
                "id": c.id,
                "title": c.collection_title,
                "volume": c.dataforseo_volume or 0,
                "impressions": c.current_impressions or 0,
            }
            for c in collections
            if (c.dataforseo_volume or 0) > 500 and not c.generated_content
        ]
        high_opp.sort(key=lambda x: x["volume"], reverse=True)

        # Revenue at risk (high-revenue collections without optimization)
        revenue_at_risk = sum(
            float(c.shopify_attributed_revenue or 0)
            for c in collections
            if c.optimization_status in ('pending', 'analyzed') and (c.shopify_attributed_revenue or 0) > 0
        )

        return {
            "total_collections": total,
            "status_breakdown": statuses,
            "content_coverage": {
                "with_content": with_content,
                "with_faq": with_faq,
                "with_schema": with_schema,
                "content_rate": round(with_content / total * 100, 1) if total else 0,
            },
            "performance": {
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_sessions": total_sessions,
                "total_revenue": round(total_revenue, 2),
                "total_search_volume": total_volume,
                "avg_position": round(
                    sum(c.current_position or 0 for c in collections if c.current_position) /
                    max(sum(1 for c in collections if c.current_position), 1), 1
                ),
            },
            "ai_visibility": {
                "total_ai_sessions": total_ai_sessions,
                "total_llm_revenue": round(total_llm_revenue, 2),
                "collections_with_ai_traffic": sum(1 for c in collections if (c.ga4_ai_referral_sessions or 0) > 0),
            },
            "cannibalization": {
                "open_alerts": recent_alerts,
            },
            "opportunities": {
                "high_volume_no_content": high_opp[:10],
                "revenue_at_risk": round(revenue_at_risk, 2),
                "unoptimized_count": statuses.get("pending", 0) + statuses.get("analyzed", 0),
            },
            "health_score": self._calculate_health_score(collections),
        }

    # ========================================================================
    # Report Section Builders
    # ========================================================================

    def _build_status_summary(self, collection: CollectionOptimizer) -> Dict:
        """Build a status summary for the collection."""
        return {
            "optimization_status": collection.optimization_status,
            "has_content": bool(collection.generated_content),
            "has_faq": bool(collection.generated_faq),
            "has_schema": bool(collection.generated_schema),
            "content_age_days": (
                (datetime.utcnow() - collection.content_generated_at).days
                if collection.content_generated_at else None
            ),
            "last_analytics_sync": collection.last_analytics_sync.isoformat() if collection.last_analytics_sync else None,
            "last_ga4_sync": collection.last_ga4_sync.isoformat() if collection.last_ga4_sync else None,
            "dataforseo_synced": bool(collection.dataforseo_primary_keyword),
        }

    def _find_content_gaps(self, collection: CollectionOptimizer, queries: List) -> Dict:
        """Find content gaps that represent optimization opportunities."""
        gaps = []

        if not collection.generated_content:
            gaps.append({
                "type": "missing_educational_content",
                "severity": "high",
                "description": "No educational/transactional content generated yet",
                "potential_impact": "15-25% organic traffic increase"
            })

        if not collection.generated_faq:
            question_queries = [q for q in queries if q.query_type == 'question']
            if question_queries:
                gaps.append({
                    "type": "missing_faq",
                    "severity": "high",
                    "description": f"{len(question_queries)} question queries without FAQ answers",
                    "queries": [q.query for q in question_queries[:5]],
                    "potential_impact": "Rich snippet eligibility"
                })

        if not collection.generated_schema:
            gaps.append({
                "type": "missing_schema",
                "severity": "medium",
                "description": "No JSON-LD schema markup",
                "potential_impact": "Featured snippet and rich result eligibility"
            })

        # DataForSEO PAA not answered
        paa = collection.dataforseo_people_also_ask or []
        if paa and not collection.generated_faq:
            gaps.append({
                "type": "unanswered_paa",
                "severity": "medium",
                "description": f"{len(paa)} People Also Ask questions from Google not answered",
                "questions": [p.get('question', '') for p in paa[:5]]
            })

        return {
            "total_gaps": len(gaps),
            "gaps": gaps
        }

    def _find_revenue_opportunities(self, collection: CollectionOptimizer) -> Dict:
        """Calculate revenue opportunity based on volume, CPC, and risk."""
        volume = collection.dataforseo_volume or 0
        cpc = float(collection.dataforseo_cpc or 0)
        sessions = collection.ga4_sessions or 0
        conv_rate = float(collection.ga4_conversion_rate or 0) / 100 if collection.ga4_conversion_rate else 0.02

        # Estimated monthly revenue if we captured all search volume
        estimated_traffic_value = volume * cpc
        estimated_conversion_revenue = volume * conv_rate * float(collection.shopify_attributed_revenue or 500) / max(sessions, 1)

        return {
            "monthly_search_volume": volume,
            "cpc": cpc,
            "estimated_traffic_value": round(estimated_traffic_value, 2),
            "current_revenue": float(collection.shopify_attributed_revenue or 0),
            "current_sessions": sessions,
            "conversion_rate": round(conv_rate * 100, 2),
            "competition": collection.dataforseo_competition,
            "top_competitor": collection.dataforseo_top_competitor,
        }

    def _analyze_ai_visibility(self, collection: CollectionOptimizer) -> Dict:
        """Analyze AI/GEO visibility for the collection."""
        ai_sessions = collection.ga4_ai_referral_sessions or 0
        total_sessions = collection.ga4_sessions or 0
        llm_revenue = float(collection.shopify_llm_revenue or 0)

        return {
            "ai_referral_sessions": ai_sessions,
            "ai_traffic_share": round(ai_sessions / total_sessions * 100, 1) if total_sessions > 0 else 0,
            "llm_attributed_revenue": llm_revenue,
            "has_schema": bool(collection.generated_schema),
            "recommendations": (
                ["Add FAQ schema for better AI parsing",
                 "Improve entity clarity in content",
                 "Ensure collection appears in llms.txt"]
                if ai_sessions == 0 else
                ["AI traffic detected - maintain structured data quality"]
            )
        }

    def _summarize_cannibalization(self, result) -> Dict:
        """Summarize cannibalization analysis."""
        if not result:
            return {"status": "not_analyzed", "risk_score": 0, "message": "Run cannibalization check first"}

        return {
            "status": result.status,
            "risk_score": result.risk_score,
            "safe_keywords": len(result.safe_keywords or []),
            "blocked_keywords": len(result.blocked_keywords or []),
            "warning_keywords": len(result.warning_keywords or []),
            "can_generate": result.can_generate,
            "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
        }

    def _analyze_keywords(self, queries: List) -> Dict:
        """Analyze keyword distribution and opportunities."""
        if not queries:
            return {"total": 0, "message": "No queries available"}

        by_intent = {"informational": 0, "transactional": 0, "navigational": 0}
        by_type = {"question": 0, "product": 0, "brand": 0, "comparison": 0}

        for q in queries:
            intent = q.intent or "navigational"
            qtype = q.query_type or "product"
            by_intent[intent] = by_intent.get(intent, 0) + 1
            by_type[qtype] = by_type.get(qtype, 0) + 1

        top_opportunities = [
            {
                "query": q.query,
                "impressions": q.impressions,
                "position": float(q.position or 0),
                "intent": q.intent,
                "priority_score": float(q.priority_score or 0)
            }
            for q in sorted(queries, key=lambda x: x.priority_score or 0, reverse=True)[:10]
        ]

        return {
            "total": len(queries),
            "by_intent": by_intent,
            "by_type": by_type,
            "top_opportunities": top_opportunities
        }

    def _analyze_trends(self, snapshots: List) -> Dict:
        """Analyze metric trends from snapshots."""
        if len(snapshots) < 2:
            return {"available": False, "message": "Need at least 2 snapshots for trends"}

        first = snapshots[0]
        latest = snapshots[-1]

        def delta(new, old):
            return (new or 0) - (old or 0)

        def pct_change(new, old):
            if (old or 0) == 0:
                return 0
            return round(((new or 0) - (old or 0)) / old * 100, 1)

        return {
            "available": True,
            "period_days": len(snapshots),
            "impressions": {
                "current": latest.gsc_impressions,
                "delta": delta(latest.gsc_impressions, first.gsc_impressions),
                "pct_change": pct_change(latest.gsc_impressions, first.gsc_impressions),
                "trend": "up" if (latest.gsc_impressions or 0) > (first.gsc_impressions or 0) else "down"
            },
            "position": {
                "current": latest.gsc_position,
                "delta": round(delta(latest.gsc_position, first.gsc_position), 1),
                "trend": "improving" if (latest.gsc_position or 100) < (first.gsc_position or 100) else "declining"
            },
            "sessions": {
                "current": latest.ga4_sessions,
                "delta": delta(latest.ga4_sessions, first.ga4_sessions),
                "pct_change": pct_change(latest.ga4_sessions, first.ga4_sessions),
            },
            "revenue": {
                "current": latest.shopify_attributed_revenue,
                "delta": round(delta(latest.shopify_attributed_revenue, first.shopify_attributed_revenue), 2),
            }
        }

    def _find_critical_issues(self, collection: CollectionOptimizer, cannibal_result) -> List[Dict]:
        """Find critical issues that need immediate attention."""
        issues = []

        if cannibal_result and cannibal_result.status == "blocked":
            issues.append({
                "type": "cannibalization_blocked",
                "severity": "critical",
                "message": f"Content generation blocked — {len(cannibal_result.blocked_keywords or [])} keywords conflict with blogs"
            })

        if (collection.ga4_bounce_rate or 0) > 80:
            issues.append({
                "type": "critical_bounce_rate",
                "severity": "high",
                "message": f"Bounce rate is {collection.ga4_bounce_rate}% — users leave immediately"
            })

        if (collection.current_position or 100) > 50:
            issues.append({
                "type": "poor_ranking",
                "severity": "high",
                "message": f"Average position is {collection.current_position:.0f} — effectively invisible"
            })

        if (collection.dataforseo_volume or 0) > 1000 and not collection.generated_content:
            issues.append({
                "type": "high_volume_no_content",
                "severity": "high",
                "message": f"Keyword volume is {collection.dataforseo_volume}/month but no content exists"
            })

        return issues

    def _find_quick_wins(self, collection: CollectionOptimizer, queries: List) -> List[Dict]:
        """Find quick wins with high impact and low effort."""
        wins = []

        # Position 4-10: small push to top 3
        close_to_top = [q for q in queries if 4 <= (q.position or 100) <= 10 and (q.impressions or 0) > 100]
        if close_to_top:
            wins.append({
                "type": "push_to_top_3",
                "effort": "low",
                "queries": [q.query for q in close_to_top[:3]],
                "message": f"{len(close_to_top)} queries are positions 4-10 — small optimization can push to top 3"
            })

        # Has content but no schema
        if collection.generated_content and not collection.generated_schema:
            wins.append({
                "type": "add_schema",
                "effort": "low",
                "message": "Content exists but no schema markup — add FAQ schema for rich snippets"
            })

        # High impressions, low CTR
        low_ctr = [q for q in queries if (q.impressions or 0) > 500 and (q.ctr or 0) < 0.02]
        if low_ctr:
            wins.append({
                "type": "improve_ctr",
                "effort": "medium",
                "queries": [q.query for q in low_ctr[:3]],
                "message": f"{len(low_ctr)} queries have high impressions but low CTR — optimize meta title/description"
            })

        return wins

    def _calculate_health_score(self, collections: List[CollectionOptimizer]) -> Dict:
        """Calculate overall collection health score (0-100)."""
        if not collections:
            return {"score": 0, "breakdown": {}}

        total = len(collections)

        # Content coverage (25 points)
        content_pct = sum(1 for c in collections if c.generated_content) / total
        content_score = content_pct * 25

        # Schema coverage (15 points)
        schema_pct = sum(1 for c in collections if c.generated_schema) / total
        schema_score = schema_pct * 15

        # Average position quality (20 points)
        positions = [c.current_position for c in collections if c.current_position and c.current_position > 0]
        avg_pos = sum(positions) / len(positions) if positions else 100
        position_score = max(0, 20 - (avg_pos - 1) * 0.5)  # 20 at pos 1, 0 at pos 41+

        # Optimization status (20 points)
        optimized = sum(1 for c in collections if c.optimization_status in ('ready', 'published', 'tracking'))
        opt_score = (optimized / total) * 20

        # Data completeness (20 points)
        has_gsc = sum(1 for c in collections if c.current_impressions) / total
        has_ga4 = sum(1 for c in collections if c.ga4_sessions) / total
        has_dfse = sum(1 for c in collections if c.dataforseo_volume) / total
        has_shopify = sum(1 for c in collections if c.shopify_attributed_revenue) / total
        data_score = ((has_gsc + has_ga4 + has_dfse + has_shopify) / 4) * 20

        total_score = content_score + schema_score + position_score + opt_score + data_score

        return {
            "score": round(min(total_score, 100), 1),
            "breakdown": {
                "content_coverage": round(content_score, 1),
                "schema_coverage": round(schema_score, 1),
                "ranking_quality": round(position_score, 1),
                "optimization_status": round(opt_score, 1),
                "data_completeness": round(data_score, 1),
            }
        }

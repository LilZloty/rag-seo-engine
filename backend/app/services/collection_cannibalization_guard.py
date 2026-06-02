"""
Collection Cannibalization Guard
=================================

Pre-generation safety check that prevents collection content from
cannibalizing existing blog and product page rankings.

Strategy: Blog articles own INFORMATIONAL intent keywords.
          Collections own TRANSACTIONAL intent keywords.
          This guard enforces that separation.

Called from:
1. API endpoint (manual check before generation)
2. Automatically before content generation in collection_optimizer_service
3. Smart recommendations service (cannibalization-aware recs)
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from pydantic import BaseModel, Field

from app.models.collection_optimizer_models import CollectionOptimizer, CollectionSearchQuery
from app.models.seo_intelligence import KeywordPageMapping
from app.models.collection_intelligence_models import CollectionCannibalizationResult

logger = logging.getLogger("cannibalization_guard")


# ============================================================================
# Pydantic Models
# ============================================================================

class KeywordConflict(BaseModel):
    keyword: str
    conflicting_url: str
    conflicting_page_type: str  # blog, product, collection
    conflicting_position: float
    conflicting_clicks: int
    conflicting_impressions: int
    intent: str  # informational, transactional, navigational
    severity: str  # blocked, warning, safe
    recommendation: str


class KeywordSafe(BaseModel):
    keyword: str
    intent: str
    impressions: int = 0
    clicks: int = 0
    position: float = 0.0
    opportunity_score: float = 0.0


class CannibalizationCheckResult(BaseModel):
    collection_id: int
    collection_title: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    total_keywords_analyzed: int = 0
    safe_keywords: List[KeywordSafe] = []
    blocked_keywords: List[KeywordConflict] = []
    warning_keywords: List[KeywordConflict] = []
    risk_score: float = 0.0  # 0-100
    status: str = "safe"  # safe, warning, blocked
    can_generate: bool = True
    generation_guidance: str = ""


# ============================================================================
# Cannibalization Guard Service
# ============================================================================

class CollectionCannibalizationGuard:
    """
    Checks whether generating content for a collection would cannibalize
    existing blog or product page rankings.
    """

    # Intent classification keywords
    TRANSACTIONAL_SIGNALS = [
        'comprar', 'precio', 'venta', 'tienda', 'donde comprar', 'cotizar',
        'envio', 'envío', 'costo', 'barato', 'económico', 'oferta',
        'kit', 'repuesto', 'refacción', 'disponible', 'stock', 'catalogo',
        'pedir', 'ordenar', 'mayoreo', 'distribuidor'
    ]
    INFORMATIONAL_SIGNALS = [
        'que es', 'qué es', 'como', 'cómo', 'sintomas', 'síntomas',
        'falla', 'codigo', 'código', 'problema', 'causa', 'diagnostico',
        'diagnóstico', 'por que', 'por qué', 'diferencia', 'vs',
        'funcionamiento', 'tipos de', 'guia', 'guía', 'tutorial',
        'cuando', 'cuándo', 'señales'
    ]

    # Severity thresholds
    BLOCKED_POSITION_THRESHOLD = 5    # Blog ranks top 5 = blocked
    BLOCKED_CLICKS_THRESHOLD = 10     # Blog has >10 clicks/month = blocked
    WARNING_POSITION_THRESHOLD = 20   # Blog ranks top 20 = warning

    def __init__(self, db: Session):
        self.db = db

    async def check_collection(self, collection_id: int) -> CannibalizationCheckResult:
        """
        Run full cannibalization analysis for a collection.

        Returns a CannibalizationCheckResult with safe/blocked/warning keywords,
        risk score, and generation guidance for the LLM prompt.
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        # 1. Get collection's target keywords from GSC queries
        collection_queries = self.db.query(CollectionSearchQuery).filter(
            CollectionSearchQuery.collection_id == collection_id
        ).order_by(CollectionSearchQuery.priority_score.desc()).limit(30).all()

        if not collection_queries:
            return CannibalizationCheckResult(
                collection_id=collection_id,
                collection_title=collection.collection_title,
                status="safe",
                can_generate=True,
                generation_guidance="No GSC queries found. Generate content targeting the collection title as primary keyword."
            )

        # 2. Get all keyword-page mappings for potential conflicts
        # Look at last 7 days of data for freshness
        target_date = (datetime.now() - timedelta(days=7)).date()
        keyword_texts = [q.query.lower() for q in collection_queries]

        existing_mappings = self.db.query(KeywordPageMapping).filter(
            KeywordPageMapping.date >= target_date,
            sql_func.lower(KeywordPageMapping.query).in_(keyword_texts)
        ).all()

        # Group mappings by keyword -> [(url, position, clicks, impressions)]
        keyword_pages: Dict[str, List[Dict]] = {}
        for m in existing_mappings:
            key = m.query.lower()
            if key not in keyword_pages:
                keyword_pages[key] = []
            keyword_pages[key].append({
                'url': m.page_url,
                'position': m.position,
                'clicks': m.clicks,
                'impressions': m.impressions,
                'page_type': m.page_type or self.classify_page_type(m.page_url)
            })

        # 3. Analyze each keyword for conflicts
        safe_keywords: List[KeywordSafe] = []
        blocked_keywords: List[KeywordConflict] = []
        warning_keywords: List[KeywordConflict] = []

        for query in collection_queries:
            keyword = query.query.lower()
            intent = self._classify_intent(keyword)
            pages = keyword_pages.get(keyword, [])

            # Filter to non-collection pages (blogs, products)
            competing_pages = [
                p for p in pages
                if p['page_type'] in ('blog', 'product')
            ]

            if not competing_pages:
                # No competition — safe to target
                safe_keywords.append(KeywordSafe(
                    keyword=query.query,
                    intent=intent,
                    impressions=query.impressions,
                    clicks=query.clicks,
                    position=query.position,
                    opportunity_score=query.priority_score
                ))
                continue

            # Check each competing page
            worst_severity = "safe"
            worst_conflict = None

            for page in competing_pages:
                severity = self._compute_severity(
                    keyword=keyword,
                    intent=intent,
                    page_type=page['page_type'],
                    position=page['position'],
                    clicks=page['clicks']
                )

                if severity == "blocked" or (severity == "warning" and worst_severity == "safe"):
                    worst_severity = severity
                    worst_conflict = KeywordConflict(
                        keyword=query.query,
                        conflicting_url=page['url'],
                        conflicting_page_type=page['page_type'],
                        conflicting_position=page['position'],
                        conflicting_clicks=page['clicks'],
                        conflicting_impressions=page['impressions'],
                        intent=intent,
                        severity=severity,
                        recommendation=self._generate_recommendation(
                            keyword, intent, page['page_type'],
                            page['position'], page['url']
                        )
                    )

                if severity == "blocked":
                    break  # No need to check further

            if worst_severity == "blocked" and worst_conflict:
                blocked_keywords.append(worst_conflict)
            elif worst_severity == "warning" and worst_conflict:
                warning_keywords.append(worst_conflict)
            else:
                safe_keywords.append(KeywordSafe(
                    keyword=query.query,
                    intent=intent,
                    impressions=query.impressions,
                    clicks=query.clicks,
                    position=query.position,
                    opportunity_score=query.priority_score
                ))

        # 4. Calculate risk score and status
        total = len(safe_keywords) + len(blocked_keywords) + len(warning_keywords)
        if total == 0:
            risk_score = 0.0
        else:
            risk_score = ((len(blocked_keywords) * 100) + (len(warning_keywords) * 40)) / total
            risk_score = min(risk_score, 100.0)

        if risk_score >= 70:
            status = "blocked"
            can_generate = False
        elif risk_score >= 30:
            status = "warning"
            can_generate = True
        else:
            status = "safe"
            can_generate = True

        # 5. Generate guidance for LLM prompt
        guidance = self._build_generation_guidance(
            collection.collection_title,
            safe_keywords, blocked_keywords, warning_keywords
        )

        result = CannibalizationCheckResult(
            collection_id=collection_id,
            collection_title=collection.collection_title,
            total_keywords_analyzed=total,
            safe_keywords=safe_keywords,
            blocked_keywords=blocked_keywords,
            warning_keywords=warning_keywords,
            risk_score=round(risk_score, 1),
            status=status,
            can_generate=can_generate,
            generation_guidance=guidance
        )

        # 6. Persist result
        self._persist_result(collection_id, result)

        return result

    async def check_batch(self, collection_ids: List[int]) -> Dict[int, CannibalizationCheckResult]:
        """Run cannibalization check for multiple collections."""
        results = {}
        for cid in collection_ids:
            try:
                results[cid] = await self.check_collection(cid)
            except Exception as e:
                logger.error(f"Cannibalization check failed for collection {cid}: {e}")
        return results

    def get_latest_result(self, collection_id: int) -> Optional[CannibalizationCheckResult]:
        """Get the most recent cannibalization check result (if fresh enough)."""
        result = self.db.query(CollectionCannibalizationResult).filter(
            CollectionCannibalizationResult.collection_id == collection_id
        ).order_by(CollectionCannibalizationResult.analyzed_at.desc()).first()

        if not result:
            return None

        # Consider stale after 24 hours
        if (datetime.utcnow() - result.analyzed_at).total_seconds() > 86400:
            return None

        return CannibalizationCheckResult(
            collection_id=result.collection_id,
            collection_title="",  # Not stored, caller can fill
            analyzed_at=result.analyzed_at,
            total_keywords_analyzed=len(result.target_keywords or []),
            safe_keywords=[KeywordSafe(**k) for k in (result.safe_keywords or [])],
            blocked_keywords=[KeywordConflict(**k) for k in (result.blocked_keywords or [])],
            warning_keywords=[KeywordConflict(**k) for k in (result.warning_keywords or [])],
            risk_score=result.risk_score,
            status=result.status,
            can_generate=result.can_generate,
            generation_guidance=result.generation_guidance or ""
        )

    def get_transactional_gap_keywords(self, collection_id: int) -> List[Dict]:
        """
        Find keywords the collection SHOULD rank for but nobody on the site does.
        These are the safest, highest-ROI keywords to target.
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            return []

        # Get DataForSEO PAA and related keywords
        paa = collection.dataforseo_people_also_ask or []
        primary_keyword = collection.dataforseo_primary_keyword or collection.collection_title

        # Get all keywords already ranking on our site
        target_date = (datetime.now() - timedelta(days=7)).date()
        our_keywords = set()
        mappings = self.db.query(KeywordPageMapping.query).filter(
            KeywordPageMapping.date >= target_date
        ).distinct().all()
        for m in mappings:
            our_keywords.add(m.query.lower())

        # Find gaps: PAA questions we don't rank for with transactional variants
        gaps = []
        for item in paa:
            question = item.get('question', '').lower()
            if question and question not in our_keywords:
                intent = self._classify_intent(question)
                gaps.append({
                    'keyword': item.get('question', ''),
                    'intent': intent,
                    'source': 'dataforseo_paa',
                    'answer_snippet': item.get('answer_snippet', '')
                })

        return gaps

    # ========================================================================
    # Private methods
    # ========================================================================

    @staticmethod
    def classify_page_type(url: str) -> str:
        """Classify a URL as blog, product, collection, or other."""
        url_lower = url.lower()
        if '/blogs/' in url_lower or '/blog/' in url_lower:
            return 'blog'
        elif '/products/' in url_lower:
            return 'product'
        elif '/collections/' in url_lower:
            return 'collection'
        return 'other'

    def _classify_intent(self, keyword: str) -> str:
        """Classify keyword intent as informational, transactional, or navigational."""
        kw = keyword.lower()
        if any(signal in kw for signal in self.TRANSACTIONAL_SIGNALS):
            return 'transactional'
        if any(signal in kw for signal in self.INFORMATIONAL_SIGNALS):
            return 'informational'
        return 'navigational'

    def _compute_severity(
        self,
        keyword: str,
        intent: str,
        page_type: str,
        position: float,
        clicks: int
    ) -> str:
        """
        Determine conflict severity based on intent + competing page performance.

        Rules:
        - Blog ranks top 5 AND has >10 clicks AND keyword is informational → BLOCKED
        - Blog ranks top 20 OR keyword has moderate overlap → WARNING
        - Product ranks top 10 AND keyword is same product type → WARNING
        - Everything else → SAFE
        """
        if page_type == 'blog':
            if intent == 'informational' and position <= self.BLOCKED_POSITION_THRESHOLD and clicks >= self.BLOCKED_CLICKS_THRESHOLD:
                return 'blocked'
            if position <= self.WARNING_POSITION_THRESHOLD:
                return 'warning'
        elif page_type == 'product':
            if position <= 10:
                return 'warning'

        return 'safe'

    def _generate_recommendation(
        self,
        keyword: str,
        intent: str,
        page_type: str,
        position: float,
        url: str
    ) -> str:
        """Generate a human-readable recommendation for a conflict."""
        if page_type == 'blog' and intent == 'informational':
            return (
                f"El blog '{url.split('/')[-1]}' ya rankea #{position:.0f} para esta keyword informacional. "
                f"NO la uses en el contenido de la colección. En su lugar, agrega un link interno "
                f"desde el blog hacia la colección para capturar tráfico transaccional."
            )
        elif page_type == 'blog':
            return (
                f"El blog compite por esta keyword (posición #{position:.0f}). "
                f"Si la usas en la colección, enmarca con intención transaccional "
                f"(ej: 'comprar {keyword}', 'precio de {keyword}')."
            )
        elif page_type == 'product':
            return (
                f"Un producto ya rankea #{position:.0f} para esta keyword. "
                f"Usa la variante de categoría (ej: 'mejores {keyword}', 'kit de {keyword}') "
                f"para evitar competencia interna."
            )
        return f"Conflicto con {url} (posición #{position:.0f}). Revisa manualmente."

    def _build_generation_guidance(
        self,
        collection_title: str,
        safe: List[KeywordSafe],
        blocked: List[KeywordConflict],
        warnings: List[KeywordConflict]
    ) -> str:
        """
        Build structured guidance that gets injected into the LLM content generation prompt.
        """
        lines = []
        lines.append(f"=== GUÍA DE KEYWORDS PARA: {collection_title} ===")
        lines.append("")

        if safe:
            lines.append("KEYWORDS SEGURAS (usar libremente en el contenido):")
            for kw in safe[:15]:
                lines.append(f"  - \"{kw.keyword}\" ({kw.intent}, {kw.impressions} impresiones)")
            lines.append("")

        if blocked:
            lines.append("KEYWORDS BLOQUEADAS (NO usar — ya rankea un blog/producto):")
            for kw in blocked:
                lines.append(f"  - \"{kw.keyword}\" → {kw.conflicting_page_type} rankea #{kw.conflicting_position:.0f}")
            lines.append("")

        if warnings:
            lines.append("KEYWORDS CON PRECAUCIÓN (usar solo con intención TRANSACCIONAL):")
            for kw in warnings:
                lines.append(f"  - \"{kw.keyword}\" → agregar 'comprar', 'precio', 'kit de' como prefijo")
            lines.append("")

        lines.append("REGLAS DE INTENCIÓN:")
        lines.append("  - Esta es una página de COLECCIÓN (transaccional). NO escribas contenido informacional/educativo largo.")
        lines.append("  - Enfócate en: comprar, precios, disponibilidad, envío, beneficios del producto.")
        lines.append("  - Si necesitas mencionar información técnica, hazlo brevemente y enlaza al blog para más detalles.")
        lines.append("  - NUNCA dupliques contenido que ya existe en artículos del blog.")

        return "\n".join(lines)

    def _persist_result(self, collection_id: int, result: CannibalizationCheckResult):
        """Save the cannibalization result to the database."""
        record = CollectionCannibalizationResult(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            analyzed_at=result.analyzed_at,
            target_keywords=[kw.keyword for kw in result.safe_keywords] +
                            [kw.keyword for kw in result.blocked_keywords] +
                            [kw.keyword for kw in result.warning_keywords],
            safe_keywords=[kw.model_dump() for kw in result.safe_keywords],
            blocked_keywords=[kw.model_dump() for kw in result.blocked_keywords],
            warning_keywords=[kw.model_dump() for kw in result.warning_keywords],
            conflicts=[kw.model_dump() for kw in result.blocked_keywords + result.warning_keywords],
            risk_score=result.risk_score,
            status=result.status,
            can_generate=result.can_generate,
            generation_guidance=result.generation_guidance
        )
        self.db.add(record)
        self.db.commit()

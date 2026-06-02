"""
Creative Intelligence — Opportunity Detector
=============================================

Extends the existing `creative_intelligence_service.py` (which builds
analytics reports grouped by vehicle brand) with the action layer:
durable, status-tracked `CreativeOpportunity` rows surfaced from four
signals. Each detector produces opportunities; this module also
handles scoring, dedup, and persistence.

Detectors
---------
1. transmission_demand_gap
   GSC query mentions a transmission code (e.g. "kit DQ250") but we
   have zero products tagged with that transmission_code.

2. query_demand_gap
   GSC query has substantial impressions, doesn't mention any known
   transmission code, AND its top semantic match against the product
   catalog is weak (similarity < 0.5). We probably can't satisfy it.

3. latent_inventory
   Product has historical sales (sold_all_time > 0) but ~zero current
   GSC impressions and GA4 sessions. Selling offline / direct,
   invisible to search.

4. marketing_gap
   Product gets meaningful GSC impressions but CTR <2%. Listing copy
   is failing to convert visibility to clicks.

Storage
-------
Writes to the `creative_opportunities` table via stable `signal_hash`
upserts. Re-running the detector refreshes `last_seen_at` and
`signal_data` without touching `status` — human resolved/dismissed
decisions are preserved across runs.
"""

import hashlib
import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.creative_opportunity import CreativeOpportunity
from app.models.product import Product
from app.services.creative_intelligence_service import (
    TRANSMISSION_BRAND_MAP,
)
from app.services.google_api_service import GoogleApiService
from app.services.product_embedding_service import product_embedding_service


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tuning knobs
# ----------------------------------------------------------------------

# Below this similarity score, we treat the top semantic match as "no
# real match" — i.e. a candidate demand gap. Calibrated for
# nomic-embed-text on transmission-parts copy; raise if the detector
# generates too many false positives.
SEMANTIC_GAP_THRESHOLD = 0.50

# CTR floor below which an impression-getting product is flagged as a
# marketing gap. 2% is a generous floor — Google's category average
# for ecommerce sits around 3-4%.
MARKETING_GAP_CTR_CEILING = 0.02

# An impression floor that filters out the long noisy tail of GSC.
MIN_QUERY_IMPRESSIONS = 50

# An impression floor for marketing-gap detection — below 200/month the
# CTR is statistically meaningless.
MIN_MARKETING_IMPRESSIONS = 200

# Conservative average revenue per click for transmission parts in MX.
# Used to monetize opportunity scores when product-specific AOV isn't
# available. ~$1500 MXN AOV × ~3% conversion = ~$45 MXN per click.
DEFAULT_RPC_MXN = 45.0

# Position → CTR benchmarks (Sistrix-style curve, transmission/auto
# category averages). Used to estimate "if your CTR matched the
# benchmark for your position, you'd get X extra clicks."
POSITION_CTR_BENCHMARK = {
    1: 0.318, 2: 0.247, 3: 0.187, 4: 0.137,
    5: 0.094, 6: 0.063, 7: 0.046, 8: 0.034,
    9: 0.026, 10: 0.021,
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

@dataclass
class _CodeMatch:
    code: str
    brand: Optional[str]


def _build_transmission_regex() -> re.Pattern:
    """Compile a single regex matching any known transmission code with word boundaries.

    Sorting by length descending prevents "TH700" from being shadowed by a hypothetical
    shorter "TH7" entry in the map.
    """
    codes = sorted(TRANSMISSION_BRAND_MAP.keys(), key=len, reverse=True)
    escaped = [re.escape(c) for c in codes]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


_TRANSMISSION_RE = _build_transmission_regex()


def _detect_transmission_codes_in_query(query: str) -> List[_CodeMatch]:
    """Return all transmission codes appearing in a query string."""
    if not query:
        return []
    matches: List[_CodeMatch] = []
    seen = set()
    for m in _TRANSMISSION_RE.finditer(query):
        code = m.group(1).upper()
        # Canonicalize to the case in TRANSMISSION_BRAND_MAP so brand lookup works.
        canonical = next(
            (k for k in TRANSMISSION_BRAND_MAP if k.upper() == code), None
        )
        if canonical and canonical not in seen:
            seen.add(canonical)
            matches.append(_CodeMatch(code=canonical, brand=TRANSMISSION_BRAND_MAP[canonical]))
    return matches


def _signal_hash(opportunity_type: str, target: str) -> str:
    raw = f"{opportunity_type}:{target}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _priority_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _expected_ctr_for_position(position: float) -> float:
    """Lookup nearest-rank CTR benchmark; capped at position 10."""
    if position <= 0:
        return 0.0
    rounded = max(1, min(10, round(position)))
    return POSITION_CTR_BENCHMARK.get(rounded, 0.01)


# ----------------------------------------------------------------------
# Detector
# ----------------------------------------------------------------------

class CreativeOpportunityDetector:
    """Runs all four detectors, scores results, persists with dedup."""

    def __init__(self, db: Session):
        self.db = db
        self.gsc = GoogleApiService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect_all(
        self, days: int = 30, persist: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Run every detector. Returns the raw opportunity dicts per type.

        Each detector is run sequentially because they share the GSC fetch
        and we want one consistent snapshot. Persistence is opt-out so we
        can preview without committing during dev.
        """
        queries = self.gsc.get_search_console_data(days=days) or []
        logger.info(f"[CreativeOpp] fetched {len(queries)} GSC queries (last {days}d)")

        transmission_gaps = self._detect_transmission_demand_gaps(queries)
        query_gaps = await self._detect_query_demand_gaps(queries)
        latent = self._detect_latent_inventory()
        marketing = self._detect_marketing_gaps()

        all_opps = transmission_gaps + query_gaps + latent + marketing

        if persist:
            self._persist(all_opps)

        return {
            "transmission_demand_gap": transmission_gaps,
            "query_demand_gap": query_gaps,
            "latent_inventory": latent,
            "marketing_gap": marketing,
        }

    # ------------------------------------------------------------------
    # 1. Transmission demand gap
    # ------------------------------------------------------------------

    def _detect_transmission_demand_gaps(
        self, queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find transmission codes searched in GSC that we have no product for."""

        # Aggregate impressions/clicks by transmission code across all queries.
        per_code: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "impressions": 0,
            "clicks": 0,
            "brand": None,
            "queries": [],
        })

        for q in queries:
            for match in _detect_transmission_codes_in_query(q.get("query", "")):
                bucket = per_code[match.code]
                bucket["brand"] = match.brand
                bucket["impressions"] += int(q.get("impressions") or 0)
                bucket["clicks"] += int(q.get("clicks") or 0)
                if len(bucket["queries"]) < 10:
                    bucket["queries"].append({
                        "query": q.get("query"),
                        "impressions": int(q.get("impressions") or 0),
                        "clicks": int(q.get("clicks") or 0),
                        "position": float(q.get("position") or 0),
                    })

        # For each candidate code, check if we have products.
        opportunities: List[Dict[str, Any]] = []
        for code, data in per_code.items():
            if data["impressions"] < MIN_QUERY_IMPRESSIONS:
                continue

            product_count = (
                self.db.query(Product)
                .filter(Product.transmission_code == code)
                .count()
            )
            if product_count > 0:
                continue  # We have inventory — not a demand gap. Other detectors may pick it up.

            # Score: impressions weighted, capped at 100.
            # 1000 impressions ≈ score 50; 5000+ → 100.
            score = min(100.0, 10 * (data["impressions"] ** 0.5))
            est_sessions = int(data["impressions"] * 0.05)  # 5% CTR optimism for new listing
            est_revenue = est_sessions * DEFAULT_RPC_MXN

            opportunities.append({
                "opportunity_type": "transmission_demand_gap",
                "target_type": "transmission",
                "target_transmission_code": code,
                "target_vehicle_brand": data["brand"],
                "target_product_id": None,
                "target_query": None,
                "signal_data": {
                    "total_impressions": data["impressions"],
                    "total_clicks": data["clicks"],
                    "query_count": len(data["queries"]),
                    "matched_queries": data["queries"],
                },
                "opportunity_score": round(score, 2),
                "estimated_monthly_sessions": est_sessions,
                "estimated_monthly_revenue": round(est_revenue, 2),
                "priority": _priority_from_score(score),
                "title": f"Demanda sin oferta: transmisión {code}"
                         + (f" ({data['brand']})" if data["brand"] else ""),
                "description": (
                    f"Detectamos {data['impressions']:,} impresiones en Google en los "
                    f"últimos 30 días para búsquedas que mencionan la transmisión "
                    f"{code}, pero no tenemos ningún producto en catálogo asociado a "
                    f"esta transmisión."
                ),
                "recommended_action": (
                    f"Evaluar si vale la pena añadir productos para {code}: "
                    f"buscar proveedores, validar viabilidad logística y márgenes, "
                    f"y crear una colección dedicada antes de lanzar contenido."
                ),
                "action_steps": [
                    f"Confirmar volumen sostenido en DataForSEO para keywords {code}",
                    "Pedir cotización a 1-2 proveedores existentes",
                    "Validar márgenes objetivo (mín. 30%)",
                    "Crear colección y 3-5 productos piloto",
                    "Generar contenido SEO + AEO para la nueva colección",
                ],
                "_signal_hash": _signal_hash("transmission_demand_gap", code),
            })

        return opportunities

    # ------------------------------------------------------------------
    # 2. Query demand gap (semantic)
    # ------------------------------------------------------------------

    async def _ollama_reachable(self) -> bool:
        """Quick probe so we degrade gracefully when Ollama isn't running."""
        import httpx
        from app.core.config import settings
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
                return resp.status_code == 200
        except Exception:
            return False


    async def _detect_query_demand_gaps(
        self, queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find high-impression queries with no good semantic match in the catalog."""

        # Skip queries that name a known transmission code — covered by detector 1.
        candidates = [
            q for q in queries
            if int(q.get("impressions") or 0) >= MIN_QUERY_IMPRESSIONS
            and not _detect_transmission_codes_in_query(q.get("query", ""))
        ]

        if not candidates:
            return []

        # Fail fast if Ollama is unreachable — otherwise we'd block ~60s per
        # candidate query waiting for the embedding timeout. A 2-second probe
        # is enough to know if the daemon is up.
        if not await self._ollama_reachable():
            logger.warning(
                "[CreativeOpp] Ollama unreachable — skipping query_demand_gap "
                "(semantic). Run `ollama serve` + `ollama pull nomic-embed-text` "
                "and re-detect to enable."
            )
            return []

        # Semantic match in bulk
        query_texts = [c["query"] for c in candidates]
        try:
            matches = await product_embedding_service.match_queries_bulk(
                query_texts, top_n=3
            )
        except Exception as e:
            logger.warning(f"[CreativeOpp] semantic match failed: {e}")
            return []

        opportunities: List[Dict[str, Any]] = []
        for q in candidates:
            query_text = q["query"]
            top_matches = matches.get(query_text, [])

            top_score = top_matches[0]["score"] if top_matches else 0.0
            if top_score >= SEMANTIC_GAP_THRESHOLD:
                continue  # We have a plausible product — not a demand gap.

            impressions = int(q.get("impressions") or 0)
            position = float(q.get("position") or 0)

            # Score: impressions weighted by gap strength.
            # gap_strength = 1 - top_score (in [0.5, 1.0])
            gap_strength = max(0.0, 1.0 - top_score)
            score = min(100.0, 6 * (impressions ** 0.5) * gap_strength * 2)

            est_sessions = int(impressions * 0.04)
            est_revenue = est_sessions * DEFAULT_RPC_MXN

            opportunities.append({
                "opportunity_type": "query_demand_gap",
                "target_type": "query",
                "target_transmission_code": None,
                "target_vehicle_brand": None,
                "target_product_id": None,
                "target_query": query_text,
                "signal_data": {
                    "impressions": impressions,
                    "clicks": int(q.get("clicks") or 0),
                    "ctr": float(q.get("ctr") or 0),
                    "position": position,
                    "top_match_similarity": round(top_score, 3),
                    "top_matches": top_matches,
                },
                "opportunity_score": round(score, 2),
                "estimated_monthly_sessions": est_sessions,
                "estimated_monthly_revenue": round(est_revenue, 2),
                "priority": _priority_from_score(score),
                "title": f"Búsqueda sin producto que la satisfaga: \"{query_text}\"",
                "description": (
                    f"Esta búsqueda generó {impressions:,} impresiones, pero el "
                    f"producto más relevante en catálogo solo coincide en "
                    f"{top_score:.0%}. Probablemente no podemos satisfacerla con "
                    f"el catálogo actual."
                ),
                "recommended_action": (
                    "Investigar la intención de búsqueda: ¿es una transmisión o "
                    "parte que no manejamos, una marca nueva, o una formulación "
                    "que requiere mejor contenido SEO?"
                ),
                "action_steps": [
                    f"Buscar \"{query_text}\" manualmente en Google + Mercado Libre para entender intención",
                    "Validar si los 3 matches semánticos son realmente irrelevantes",
                    "Si es un producto que falta: añadir a la lista de evaluación de catálogo",
                    "Si es contenido faltante: crear blog o colección dirigida",
                ],
                "_signal_hash": _signal_hash("query_demand_gap", query_text.lower().strip()),
            })

        return opportunities

    # ------------------------------------------------------------------
    # 3. Latent inventory
    # ------------------------------------------------------------------

    def _detect_latent_inventory(self) -> List[Dict[str, Any]]:
        """Products with historical sales but ~zero current search visibility."""

        # Has sold at least once historically, but isn't showing up in search now.
        products = (
            self.db.query(Product)
            .filter(Product.sold_all_time >= 3)
            .filter(or_(
                Product.gsc_impressions.is_(None),
                Product.gsc_impressions <= 10,
            ))
            .filter(or_(
                Product.ga4_sessions.is_(None),
                Product.ga4_sessions <= 5,
            ))
            .all()
        )

        opportunities: List[Dict[str, Any]] = []
        for p in products:
            sales = p.sold_all_time or 0
            sales_30d = p.sold_30d or 0

            # Score: weighted by all-time sales and recency.
            # A product that sold 50 lifetime and 5 in the last 30d is more
            # interesting than one that sold 50 a year ago and nothing since.
            score = min(100.0, 2 * (sales ** 0.5) + 4 * (sales_30d ** 0.5))

            est_sessions = max(50, int(sales * 3))  # rough — sales × 3 ~ baseline traffic potential
            est_revenue = (p.revenue_30d or 0) * 2  # double current direct-sales pace if we add search

            title = p.title[:120] if p.title else "(sin título)"

            opportunities.append({
                "opportunity_type": "latent_inventory",
                "target_type": "product",
                "target_transmission_code": p.transmission_code,
                "target_vehicle_brand": None,
                "target_product_id": str(p.id),
                "target_query": None,
                "signal_data": {
                    "sold_all_time": sales,
                    "sold_30d": sales_30d,
                    "gsc_impressions": p.gsc_impressions or 0,
                    "ga4_sessions": p.ga4_sessions or 0,
                    "handle": p.handle,
                    "price": p.price,
                },
                "opportunity_score": round(score, 2),
                "estimated_monthly_sessions": est_sessions,
                "estimated_monthly_revenue": round(est_revenue, 2),
                "priority": _priority_from_score(score),
                "title": f"Producto vendido pero invisible en búsqueda: {title}",
                "description": (
                    f"Vendió {sales} unidades históricamente ({sales_30d} en los "
                    f"últimos 30 días) pero tiene {p.gsc_impressions or 0} "
                    f"impresiones en Google y {p.ga4_sessions or 0} sesiones GA4. "
                    f"Está generando ventas por canal directo / offline pero no "
                    f"está capturando demanda orgánica."
                ),
                "recommended_action": (
                    "Auditar SEO del producto: meta title, descripción, schema, "
                    "links internos. Verificar que esté indexado en Google."
                ),
                "action_steps": [
                    "Verificar indexación: site:example-store.com/products/" + (p.handle or ""),
                    "Revisar / regenerar meta title + meta description",
                    "Añadir a 1-2 colecciones relevantes para link interno",
                    "Si tiene schema, validar; si no, generarlo",
                ],
                "_signal_hash": _signal_hash("latent_inventory", str(p.id)),
            })

        return opportunities

    # ------------------------------------------------------------------
    # 4. Marketing gap
    # ------------------------------------------------------------------

    def _detect_marketing_gaps(self) -> List[Dict[str, Any]]:
        """Products with meaningful impressions but CTR below the floor."""

        products = (
            self.db.query(Product)
            .filter(Product.gsc_impressions >= MIN_MARKETING_IMPRESSIONS)
            .filter(Product.gsc_ctr < MARKETING_GAP_CTR_CEILING)
            .all()
        )

        opportunities: List[Dict[str, Any]] = []
        for p in products:
            impressions = p.gsc_impressions or 0
            ctr = float(p.gsc_ctr or 0)
            position = float(p.gsc_position or 0)
            clicks = p.gsc_clicks or 0

            expected_ctr = _expected_ctr_for_position(position)
            ctr_gap = max(0.0, expected_ctr - ctr)
            missed_clicks = int(impressions * ctr_gap)

            # Score: weighted by missed clicks (the counterfactual gain).
            score = min(100.0, 4 * (missed_clicks ** 0.5))
            est_revenue = missed_clicks * DEFAULT_RPC_MXN

            title = p.title[:120] if p.title else "(sin título)"

            opportunities.append({
                "opportunity_type": "marketing_gap",
                "target_type": "product",
                "target_transmission_code": p.transmission_code,
                "target_vehicle_brand": None,
                "target_product_id": str(p.id),
                "target_query": None,
                "signal_data": {
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr": ctr,
                    "position": position,
                    "expected_ctr_at_position": expected_ctr,
                    "missed_clicks": missed_clicks,
                    "handle": p.handle,
                },
                "opportunity_score": round(score, 2),
                "estimated_monthly_sessions": missed_clicks,
                "estimated_monthly_revenue": round(est_revenue, 2),
                "priority": _priority_from_score(score),
                "title": f"Listing con baja conversión de impresiones: {title}",
                "description": (
                    f"Aparece en Google con {impressions:,} impresiones en posición "
                    f"{position:.1f}, pero el CTR es {ctr * 100:.2f}% (benchmark para "
                    f"esa posición: {expected_ctr * 100:.1f}%). Si la tasa subiera al "
                    f"benchmark, ganaríamos ~{missed_clicks:,} clicks adicionales/mes."
                ),
                "recommended_action": (
                    "Reescribir el meta title + meta description: enfocar en el "
                    "valor concreto y la intención de búsqueda. Probar variantes A/B."
                ),
                "action_steps": [
                    "Revisar las 5 queries con más impresiones que llegan al producto",
                    "Reescribir meta title con keyword principal + diferenciador",
                    "Reescribir meta description con CTA + envío + garantía",
                    "Validar que el H1 y schema estén alineados",
                    "Esperar 14 días y comparar CTR antes/después",
                ],
                "_signal_hash": _signal_hash("marketing_gap", str(p.id)),
            })

        return opportunities

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self, opportunities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Upsert opportunities by signal_hash. Preserves human status decisions."""
        inserted = 0
        updated = 0
        now = datetime.now(timezone.utc)

        for opp in opportunities:
            signal_hash = opp.pop("_signal_hash")
            existing = (
                self.db.query(CreativeOpportunity)
                .filter(CreativeOpportunity.signal_hash == signal_hash)
                .first()
            )

            if existing:
                # Refresh signal data + score, but keep status/notes/resolution.
                # Preserve any out-of-band artifacts (underscore-prefixed keys
                # like `_generated_copy`) across detection re-runs.
                preserved = {
                    k: v for k, v in (existing.signal_data or {}).items()
                    if k.startswith("_")
                }
                existing.last_seen_at = now
                existing.signal_data = {**opp["signal_data"], **preserved}
                existing.opportunity_score = opp["opportunity_score"]
                existing.estimated_monthly_sessions = opp["estimated_monthly_sessions"]
                existing.estimated_monthly_revenue = opp["estimated_monthly_revenue"]
                existing.priority = opp["priority"]
                existing.title = opp["title"]
                existing.description = opp["description"]
                existing.recommended_action = opp["recommended_action"]
                existing.action_steps = opp["action_steps"]
                updated += 1
            else:
                row = CreativeOpportunity(
                    id=f"copp_{uuid.uuid4().hex[:16]}",
                    signal_hash=signal_hash,
                    **opp,
                )
                self.db.add(row)
                inserted += 1

        self.db.commit()
        logger.info(f"[CreativeOpp] persisted: {inserted} new, {updated} updated")
        return {"inserted": inserted, "updated": updated}


def get_creative_opportunity_detector(db: Session) -> CreativeOpportunityDetector:
    return CreativeOpportunityDetector(db)

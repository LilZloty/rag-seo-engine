"""
SERP Cluster Sync Service

Populates the SERP cache (cache_entries table) for the entire catalog using
a layered keyword strategy. Once cached, the data is consumed transparently
by content_generator, article_enrichment_service, collection_optimizer,
and aeo/schema_generator with zero per-generation API calls.

Layers:
  1. GSC head terms     (≥100 imp, ~197 kws — already-validated demand)
  2. Transmission codes (~30 kws,  shape: "kit reparacion <code>")
  3. Fault codes        (~30 kws,  shape: "<code> falla")
  4. Brand SERPs        (~15 kws,  top vendors)
  5. Long-tail info     (~34 kws,  question-stem GSC queries ≥50 imp)

Total ~305 unique keywords across the catalog.
"""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.dataforseo_service import dataforseo_service

logger = get_logger(__name__)


BRAND_KEYWORDS = [
    "transgo", "raybestos", "allomatic", "lubegard", "sonnax",
    "freudenberg", "zf aftermarket", "yokomitsu", "superior",
    "sachs", "transtec", "xtra rev", "ford racing", "atra",
    "tss transmissions",
]

INFO_QUERY_PATTERNS = (
    "por que ", "porque ", "cuanto ", "cuánto ", "como ", "cómo ",
    "donde ", "dónde ", "que es ", "qué es ", "cual ", "cuál ",
    "cuando ", "cuándo ", "para que ", "para qué ",
    "tipos de ", "diferencia entre ",
)

LAYER_NAMES = {
    1: "GSC head terms (≥100 imp)",
    2: "Transmission codes",
    3: "Fault codes",
    4: "Brand SERPs",
    5: "Long-tail informational",
}


class SerpClusterSyncService:
    """Generates the catalog keyword universe and syncs it to DataForSEO cache."""

    def __init__(self, db: Session):
        self.db = db

    def generate_keywords(
        self, layers: Optional[List[int]] = None
    ) -> Dict[int, List[str]]:
        """Build the keyword cluster across requested layers (deduped within layer)."""
        layers = layers or [1, 2, 3, 4, 5]
        out: Dict[int, List[str]] = {}
        if 1 in layers:
            out[1] = self._layer1_gsc_head_terms()
        if 2 in layers:
            out[2] = self._layer2_transmission_codes()
        if 3 in layers:
            out[3] = self._layer3_fault_codes()
        if 4 in layers:
            out[4] = self._layer4_brands()
        if 5 in layers:
            out[5] = self._layer5_informational()
        return out

    def _layer1_gsc_head_terms(self, min_impressions: int = 100) -> List[str]:
        rows = self.db.execute(text("""
            SELECT query, SUM(impressions) AS imp
            FROM collection_search_queries
            WHERE query IS NOT NULL AND query != ''
            GROUP BY query
            HAVING SUM(impressions) >= :min_imp
            ORDER BY imp DESC
        """), {"min_imp": min_impressions}).fetchall()
        return [r[0].strip().lower() for r in rows]

    def _layer2_transmission_codes(self) -> List[str]:
        rows = self.db.execute(text("""
            SELECT DISTINCT transmission_code
            FROM products
            WHERE transmission_code IS NOT NULL AND transmission_code != ''
        """)).fetchall()
        return [f"kit reparacion {r[0].strip().lower()}" for r in rows]

    def _layer3_fault_codes(self) -> List[str]:
        rows = self.db.execute(text(
            "SELECT code FROM fault_codes WHERE code IS NOT NULL AND code != ''"
        )).fetchall()
        return [f"{r[0].strip().lower()} falla" for r in rows]

    def _layer4_brands(self) -> List[str]:
        return list(BRAND_KEYWORDS)

    def _layer5_informational(self, min_impressions: int = 50) -> List[str]:
        rows = self.db.execute(text("""
            SELECT query, SUM(impressions) AS imp
            FROM collection_search_queries
            WHERE query IS NOT NULL AND query != ''
            GROUP BY query
            HAVING SUM(impressions) >= :min_imp
            ORDER BY imp DESC
        """), {"min_imp": min_impressions}).fetchall()
        return [
            (r[0] or "").strip().lower()
            for r in rows
            if any((r[0] or "").lower().lstrip().startswith(p) for p in INFO_QUERY_PATTERNS)
        ]

    async def sync(
        self,
        layers: Optional[List[int]] = None,
        force_refresh: bool = False,
        max_concurrent: int = 5,
    ) -> Dict:
        """Run sync. Cache hits cost nothing; only misses hit DataForSEO."""
        if not dataforseo_service.is_configured():
            return {"status": "error", "reason": "DataForSEO credentials not configured"}

        keywords_by_layer = self.generate_keywords(layers)

        # Flatten + dedupe across layers (first occurrence keeps its layer label)
        seen: Set[str] = set()
        deduped: List[Tuple[int, str]] = []
        for layer, kws in keywords_by_layer.items():
            for kw in kws:
                if kw and kw not in seen:
                    seen.add(kw)
                    deduped.append((layer, kw))

        logger.info(
            f"[SerpClusterSync] {len(deduped)} unique keywords across "
            f"layers {sorted(keywords_by_layer.keys())} "
            f"(force_refresh={force_refresh})"
        )

        per_layer = {
            l: {"name": LAYER_NAMES[l], "total": 0, "hit": 0, "miss": 0,
                "error": 0, "keyword_count": len(keywords_by_layer.get(l, []))}
            for l in keywords_by_layer
        }

        if force_refresh:
            self._invalidate_cache_for([kw for _, kw in deduped])

        sem = asyncio.Semaphore(max_concurrent)

        async def fetch_one(layer: int, kw: str):
            async with sem:
                try:
                    result = await dataforseo_service.fetch_serp(kw, db=self.db)
                    return layer, kw, result
                except Exception as e:
                    logger.error(f"[SerpClusterSync] '{kw}' failed: {e}")
                    return layer, kw, {"error": str(e)}

        results = await asyncio.gather(*(fetch_one(l, k) for l, k in deduped))

        for layer, _, result in results:
            per_layer[layer]["total"] += 1
            if result.get("error"):
                per_layer[layer]["error"] += 1
            elif result.get("cached"):
                per_layer[layer]["hit"] += 1
            else:
                per_layer[layer]["miss"] += 1

        return {
            "status": "success",
            "total_keywords": len(deduped),
            "per_layer": per_layer,
        }

    def _invalidate_cache_for(self, keywords: List[str]) -> int:
        """Delete cache entries for given keywords so the next fetch hits the API."""
        from app.models.aeo_models import CacheEntry
        cache_keys = [dataforseo_service._build_cache_key(k) for k in keywords]
        deleted = self.db.query(CacheEntry).filter(
            CacheEntry.cache_key.in_(cache_keys)
        ).delete(synchronize_session=False)
        self.db.commit()
        logger.info(f"[SerpClusterSync] Invalidated {deleted} cache entries")
        return deleted

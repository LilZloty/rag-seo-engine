"""
Product Catalog Embedding Service
=================================

Embeds the Shopify product catalog into a dedicated Qdrant collection
(`app_products`) so we can semantically match arbitrary search
queries against the catalog. Used by the Creative Opportunity detector
to answer "is there a product that satisfies this query?" — when the
top semantic match is weak (similarity < ~0.5), the query is a
candidate demand gap.

Kept separate from the existing `qdrant_service.py` (which holds
document/RAG chunks) so payloads, filters, and rebuilds don't collide.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product import Product
from app.services.document_ingestion_service import document_ingestion_service


logger = logging.getLogger(__name__)

PRODUCT_COLLECTION = "app_products"
VECTOR_SIZE = 768  # nomic-embed-text


def _strip_html(html: Optional[str]) -> str:
    """Cheap HTML→text. Good enough for embedding input."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_embedding_text(product: Product) -> str:
    """Compose the canonical text we embed for a product.

    Order matters: title first (most signal-dense), then identifying
    metadata (transmission code, brand, type) so codes like "4L60E" or
    "DQ200" land near the top of the input. Description tail is
    truncated to keep tokens under nomic's 8k window.
    """
    parts: List[str] = []
    if product.title:
        parts.append(product.title)
    if product.transmission_code:
        parts.append(f"Transmisión: {product.transmission_code}")
    if product.product_type:
        parts.append(f"Tipo: {product.product_type}")
    if product.vendor:
        parts.append(f"Marca: {product.vendor}")

    fitments = product.cached_vehicle_fitments
    if fitments and isinstance(fitments, list):
        makes = set()
        for f in fitments[:10]:
            make = f.get("make") if isinstance(f, dict) else None
            if isinstance(make, list):
                make = make[0] if make else None
            if make:
                makes.add(str(make))
        if makes:
            parts.append(f"Vehículos: {', '.join(sorted(makes))}")

    desc = _strip_html(product.current_description_html)
    if desc:
        parts.append(desc[:800])

    return "\n".join(parts)


class ProductEmbeddingService:
    """Manages product embeddings in the dedicated Qdrant collection."""

    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=30,
            prefer_grpc=False,
            check_compatibility=False,
        )
        self.collection_name = PRODUCT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Could not verify collection {self.collection_name}: {e}")

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    async def _embed_text(self, text: str) -> List[float]:
        """Reuse the existing Ollama embedding pipeline."""
        return await document_ingestion_service.generate_embedding(text)

    def _payload_for(self, product: Product) -> Dict:
        return {
            "product_id": str(product.id),
            "shopify_id": product.shopify_id,
            "handle": product.handle,
            "title": product.title,
            "transmission_code": product.transmission_code,
            "product_type": product.product_type,
            "vendor": product.vendor,
            "gsc_impressions": product.gsc_impressions or 0,
            "ga4_sessions": product.ga4_sessions or 0,
            "sold_30d": product.sold_30d or 0,
            "sold_all_time": product.sold_all_time or 0,
        }

    def _point_id_for(self, product: Product) -> str:
        """Stable per-product point ID so upserts replace, not duplicate."""
        # Qdrant accepts UUIDs or unsigned ints; product.id is already a unique
        # string. We use it as-is — Qdrant's REST API accepts strings.
        return str(product.id)

    # ------------------------------------------------------------------
    # Single-product upsert
    # ------------------------------------------------------------------

    async def embed_product(self, product: Product) -> bool:
        text = _build_embedding_text(product)
        if not text.strip():
            return False
        vector = await self._embed_text(text)
        if not vector or sum(vector) == 0:
            return False

        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(
                id=self._point_id_for(product),
                vector=vector,
                payload=self._payload_for(product),
            )],
        )
        return True

    # ------------------------------------------------------------------
    # Bulk rebuild
    # ------------------------------------------------------------------

    async def embed_all_products(
        self, db: Session, batch_size: int = 64, concurrency: int = 5
    ) -> Dict[str, int]:
        """Bulk-embed every product. Idempotent — upserts on product.id.

        Yields control between batches so a long rebuild doesn't starve
        the event loop. Designed to be called from a Celery task.
        """
        products = (
            db.query(Product)
            .filter(Product.title.isnot(None))
            .order_by(Product.id)
            .all()
        )

        total = len(products)
        embedded = 0
        skipped = 0

        for batch_start in range(0, total, batch_size):
            batch = products[batch_start:batch_start + batch_size]
            texts = [_build_embedding_text(p) for p in batch]

            vectors = await document_ingestion_service.generate_embeddings_batch(
                texts, concurrency=concurrency
            )

            points: List[PointStruct] = []
            for product, text, vector in zip(batch, texts, vectors):
                if not text.strip() or not vector or sum(vector) == 0:
                    skipped += 1
                    continue
                points.append(PointStruct(
                    id=self._point_id_for(product),
                    vector=vector,
                    payload=self._payload_for(product),
                ))

            if points:
                self.client.upsert(collection_name=self.collection_name, points=points)
                embedded += len(points)

            logger.info(
                f"[Product Embedder] {embedded}/{total} embedded, {skipped} skipped "
                f"(batch {batch_start // batch_size + 1}/{(total + batch_size - 1) // batch_size})"
            )

        return {"total": total, "embedded": embedded, "skipped": skipped}

    # ------------------------------------------------------------------
    # Query → catalog matching (the core of demand-gap detection)
    # ------------------------------------------------------------------

    async def match_query(
        self,
        query: str,
        top_n: int = 5,
        transmission_code: Optional[str] = None,
    ) -> List[Dict]:
        """Embed `query`, return top-N matched products with similarity scores.

        Each result is a dict: {product_id, handle, title, transmission_code,
        product_type, score, gsc_impressions, ga4_sessions, sold_30d, sold_all_time}.
        Score is cosine similarity in [-1, 1]; in practice [0, 1] for our
        corpus. Caller decides the threshold (~0.5 weak / ~0.7 strong).
        """
        if not query or not query.strip():
            return []

        vector = await self._embed_text(query)
        if not vector or sum(vector) == 0:
            return []

        query_filter = None
        if transmission_code:
            query_filter = Filter(must=[
                FieldCondition(key="transmission_code", match=MatchValue(value=transmission_code))
            ])

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=query_filter,
                limit=top_n,
                with_payload=True,
            ).points
        except AttributeError:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_n,
                with_payload=True,
            )

        out: List[Dict] = []
        for r in results:
            payload = r.payload or {}
            out.append({
                "product_id": payload.get("product_id"),
                "handle": payload.get("handle"),
                "title": payload.get("title"),
                "transmission_code": payload.get("transmission_code"),
                "product_type": payload.get("product_type"),
                "vendor": payload.get("vendor"),
                "score": float(r.score),
                "gsc_impressions": payload.get("gsc_impressions", 0),
                "ga4_sessions": payload.get("ga4_sessions", 0),
                "sold_30d": payload.get("sold_30d", 0),
                "sold_all_time": payload.get("sold_all_time", 0),
            })
        return out

    async def match_queries_bulk(
        self, queries: List[str], top_n: int = 3
    ) -> Dict[str, List[Dict]]:
        """Match many queries in parallel. Returns {query: [matches]}."""
        results = await asyncio.gather(*[
            self.match_query(q, top_n=top_n) for q in queries
        ])
        return dict(zip(queries, results))


product_embedding_service = ProductEmbeddingService()

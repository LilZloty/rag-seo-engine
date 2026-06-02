"""
Celery tasks for Creative Intelligence opportunities.

Runs daily after the morning GSC/GA4 sync — by 07:30 the analytics
data has been refreshed and we can recompute opportunities against
the latest signal snapshot.
"""

import asyncio

from app.celery_app import celery
from app.db.session import SessionLocal


@celery.task(bind=True, name="detect_creative_opportunities")
def detect_creative_opportunities(self, days: int = 30):
    """Run all four detectors against the last `days` of GSC data.

    Persists results to the `creative_opportunities` table via signal_hash
    upserts. Human status decisions (resolved/dismissed) are preserved.
    """
    from app.services.creative_intelligence_opportunities import (
        get_creative_opportunity_detector,
    )

    db = SessionLocal()
    try:
        detector = get_creative_opportunity_detector(db)
        result = asyncio.run(detector.detect_all(days=days, persist=True))
        return {
            "status": "completed",
            "counts": {k: len(v) for k, v in result.items()},
            "total": sum(len(v) for v in result.values()),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="embed_product_catalog")
def embed_product_catalog(self):
    """Bulk-embed every product into the Qdrant catalog collection.

    Cheap to re-run (upserts on product.id). Schedule weekly so new
    products get picked up without thrashing Ollama.
    """
    from app.services.product_embedding_service import product_embedding_service

    db = SessionLocal()
    try:
        result = asyncio.run(product_embedding_service.embed_all_products(db))
        return {"status": "completed", **result}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

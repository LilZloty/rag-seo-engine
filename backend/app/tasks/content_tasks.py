import asyncio
from app.celery_app import celery
from app.db.session import SessionLocal


@celery.task(bind=True, name="analyze_all_collections")
def analyze_all_collections(self):
    """Analyze all GA4 collections — long-running."""
    from app.services.collection_optimizer_service import CollectionOptimizerService

    db = SessionLocal()
    try:
        service = CollectionOptimizerService(db)
        result = asyncio.run(service.analyze_all_ga4())
        return {"status": "completed", "result": result}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="sync_shopify_collections")
def sync_shopify_collections(self):
    """Sync all Shopify collections — moderate duration."""
    from app.services.collection_optimizer_service import CollectionOptimizerService

    db = SessionLocal()
    try:
        service = CollectionOptimizerService(db)
        result = asyncio.run(service.sync_collections())
        return {"status": "completed", "result": result}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

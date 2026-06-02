"""
Crawling Celery tasks — run in the crawler-worker image (has crawl4ai).

The light API image dispatches these tasks via Celery when a caller needs
JS-rendered scraping. Static-HTML URLs can still be scraped synchronously
on the API via DocumentIngestionService.scrape_url's httpx fallback.
"""
import asyncio
from typing import List, Optional

from app.celery_app import celery
from app.db.session import SessionLocal


@celery.task(bind=True, name="ingest_url")
def ingest_url_task(
    self,
    url: str,
    brands: Optional[List[str]] = None,
    product_types: Optional[List[str]] = None,
    transmission_codes: Optional[List[str]] = None,
):
    """Scrape a single URL (via crawl4ai) and ingest it into Qdrant.

    Returns the same shape as DocumentIngestionService.ingest_from_url so the
    polling endpoint can surface it unchanged to callers.
    """
    from app.services.document_ingestion_service import document_ingestion_service

    db = SessionLocal()
    try:
        result = asyncio.run(
            document_ingestion_service.ingest_from_url(
                url=url,
                brands=brands or [],
                product_types=product_types or [],
                transmission_codes=transmission_codes or [],
                db_session=db,
            )
        )
        return {"status": "completed", "result": result}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="bulk_ingest_urls")
def bulk_ingest_urls_task(
    self,
    urls: List[str],
    brands: Optional[List[str]] = None,
    product_types: Optional[List[str]] = None,
    transmission_codes: Optional[List[str]] = None,
    max_concurrent: int = 5,
):
    """Crawl many URLs in parallel (Crawl4AI SemaphoreDispatcher) and ingest.

    Meant for bulk-onboarding supplier docs. Only runs on the crawler image.
    """
    from app.services.document_ingestion_service import document_ingestion_service

    db = SessionLocal()
    try:
        results = asyncio.run(
            document_ingestion_service.ingest_from_urls_bulk(
                urls=urls,
                brands=brands or [],
                product_types=product_types or [],
                transmission_codes=transmission_codes or [],
                max_concurrent=max_concurrent,
                db_session=db,
            )
        )
        return {"status": "completed", "ingested": len(results), "results": results}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

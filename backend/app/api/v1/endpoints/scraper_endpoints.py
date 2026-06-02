"""
Scraper endpoints — trigger catalog scrapers and pipe results into the RAG pipeline.

Routes
------
POST /scraper/tss/run     — start a TSS catalog scrape (background job)
GET  /scraper/tss/status  — check the status of the last / a specific job
"""
import sys
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory job tracker  (process-level, resets on restart — good enough here)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}


def _new_job() -> dict:
    return {
        "job_id": str(uuid.uuid4()),
        "status": "pending",       # pending | running | done | error
        "started_at": None,
        "finished_at": None,
        "products_found": 0,
        "products_ingested": 0,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Helper — convert a scraped product dict to plain text for the RAG pipeline
# ---------------------------------------------------------------------------

def _product_to_text(product: dict) -> str:
    lines = [
        f"Producto: {product.get('product_name', '')}",
        f"Número de parte: {product.get('part_number', '')}",
        f"Proveedor: TSS",
        f"Transmisión: {product.get('transmission_code', '')}",
        f"Tipo de parte: {product.get('part_type', '')}",
        f"URL: {product.get('source_url', '')}",
    ]

    specs = product.get("specifications") or {}
    if specs:
        lines.append("\nEspecificaciones:")
        for k, v in specs.items():
            lines.append(f"  {k}: {v}")

    vehicles = product.get("compatible_vehicles") or []
    if vehicles:
        lines.append("\nVehículos compatibles:")
        for v in vehicles:
            lines.append(
                f"  {v.get('make', '')} {v.get('model', '')} ({v.get('years', '')})"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

async def _run_tss_scrape(
    job: dict,
    max_products: int,
    library_id: Optional[str],
    db_factory,
):
    # Add the scraper folder to path so we can import tss.py
    scraper_path = os.path.join(
        os.path.dirname(__file__),   # .../endpoints/
        "..", "..", "..", "..",       # up to project backend root
        "..", "scraper", "scrapers"  # scraper/scrapers/
    )
    scraper_path = os.path.normpath(scraper_path)
    if scraper_path not in sys.path:
        sys.path.insert(0, scraper_path)

    from app.services.document_ingestion_service import document_ingestion_service
    from app.models.library import Document, Library

    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    try:
        from tss import TSSProductsScraper

        scraper = TSSProductsScraper()
        products = await scraper.scrape_product_catalog(max_products=max_products)
        job["products_found"] = len(products)

        with db_factory() as db:
            library = None
            if library_id:
                library = db.query(Library).filter(Library.id == library_id).first()

            for product in products:
                try:
                    text = _product_to_text(product)
                    title = product.get("product_name") or product.get("part_number") or "TSS Product"

                    result = await document_ingestion_service.ingest_document(
                        content=text,
                        title=title,
                        source_type="scraped",
                        source_url=product.get("source_url"),
                        brands=["TSS"],
                        product_types=[product["part_type"]] if product.get("part_type") else [],
                        transmission_codes=[product["transmission_code"]] if product.get("transmission_code") else [],
                        db_session=db,
                    )

                    # Link to library if requested
                    if library:
                        doc = db.query(Document).filter(
                            Document.id == result["document_id"]
                        ).first()
                        if doc and library not in doc.libraries:
                            doc.libraries.append(library)
                            library.document_count = len(library.documents)
                            db.commit()

                    job["products_ingested"] += 1

                except Exception as e:
                    job["errors"].append(f"{product.get('product_name', '?')}: {e}")

        job["status"] = "done"

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(str(e))

    finally:
        job["finished_at"] = datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scraper/tss/run")
async def run_tss_scraper(
    background_tasks: BackgroundTasks,
    max_products: int = Query(100, ge=1, le=500, description="Max products to scrape"),
    library_id: Optional[str] = Query(None, description="Library ID to link ingested documents to"),
):
    """
    Start a TSS catalog scrape in the background.

    Scrapes example-store.com/products, converts every product into a RAG document
    (text with specs + compatible vehicles), and stores it in Qdrant + SQLite.

    Returns a job_id you can poll with GET /scraper/tss/status?job_id=...
    """
    from app.db.session import SessionLocal

    job = _new_job()
    _jobs[job["job_id"]] = job

    background_tasks.add_task(
        _run_tss_scrape,
        job=job,
        max_products=max_products,
        library_id=library_id,
        db_factory=SessionLocal,
    )

    return {
        "status": "started",
        "job_id": job["job_id"],
        "message": f"TSS scrape started — up to {max_products} products. Poll /scraper/tss/status?job_id={job['job_id']} for progress.",
    }


@router.get("/scraper/tss/status")
async def get_tss_scrape_status(
    job_id: Optional[str] = Query(None, description="Job ID from /scraper/tss/run. Omit to get the latest job."),
):
    """
    Check the status of a TSS scrape job.
    Omit job_id to see the most recently started job.
    """
    if not _jobs:
        return {"status": "no_jobs", "message": "No scrape jobs have been run yet."}

    if job_id:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    else:
        # Return the most recently started job
        job = list(_jobs.values())[-1]

    return job

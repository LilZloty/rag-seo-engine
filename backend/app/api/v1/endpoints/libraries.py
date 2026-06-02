# API endpoints for Libraries, Documents, and PromptTemplates
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.db.session import get_db
from app.models import Library, Document, PromptTemplate
from app.schemas import (
    LibraryCreate, LibraryUpdate, LibraryResponse, LibraryWithDocuments,
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentWithContent,
    PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateResponse,
    LibraryType
)
from app.services.document_ingestion_service import document_ingestion_service

router = APIRouter()


# ============== LIBRARY ENDPOINTS ==============

@router.get("/libraries", response_model=List[LibraryResponse])
async def list_libraries(
    library_type: Optional[LibraryType] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List all libraries, optionally filtered by type"""
    query = db.query(Library)
    
    if library_type:
        query = query.filter(Library.library_type == library_type.value)
    if is_active is not None:
        query = query.filter(Library.is_active == is_active)
    
    return query.order_by(Library.library_type, Library.name).all()


@router.get("/libraries/{library_id}", response_model=LibraryWithDocuments)
async def get_library(library_id: str, db: Session = Depends(get_db)):
    """Get a single library with its documents"""
    library = db.query(Library).filter(Library.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    return library


@router.post("/libraries", response_model=LibraryResponse)
async def create_library(library: LibraryCreate, db: Session = Depends(get_db)):
    """Create a new library"""
    existing = db.query(Library).filter(Library.id == library.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Library with this ID already exists")
    
    db_library = Library(**library.model_dump())
    db.add(db_library)
    db.commit()
    db.refresh(db_library)
    return db_library


@router.put("/libraries/{library_id}", response_model=LibraryResponse)
async def update_library(
    library_id: str,
    library_update: LibraryUpdate,
    db: Session = Depends(get_db)
):
    """Update a library"""
    db_library = db.query(Library).filter(Library.id == library_id).first()
    if not db_library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    update_data = library_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_library, field, value)
    
    db.commit()
    db.refresh(db_library)
    return db_library


@router.delete("/libraries/{library_id}")
async def delete_library(library_id: str, db: Session = Depends(get_db)):
    """Delete a library"""
    db_library = db.query(Library).filter(Library.id == library_id).first()
    if not db_library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    db.delete(db_library)
    db.commit()
    return {"status": "deleted", "id": library_id}


# ============== DOCUMENT ENDPOINTS ==============

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    library_id: Optional[str] = None,
    brand: Optional[str] = None,
    product_type: Optional[str] = None,
    transmission_code: Optional[str] = None,
    verified: Optional[bool] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List documents with filters"""
    query = db.query(Document)
    
    if library_id:
        query = query.join(Document.libraries).filter(Library.id == library_id)
    if brand:
        query = query.filter(Document.brands.contains([brand]))
    if product_type:
        query = query.filter(Document.product_types.contains([product_type]))
    if transmission_code:
        query = query.filter(Document.transmission_codes.contains([transmission_code]))
    if verified is not None:
        query = query.filter(Document.verified == verified)
    
    return query.offset(offset).limit(limit).all()


@router.get("/documents/{document_id}", response_model=DocumentWithContent)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get a single document with full content"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    brands: Optional[str] = Form(None),
    product_types: Optional[str] = Form(None),
    transmission_codes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a PDF document - processes in background for large files"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Parse comma-separated lists from Form data
    brands_list = [b.strip() for b in brands.split(',')] if brands else None
    pt_list = [p.strip() for p in product_types.split(',')] if product_types else None
    tc_list = [t.strip() for t in transmission_codes.split(',')] if transmission_codes else None
    
    try:
        content = await file.read()
        
        # For small files (< 50KB), process synchronously
        if len(content) < 50 * 1024:
            document_data = await document_ingestion_service.ingest_pdf_upload(
                file_bytes=content,
                filename=file.filename,
                brands=brands_list,
                product_types=pt_list,
                transmission_codes=tc_list,
                db_session=db
            )
            doc_id = document_data.get("document_id")
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                raise HTTPException(status_code=500, detail="Document created but not found in DB")
            return {"status": "completed", "document": document}
        
        # For large files, process in background
        print(f"[Upload] Large PDF ({len(content)/1024:.0f}KB) - processing in background")
        
        # Define background task
        async def process_pdf_background():
            from app.db.session import SessionLocal
            with SessionLocal() as bg_db:
                try:
                    await document_ingestion_service.ingest_pdf_upload(
                        file_bytes=content,
                        filename=file.filename,
                        brands=brands_list,
                        product_types=pt_list,
                        transmission_codes=tc_list,
                        db_session=bg_db
                    )
                    print(f"[Upload] Background processing complete: {file.filename}")
                except Exception as e:
                    print(f"[Upload] Background processing error: {e}")
        
        # Queue the background task
        background_tasks.add_task(process_pdf_background)
        
        return {
            "status": "processing",
            "message": f"PDF '{file.filename}' queued for background processing. Refresh to see when complete.",
            "filename": file.filename,
            "size_kb": len(content) / 1024
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents", response_model=DocumentResponse)
async def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    """Create a new document"""
    doc_id = str(uuid.uuid4())
    content_preview = document.content[:500] if len(document.content) > 500 else document.content
    
    db_document = Document(
        id=doc_id,
        content_preview=content_preview,
        **document.model_dump()
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db)
):
    """Update a document"""
    db_document = db.query(Document).filter(Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    update_data = document_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_document, field, value)
    
    db.commit()
    db.refresh(db_document)
    return db_document


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document"""
    db_document = db.query(Document).filter(Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(db_document)
    db.commit()
    return {"status": "deleted", "id": document_id}


@router.post("/documents/{document_id}/link/{library_id}")
async def link_document_to_library(
    document_id: str,
    library_id: str,
    db: Session = Depends(get_db)
):
    """Link a document to a library"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    library = db.query(Library).filter(Library.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    # Check if already linked
    if library in document.libraries:
        return {"status": "already_linked", "document_id": document_id, "library_id": library_id}
    
    # Add link
    document.libraries.append(library)
    library.document_count = len(library.documents)
    db.commit()
    
    return {"status": "linked", "document_id": document_id, "library_id": library_id}


@router.delete("/documents/{document_id}/link/{library_id}")
async def unlink_document_from_library(
    document_id: str,
    library_id: str,
    db: Session = Depends(get_db)
):
    """Unlink a document from a library"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    library = db.query(Library).filter(Library.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    
    # Remove link if exists
    if library in document.libraries:
        document.libraries.remove(library)
        library.document_count = len(library.documents)
        db.commit()
        return {"status": "unlinked", "document_id": document_id, "library_id": library_id}
    
    return {"status": "not_linked", "document_id": document_id, "library_id": library_id}


@router.get("/documents/{document_id}/libraries")
async def get_document_libraries(
    document_id: str,
    db: Session = Depends(get_db)
):
    """Get all libraries linked to a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": document_id,
        "libraries": [{"id": lib.id, "name": lib.name, "library_type": lib.library_type} for lib in document.libraries]
    }

@router.post("/documents/{document_id}/verify")
async def verify_document(
    document_id: str,
    verified_by: str = Query(...),
    db: Session = Depends(get_db)
):
    """Mark a document as verified"""
    from datetime import datetime
    
    db_document = db.query(Document).filter(Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db_document.verified = True
    db_document.verified_by = verified_by
    db_document.verified_at = datetime.now()
    
    db.commit()
    return {"status": "verified", "id": document_id}



def _parse_csv_list(value: Optional[str]) -> List[str]:
    """Parse a comma-separated query string param into a list of trimmed values."""
    return [v.strip() for v in value.split(',')] if value else []


@router.post("/documents/scrape")
async def scrape_url_document(
    url: str,
    brands: Optional[str] = None,
    product_types: Optional[str] = None,
    transmission_codes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Scrape a URL and ingest it synchronously.

    On the light API image this uses the httpx+BeautifulSoup fallback (static
    HTML only). For JS-rendered pages use /documents/scrape/async which
    dispatches the work to a crawler worker that has crawl4ai + Playwright.
    """
    from app.services.document_ingestion_service import document_ingestion_service

    try:
        result = await document_ingestion_service.ingest_from_url(
            url=url,
            brands=_parse_csv_list(brands),
            product_types=_parse_csv_list(product_types),
            transmission_codes=_parse_csv_list(transmission_codes),
            db_session=db
        )
        return {
            "status": "success",
            "message": f"URL scraped and processed: {result['chunk_count']} chunks created",
            **result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/scrape/async", status_code=202)
async def scrape_url_document_async(
    url: str,
    brands: Optional[str] = None,
    product_types: Optional[str] = None,
    transmission_codes: Optional[str] = None,
):
    """Dispatch URL ingestion to a crawler worker (crawl4ai + Playwright).

    Use this for JS-rendered pages the sync endpoint can't handle. Returns
    202 Accepted with a task_id immediately; poll GET /api/v1/tasks/{task_id}
    for progress and the final ingest result.
    """
    from app.core.config import settings
    if not settings.USE_CELERY:
        raise HTTPException(
            status_code=501,
            detail="Celery not enabled; async crawling unavailable. Use /documents/scrape for sync httpx fallback.",
        )

    # Lazy import — keeps module-load light and avoids pulling task deps
    # into any caller that doesn't use async crawling.
    from app.tasks.crawling_tasks import ingest_url_task

    task = ingest_url_task.delay(
        url=url,
        brands=_parse_csv_list(brands),
        product_types=_parse_csv_list(product_types),
        transmission_codes=_parse_csv_list(transmission_codes),
    )

    return {
        "task_id": task.id,
        "status": "pending",
        "poll_url": f"/api/v1/tasks/{task.id}",
    }


@router.post("/documents/scrape/bulk-async", status_code=202)
async def scrape_urls_bulk_async(
    urls: List[str],
    brands: Optional[str] = None,
    product_types: Optional[str] = None,
    transmission_codes: Optional[str] = None,
    max_concurrent: int = 5,
):
    """Dispatch bulk URL ingestion to a crawler worker (parallel crawl4ai)."""
    from app.core.config import settings
    if not settings.USE_CELERY:
        raise HTTPException(status_code=501, detail="Celery not enabled")

    from app.tasks.crawling_tasks import bulk_ingest_urls_task

    task = bulk_ingest_urls_task.delay(
        urls=urls,
        brands=_parse_csv_list(brands),
        product_types=_parse_csv_list(product_types),
        transmission_codes=_parse_csv_list(transmission_codes),
        max_concurrent=max_concurrent,
    )

    return {
        "task_id": task.id,
        "status": "pending",
        "url_count": len(urls),
        "poll_url": f"/api/v1/tasks/{task.id}",
    }


@router.post("/documents/text")
async def ingest_text_document(
    title: str,
    content: str,
    brands: Optional[str] = None,
    product_types: Optional[str] = None,
    transmission_codes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Ingest raw text content for RAG"""
    from app.services.document_ingestion_service import document_ingestion_service
    
    # Parse comma-separated values
    brand_list = [b.strip() for b in brands.split(',')] if brands else []
    product_type_list = [p.strip() for p in product_types.split(',')] if product_types else []
    transmission_list = [t.strip() for t in transmission_codes.split(',')] if transmission_codes else []
    
    try:
        result = await document_ingestion_service.ingest_document(
            content=content,
            title=title,
            source_type='manual',
            brands=brand_list,
            product_types=product_type_list,
            transmission_codes=transmission_list,
            db_session=db
        )
        return {
            "status": "success",
            "message": f"Text ingested: {result['chunk_count']} chunks created",
            **result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============== PROMPT TEMPLATE ENDPOINTS ==============

@router.get("/prompts", response_model=List[PromptTemplateResponse])
async def list_prompts(
    template_type: Optional[str] = None,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """List all prompt templates"""
    query = db.query(PromptTemplate)
    
    if template_type:
        query = query.filter(PromptTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(PromptTemplate.is_active == is_active)
    
    return query.order_by(PromptTemplate.priority.desc()).all()


@router.get("/prompts/{prompt_id}", response_model=PromptTemplateResponse)
async def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Get a single prompt template"""
    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return prompt


@router.post("/prompts", response_model=PromptTemplateResponse)
async def create_prompt(prompt: PromptTemplateCreate, db: Session = Depends(get_db)):
    """Create a new prompt template"""
    existing = db.query(PromptTemplate).filter(PromptTemplate.id == prompt.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Prompt with this ID already exists")
    
    db_prompt = PromptTemplate(**prompt.model_dump())
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt


@router.put("/prompts/{prompt_id}", response_model=PromptTemplateResponse)
async def update_prompt(
    prompt_id: str,
    prompt_update: PromptTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update a prompt template"""
    db_prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    
    if db_prompt.is_readonly:
        raise HTTPException(status_code=400, detail="Cannot modify read-only prompt template")
    
    update_data = prompt_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prompt, field, value)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Delete a prompt template"""
    db_prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    
    if db_prompt.is_readonly:
        raise HTTPException(status_code=400, detail="Cannot delete read-only prompt template")
    
    db.delete(db_prompt)
    db.commit()
    return {"status": "deleted", "id": prompt_id}


@router.get("/prompts/active/{product_id}")
async def get_active_prompts_for_product(
    product_id: str,
    db: Session = Depends(get_db)
):
    """Get all prompts that would be active for a given product"""
    # TODO: Implement product detection logic to determine brand, type, transmission
    # For now, return all active prompts ordered by priority
    prompts = db.query(PromptTemplate)\
        .filter(PromptTemplate.is_active == True)\
        .order_by(PromptTemplate.priority.desc())\
        .all()
    
    return {
        "product_id": product_id,
        "active_prompts": [p.id for p in prompts],
        "prompts": prompts
    }

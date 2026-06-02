from fastapi import APIRouter, HTTPException, Request
from app.services.content_generator import content_generator_service
from app.services.qdrant_service import qdrant_service
from app.schemas.library import GenerateContentRequest
from app.core.rate_limiter import limiter, RATE_CONTENT_GEN

router = APIRouter()


@router.post("/content/generate")
@limiter.limit(RATE_CONTENT_GEN)
async def generate_content(request: Request, body: GenerateContentRequest):
    try:
        qdrant_service.create_collection()
        content = await content_generator_service.generate_for_product(
            body.product_id,
            library_ids=body.library_ids,
            template_id=body.template_id,
            provider=body.provider,
            model_name=body.model_name,
            analysis_insights=body.analysis_insights
        )
        print(f"[API] Generated content keys: {content.keys() if isinstance(content, dict) else type(content)}")
        print(f"[API] h1_title: {content.get('h1_title', 'MISSING')[:50] if isinstance(content, dict) else 'N/A'}")
        print(f"[API] url_handle: {content.get('url_handle', 'MISSING') if isinstance(content, dict) else 'N/A'}")
        print(f"[API] alt_tags: {content.get('alt_tags', 'MISSING') if isinstance(content, dict) else 'N/A'}")
        return {"content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scraping/run-tss")
async def run_tss_scraper():
    import asyncio
    from scraper.scrapers.tss import main
    
    try:
        await main()
        return {"message": "TSS scraper completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    llm_status = await content_generator_service.llm_service.check_connection()
    
    return {
        "status": "healthy",
        "llm_connected": llm_status,
        "qdrant": qdrant_service.client.collection_exists("supplier_parts")
    }

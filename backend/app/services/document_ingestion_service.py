"""
Document Ingestion Service for Phase 2 RAG System.
Handles:
- PDF extraction
- Text ingestion
- URL scraping
- Document chunking
- Embedding generation
- Qdrant storage
"""
import os
import uuid
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from app.core.config import settings


class DocumentIngestionService:
    def __init__(self):
        self.chunk_size = settings.RAG_CHUNK_SIZE  # 1000 chars
        self.chunk_overlap = settings.RAG_CHUNK_OVERLAP  # 200 chars
        self._embedding_client = None
    
    # ============== TEXT CHUNKING ==============
    
    def chunk_text(self, text: str) -> List[Dict]:
        """Split text into overlapping chunks for RAG"""
        if not text or not text.strip():
            return []
        
        # Clean the text
        text = self._clean_text(text)
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to end at a sentence boundary
            if end < len(text):
                # Look for sentence endings
                for sep in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > self.chunk_size * 0.5:  # At least half the chunk
                        end = start + last_sep + len(sep)
                        break
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    'index': chunk_index,
                    'content': chunk_text,
                    'start_position': start,
                    'end_position': end,
                    'token_count': len(chunk_text.split())  # Simple word count
                })
                chunk_index += 1
            
            # Move start with overlap
            start = end - self.chunk_overlap
            if start <= chunks[-1]['start_position'] if chunks else 0:
                start = end  # Prevent infinite loop
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean text for processing"""
        # Remove multiple spaces/newlines
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that break things
        text = text.replace('\x00', '')
        return text.strip()
    
    # ============== PDF EXTRACTION ==============
    
    def extract_pdf(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text from a PDF file"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            text_parts = []
            metadata = {
                'page_count': len(doc),
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
            }
            
            for page in doc:
                text_parts.append(page.get_text())
            
            doc.close()
            
            full_text = '\n'.join(text_parts)
            return full_text, metadata
            
        except ImportError:
            # Fallback to pdfplumber if PyMuPDF not installed
            try:
                import pdfplumber
                
                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    metadata = {'page_count': len(pdf.pages)}
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                
                return '\n'.join(text_parts), metadata
                
            except ImportError:
                raise ImportError("Please install PyMuPDF (fitz) or pdfplumber for PDF extraction: pip install pymupdf")
    
    def extract_pdf_from_bytes(self, file_bytes: bytes, filename: str = "document.pdf") -> Tuple[str, Dict]:
        """Extract text from PDF bytes (for file uploads)"""
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            text, metadata = self.extract_pdf(tmp_path)
            metadata['original_filename'] = filename
            return text, metadata
        finally:
            os.unlink(tmp_path)
    
    # ============== URL SCRAPING ==============

    async def scrape_url(self, url: str) -> Tuple[str, Dict]:
        """
        Scrape content from a URL using Crawl4AI 0.8.x.
        Returns clean, LLM-ready markdown + metadata.
        Falls back to httpx+BeautifulSoup if crawl4ai is not installed.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

            browser_config = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
            run_config = CrawlerRunConfig()

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                raise RuntimeError(f"Crawl4AI failed for {url}: {result.error_message}")

            metadata = {
                'url': url,
                'title': (result.metadata or {}).get('title', '') or url,
                'scraped_at': datetime.utcnow().isoformat(),
                'scraper': 'crawl4ai',
            }

            # result.markdown is StringCompatibleMarkdown (str subclass) in 0.8.x
            # .fit_markdown gives the focused/pruned version; fall back to raw
            md = result.markdown
            text = (md.fit_markdown if md else None) or (str(md) if md else '') or ''
            return text, metadata

        except ImportError:
            return await self._scrape_url_fallback(url)

    async def _scrape_url_fallback(self, url: str) -> Tuple[str, Dict]:
        """Legacy httpx+BeautifulSoup fallback (static pages only)."""
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        text = soup.get_text(separator='\n', strip=True)

        title = soup.find('title')
        metadata = {
            'url': url,
            'title': title.string if title else '',
            'scraped_at': datetime.utcnow().isoformat(),
            'scraper': 'httpx_fallback',
        }

        return text, metadata

    async def scrape_urls_bulk(
        self,
        urls: List[str],
        max_concurrent: int = 5
    ) -> List[Tuple[str, Dict]]:
        """
        Crawl multiple URLs in parallel using Crawl4AI 0.8.x.
        Ideal for bulk-ingesting supplier documentation sites.

        Args:
            urls: List of URLs to crawl
            max_concurrent: Parallel crawlers running at once (via SemaphoreDispatcher)

        Returns:
            List of (markdown_text, metadata) tuples, one per URL.
            Failed URLs return ('', metadata_with_error).
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
            from crawl4ai.async_dispatcher import SemaphoreDispatcher

            browser_config = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
            run_config = CrawlerRunConfig()
            dispatcher = SemaphoreDispatcher(semaphore_count=max_concurrent)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = await crawler.arun_many(
                    urls=urls,
                    config=run_config,
                    dispatcher=dispatcher,
                )

            output = []
            for result in results:
                url = result.url
                if result.success:
                    md = result.markdown
                    text = (md.fit_markdown if md else None) or (str(md) if md else '') or ''
                    metadata = {
                        'url': url,
                        'title': (result.metadata or {}).get('title', '') or url,
                        'scraped_at': datetime.utcnow().isoformat(),
                        'scraper': 'crawl4ai_bulk',
                    }
                else:
                    print(f"[Ingestion] Crawl4AI failed for {url}: {result.error_message}")
                    text = ''
                    metadata = {
                        'url': url,
                        'title': url,
                        'scraped_at': datetime.utcnow().isoformat(),
                        'error': result.error_message,
                    }
                output.append((text, metadata))

            return output

        except ImportError:
            import asyncio
            print("[Ingestion] crawl4ai not installed — falling back to sequential scraping")
            tasks = [self._scrape_url_fallback(u) for u in urls]
            return await asyncio.gather(*tasks, return_exceptions=False)
    
    # ============== EMBEDDING GENERATION ==============
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector using Ollama (nomic-embed-text)"""
        import httpx
        
        try:
            # Use Ollama for embeddings (local, free)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text[:8000]  # Truncate if too long
                    },
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [0.0] * 768)
                
        except Exception as e:
            print(f"[Embedding] Ollama error: {e}")
            print("[Embedding] Make sure Ollama is running and nomic-embed-text is pulled:")
            print("           ollama pull nomic-embed-text")
            # Return zero vector as fallback (768 dimensions for nomic-embed-text)
            return [0.0] * 768
    
    async def generate_embeddings_batch(self, texts: List[str], concurrency: int = 5) -> List[List[float]]:
        """Generate embeddings for multiple texts using Ollama with parallel processing.
        
        Args:
            texts: List of text chunks to embed
            concurrency: Number of parallel embedding requests (default 5)
        
        Returns:
            List of embedding vectors
        """
        import asyncio
        
        all_embeddings = []
        total = len(texts)
        
        # Process in parallel batches for ~5x speed improvement
        for i in range(0, total, concurrency):
            batch = texts[i:i + concurrency]
            batch_num = i // concurrency + 1
            total_batches = (total + concurrency - 1) // concurrency
            
            print(f"[Embedding] Batch {batch_num}/{total_batches} ({i+1}-{min(i+len(batch), total)}/{total} chunks)...")
            
            # Run embeddings in parallel
            batch_embeddings = await asyncio.gather(*[
                self.generate_embedding(text) for text in batch
            ])
            
            all_embeddings.extend(batch_embeddings)
        
        print(f"[Embedding] Complete: {total} chunks processed")
        return all_embeddings
    
    # ============== FULL INGESTION PIPELINE ==============
    
    async def ingest_document(
        self,
        content: str,
        title: str,
        source_type: str,
        source_url: str = None,
        source_filename: str = None,
        brands: List[str] = None,
        product_types: List[str] = None,
        transmission_codes: List[str] = None,
        tags: List[str] = None,
        db_session = None
    ) -> Dict:
        """
        Full pipeline to ingest a document:
        1. Chunk the text
        2. Generate embeddings
        3. Store in database
        4. Store in Qdrant
        """
        from app.models.library import Document, DocumentChunk
        from app.services.qdrant_service import qdrant_service
        
        # Generate document ID
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Step 1: Chunk the text
        print(f"[Ingestion] Chunking document: {title}")
        chunks = self.chunk_text(content)
        
        if not chunks:
            raise ValueError("Document produced no chunks after processing")
        
        print(f"[Ingestion] Created {len(chunks)} chunks")
        
        # Step 2: Generate embeddings for all chunks
        print(f"[Ingestion] Generating embeddings...")
        chunk_texts = [c['content'] for c in chunks]
        embeddings = await self.generate_embeddings_batch(chunk_texts)
        
        # Step 3: Prepare Qdrant points
        qdrant_ids = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}_chunk_{i}"
            
            # Store in Qdrant
            payload = {
                'document_id': doc_id,
                'document_title': title,
                'chunk_index': i,
                'content': chunk['content'],
                'brands': brands or [],
                'product_types': product_types or [],
                'transmission_codes': transmission_codes or [],
                'source_type': source_type
            }
            
            point_id = qdrant_service.insert_part(embedding, payload)
            qdrant_ids.append(point_id)
            chunks[i]['qdrant_id'] = point_id
        
        print(f"[Ingestion] Stored {len(qdrant_ids)} vectors in Qdrant")
        
        # Step 4: Store in database if session provided
        if db_session:
            document = Document(
                id=doc_id,
                title=title,
                content=content,
                content_preview=content[:500] if content else '',
                source_type=source_type,
                source_url=source_url,
                source_filename=source_filename,
                brands=brands or [],
                product_types=product_types or [],
                transmission_codes=transmission_codes or [],
                tags=tags or [],
                chunk_count=len(chunks),
                qdrant_ids=qdrant_ids,
                embedding_model=settings.EMBEDDING_MODEL
            )
            db_session.add(document)
            
            # Add chunks
            for chunk in chunks:
                db_chunk = DocumentChunk(
                    id=f"{doc_id}_chunk_{chunk['index']}",
                    document_id=doc_id,
                    chunk_index=chunk['index'],
                    content=chunk['content'],
                    token_count=chunk['token_count'],
                    qdrant_id=chunk.get('qdrant_id')
                )
                db_session.add(db_chunk)
            
            db_session.commit()
            print(f"[Ingestion] Saved document to database: {doc_id}")
        
        return {
            'document_id': doc_id,
            'title': title,
            'chunk_count': len(chunks),
            'qdrant_ids': qdrant_ids,
            'source_type': source_type
        }
    
    async def ingest_pdf_upload(
        self,
        file_bytes: bytes,
        filename: str,
        brands: List[str] = None,
        product_types: List[str] = None,
        transmission_codes: List[str] = None,
        db_session = None
    ) -> Dict:
        """Convenience method for PDF uploads"""
        # Extract text from PDF
        text, metadata = self.extract_pdf_from_bytes(file_bytes, filename)
        
        title = metadata.get('title') or filename.replace('.pdf', '')
        
        return await self.ingest_document(
            content=text,
            title=title,
            source_type='uploaded_pdf',
            source_filename=filename,
            brands=brands,
            product_types=product_types,
            transmission_codes=transmission_codes,
            db_session=db_session
        )
    
    async def ingest_from_url(
        self,
        url: str,
        brands: List[str] = None,
        product_types: List[str] = None,
        transmission_codes: List[str] = None,
        db_session = None
    ) -> Dict:
        """Convenience method for URL scraping"""
        text, metadata = await self.scrape_url(url)

        title = metadata.get('title') or url

        return await self.ingest_document(
            content=text,
            title=title,
            source_type='scraped',
            source_url=url,
            brands=brands,
            product_types=product_types,
            transmission_codes=transmission_codes,
            db_session=db_session
        )

    async def ingest_from_urls_bulk(
        self,
        urls: List[str],
        brands: List[str] = None,
        product_types: List[str] = None,
        transmission_codes: List[str] = None,
        max_concurrent: int = 5,
        db_session = None
    ) -> List[Dict]:
        """
        Bulk ingest multiple URLs into the RAG knowledge base.
        Uses Crawl4AI parallel crawling for speed.

        Args:
            urls: List of URLs to scrape and ingest
            brands / product_types / transmission_codes: Applied to all documents
            max_concurrent: Parallel Crawl4AI workers
            db_session: SQLAlchemy session for DB persistence

        Returns:
            List of ingest results, one per URL (skips empty pages).
        """
        print(f"[Ingestion] Bulk crawling {len(urls)} URLs (max_concurrent={max_concurrent})")

        scraped = await self.scrape_urls_bulk(urls, max_concurrent=max_concurrent)

        results = []
        for text, metadata in scraped:
            url = metadata.get('url', '')
            if not text.strip():
                print(f"[Ingestion] Skipping empty page: {url}")
                continue
            try:
                result = await self.ingest_document(
                    content=text,
                    title=metadata.get('title') or url,
                    source_type='scraped_bulk',
                    source_url=url,
                    brands=brands,
                    product_types=product_types,
                    transmission_codes=transmission_codes,
                    db_session=db_session
                )
                results.append(result)
            except Exception as e:
                print(f"[Ingestion] Failed to ingest {url}: {e}")

        print(f"[Ingestion] Bulk ingestion complete: {len(results)}/{len(urls)} pages ingested")
        return results
    
    # ============== RAG RETRIEVAL ==============
    
    async def retrieve_rag_context(
        self,
        product_title: str,
        brands: List[str] = None,
        transmission_codes: List[str] = None,
        product_types: List[str] = None,
        document_ids: List[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant document chunks from Qdrant for RAG-powered content generation.
        
        Args:
            product_title: The product name/title to search for
            brands: Optional list of brands to filter by
            transmission_codes: Optional transmission codes to filter
            product_types: Optional product types to filter
            document_ids: Optional specific document IDs to restrict search to
            limit: Number of chunks to retrieve
            
        Returns:
            List of relevant document chunks with their content and metadata
        """
        from app.services.qdrant_service import qdrant_service
        
        # Build search query from product info
        search_query = product_title
        if brands:
            search_query += f" {' '.join(brands)}"
        if transmission_codes:
            search_query += f" {' '.join(transmission_codes)}"
        if product_types:
            search_query += f" {' '.join(product_types)}"
        
        print(f"[RAG] Searching for context: {search_query[:100]}...")
        
        # Generate embedding for the search query
        query_embedding = await self.generate_embedding(search_query)
        
        # Check if embedding was generated successfully (not a zero vector)
        if sum(query_embedding) == 0:
            print("[RAG] Warning: Zero embedding returned, skipping search")
            return []
        
        # Search Qdrant for relevant chunks
        try:
            # Simple vector search without filters to avoid index requirements
            results = qdrant_service.search_parts(
                query_vector=query_embedding,
                limit=limit
                # Filters removed to avoid Qdrant index errors
            )
            
            print(f"[RAG] Found {len(results)} relevant chunks")
            
            # Format results for LLM context
            context_chunks = []
            for result in results:
                payload = result.get('payload', {})
                context_chunks.append({
                    'content': payload.get('content', payload.get('text', '')),
                    'source': payload.get('source_filename', payload.get('source_url', 'Unknown')),
                    'brands': payload.get('brands', []),
                    'transmission_codes': payload.get('transmission_codes', []),
                    'score': result.get('score', 0),
                    'supplier': payload.get('supplier', ''),
                    'product_name': payload.get('product_name', ''),
                    'part_number': payload.get('part_number', ''),
                    'specifications': payload.get('specifications', {}),
                    'compatible_vehicles': payload.get('compatible_vehicles', [])
                })
            
            return context_chunks
            
        except Exception as e:
            print(f"[RAG] Error searching Qdrant: {e}")
            return []


# Singleton instance
document_ingestion_service = DocumentIngestionService()

"""
Web Search Service for supplementing RAG when documentation is sparse.
Uses Serper API for Google Search.
"""
import httpx
from typing import List, Dict, Optional
from app.core.config import settings


class WebSearchService:
    """Service for web search to supplement RAG context"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'SERPER_API_KEY', None)
        self.api_url = "https://google.serper.dev/search"
    
    def is_configured(self) -> bool:
        """Check if Serper API is configured"""
        return bool(self.api_key)
    
    async def search(self, query: str, num_results: int = 5) -> List[Dict]:
        """
        Perform a web search and return results.
        
        Args:
            query: Search query (e.g., "ZF8HP45 transmission filter specifications")
            num_results: Number of results to return
            
        Returns:
            List of search results with title, snippet, link
        """
        if not self.is_configured():
            print("[WebSearch] Serper API not configured - skipping web search")
            return []
        
        try:
            payload = {
                "q": query,
                "num": num_results,
                "gl": "mx",  # Mexico region
                "hl": "es"   # Spanish language
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                print(f"[WebSearch] Searching: {query[:80]}...")
                response = await client.post(
                    self.api_url,
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code != 200:
                    print(f"[WebSearch] Error: {response.status_code} - {response.text[:200]}")
                    return []
                
                data = response.json()
                results = []
                
                # Extract organic results
                for item in data.get("organic", [])[:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                        "source": "web_search"
                    })
                
                print(f"[WebSearch] Found {len(results)} results")
                return results
                
        except Exception as e:
            print(f"[WebSearch] Error: {e}")
            return []
    
    def format_for_context(self, results: List[Dict]) -> str:
        """
        Format web search results as context for the LLM prompt.
        
        Args:
            results: List of search results
            
        Returns:
            Formatted string to add to prompt context
        """
        if not results:
            return ""
        
        context = "\n\n=== INFORMACIÓN DE BÚSQUEDA WEB ===\n"
        context += "(Contexto adicional de internet para complementar la base de conocimiento)\n\n"
        
        for i, result in enumerate(results, 1):
            context += f"Fuente {i}: {result['title']}\n"
            context += f"  {result['snippet']}\n"
            context += f"  URL: {result['link']}\n\n"
        
        return context


# Singleton instance
web_search_service = WebSearchService()

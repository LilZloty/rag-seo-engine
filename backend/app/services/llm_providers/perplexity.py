"""
Perplexity AI Provider

Implements the BaseLLMProvider interface for Perplexity's API.
Uses OpenAI-compatible API format.
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("perplexity")
class PerplexityProvider(BaseLLMProvider):
    """Perplexity AI API provider - uses OpenAI-compatible API"""
    
    provider_name = "perplexity"
    API_URL = "https://api.perplexity.ai/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'PERPLEXITY_API_KEY', None)
        self.model = model or getattr(settings, 'PERPLEXITY_MODEL', 'llama-3.1-sonar-large-128k-online')
        super().__init__(api_key=self.api_key, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate Perplexity configuration"""
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not configured - provider may not work")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,  # Perplexity may not support JSON mode reliably
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """Generate content using Perplexity AI"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 2048
        }
        
        # Perplexity-specific options
        if kwargs.get('return_citations', False):
            payload['return_citations'] = True
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"[Perplexity] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            result = response.json()
            content_text = result["choices"][0]["message"]["content"]
            
            # Return with citations if available
            citations = result.get("citations", [])
            
            if json_mode:
                try:
                    return self._parse_json_response(content_text)
                except:
                    return {"content": content_text, "citations": citations}
            
            return {"content": content_text, "citations": citations}
    
    async def check_connection(self) -> bool:
        """Check if Perplexity API is accessible"""
        if not self.api_key:
            return False
        try:
            # Simple test query
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 5
                    },
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Perplexity connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
        }

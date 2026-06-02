"""
Ollama Local Provider

Implements the BaseLLMProvider interface for local Ollama instances.
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("ollama")
class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    provider_name = "ollama"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        super().__init__(api_key=None, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate Ollama configuration"""
        if not self.base_url:
            raise ValueError("OLLAMA_BASE_URL not configured")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """Generate content using local Ollama"""
        payload = {
            "model": self._get_model_name(settings.OLLAMA_MODEL),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "stream": False
        }
        
        if json_mode:
            payload["format"] = "json"
        
        async with httpx.AsyncClient(timeout=180.0) as client:  # Longer timeout for local
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"[Ollama] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            response.raise_for_status()
            result = response.json()
            content_text = result.get("message", {}).get("content", "")
            
            if not json_mode:
                return {"content": content_text}
                
            return self._parse_json_response(content_text)
    
    async def check_connection(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama connection check failed: {e}")
            return False
    
    async def list_models(self) -> list:
        """List available Ollama models"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
                return []
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.base_url),
            "api_url": self.base_url,
        }

"""
X.AI Grok Provider

Implements the BaseLLMProvider interface for X.AI's Grok API.
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("grok")
@LLMProviderFactory.register("xai")
class GrokProvider(BaseLLMProvider):
    """X.AI Grok API provider"""
    
    provider_name = "grok"
    API_URL = "https://api.x.ai/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.XAI_API_KEY
        self.model = model or settings.XAI_MODEL
        super().__init__(api_key=self.api_key, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate Grok configuration"""
        if not self.api_key:
            logger.warning("XAI_API_KEY not configured - provider may not work")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.5,
        enable_search: bool = False,
        **kwargs
    ) -> Dict:
        """Generate content using Grok"""
        # Allow model override via kwargs (used by multi-pass analysis)
        model_override = kwargs.get('model') or kwargs.get('model_name')
        model_name = model_override or self.model or settings.XAI_MODEL
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "top_p": 0.95,
            "stream": False
        }
        
        # Force JSON mode if requested (X.AI supports response_format)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            logger.debug("[Grok] JSON mode enabled via response_format")
        
        # Longer timeout for 4.20 models (2M context, deeper reasoning)
        request_timeout = 300.0 if '4.20' in model_name or '4-20' in model_name else 120.0
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"[Grok] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            response.raise_for_status()
            result = response.json()
            content_text = result["choices"][0]["message"]["content"]
            
            if not json_mode:
                return {"content": content_text}
                
            return self._parse_json_response(content_text)
    
    async def check_connection(self) -> bool:
        """Check if Grok API is accessible"""
        try:
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
            logger.error(f"Grok connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
        }

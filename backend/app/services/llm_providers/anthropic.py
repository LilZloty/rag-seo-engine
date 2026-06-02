"""
Anthropic Claude Provider

Implements the BaseLLMProvider interface for Anthropic's Claude API.
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("anthropic")
class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider"""
    
    provider_name = "anthropic"
    API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        super().__init__(api_key=self.api_key, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate Anthropic configuration"""
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured - provider may not work")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """Generate content using Anthropic Claude"""
        payload = {
            "model": self._get_model_name(settings.ANTHROPIC_MODEL),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"[Claude] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            response.raise_for_status()
            result = response.json()
            content_text = result["content"][0]["text"]
            
            if not json_mode:
                return {"content": content_text}
                
            return self._parse_json_response(content_text)
    
    async def check_connection(self) -> bool:
        """Check if Anthropic API is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": self.api_key},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Anthropic connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
        }

"""
OpenAI GPT Provider

Implements the BaseLLMProvider interface for OpenAI's GPT API.
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("openai")
class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT API provider"""
    
    provider_name = "openai"
    API_URL = "https://api.openai.com/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        super().__init__(api_key=self.api_key, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate OpenAI configuration"""
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not configured - provider may not work")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """Generate content using OpenAI GPT"""
        payload = {
            "model": self._get_model_name(settings.OPENAI_MODEL),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
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
                error_msg = f"[OpenAI] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            response.raise_for_status()
            result = response.json()
            content_text = result["choices"][0]["message"]["content"]
            
            if not json_mode:
                return {"content": content_text}
                
            return self._parse_json_response(content_text)
    
    async def check_connection(self) -> bool:
        """Check if OpenAI API is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
        }

"""
Kimi (Moonshot AI) Provider

Implements the BaseLLMProvider interface for Moonshot AI's Kimi API.
Uses OpenAI-compatible endpoint at api.moonshot.ai/v1.

Models available:
- kimi-k2.5: Latest multimodal with 1T params (32B active)
- kimi-k2-turbo-preview: Faster turbo variant
- moonshot-v1-auto: Auto-select best model

Ref: https://platform.moonshot.ai/docs
"""

import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("kimi")
class KimiProvider(BaseLLMProvider):
    """Moonshot Kimi API provider (OpenAI-compatible)"""
    
    provider_name = "kimi"
    # Kimi Code API endpoint (for sk-kimi-* keys)
    API_URL = "https://api.kimi.com/coding/v1/chat/completions"
    MODELS_URL = "https://api.kimi.com/coding/v1/models"
    
    # Available models with descriptions
    AVAILABLE_MODELS = {
        "kimi-k2.5": "Kimi K2.5 - 1T MoE model, multimodal, 256K context",
        "kimi-k2-turbo-preview": "Kimi K2 Turbo - Fast reasoning model",
        "moonshot-v1-auto": "Auto-select optimal model",
        "moonshot-v1-8k": "Moonshot V1 with 8K context",
        "moonshot-v1-32k": "Moonshot V1 with 32K context",
        "moonshot-v1-128k": "Moonshot V1 with 128K context",
    }
    
    DEFAULT_MODEL = "kimi-k2.5"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'KIMI_API_KEY', None)
        self.model = model or getattr(settings, 'KIMI_MODEL', self.DEFAULT_MODEL)
        super().__init__(api_key=self.api_key, model=self.model)
    
    def _validate_config(self) -> None:
        """Validate Kimi configuration"""
        if not self.api_key:
            logger.warning("KIMI_API_KEY not configured - provider may not work")
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """
        Generate content using Kimi K2.5.
        
        Kimi supports extended thinking for complex reasoning tasks.
        """
        model = self._get_model_name(self.DEFAULT_MODEL)
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
        }
        
        # Add JSON response format if supported (k2.5 supports it)
        if json_mode and ("k2" in model or "moonshot" in model):
            payload["response_format"] = {"type": "json_object"}
        
        logger.info(f"[Kimi] Calling {model} with {len(user_prompt)} chars")
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"[Kimi] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            result = response.json()
            
            # Extract content from response
            message = result.get("choices", [{}])[0].get("message", {})
            content_text = message.get("content", "")
            
            # Log token usage if available
            usage = result.get("usage", {})
            if usage:
                logger.info(
                    f"[Kimi] Tokens - input: {usage.get('prompt_tokens', 0)}, "
                    f"output: {usage.get('completion_tokens', 0)}"
                )
            
            if not json_mode:
                return {"content": content_text}
                
            return self._parse_json_response(content_text)
    
    async def check_connection(self) -> bool:
        """Check if Kimi API is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.MODELS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Kimi connection check failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
            "available_models": list(self.AVAILABLE_MODELS.keys()),
        }

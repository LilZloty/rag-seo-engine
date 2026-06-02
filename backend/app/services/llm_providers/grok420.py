"""
Grok 4.20 Provider - Native Multi-Agent

Uses X.AI's dedicated grok-4.20-multi-agent-0309 model via the Responses API.
Single API call — multi-agent reasoning handled natively by the model.
"""

import httpx
from typing import Dict, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import BaseLLMProvider, LLMProviderFactory

logger = get_logger(__name__)


@LLMProviderFactory.register("grok420")
class Grok420Provider(BaseLLMProvider):
    """Grok 4.20 native multi-agent provider via Responses API."""

    provider_name = "grok420"
    API_URL = "https://api.x.ai/v1/responses"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.XAI_API_KEY
        self.model = model or settings.XAI_GROK420_MODEL
        super().__init__(api_key=self.api_key, model=self.model)

    def _validate_config(self) -> None:
        if not self.api_key:
            logger.warning("XAI_API_KEY not configured - grok420 provider may not work")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.5,
        task_type: str = "general",
        **kwargs,
    ) -> Dict:
        """Generate content using Grok 4.20 native multi-agent model."""
        # Responses API uses 'input' with instructions instead of messages
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "temperature": temperature,
            "stream": False,
        }

        if json_mode:
            payload["text"] = {"format": {"type": "json_object"}}

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code != 200:
                error_msg = f"[Grok420] Error {response.status_code}: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(error_msg)

            result = response.json()

            # Responses API returns output as array of message objects
            content_text = ""
            for output_item in result.get("output", []):
                if output_item.get("type") == "message":
                    for content_block in output_item.get("content", []):
                        if content_block.get("type") == "output_text":
                            content_text += content_block.get("text", "")

            if not content_text:
                raise Exception("[Grok420] No text content in response")

            if not json_mode:
                return {"content": content_text}

            parsed = self._parse_json_response(content_text)
            parsed["_multi_agent"] = {
                "mode": "native",
                "model": self.model,
                "agents_used": [self.model],
                "consensus_score": 100.0,
                "task_type": task_type,
            }
            return parsed

    async def check_connection(self) -> bool:
        """Check if the Grok 4.20 multi-agent model is accessible."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": "test",
                        "max_output_tokens": 5,
                    },
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Grok420 connection check failed: {e}")
            return False

    def get_status(self) -> Dict:
        return {
            "provider": self.provider_name,
            "model": self.model,
            "configured": bool(self.api_key),
            "api_url": self.API_URL,
        }

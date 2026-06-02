"""
Base LLM Provider Interface

Abstract base class for all LLM providers to ensure consistent API.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    provider_name: str = "base"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self._validate_config()
    
    @property
    def name(self) -> str:
        """Return the provider name (instance property for compatibility)"""
        return self.provider_name
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        pass
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        **kwargs
    ) -> Dict:
        """
        Generate content from the LLM.
        
        Args:
            system_prompt: System instructions
            user_prompt: User message
            json_mode: If True, parses response as JSON. If False, returns raw string in a dict.
            **kwargs: Provider-specific options
        
        Returns:
            Dict containing the generated content (parsed from JSON or as raw text)
        """
        pass
    
    @abstractmethod
    async def check_connection(self) -> bool:
        """Check if the provider is available"""
        pass
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks"""
        import json
        import re
        
        # Strip markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Try to find JSON object in the text
        if not content.strip().startswith("{"):
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from {self.provider_name} response",
                extra={"error": str(e), "content_preview": content[:200]}
            )
            raise ValueError(f"Invalid JSON response from {self.provider_name}: {e}")
    
    def _get_model_name(self, default: str) -> str:
        """Get the model name to use, preferring instance model over default"""
        return self.model or default


class LLMProviderFactory:
    """Factory for creating LLM provider instances"""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, provider_name: str):
        """Decorator to register a provider"""
        def decorator(provider_class: type):
            cls._providers[provider_name.lower()] = provider_class
            return provider_class
        return decorator
    
    @classmethod
    def create(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> BaseLLMProvider:
        """Create a provider instance by name"""
        provider_class = cls._providers.get(provider_name.lower())
        
        if not provider_class:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        
        return provider_class(api_key=api_key, model=model)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered providers"""
        return list(cls._providers.keys())
    
    @classmethod
    def is_registered(cls, provider_name: str) -> bool:
        """Check if a provider is registered"""
        return provider_name.lower() in cls._providers


# Registry for auto-discovery
_known_providers = [
    "anthropic",
    "openai", 
    "grok",
    "ollama",
    "minimax",
    "mistral",
    "kimi",
]


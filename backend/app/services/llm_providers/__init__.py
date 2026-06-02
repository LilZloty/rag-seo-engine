"""
LLM Providers Module

Modular LLM providers with factory pattern for easy switching and testing.

Providers:
- AnthropicProvider: Claude API (recommended for quality)
- OpenAIProvider: GPT-4 API
- GrokProvider: X.AI Grok API
- Grok420Provider: X.AI Grok 4.20 Multi-Agent Architecture
- OllamaProvider: Local Ollama instance
- KimiProvider: Moonshot AI Kimi K2.5 (OpenAI-compatible)
- PerplexityProvider: Perplexity AI with online search
"""

from .base import BaseLLMProvider, LLMProviderFactory
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .grok import GrokProvider
from .grok420 import Grok420Provider
from .ollama import OllamaProvider
from .kimi import KimiProvider
from .perplexity import PerplexityProvider

__all__ = [
    "BaseLLMProvider",
    "LLMProviderFactory",
    "AnthropicProvider",
    "OpenAIProvider",
    "GrokProvider",
    "Grok420Provider",
    "OllamaProvider",
    "KimiProvider",
    "PerplexityProvider",
]

# Auto-import all providers to register them with the factory
_providers = [
    AnthropicProvider,
    OpenAIProvider,
    GrokProvider,
    Grok420Provider,
    OllamaProvider,
    KimiProvider,
    PerplexityProvider,
]



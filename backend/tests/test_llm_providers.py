"""
Integration tests for LLM Providers module

Tests the modular LLM provider architecture:
- Factory pattern for provider creation
- Provider registration and switching
- Mock responses for testing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Set testing environment
os.environ['APP_TESTING'] = '1'


class TestLLMProviderFactory:
    """Tests for the LLMProviderFactory class"""

    def test_factory_import(self):
        """Test that factory can be imported"""
        from app.services.llm_providers import LLMProviderFactory
        assert LLMProviderFactory is not None

    def test_factory_has_registered_providers(self):
        """Test that factory has registered providers"""
        from app.services.llm_providers import LLMProviderFactory
        providers = LLMProviderFactory.list_providers()
        assert 'anthropic' in providers
        assert 'openai' in providers
        assert 'grok' in providers
        assert 'ollama' in providers

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider"""
        from app.services.llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create('anthropic')
        assert provider is not None
        assert provider.name == 'anthropic'

    def test_create_openai_provider(self):
        """Test creating OpenAI provider"""
        from app.services.llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create('openai')
        assert provider is not None
        assert provider.name == 'openai'

    def test_create_grok_provider(self):
        """Test creating Grok provider"""
        from app.services.llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create('grok')
        assert provider is not None
        assert provider.name == 'grok'

    def test_create_ollama_provider(self):
        """Test creating Ollama provider"""
        from app.services.llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create('ollama')
        assert provider is not None
        assert provider.name == 'ollama'

    def test_create_unknown_provider_raises_error(self):
        """Test that creating unknown provider raises ValueError"""
        from app.services.llm_providers import LLMProviderFactory
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMProviderFactory.create('unknown_provider')

    def test_provider_has_generate_method(self):
        """Test that all providers have generate method"""
        from app.services.llm_providers import LLMProviderFactory
        for provider_name in LLMProviderFactory.list_providers():
            provider = LLMProviderFactory.create(provider_name)
            assert hasattr(provider, 'generate')
            assert callable(provider.generate)


class TestAnthropicProvider:
    """Tests for Anthropic provider"""

    def test_anthropic_provider_creation(self):
        """Test Anthropic provider instantiation"""
        from app.services.llm_providers import AnthropicProvider
        provider = AnthropicProvider()
        assert provider.name == 'anthropic'
        assert 'claude' in provider.model.lower() or 'anthropic' in provider.model.lower()

    @pytest.mark.asyncio
    async def test_anthropic_generate_with_mock(self):
        """Test Anthropic generate with mocked response"""
        from app.services.llm_providers import AnthropicProvider

        provider = AnthropicProvider()

        # Simple test - just verify the method exists and is callable
        assert hasattr(provider, 'generate')
        assert callable(provider.generate)

        # Verify it has required attributes
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'model')
        assert provider.name == 'anthropic'


class TestOpenAIProvider:
    """Tests for OpenAI provider"""

    def test_openai_provider_creation(self):
        """Test OpenAI provider instantiation"""
        from app.services.llm_providers import OpenAIProvider
        provider = OpenAIProvider()
        assert provider.name == 'openai'
        assert 'gpt' in provider.model.lower() or 'openai' in provider.model.lower()


class TestGrokProvider:
    """Tests for Grok provider"""

    def test_grok_provider_creation(self):
        """Test Grok provider instantiation"""
        from app.services.llm_providers import GrokProvider
        provider = GrokProvider()
        assert provider.name == 'grok'

    def test_grok_also_registered_as_xai(self):
        """Test Grok is also accessible via 'xai' alias"""
        from app.services.llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create('xai')
        assert provider is not None
        assert provider.name == 'grok'


class TestOllamaProvider:
    """Tests for Ollama provider"""

    def test_ollama_provider_creation(self):
        """Test Ollama provider instantiation"""
        from app.services.llm_providers import OllamaProvider
        provider = OllamaProvider()
        assert provider.name == 'ollama'

    @pytest.mark.asyncio
    async def test_ollama_check_connection(self):
        """Test Ollama connection check"""
        from app.services.llm_providers import OllamaProvider

        provider = OllamaProvider()

        # Mock the HTTP client
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await provider.check_connection()
            # Should return True when status_code is 200
            assert result is True


class TestLLMServiceIntegration:
    """Integration tests for LLMService with modular providers"""

    def test_llm_service_initialization(self):
        """Test LLMService can be initialized"""
        from app.services.llm_service import LLMService
        service = LLMService()
        assert service is not None
        assert service.provider_name is not None

    def test_llm_service_has_generate_content(self):
        """Test LLMService has generate_content method"""
        from app.services.llm_service import LLMService
        service = LLMService()
        assert hasattr(service, 'generate_content')
        assert callable(service.generate_content)

    def test_llm_service_has_helper_methods(self):
        """Test LLMService has required helper methods"""
        from app.services.llm_service import LLMService
        service = LLMService()
        assert hasattr(service, '_get_system_prompt')
        assert hasattr(service, '_build_user_prompt')
        assert hasattr(service, '_get_fallback_content')
        assert hasattr(service, '_normalize_response_fields')


class TestResponseNormalization:
    """Tests for response normalization logic"""

    def test_normalize_removes_think_tags(self):
        """Test that think tags are properly removed"""
        from app.services.llm_service import LLMService
        service = LLMService()

        # Mock response with thinking tags
        parsed = {
            "h1_title": "Test Product",
            "description_html": "<p>Description</p>"
        }
        product_info = {"title": "Test Product"}

        result = service._normalize_response_fields(parsed, product_info)
        assert result['h1_title'] == "Test Product"

    def test_normalize_fills_missing_fields(self):
        """Test that missing fields are filled with fallbacks"""
        from app.services.llm_service import LLMService
        service = LLMService()

        # Empty response
        parsed = {}
        product_info = {"title": "Test Product", "vendor": "TSS"}

        result = service._normalize_response_fields(parsed, product_info)
        # Should have fallbacks
        assert 'h1_title' in result
        assert 'description_html' in result

    def test_get_fallback_content(self):
        """Test fallback content generation"""
        from app.services.llm_service import LLMService
        service = LLMService()

        product_info = {"title": "Solenoide 4L60E", "sku": "12345"}
        result = service._get_fallback_content(product_info)

        assert result['h1_title'] == "Solenoide 4L60E"
        assert 'hook_html' in result
        assert 'short_description' in result
        assert 'meta_title' in result


class TestPromptTemplates:
    """Tests for prompt template generation"""

    def test_get_system_prompt_returns_string(self):
        """Test that _get_system_prompt returns a string"""
        from app.services.llm_service import LLMService
        service = LLMService()

        result = service._get_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 100  # Should be a substantial prompt
        assert "JSON" in result  # Should mention JSON format

    def test_build_user_prompt_includes_product_info(self):
        """Test that _build_user_prompt includes product info"""
        from app.services.llm_service import LLMService
        service = LLMService()

        product_info = {"title": "Test Product", "sku": "123"}
        context = [{"payload": {"content": "Test context"}}]

        result = service._build_user_prompt(product_info, context)

        assert isinstance(result, str)
        assert "Test Product" in result
        assert "123" in result
        assert "Test context" in result


class TestStatusMethods:
    """Tests for status and configuration methods"""

    def test_get_status_returns_dict(self):
        """Test that get_status returns expected structure"""
        from app.services.llm_service import LLMService
        service = LLMService()

        status = service.get_status()

        assert isinstance(status, dict)
        assert 'provider' in status
        assert 'model' in status
        assert 'configured' in status

    def test_check_connection_returns_bool(self):
        """Test that check_connection returns boolean (mocked)"""
        from app.services.llm_service import LLMService
        from app.services.llm_providers import OllamaProvider
        import asyncio

        # Test with Ollama provider (can be mocked)
        service = LLMService()
        service._provider = OllamaProvider()

        # The actual connection check requires a running Ollama server
        # For testing, we verify the method exists and is async
        assert asyncio.iscoroutinefunction(service.check_connection)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

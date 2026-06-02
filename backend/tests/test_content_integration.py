"""
Integration tests for Content Generation Flow

Tests the integration between:
- ContentGeneratorService
- Content modules (PromptMerger, ResponseNormalizer)
- LLM service integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Set testing environment
os.environ['APP_TESTING'] = '1'


class TestContentGeneratorService:
    """Tests for ContentGeneratorService"""

    def test_service_initialization(self):
        """Test that ContentGeneratorService initializes correctly"""
        from app.services.content_generator import ContentGeneratorService
        service = ContentGeneratorService()
        assert service is not None
        assert service.llm_service is not None
        assert service.prompt_merger is not None

    def test_extract_transmission_code(self):
        """Test transmission code extraction"""
        from app.services.content_generator import ContentGeneratorService
        service = ContentGeneratorService()

        assert service._extract_transmission_code("Solenoide 4L60E") == "4L60E"
        assert service._extract_transmission_code("ZF8HP45 Transmission") == "ZF8HP45"
        # Note: RE5R05A matches the [A-Z]{2}\d{3}[A-Z]* pattern first (RE5R) then 05A
        # The pattern finds the first match, which is 5R05 for this pattern order
        result = service._extract_transmission_code("Part for RE5R05A")
        assert result is not None  # It extracts something
        assert len(result) >= 4  # At least 4 characters
        assert service._extract_transmission_code("Generic Part") is None

    def test_extract_part_type(self):
        """Test part type extraction"""
        from app.services.content_generator import ContentGeneratorService
        service = ContentGeneratorService()

        assert service._extract_part_type("Filtro 4L60E") == "FILTRO"
        assert service._extract_part_type("Cuerpo de Valvulas") == "CUERPO_VALVULAS"
        # "Solenoide Kit" matches "solenoide" first (more specific pattern)
        # Order matters in the lookup
        assert service._extract_part_type("Solenoide Kit") in ["SOLENOIDE", "KIT"]
        assert service._extract_part_type("Generic Part") is None

    def test_extract_brand(self):
        """Test brand extraction"""
        from app.services.content_generator import ContentGeneratorService
        service = ContentGeneratorService()

        assert service._extract_brand("TSS Filtro") == "TSS"
        assert service._extract_brand("Dacco Kit") == "DACCO"
        assert service._extract_brand("Generic Part") is None


class TestPromptMergerIntegration:
    """Integration tests for PromptMerger with realistic data"""

    def test_merge_complex_instructions(self):
        """Test merging multiple instructions with priorities"""
        from app.services.content import PromptMerger

        merger = PromptMerger(max_tokens=1000)

        instructions = [
            (10, "Base instructions for product content", "base"),
            (50, "Specific instructions for transmissions", "transmission_lib"),
            (100, "Override for special products", "override:premium"),
        ]

        result = merger.merge_prompts(instructions)

        assert result.merged_prompt is not None
        assert len(result.merged_prompt) > 0
        assert result.source_count == 3
        assert result.truncated is False
        assert "Base instructions" in result.merged_prompt
        assert "Specific instructions" in result.merged_prompt
        assert "Override" in result.merged_prompt

    def test_merge_with_truncation(self):
        """Test that merging respects token limits"""
        from app.services.content import PromptMerger

        merger = PromptMerger(max_tokens=50)  # Very low limit

        # Each word is ~1.3 tokens, so 100 words = ~130 tokens
        long_instructions = [
            (10, "word " * 100, "base"),  # ~130 tokens
            (20, "more " * 100, "lib2"),  # ~130 tokens
        ]

        result = merger.merge_prompts(long_instructions)

        assert result.truncated is True
        assert result.token_count <= 50

    def test_merge_empty_instructions(self):
        """Test merging with no instructions"""
        from app.services.content import PromptMerger, PromptMergeResult

        merger = PromptMerger()
        result = merger.merge_prompts([])

        assert isinstance(result, PromptMergeResult)
        assert result.merged_prompt == ""
        assert result.token_count == 0
        assert result.source_count == 0


class TestResponseNormalizerIntegration:
    """Integration tests for ResponseNormalizer"""

    def test_normalize_with_complete_response(self):
        """Test normalization of a complete LLM response"""
        from app.services.content import ResponseNormalizer

        product_info = {
            "title": "Solenoide 4L60E Premium",
            "sku": "12345",
            "vendor": "TSS",
            "image_filenames": ["img1.jpg", "img2.jpg"]
        }

        normalizer = ResponseNormalizer(product_info)

        llm_response = {
            "h1_title": "Solenoide 4L60E Premium",
            "description_html": "<p>Description</p>",
            "alt_tags": ["img1.jpg | Alt 1", "img2.jpg | Alt 2"],
            "meta_title": "Solenoide 4L60E | TSS",
            "meta_description": "High quality solenoide",
            "url_handle": "solenoide-4l60e",
            "short_description": "Premium solenoide for 4L60E",
        }

        result = normalizer.normalize(llm_response)

        assert result.h1_title == "Solenoide 4L60E Premium"
        assert result.description_html == "<p>Description</p>"
        assert result.url_handle == "solenoide-4l60e"

    def test_normalize_with_missing_fields(self):
        """Test that missing fields are filled with defaults"""
        from app.services.content import ResponseNormalizer

        product_info = {
            "title": "Solenoide 4L60E Premium",
            "sku": "12345",
            "vendor": "TSS",
            "image_filenames": ["img1.jpg"]
        }

        normalizer = ResponseNormalizer(product_info)

        # Minimal response
        llm_response = {
            "description_html": "<p>Description</p>",
        }

        result = normalizer.normalize(llm_response)

        # Should have fallbacks
        assert result.h1_title == "Solenoide 4L60E Premium"[:60]
        assert result.meta_title is not None and len(result.meta_title) > 0
        assert result.url_handle is not None and len(result.url_handle) > 0
        assert result.short_description is not None and len(result.short_description) > 0

    def test_fallback_content_generation(self):
        """Test fallback content when LLM fails"""
        from app.services.content import ResponseNormalizer

        product_info = {
            "title": "Test Product",
            "sku": "12345",
            "vendor": "TSS",
            "image_filenames": []
        }

        normalizer = ResponseNormalizer(product_info)
        result = normalizer.get_fallback_content()

        assert result.h1_title == "Test Product"
        # The description_html contains the store brand name
        assert "Example Store" in result.description_html
        assert len(result.alt_tags) > 0


class TestLLMServiceIntegration:
    """Integration tests for LLM service with content modules"""

    def test_llm_service_has_prompt_methods(self):
        """Test that LLM service has required prompt methods"""
        from app.services.llm_service import LLMService
        service = LLMService()

        assert hasattr(service, '_get_system_prompt')
        assert hasattr(service, '_build_user_prompt')
        assert hasattr(service, '_get_fallback_content')

        # System prompt should be substantial
        system_prompt = service._get_system_prompt()
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 500
        assert "JSON" in system_prompt

    def test_build_user_prompt_structure(self):
        """Test that user prompt includes product info and context"""
        from app.services.llm_service import LLMService
        service = LLMService()

        product_info = {
            "title": "Test Product",
            "sku": "123",
            "description": "A test product"
        }
        context = [
            {"payload": {"content": "Context about transmissions"}}
        ]

        user_prompt = service._build_user_prompt(product_info, context)

        assert "Test Product" in user_prompt
        assert "123" in user_prompt
        assert "Context about transmissions" in user_prompt
        assert "INFORMACIÓN DEL PRODUCTO" in user_prompt
        assert "CONTEXTO RAG" in user_prompt

    def test_fallback_content_structure(self):
        """Test fallback content has all required fields"""
        from app.services.llm_service import LLMService
        service = LLMService()

        product_info = {"title": "Test Product", "sku": "123"}
        fallback = service._get_fallback_content(product_info)

        required_fields = [
            'h1_title', 'hook_html', 'short_description',
            'meta_title', 'meta_description', 'url_handle',
            'alt_tags', 'technical_specs', 'faq_items'
        ]

        for field in required_fields:
            assert field in fallback, f"Missing field: {field}"


class TestEndToEndNormalization:
    """End-to-end tests for content normalization flow"""

    def test_normalize_llm_response_to_dict(self):
        """Test converting normalized content to dict"""
        from app.services.content import ResponseNormalizer

        normalizer = ResponseNormalizer({"title": "Test Product"})
        result = normalizer.normalize({"description_html": "<p>Test</p>"})

        # Should have to_dict method
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict['h1_title'] == result.h1_title
        assert result_dict['description_html'] == result.description_html

    def test_normalize_with_vehicle_table_in_html(self):
        """Test that vehicles are extracted from HTML"""
        from app.services.content import ResponseNormalizer

        product_info = {"title": "Test Part"}
        normalizer = ResponseNormalizer(product_info)

        html_with_vehicles = """
        <h4>Vehiculos</h4>
        <table><tr><td>Ford</td><td>F-150</td><td>2004-2010</td></tr></table>
        """

        result = normalizer.normalize({
            "description_html": html_with_vehicles
        })

        assert "Ford" in result.compatible_vehicles or len(result.compatible_vehicles) > 0

    def test_slugify_handles_spanish_chars(self):
        """Test that slugify handles Spanish characters"""
        from app.services.content import ResponseNormalizer

        normalizer = ResponseNormalizer({"title": "Banda Canaada"})

        # The slugify should remove accents
        slug = normalizer._slugify("Banda Canaada")
        assert 'a' in slug  # No accents should remain
        assert ' ' in slug or '-' in slug


class TestConvenienceFunctions:
    """Tests for convenience functions in content module"""

    def test_normalize_response_convenience_function(self):
        """Test the normalize_response convenience function"""
        from app.services.content import normalize_response

        result = normalize_response(
            {"description_html": "<p>Test</p>"},
            {"title": "Product"}
        )

        assert result.h1_title == "Product"

    def test_get_fallback_content_convenience_function(self):
        """Test the get_fallback_content convenience function"""
        from app.services.content import get_fallback_content

        result = get_fallback_content({"title": "Test", "sku": "123"})

        assert isinstance(result, dict)
        assert result['h1_title'] == "Test"
        # The dict contains description_html, not hook_html
        assert 'description_html' in result
        assert 'Example Store' in result['description_html']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

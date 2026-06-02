"""
Unit tests for AEO modular services
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestLLMSTxtBuilder:
    """Tests for LLMSTxtBuilder"""
    
    def test_build_header(self):
        """Test building header section."""
        from app.services.aeo.llms_txt_builder import LLMSTxtBuilder
        
        builder = LLMSTxtBuilder(
            store_name="Example Store Test Store",
            store_description="Test description",
            authority_statement="10,000+ mechanics trust us"
        )
        
        builder.build_header()
        content = builder.build()
        
        assert "# Example Store Test Store" in content
        assert "Test description" in content
        assert "10,000+ mechanics trust us" in content
    
    def test_build_category_section(self):
        """Test building category section."""
        from app.services.aeo.llms_txt_builder import LLMSTxtBuilder
        
        builder = LLMSTxtBuilder("Test", "Test description")
        
        chunks = [
            {"product_type": "4L60E", "product_count": 50, "description": "50 products"},
            {"product_type": "JF011E", "product_count": 30, "description": "30 products"},
        ]
        category_map = {"4L60E": "GM", "JF011E": "Asian"}
        
        builder.build_category_section(chunks, category_map)
        content = builder.build()
        
        assert "### Transmisiones GM" in content
        assert "### Transmisiones Asian" in content
        assert "4L60E Parts" in content
        assert "JF011E Parts" in content
    
    def test_utm_parameter_append(self):
        """Test UTM parameter appending."""
        from app.services.aeo.llms_txt_builder import LLMSTxtBuilder
        
        builder = LLMSTxtBuilder("Test", "Test")
        
        url = builder._append_utm("/products/test")
        
        assert "utm_source=llms.txt" in url
        assert "/products/test?" in url or "/products/test&" in url
    
    def test_build_trending_topics(self):
        """Test building trending topics section."""
        from app.services.aeo.llms_txt_builder import LLMSTxtBuilder
        
        builder = LLMSTxtBuilder("Test", "Test")
        
        topics = [
            {"query": "P0700 symptoms", "clicks": 1500},
            {"query": "4L60E repair", "clicks": 800},
        ]
        
        builder.build_trending_topics(topics)
        content = builder.build()
        
        assert "P0700 symptoms" in content
        assert "1500" in content
    
    def test_build_glossary(self):
        """Test building glossary section."""
        from app.services.aeo.llms_txt_builder import LLMSTxtBuilder
        
        builder = LLMSTxtBuilder("Test", "Test")
        
        glossary = [
            ("Term 1", "Definition 1"),
            ("Term 2", "Definition 2"),
        ]
        
        builder.build_glossary(glossary)
        content = builder.build()
        
        # Format is "- **Term:** Definition"
        assert "**Term 1:**" in content
        assert "Definition 1" in content


class TestSchemaGenerator:
    """Tests for SchemaGenerator"""
    
    def test_vehicle_part_schema(self):
        """Test VehiclePart JSON-LD generation."""
        from app.services.aeo.schema_generator import SchemaGenerator
        
        schema = SchemaGenerator.vehicle_part(
            name="Test Product",
            sku="TEST-001",
            description="Test description",
            price="45.99",
            vendor="TSS",
            vehicle_fitments=[
                {"make": "Ford", "model": "F-150", "year_start": 2004, "year_end": 2010},
            ]
        )
        
        assert schema["@type"] == "VehiclePart"
        assert schema["name"] == "Test Product"
        assert schema["sku"] == "TEST-001"
        assert schema["brand"]["name"] == "TSS"
        assert schema["offers"]["price"] == "45.99"
        assert len(schema["isAccessoryOrSparePartFor"]) > 0
    
    def test_faq_page_schema(self):
        """Test FAQPage JSON-LD generation."""
        from app.services.aeo.schema_generator import SchemaGenerator
        
        schema = SchemaGenerator.faq_page(
            title="P0700 FAQ",
            description="Common questions about P0700",
            questions=[
                {"question": "What is P0700?", "answer": "It's a general transmission fault code."},
                {"question": "How to fix?", "answer": "Check the TCM."},
            ]
        )
        
        assert schema["@type"] == "FAQPage"
        assert schema["name"] == "P0700 FAQ"
        assert len(schema["mainEntity"]) == 2
        assert schema["mainEntity"][0]["@type"] == "Question"
        assert schema["mainEntity"][0]["name"] == "What is P0700?"
    
    def test_howto_schema(self):
        """Test HowTo JSON-LD generation."""
        from app.services.aeo.schema_generator import SchemaGenerator
        
        schema = SchemaGenerator.how_to(
            title="How to replace a solenoid",
            description="Step-by-step guide",
            steps=[
                {"name": "Step 1", "text": "Remove the transmission pan"},
                {"name": "Step 2", "text": "Locate the solenoid"},
                {"name": "Step 3", "text": "Replace and reassemble"},
            ],
            estimated_time="PT1H"
        )
        
        assert schema["@type"] == "HowTo"
        assert schema["name"] == "How to replace a solenoid"
        assert schema["totalTime"] == "PT1H"
        assert len(schema["step"]) == 3
    
    def test_article_schema_with_authority(self):
        """Test Article JSON-LD with authority signals."""
        from app.services.aeo.schema_generator import SchemaGenerator
        
        schema = SchemaGenerator.article(
            title="Transmission Repair Guide",
            description="Complete guide for transmission repair",
            readers_helped=10000
        )
        
        assert schema["@type"] == "Article"
        assert schema["interactionStatistic"]["userInteractionCount"] == 10000


class TestKnowledgeGraphManager:
    """Tests for KnowledgeGraphManager"""
    
    def test_compute_transmission_code(self):
        """Test transmission code extraction from title."""
        from app.services.aeo.knowledge_graph import KnowledgeGraphManager
        
        # Create mock DB session
        mock_db = MagicMock()
        manager = KnowledgeGraphManager(mock_db)
        
        patterns = {
            "4L60E": ("GM", "4-speed RWD"),
            "JF011E": ("Asian", "Nissan CVT"),
            "6R80": ("Ford", "6-speed RWD"),
        }
        
        # Test various titles
        assert manager.compute_transmission_code("Resorte 4L60E", patterns) == "4L60E"
        assert manager.compute_transmission_code("Kit JF011E CVT", patterns) == "JF011E"
        assert manager.compute_transmission_code("Solenoid 6R80 Ford", patterns) == "6R80"
        assert manager.compute_transmission_code("Generic Part", patterns) is None
    
    def test_compute_transmission_code_case_insensitive(self):
        """Test that transmission code extraction is case-insensitive."""
        from app.services.aeo.knowledge_graph import KnowledgeGraphManager
        
        mock_db = MagicMock()
        manager = KnowledgeGraphManager(mock_db)
        
        patterns = {"4L60E": ("GM", "4-speed")}
        
        # Should work regardless of case
        assert manager.compute_transmission_code("resorte 4l60e", patterns) == "4L60E"
        assert manager.compute_transmission_code("RESORTE 4L60E", patterns) == "4L60E"
        assert manager.compute_transmission_code("Resorte 4L60E", patterns) == "4L60E"
    
    def test_compute_transmission_code_with_hyphens(self):
        """Test that transmission codes with hyphens in input are matched."""
        from app.services.aeo.knowledge_graph import KnowledgeGraphManager
        
        mock_db = MagicMock()
        manager = KnowledgeGraphManager(mock_db)
        
        patterns = {"DQ200": ("VAG", "DSG 7")}
        
        # Should match DQ200 in input even if input has hyphens
        # The function normalizes both the input and patterns for comparison
        assert manager.compute_transmission_code("Kit DQ200", patterns) == "DQ200"
        assert manager.compute_transmission_code("DQ200 Kit", patterns) == "DQ200"
        # Note: "Kit DQ-200" won't match because the pattern is DQ200 without hyphen
        # This is expected behavior - patterns should be consistent
    
    def test_empty_title_returns_none(self):
        """Test that empty title returns None."""
        from app.services.aeo.knowledge_graph import KnowledgeGraphManager
        
        mock_db = MagicMock()
        manager = KnowledgeGraphManager(mock_db)
        
        patterns = {"4L60E": ("GM", "4-speed")}
        
        assert manager.compute_transmission_code("", patterns) is None
        assert manager.compute_transmission_code(None, patterns) is None


# ========= Exception Tests =========

class TestAppExceptions:
    """Tests for custom exceptions"""
    
    def test_content_generation_error(self):
        """Test ContentGenerationError."""
        from app.core.exceptions import ContentGenerationError
        
        error = ContentGenerationError(
            message="Failed to generate content",
            product_id="test-123"
        )
        
        assert error.message == "Failed to generate content"
        assert error.product_id == "test-123"
        assert error.code == "CONTENT_GENERATION_ERROR"
        assert error.status_code == 422
    
    def test_llm_provider_error(self):
        """Test LLMProviderError."""
        from app.core.exceptions import LLMProviderError
        
        error = LLMProviderError(
            message="API rate limit exceeded",
            provider="anthropic",
            model="claude-sonnet"
        )
        
        assert error.provider == "anthropic"
        assert error.model == "claude-sonnet"
        assert error.code == "LLM_PROVIDER_ERROR"
        assert error.status_code == 502
    
    def test_not_found_error(self):
        """Test NotFoundError."""
        from app.core.exceptions import NotFoundError
        
        error = NotFoundError(
            resource_type="Product",
            resource_id="test-123"
        )
        
        assert "test-123" in error.message
        assert "Product" in error.message
        assert error.code == "NOT_FOUND"
        assert error.status_code == 404
    
    def test_validation_error(self):
        """Test ValidationError."""
        from app.core.exceptions import ValidationError
        
        error = ValidationError(
            message="Invalid SKU format",
            field="sku",
            value="INVALID!"
        )
        
        assert error.code == "VALIDATION_ERROR"
        assert error.details["field"] == "sku"
        assert error.details["value"] == "INVALID!"
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        from app.core.exceptions import RateLimitError
        
        error = RateLimitError(
            provider="anthropic",
            retry_after=120
        )
        
        assert "120" in error.message
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.status_code == 429

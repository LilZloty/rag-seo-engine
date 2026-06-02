"""
Pytest configuration and fixtures for RAG SEO Engine tests
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


# ============ Fixtures ============

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value = session
    session.filter.return_value = session
    session.filter_by.return_value = session
    session.first.return_value = None
    session.all.return_value = []
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_product():
    """Create a mock product."""
    product = MagicMock()
    product.id = "test-product-123"
    product.shopify_id = "shopify-123"
    product.sku = "TEST-SKU-001"
    product.title = "Resorte Acumulador 1-2 Azul Transmisión 4R70W 4R75W"
    product.handle = "resorte-acumulador-1-2-azul-4r70w"
    product.vendor = "TSS"
    product.price = "45.99"
    product.transmission_code = "4R70W"
    product.seo_status = "needs_seo"
    product.total_sold = 150
    product.description = "Test product description"
    product.description_length = 200
    product.image_count = 3
    product.cached_vehicle_fitments = [
        {"make": "Ford", "model": "F-150", "year_start": 2004, "year_end": 2010},
        {"make": "Ford", "model": "Mustang", "year_start": 2005, "year_end": 2014},
    ]
    return product


@pytest.fixture
def mock_fault_code():
    """Create a mock fault code."""
    fc = MagicMock()
    fc.code = "P0700"
    fc.name = "Falla General de Transmisión"
    fc.description = "Código genérico que indica una falla en el sistema de transmisión"
    fc.severity = "high"
    fc.monthly_clicks = 1113
    fc.monthly_impressions = 40005
    fc.current_ctr = 0.0278
    fc.transmissions = ["4L60E", "6L80", "A604"]
    fc.vehicles = ["Chevrolet Silverado", "Dodge Ram"]
    fc.common_causes = ["Falla de solenoide", "Problema de cableado"]
    fc.symptoms_text = ["Luz Check Engine", "Cambios erráticos"]
    fc.blog_url = "/blogs/news/p0700"
    fc.is_priority = True
    return fc


@pytest.fixture
def sample_product_info():
    """Sample product info for testing content generation."""
    return {
        'title': 'Resorte Acumulador 1-2 Azul Transmisión 4R70W 4R75W (2004-UP)',
        'sku': '76821K',
        'handle': 'resorte-azul-acumulador-1-2-4r70w',
        'vendor': 'TSS',
        'product_type': 'Resorte',
        'description': 'Resorte acumulador de cambios para transmisión Ford 4R70W',
        'tags': ['ford', '4r70w', 'resorte', 'acumulador'],
        'image_filenames': ['76821k-1.jpg', '76821k-2.jpg'],
    }


@pytest.fixture
def sample_rag_context():
    """Sample RAG context for testing."""
    return [
        {
            'payload': {
                'content': 'El resorte azul acumulador 1-2 es un componente crítico...',
                'source_filename': 'TSS_Catalog_2024.pdf',
                'supplier': 'TSS',
                'transmission_code': '4R70W',
                'product_name': 'Resorte Acumulador 1-2 Azul',
            }
        },
        {
            'payload': {
                'content': 'Compatible con Ford F-150 2004-2010, Mustang 2005-2014...',
                'source_filename': 'Ford_Compatibility_Guide.pdf',
                'supplier': 'Ford',
                'transmission_code': '4R70W',
            }
        },
    ]


# ============ Async Fixtures ============

@pytest.fixture
async def mock_llm_response():
    """Sample LLM response for testing."""
    return {
        'h1_title': 'Resorte Acumulador 1-2 Azul 4R70W 4R75W 2004-UP',
        'description_html': '<h2>¿Golpes bruscos al cambiar?</h2><p>El resorte del acumulador...</p>',
        'short_description': 'Resorte acumulador 1-2 azul para 4R70W 4R75W. TSS calidad superior.',
        'meta_title': 'Resorte Acumulador 1-2 Azul 4R70W | Example Store',
        'meta_description': 'Resorte azul para acumulador 1-2 transmisión Ford 4R70W 4R75W 2004+. SKU 76821K.',
        'url_handle': 'resorte-azul-acumulador-1-2-4r70w-4r75w-2004-up',
        'alt_tags': ['76821k-1.jpg | Resorte azul 1-2 para 4R70W', '76821k-2.jpg | Vista lateral'],
        'technical_specs': ['Color: Azul', 'Diámetro: 25mm', 'Material: Acero spring'],
        'compatible_vehicles': 'FORD F-150 2004-2010, FORD MUSTANG 2005-2014',
    }


# ============ Test Helpers ============

def create_mock_settings(**overrides):
    """Create mock settings with optional overrides."""
    from pydantic import BaseModel
    
    class MockSettings(BaseModel):
        PROJECT_NAME: str = "RAG SEO Engine"
        VERSION: str = "1.0.0"
        LLM_PROVIDER: str = "anthropic"
        ANTHROPIC_API_KEY: str = "test-key"
        ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250520"
        OLLAMA_BASE_URL: str = "http://localhost:11434"
        OLLAMA_MODEL: str = "llama3.2:latest"
        OPENAI_API_KEY: str = ""
        OPENAI_MODEL: str = "gpt-4o"
        XAI_API_KEY: str = ""
        XAI_MODEL: str = "grok-4.3"
        MISTRAL_API_KEY: str = ""
        MISTRAL_MODEL: str = "mistral-large-latest"
        RAG_CHUNK_SIZE: int = 1000
        RAG_CHUNK_OVERLAP: int = 200
        RAG_TOP_K: int = 5
        MAX_PROMPT_TOKENS: int = 4000
        
        class Config:
            arbitrary_types_allowed = True
    
    settings = MockSettings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


# =========.markers =========

pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow


# ========= Configuration =========

pytest_plugins = [
    "pytest_asyncio",
]

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: Mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: Mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file location."""
    for item in items:
        if "test_" in item.name and "integration" not in item.name:
            item.add_marker(pytest.mark.unit)

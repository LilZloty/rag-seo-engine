"""
AEO (Answer Engine Optimization) Services

Modular services for:
- llms.txt generation
- Schema.org JSON-LD generation
- Knowledge Graph management
"""

from .llms_txt_builder import LLMSTxtBuilder, create_llms_txt_builder
from .schema_generator import (
    SchemaGenerator,
    generate_product_schema,
    generate_faq_schema,
    generate_howto_schema,
    generate_combined_product_schema,
    generate_schema_from_product_page,
    extract_faq_from_html,
    extract_install_steps_from_html,
    extract_install_total_time_from_html,
    extract_oem_references_from_html,
)
from .knowledge_graph import KnowledgeGraphManager, create_knowledge_graph_manager

__all__ = [
    # llms.txt builder
    "LLMSTxtBuilder",
    "create_llms_txt_builder",
    
    # Schema generator
    "SchemaGenerator",
    "generate_product_schema",
    "generate_faq_schema",
    "generate_howto_schema",
    "generate_combined_product_schema",
    "generate_schema_from_product_page",
    "extract_faq_from_html",
    "extract_install_steps_from_html",
    "extract_install_total_time_from_html",
    "extract_oem_references_from_html",
    
    # Knowledge Graph
    "KnowledgeGraphManager",
    "create_knowledge_graph_manager",
]

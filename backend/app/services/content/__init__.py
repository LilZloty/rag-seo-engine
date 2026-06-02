"""
Content Module - Content generation services

Services for generating SEO-optimized product content.
"""

from .prompt_manager import (
    PromptMerger,
    PromptTemplateManager,
    PromptMergeResult,
    create_prompt_merger
)

from .response_normalizer import (
    ResponseNormalizer,
    NormalizedContent,
    normalize_response,
    get_fallback_content
)

__all__ = [
    # Prompt management
    "PromptMerger",
    "PromptTemplateManager",
    "PromptMergeResult",
    "create_prompt_merger",
    
    # Response normalization
    "ResponseNormalizer",
    "NormalizedContent",
    "normalize_response",
    "get_fallback_content",
]

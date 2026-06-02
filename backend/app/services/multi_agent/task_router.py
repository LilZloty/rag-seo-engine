"""
Multi-Agent Task Router

Routes tasks to either single-agent Grok or multi-agent Grok 4.20 orchestrator
based on task complexity and user toggle state.
"""

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Tasks that benefit from multi-agent consensus (complex analysis)
_MULTI_AGENT_TASKS = {
    "fault_code_analysis",
    "blog_generation",
    "geo_snippet",
    # NEW: SEO Dashboard multi-agent tasks
    "product_analysis",        # Deep product SEO/AEO/GEO analysis
    "recommendation_engine",   # Smart recommendations generation
    "content_generation",      # Enhanced content creation with consensus
    "seo_optimization",        # SEO improvement recommendations
    # Collection Intelligence multi-agent tasks
    "collection_analysis",                # Deep collection SEO/AEO/GEO analysis
    "collection_recommendation_engine",   # Collection smart recommendations
    "collection_content_generation",      # Collection content with consensus
}

# Tasks that stay single-agent (simple or high-volume)
_SINGLE_AGENT_TASKS = {
    "product_content",         # Basic product content (high volume)
    "meta_generation",         # Quick meta tag generation
    "visibility_check",        # Fast visibility scoring
    "quick_scan",              # Quick single-product scan
}


class TaskRouter:
    """Routes tasks to the appropriate provider based on complexity and toggle state."""

    def route(self, task_type: str, multi_agent_enabled: bool = False) -> str:
        """
        Decide which provider to use for a given task.

        Returns:
            "grok420" for multi-agent orchestration
            "grok" for standard single-agent
        """
        if not multi_agent_enabled:
            logger.debug(f"[TaskRouter] Multi-agent disabled, routing '{task_type}' -> grok")
            return "grok"

        if task_type in _MULTI_AGENT_TASKS:
            logger.info(f"[TaskRouter] Routing '{task_type}' -> grok420 (multi-agent)")
            return "grok420"

        if task_type in _SINGLE_AGENT_TASKS:
            logger.debug(f"[TaskRouter] Routing '{task_type}' -> grok (simple task)")
            return "grok"

        # Default: use single-agent for unknown task types
        logger.debug(f"[TaskRouter] Unknown task '{task_type}', routing -> grok")
        return "grok"

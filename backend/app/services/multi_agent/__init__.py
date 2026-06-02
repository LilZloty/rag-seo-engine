"""
Multi-Agent System for Grok 4.20 Architecture

Orchestrates 4 specialized agents (Harper, Benjamin, Lucas, Captain)
for consensus-driven AI responses.
"""

from .agents import AgentRole, AgentConfig, DEFAULT_AGENTS
from .orchestrator import MultiAgentOrchestrator
from .task_router import TaskRouter

__all__ = [
    "MultiAgentOrchestrator",
    "TaskRouter",
    "AgentRole",
    "AgentConfig",
    "DEFAULT_AGENTS",
]

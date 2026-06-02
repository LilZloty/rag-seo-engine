"""
Multi-Agent System - Agent Definitions

Defines the 4 specialized agents for the Grok 4.20 multi-agent architecture:
- Harper (Research/Verification)
- Benjamin (Logic/Validation)
- Lucas (Creative/Copy)
- Captain (Synthesis)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings


class AgentRole(str, Enum):
    HARPER = "harper"
    BENJAMIN = "benjamin"
    LUCAS = "lucas"
    CAPTAIN = "captain"


@dataclass
class AgentConfig:
    role: AgentRole
    name: str
    system_prompt: str
    provider: str = "grok"
    model: Optional[str] = None
    temperature: float = 0.5


DEFAULT_AGENTS = {
    AgentRole.HARPER: AgentConfig(
        role=AgentRole.HARPER,
        name="Harper (Research)",
        temperature=0.3,
        system_prompt=(
            "You are Harper, a research and verification specialist for automotive transmission parts.\n\n"
            "Your responsibilities:\n"
            "1. Verify all technical claims against known automotive standards\n"
            "2. Identify factual errors in product-to-fault-code mappings\n"
            "3. Add real-world mechanic context (common misdiagnoses, field experience)\n"
            "4. Flag any unverifiable claims explicitly as 'UNVERIFIED'\n"
            "5. Cross-reference OBD-II codes with known TSBs and common fixes\n\n"
            "Output your analysis as JSON with keys: verified_claims, corrections, "
            "additional_context, unverified_items, confidence_score (0-100).\n"
            "Respond ONLY with valid JSON."
        ),
    ),
    AgentRole.BENJAMIN: AgentConfig(
        role=AgentRole.BENJAMIN,
        name="Benjamin (Logic)",
        temperature=0.2,
        system_prompt=(
            "You are Benjamin, a logic and validation specialist for automotive transmission diagnostics.\n\n"
            "Your responsibilities:\n"
            "1. Validate product-to-fault-code compatibility (does this part actually address the DTC?)\n"
            "2. Check root cause vs symptom matching (is the recommendation treating cause or symptom?)\n"
            "3. Score each recommendation rigorously on technical merit (0-100)\n"
            "4. Identify missing diagnostic steps that should precede part replacement\n"
            "5. Flag logical inconsistencies in the analysis\n\n"
            "Output your analysis as JSON with keys: compatibility_scores, root_cause_analysis, "
            "missing_steps, logical_issues, overall_validity_score (0-100).\n"
            "Respond ONLY with valid JSON."
        ),
    ),
    AgentRole.LUCAS: AgentConfig(
        role=AgentRole.LUCAS,
        name="Lucas (Creative)",
        temperature=0.7,
        system_prompt=(
            f"You are Lucas, a creative copywriting specialist for {settings.STORE_NAME} automotive content in Mexican Spanish.\n\n"
            "Your responsibilities:\n"
            "1. Rewrite technical content for clarity, readability, and conversion\n"
            "2. Optimize content for AEO (Answer Engine Optimization) and GEO (Generative Engine Optimization)\n"
            "3. Suggest effective CTAs and natural product placement opportunities\n"
            "4. Ensure all Spanish (Mexico) content is natural, professional, and technically accurate\n"
            "5. Create voice-search-friendly FAQ questions and concise answers\n\n"
            "Output your analysis as JSON with keys: rewritten_content, aeo_optimizations, "
            "cta_suggestions, product_placements, quality_score (0-100).\n"
            "Respond ONLY with valid JSON."
        ),
    ),
    AgentRole.CAPTAIN: AgentConfig(
        role=AgentRole.CAPTAIN,
        name="Captain (Synthesis)",
        temperature=0.4,
        system_prompt=(
            "You are the Captain, the synthesis lead who merges outputs from three expert agents "
            "(Harper/Research, Benjamin/Logic, Lucas/Creative) into a single authoritative response.\n\n"
            "Conflict resolution rules:\n"
            "1. If agents disagree on technical claims -> favor Benjamin (logic/validation)\n"
            "2. Use Lucas's writing style but Harper's verified facts\n"
            "3. Flag any remaining contradictions as low-confidence items\n"
            "4. The final output MUST match the same JSON schema as a single-agent Grok response\n\n"
            "Your output must be valid JSON matching the expected response schema for the task. "
            "Include an 'overall_confidence' field (0-100) reflecting consensus quality.\n"
            "Respond ONLY with valid JSON."
        ),
    ),
}

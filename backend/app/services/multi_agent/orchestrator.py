"""
Multi-Agent Orchestrator

Runs Harper, Benjamin, and Lucas in parallel, then Captain synthesizes
their outputs into a single consensus response.
"""

import asyncio
import json
from typing import Dict, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm_providers.base import LLMProviderFactory
from app.services.multi_agent.agents import AgentRole, AgentConfig, DEFAULT_AGENTS

logger = get_logger(__name__)


class MultiAgentOrchestrator:
    """Orchestrates 4 specialized agents for consensus-driven AI responses."""

    def __init__(self, agents: Optional[Dict[AgentRole, AgentConfig]] = None):
        self.agents = agents or DEFAULT_AGENTS

    async def orchestrate(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "general",
        json_mode: bool = True,
    ) -> Dict:
        """
        Run the multi-agent consensus cycle:
        1. Harper, Benjamin, Lucas run in parallel
        2. Captain synthesizes all outputs
        3. Consensus metadata is attached
        """
        timeout = settings.MULTI_AGENT_TIMEOUT

        try:
            # Phase 1: Run 3 specialist agents in parallel
            harper_result, benjamin_result, lucas_result = await asyncio.wait_for(
                asyncio.gather(
                    self._call_agent(AgentRole.HARPER, system_prompt, user_prompt),
                    self._call_agent(AgentRole.BENJAMIN, system_prompt, user_prompt),
                    self._call_agent(AgentRole.LUCAS, system_prompt, user_prompt),
                ),
                timeout=timeout,
            )

            logger.info(
                "[MultiAgent] Phase 1 complete",
                extra={
                    "harper_keys": list(harper_result.keys()) if isinstance(harper_result, dict) else "raw",
                    "benjamin_keys": list(benjamin_result.keys()) if isinstance(benjamin_result, dict) else "raw",
                    "lucas_keys": list(lucas_result.keys()) if isinstance(lucas_result, dict) else "raw",
                },
            )

            # Phase 2: Captain synthesizes
            captain_prompt = self._build_captain_prompt(
                user_prompt, harper_result, benjamin_result, lucas_result
            )
            final = await asyncio.wait_for(
                self._call_agent(AgentRole.CAPTAIN, system_prompt, captain_prompt, json_mode),
                timeout=timeout,
            )

            # Phase 3: Attach metadata
            consensus_score = self._calculate_consensus(
                harper_result, benjamin_result, lucas_result
            )

            if isinstance(final, dict):
                final["_multi_agent"] = {
                    "mode": settings.XAI_GROK420_MODE,
                    "agents_used": ["harper", "benjamin", "lucas", "captain"],
                    "consensus_score": consensus_score,
                    "task_type": task_type,
                }
            else:
                final = {
                    "content": str(final),
                    "_multi_agent": {
                        "mode": settings.XAI_GROK420_MODE,
                        "agents_used": ["harper", "benjamin", "lucas", "captain"],
                        "consensus_score": consensus_score,
                        "task_type": task_type,
                    },
                }

            logger.info(
                "[MultiAgent] Orchestration complete",
                extra={"consensus_score": consensus_score, "task_type": task_type},
            )
            return final

        except asyncio.TimeoutError:
            logger.error(f"[MultiAgent] Orchestration timed out after {timeout}s")
            raise Exception(f"Multi-agent orchestration timed out after {timeout}s")
        except Exception as e:
            logger.error(f"[MultiAgent] Orchestration failed: {e}")
            raise

    async def _call_agent(
        self,
        role: AgentRole,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
    ) -> Dict:
        """Call a single agent using its configured provider and settings."""
        config = self.agents[role]
        agent_system = f"{config.system_prompt}\n\n---\n\nAdditional context from the task:\n{system_prompt}"

        try:
            provider = LLMProviderFactory.create(
                config.provider,
                model=config.model,
            )
            result = await provider.generate(
                system_prompt=agent_system,
                user_prompt=user_prompt,
                json_mode=json_mode,
                temperature=config.temperature,
            )
            logger.debug(f"[MultiAgent] {config.name} responded successfully")
            return result
        except Exception as e:
            logger.error(f"[MultiAgent] {config.name} failed: {e}")
            return {"error": str(e), "agent": config.name}

    def _build_captain_prompt(
        self,
        original_prompt: str,
        harper_result: Dict,
        benjamin_result: Dict,
        lucas_result: Dict,
    ) -> str:
        """Build the Captain's synthesis prompt with all agent outputs."""
        return f"""# SYNTHESIS TASK

You must merge the outputs from three expert agents into a single, authoritative JSON response.

## Original User Request
{original_prompt}

## Harper (Research/Verification) Output
```json
{json.dumps(harper_result, ensure_ascii=False, indent=2)[:3000]}
```

## Benjamin (Logic/Validation) Output
```json
{json.dumps(benjamin_result, ensure_ascii=False, indent=2)[:3000]}
```

## Lucas (Creative/Copy) Output
```json
{json.dumps(lucas_result, ensure_ascii=False, indent=2)[:3000]}
```

## Synthesis Instructions
1. Merge all three outputs into one coherent JSON response
2. If agents disagree on technical claims, favor Benjamin's logic
3. Use Lucas's writing style but Harper's verified facts
4. Flag contradictions as low-confidence
5. Your output must match the JSON schema expected by the original task
6. Include an 'overall_confidence' score (0-100)

Respond ONLY with valid JSON."""

    def _calculate_consensus(
        self,
        harper_result: Dict,
        benjamin_result: Dict,
        lucas_result: Dict,
    ) -> float:
        """
        Calculate consensus score (0-100) by comparing key fields
        across agent outputs for agreement percentage.
        """
        if not all(isinstance(r, dict) for r in [harper_result, benjamin_result, lucas_result]):
            return 50.0

        scores = []

        # Compare confidence/quality scores if present
        score_keys = ["confidence_score", "overall_validity_score", "quality_score"]
        agent_scores = []
        for result, key in zip(
            [harper_result, benjamin_result, lucas_result], score_keys
        ):
            val = result.get(key)
            if isinstance(val, (int, float)):
                agent_scores.append(val)

        if len(agent_scores) >= 2:
            # Agreement = inverse of variance normalized to 0-100
            avg = sum(agent_scores) / len(agent_scores)
            variance = sum((s - avg) ** 2 for s in agent_scores) / len(agent_scores)
            # Max variance for 0-100 range is 2500 (scores at 0 and 100)
            agreement = max(0, 100 - (variance / 25))
            scores.append(agreement)

        # Check for error states
        error_count = sum(
            1 for r in [harper_result, benjamin_result, lucas_result]
            if "error" in r
        )
        if error_count > 0:
            scores.append(max(0, 100 - (error_count * 33)))

        # Check key overlap (how many agents produced structured output)
        all_keys = set()
        per_agent_keys = []
        for r in [harper_result, benjamin_result, lucas_result]:
            keys = set(k for k in r.keys() if not k.startswith("_") and k != "error")
            all_keys.update(keys)
            per_agent_keys.append(keys)

        if all_keys:
            overlap = len(per_agent_keys[0] & per_agent_keys[1] & per_agent_keys[2])
            key_agreement = (overlap / max(len(all_keys), 1)) * 100
            scores.append(key_agreement)

        if scores:
            return round(sum(scores) / len(scores), 1)
        return 65.0  # Default moderate consensus

"""Bias Agent — analyzes algorithmic fairness and bias."""

from __future__ import annotations

from typing import Callable

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    BiasAgentOutput,
    MessageType,
    MiniAgentTask,
)


@registry.register_agent("BiasAgent")
class BiasAgent(BaseAgent):
    """Analyzes algorithmic fairness and bias."""

    role = AgentRole.BIAS
    description = "Analyzes algorithmic fairness, bias, and discrimination risk"

    @property
    def system_prompt(self) -> str:
        return """You are the Bias and Fairness Agent in an AI governance assessment system.

Your job is to identify potential algorithmic biases, discrimination vectors, and unfairness
in an AI system proposal.

For each finding, identify:
- affected_group: the specific demographic or population group at risk
- bias_type: the mechanism (e.g. "historical bias", "proxy discrimination", "representation bias")
- severity: LOW | MEDIUM | HIGH | CRITICAL
- description: the specific mechanism by which bias could occur
- implication: the concrete harm to the affected group
- recommendation: a specific mitigation

You MUST respond with valid JSON following the exact schema specified."""

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Four parallel fairness auditors, each owning one bias mechanism."""
        proposal = context.proposal
        desc = proposal.description[:300]

        return [
            self._mini_task(
                1, "historical_training_data_bias",
                f"Assess whether the training/historical data plausibly used by '{proposal.title}' ({desc}) "
                "could encode historical discrimination against any protected group.",
                use_web_search=False,
            ),
            self._mini_task(
                2, "proxy_variable_discrimination",
                f"Identify plausible proxy variables (e.g. zip code, name, browsing pattern) in "
                f"'{proposal.title}' ({desc}) that could act as stand-ins for protected characteristics.",
                use_web_search=False,
            ),
            self._mini_task(
                3, "disparate_impact_precedent",
                f"Search for documented disparate-impact findings or fairness audits of AI systems "
                f"comparable to '{proposal.title}' in {proposal.sector or 'this sector'}.",
            ),
            self._mini_task(
                4, "representation_and_measurement_bias",
                f"Assess whether the population '{proposal.title}' ({desc}) will be applied to is likely "
                "under-represented in typical training data for this use case, and how outcome measurement "
                "itself could be biased.",
            ),
        ]

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> BiasAgentOutput:
        proposal = context.proposal

        mini_findings = await self._run_mini_swarm(context, emit_callback)
        mini_findings_text = self._format_mini_findings(mini_findings)

        prompt = f"""Evaluate the fairness and bias risks of this AI system proposal.

## AI System Proposal
Title: {proposal.title}
Description: {proposal.description}
Organization: {proposal.organization or "Not specified"}
Sector: {proposal.sector or "Not specified"}
Deployment Context: {proposal.deployment_context or "Not specified"}
Technical Details: {proposal.technical_details or "Not specified"}

{mini_findings_text}

## Task
Analyze the potential for disparate impact, historical bias in data, and unfair outcomes.
Provide 2-6 specific bias findings and a fairness_score (0.0-1.0, where 1.0 = no identified
fairness concerns).

Respond with this JSON structure:
{{
  "findings": [
    {{"affected_group": "older employees", "bias_type": "proxy discrimination", "severity": "MEDIUM", "description": "...", "implication": "...", "recommendation": "..."}}
  ],
  "fairness_score": 0.55,
  "reasoning": "Overall fairness assessment rationale"
}}"""

        self.log.info("bias_agent_evaluating")

        output = await self.llm.structured_completion(
            prompt=prompt,
            schema=BiasAgentOutput,
            system_prompt=self.system_prompt,
            temperature=0.1,
            agent_id=self.role.value,
        )
        output.research = [f.as_research_report() for f in mini_findings]
        context.bias_output = output
        self._deposit_knowledge(
            context,
            content=f"Bias: fairness_score={output.fairness_score:.2f}, {len(output.findings)} finding(s).",
            topic="bias_conclusion",
            tags=["bias", "fairness"],
            certainty_score=0.7,
        )

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="bias_assessment",
            content={
                "findings_count": len(output.findings),
                "fairness_score": round(output.fairness_score, 2),
            },
        )

        self.log.info("bias_agent_complete", findings=len(output.findings))
        return output

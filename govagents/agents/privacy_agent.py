"""Privacy Agent — analyzes data privacy, minimization, and GDPR compliance."""

from __future__ import annotations

from typing import Callable

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    MessageType,
    MiniAgentTask,
    PrivacyAgentOutput,
)


@registry.register_agent("PrivacyAgent")
class PrivacyAgent(BaseAgent):
    """Analyzes data privacy, minimization, and GDPR compliance."""

    role = AgentRole.PRIVACY
    description = "Analyzes data privacy, PII handling, and data minimization"

    @property
    def system_prompt(self) -> str:
        return """You are the Privacy Agent in an AI governance assessment system.

Your job is to identify privacy concerns, PII handling issues, and data minimization
violations in an AI system proposal.

For each finding, identify:
- data_type: the specific category of data involved (e.g. "employee communications", "biometric data")
- issue: the specific privacy problem
- severity: LOW | MEDIUM | HIGH | CRITICAL
- gdpr_article: the most relevant GDPR article, if any (e.g. "Article 5", "Article 9"), else null

You MUST respond with valid JSON following the exact schema specified."""

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Four parallel privacy specialists, each owning one angle of data protection."""
        proposal = context.proposal
        desc = proposal.description[:300]

        return [
            self._mini_task(
                1, "pii_inventory",
                f"Inventory every category of personal or sensitive data plausibly processed by "
                f"'{proposal.title}': {desc}. Flag any special-category data (health, biometric, "
                "political, etc.) under GDPR Article 9.",
                use_web_search=False,
            ),
            self._mini_task(
                2, "gdpr_article_mapping",
                f"Map the data processing implied by '{proposal.title}' ({desc}) to specific GDPR articles "
                "(lawful basis Art.6, special category Art.9, automated decisions Art.22, DPIA Art.35). "
                "Which are triggered and why?",
            ),
            self._mini_task(
                3, "data_flow_and_retention",
                f"Trace the likely data flow (collection → processing → storage → sharing → deletion) for "
                f"'{proposal.title}' and identify retention or third-party sharing risks.",
                use_web_search=False,
            ),
            self._mini_task(
                4, "data_minimization_purpose_limitation",
                f"Assess whether '{proposal.title}' ({desc}) collects only what is necessary for its stated "
                "purpose, or over-collects. Search for data minimization best practices for comparable systems.",
            ),
        ]

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> PrivacyAgentOutput:
        proposal = context.proposal

        mini_findings = await self._run_mini_swarm(context, emit_callback)
        mini_findings_text = self._format_mini_findings(mini_findings)

        prompt = f"""Evaluate the privacy aspects of this AI system proposal.

## AI System Proposal
Title: {proposal.title}
Description: {proposal.description}
Organization: {proposal.organization or "Not specified"}
Sector: {proposal.sector or "Not specified"}
Deployment Context: {proposal.deployment_context or "Not specified"}
Technical Details: {proposal.technical_details or "Not specified"}

{mini_findings_text}

## Task
Analyze the data types processed, identify PII, and assess data minimization.
Provide 2-6 specific privacy findings, whether pii_handled is true/false, and a
data_minimization_score (0.0-1.0).

Respond with this JSON structure:
{{
  "findings": [
    {{"data_type": "employee communications", "issue": "Monitored without informed consent", "severity": "HIGH", "gdpr_article": "Article 6"}}
  ],
  "pii_handled": true,
  "data_minimization_score": 0.4,
  "reasoning": "Overall privacy assessment rationale"
}}"""

        self.log.info("privacy_agent_evaluating")

        output = await self.llm.structured_completion(
            prompt=prompt,
            schema=PrivacyAgentOutput,
            system_prompt=self.system_prompt,
            temperature=0.1,
            agent_id=self.role.value,
        )
        output.research = [f.as_research_report() for f in mini_findings]
        context.privacy_output = output
        self._deposit_knowledge(
            context,
            content=f"Privacy: pii_handled={output.pii_handled}, minimization={output.data_minimization_score:.2f}.",
            topic="privacy_conclusion",
            tags=["privacy", "pii"],
            certainty_score=0.7,
        )

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="privacy_assessment",
            content={
                "findings_count": len(output.findings),
                "pii_handled": output.pii_handled,
                "data_minimization_score": round(output.data_minimization_score, 2),
            },
        )

        self.log.info("privacy_agent_complete", findings=len(output.findings))
        return output

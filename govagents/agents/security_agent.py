"""Security Agent — analyzes security, threat models, and vulnerabilities."""

from __future__ import annotations

from typing import Callable

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    MessageType,
    MiniAgentTask,
    SecurityAgentOutput,
)


@registry.register_agent("SecurityAgent")
class SecurityAgent(BaseAgent):
    """Analyzes security, threat models, and vulnerabilities."""

    role = AgentRole.SECURITY
    description = "Analyzes security vulnerabilities and threat models"

    @property
    def system_prompt(self) -> str:
        return """You are the Security Agent in an AI governance assessment system.

Your job is to identify security vulnerabilities, attack vectors, and data flow risks
in an AI system proposal.

For each vulnerability, identify:
- component: the specific part of the system affected
- vulnerability: the specific security issue
- severity: LOW | MEDIUM | HIGH | CRITICAL
- cvss_estimate: a rough CVSS-style score (0.0-10.0), or null if not applicable

You MUST respond with valid JSON following the exact schema specified."""

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Four parallel security specialists, each owning one threat surface."""
        proposal = context.proposal
        details = proposal.technical_details or proposal.description[:300]

        return [
            self._mini_task(
                1, "threat_modeling",
                f"Build a lightweight STRIDE-style threat model for '{proposal.title}' ({details}). "
                "What are the top 2-3 attack surfaces?",
                use_web_search=False,
            ),
            self._mini_task(
                2, "adversarial_ml_vulnerabilities",
                f"Search for known adversarial ML attack techniques (prompt injection, data poisoning, "
                f"model extraction, evasion) that would apply to a system like '{proposal.title}': {details}.",
            ),
            self._mini_task(
                3, "supply_chain_dependency_risk",
                f"Identify third-party/vendor/model supply-chain security risks for '{proposal.title}'. "
                "Search for known vulnerabilities in comparable dependencies.",
            ),
            self._mini_task(
                4, "incident_response_readiness",
                f"Assess whether '{proposal.title}' ({details}) has (or plausibly needs) incident detection, "
                "logging, and response capabilities for a security breach.",
                use_web_search=False,
            ),
        ]

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> SecurityAgentOutput:
        proposal = context.proposal

        mini_findings = await self._run_mini_swarm(context, emit_callback)
        mini_findings_text = self._format_mini_findings(mini_findings)

        prompt = f"""Evaluate the security aspects of this AI system proposal.

## AI System Proposal
Title: {proposal.title}
Description: {proposal.description}
Organization: {proposal.organization or "Not specified"}
Sector: {proposal.sector or "Not specified"}
Deployment Context: {proposal.deployment_context or "Not specified"}
Technical Details: {proposal.technical_details or "Not specified"}

{mini_findings_text}

## Task
Analyze the architecture for vulnerabilities, injection risks, and encryption issues.
Provide 2-6 specific security vulnerabilities and an overall_security_posture summary
(one of: "strong", "adequate", "weak", "critical", "unknown").

Respond with this JSON structure:
{{
  "vulnerabilities": [
    {{"component": "API gateway", "vulnerability": "No rate limiting or authentication described", "severity": "HIGH", "cvss_estimate": 7.5}}
  ],
  "overall_security_posture": "weak",
  "reasoning": "Overall security assessment rationale"
}}"""

        self.log.info("security_agent_evaluating")

        output = await self.llm.structured_completion(
            prompt=prompt,
            schema=SecurityAgentOutput,
            system_prompt=self.system_prompt,
            temperature=0.1,
            agent_id=self.role.value,
        )
        output.research = [f.as_research_report() for f in mini_findings]
        context.security_output = output
        self._deposit_knowledge(
            context,
            content=f"Security: posture={output.overall_security_posture}, {len(output.vulnerabilities)} vulnerabilit(y/ies).",
            topic="security_conclusion",
            tags=["security", "threat"],
            certainty_score=0.7,
        )

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="security_assessment",
            content={
                "vulnerabilities_count": len(output.vulnerabilities),
                "overall_security_posture": output.overall_security_posture,
            },
        )

        self.log.info("security_agent_complete", vulnerabilities=len(output.vulnerabilities))
        return output

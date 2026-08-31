"""Guardrail Agent — final check for absolute red lines before the governance decision."""

from __future__ import annotations

from typing import Callable

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    GuardrailAgentOutput,
    KnowledgeScope,
    MessageType,
    MiniAgentTask,
    RiskLevel,
)


@registry.register_agent("GuardrailAgent")
class GuardrailAgent(BaseAgent):
    """Checks the proposal against absolute, non-negotiable red lines.

    Unlike every other module, a guardrail trigger is a hard veto (see
    `govagents.orchestration.logic_gates`): it is not weighed against other
    evidence, it forces the final decision. Three specialist mini-agents each
    independently scan for one category of unacceptable practice — this is an
    OR-gate by design: if ANY one of them is confident a red line is crossed,
    the module reports triggered=True regardless of what the others found.
    """

    role = AgentRole.GUARDRAIL
    description = "Checks for absolute, non-negotiable governance red lines"

    @property
    def system_prompt(self) -> str:
        return """You are the Guardrail Agent — the last line of defense in an AI governance
assessment system, checking for absolute "red line" practices that no mitigation can fix.

Red lines include (non-exhaustive):
- Social scoring of individuals by public or private actors
- Real-time remote biometric identification in publicly accessible spaces for law enforcement
- Biometric categorization inferring protected characteristics (race, political/religious belief, sexual orientation)
- Subliminal manipulation or exploitation of vulnerabilities (age, disability, socioeconomic situation) causing harm
- Predictive policing based solely on profiling
- Untargeted scraping of facial images to build recognition databases

A red line is NOT the same as an ordinary risk — ordinary compliance gaps belong to the
other modules. Only flag `triggered=True` if the practice itself is categorically
unacceptable, not merely risky or poorly implemented.

You MUST respond with valid JSON following the exact schema specified."""

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Three independent red-line scanners — an OR-gate over their verdicts."""
        proposal = context.proposal
        desc = proposal.description[:350]

        return [
            self._mini_task(
                1, "social_scoring_and_profiling",
                f"Does '{proposal.title}' ({desc}) constitute or closely resemble social scoring — evaluating "
                "or classifying people based on social behavior or personal traits, with detrimental or "
                "unfavorable treatment unrelated to the original context? Answer precisely, citing the exact "
                "proposal text that supports or refutes this.",
                use_web_search=False,
            ),
            self._mini_task(
                2, "biometric_surveillance_categorization",
                f"Does '{proposal.title}' ({desc}) involve real-time remote biometric identification in public "
                "spaces, or biometric categorization inferring race, political/religious belief, or sexual "
                "orientation? Cite the exact proposal text.",
                use_web_search=False,
            ),
            self._mini_task(
                3, "manipulation_and_vulnerability_exploitation",
                f"Does '{proposal.title}' ({desc}) use subliminal techniques or exploit vulnerabilities of a "
                "specific group (age, disability, socioeconomic situation) in a way likely to cause harm? "
                "Cite the exact proposal text.",
                use_web_search=False,
            ),
        ]

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> GuardrailAgentOutput:
        proposal = context.proposal

        mini_findings = await self._run_mini_swarm(context, emit_callback)
        mini_findings_text = self._format_mini_findings(mini_findings)

        # OR-gate: any specialist reporting HIGH/CRITICAL concern is a strong signal on its own
        specialist_flags = [f for f in mini_findings if f.concern_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)]

        prompt = f"""Evaluate this AI system proposal against absolute unacceptable-risk red lines.

## AI System Proposal
Title: {proposal.title}
Description: {proposal.description}
Technical Details: {proposal.technical_details or "N/A"}
Deployment Context: {proposal.deployment_context or "N/A"}

{mini_findings_text}

{f"NOTE: {len(specialist_flags)} of your {len(mini_findings)} specialist scanners flagged HIGH/CRITICAL concern on their assigned red-line category. Weigh this seriously — an OR-gate means a single confident specialist is enough to trigger." if specialist_flags else ""}

## Task
Are there any absolute red-line violations? Return a boolean `triggered` and a list of
specific violations if any (empty list if none).

Respond with this JSON structure:
{{
  "triggered": false,
  "violations": [],
  "reasoning": "Why this proposal does or does not cross an absolute red line"
}}"""

        self.log.info("guardrail_agent_evaluating")

        output = await self.llm.structured_completion(
            prompt=prompt,
            schema=GuardrailAgentOutput,
            system_prompt=self.system_prompt,
            temperature=0.0,
            agent_id=self.role.value,
        )

        # Enforce the OR-gate deterministically: don't let the synthesis call silently
        # override a confident specialist's red-line finding.
        if specialist_flags and not output.triggered:
            output.triggered = True
            for f in specialist_flags:
                if f.summary and f.summary not in output.violations:
                    output.violations.append(f.summary)
            output.reasoning = (
                (output.reasoning + " ") if output.reasoning else ""
            ) + "Overridden to triggered=True: at least one specialist scanner reported HIGH/CRITICAL concern."

        output.research = [f.as_research_report() for f in mini_findings]
        context.guardrail_output = output
        self._deposit_knowledge(
            context,
            content=f"Guardrail: triggered={output.triggered}. {'; '.join(output.violations[:3])}",
            topic="guardrail_conclusion",
            tags=["guardrail", "redline"],
            certainty_score=0.9,
            scope=KnowledgeScope.SHARED,
        )

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="guardrail_check",
            content={
                "triggered": output.triggered,
                "violations_count": len(output.violations),
            },
        )

        self.log.info("guardrail_agent_complete", triggered=output.triggered)
        return output

"""Debate protocol — structured disagreement resolution between agents."""

from __future__ import annotations

from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    AgentRole,
    ComplianceStatus,
    DebatePosition,
    RiskLevel,
)

log = get_logger(__name__)


class DebateProtocol:
    """Implements structured debate between agents when disagreements are detected.

    The protocol:
    1. Detects disagreements (e.g., Compliance says SATISFIED but Technical says HIGH risk)
    2. Each disagreeing agent states its position with evidence
    3. Agents respond to challenges (up to N rounds)
    4. Governance Agent breaks ties if no convergence
    """

    def __init__(self, llm: LLMClient | None = None, max_rounds: int = 2) -> None:
        self.llm = llm or get_llm_client()
        self.max_rounds = max_rounds

    def detect_disagreements(self, context: AgentContext) -> list[dict]:
        """Find significant disagreements between agent outputs."""
        disagreements = []

        if not (context.compliance_output and context.technical_output and context.risk_output):
            return []

        # Check: Compliance says mostly satisfied but Technical found critical issues
        critical_technical = [
            f for f in context.technical_output.findings if f.severity == RiskLevel.CRITICAL
        ]
        if (
            context.compliance_output.overall_compliance_score > 0.7
            and len(critical_technical) > 0
        ):
            disagreements.append(
                {
                    "type": "compliance_vs_technical",
                    "description": (
                        f"Compliance Agent assessed high compliance "
                        f"({context.compliance_output.overall_compliance_score:.2f}) "
                        f"but Technical Agent found {len(critical_technical)} CRITICAL issues"
                    ),
                    "agents": [AgentRole.COMPLIANCE, AgentRole.TECHNICAL],
                    "severity": "HIGH",
                }
            )

        # Check: Risk is CRITICAL but Compliance says SATISFIED
        if (
            context.risk_output.overall_risk_level == RiskLevel.CRITICAL
            and context.compliance_output.overall_status == ComplianceStatus.SATISFIED
        ):
            disagreements.append(
                {
                    "type": "risk_vs_compliance",
                    "description": (
                        "Risk Agent identified CRITICAL overall risk "
                        "while Compliance Agent assessed full compliance — this is contradictory"
                    ),
                    "agents": [AgentRole.RISK, AgentRole.COMPLIANCE],
                    "severity": "CRITICAL",
                }
            )

        # Check: Ethics very low but Compliance scored high
        if context.ethics_output:
            if (
                context.ethics_output.overall_score < 0.4
                and context.compliance_output.overall_compliance_score > 0.65
            ):
                disagreements.append(
                    {
                        "type": "ethics_vs_compliance",
                        "description": (
                            f"Ethics Agent scored poorly ({context.ethics_output.overall_score:.2f}) "
                            f"while Compliance Agent scored well ({context.compliance_output.overall_compliance_score:.2f}) — "
                            "ethical requirements may be insufficiently weighted"
                        ),
                        "agents": [AgentRole.ETHICS, AgentRole.COMPLIANCE],
                        "severity": "MEDIUM",
                    }
                )

        if disagreements:
            log.info("disagreements_detected", count=len(disagreements))
        return disagreements

    async def run_debate(
        self, context: AgentContext, disagreements: list[dict]
    ) -> list[dict]:
        """Run debate rounds to resolve disagreements. Returns debate outcomes."""
        if not disagreements:
            return []

        debate_log = []
        for disagreement in disagreements:
            log.info(
                "debate_starting",
                type=disagreement["type"],
                severity=disagreement["severity"],
            )

            outcome = await self._resolve_disagreement(context, disagreement)
            debate_log.append(outcome)

        return debate_log

    async def _resolve_disagreement(
        self, context: AgentContext, disagreement: dict
    ) -> dict:
        """Run a single disagreement through the debate protocol."""
        prompt = f"""Two AI governance agents have reached conflicting conclusions.

## Disagreement

{disagreement["description"]}

## Full Context

### Proposal
{context.proposal.title}: {context.proposal.description[:400]}

### Compliance Assessment
Score: {context.compliance_output.overall_compliance_score if context.compliance_output else "N/A"}
Status: {context.compliance_output.overall_status.value if context.compliance_output else "N/A"}

### Risk Assessment  
Level: {context.risk_output.overall_risk_level.value if context.risk_output else "N/A"}
Score: {context.risk_output.risk_score if context.risk_output else "N/A"}

### Technical Findings
Critical: {sum(1 for f in context.technical_output.findings if f.severity == RiskLevel.CRITICAL) if context.technical_output else 0}
High: {sum(1 for f in context.technical_output.findings if f.severity == RiskLevel.HIGH) if context.technical_output else 0}

### Ethics Score
{context.ethics_output.overall_score if context.ethics_output else "N/A"}

## Task

Analyze this disagreement and determine:
1. Which agent's assessment is more accurate given the evidence?
2. Why do they disagree? (scope difference, evidence interpretation, or genuine uncertainty?)
3. What is the correct interpretation?

Respond with JSON:
{{
  "disagreement_type": "{disagreement["type"]}",
  "resolution": "COMPLIANCE_AGENT_CORRECT | TECHNICAL_AGENT_CORRECT | BOTH_PARTIALLY_CORRECT | INSUFFICIENT_EVIDENCE",
  "reasoning": "Explanation of the resolution",
  "impact_on_decision": "How this affects the final governance decision",
  "remaining_uncertainty": "What remains unclear after resolution"
}}"""

        raw = await self.llm.complete_json(
            [
                {
                    "role": "system",
                    "content": "You are a senior AI governance expert arbitrating between two AI governance agents. "
                    "Be rigorous, cite evidence, and be honest about uncertainty. "
                    "Respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ]
        )

        return {
            "disagreement": disagreement,
            "resolution": raw.get("resolution", "INSUFFICIENT_EVIDENCE"),
            "reasoning": raw.get("reasoning", ""),
            "impact_on_decision": raw.get("impact_on_decision", ""),
            "remaining_uncertainty": raw.get("remaining_uncertainty", ""),
        }

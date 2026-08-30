"""Risk Agent — identifies and scores technical, organizational, and AI-specific risks."""

from __future__ import annotations

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    MessageType,
    RiskAgentOutput,
    RiskItem,
    RiskLevel,
)


@registry.register_agent("RiskAgent")
class RiskAgent(BaseAgent):
    """Identifies and scores risks associated with the AI deployment proposal.

    Covers:
    - Technical risks (system failure, adversarial attacks, drift)
    - Organizational risks (lack of governance, skill gaps)
    - Legal/regulatory risks (non-compliance penalties)
    - Ethical risks (bias, discrimination, harm to individuals)
    - Operational risks (monitoring, maintenance, incident response)
    """

    role = AgentRole.RISK
    description = "Identifies and scores governance and deployment risks"

    @property
    def system_prompt(self) -> str:
        return """You are the Risk Agent in an AI governance assessment system.

Your job is to identify and score all significant risks associated with an AI system
or deployment proposal.

Risk categories:
- technical: model failures, adversarial robustness, distribution shift, data quality
- organizational: governance gaps, skill deficits, change management
- legal: regulatory non-compliance, liability, penalties
- ethical: bias, discrimination, harm to individuals or groups
- operational: monitoring, incident response, vendor lock-in, continuity
- reputational: public trust, stakeholder confidence
- societal: broader social impacts, digital divide, sovereignty

Risk scoring:
- likelihood: probability of the risk materializing (0.0-1.0)
- impact: severity of consequences if it occurs (0.0-1.0)
- severity: overall risk level (LOW/MEDIUM/HIGH/CRITICAL)

Severity guidelines:
- CRITICAL: likelihood > 0.7 AND impact > 0.8, or single catastrophic impact > 0.95
- HIGH: likelihood × impact > 0.4
- MEDIUM: likelihood × impact 0.15-0.4
- LOW: likelihood × impact < 0.15

You MUST respond with valid JSON following the exact schema specified."""

    async def run(self, context: AgentContext) -> RiskAgentOutput:
        proposal = context.proposal
        requirements = context.retrieved_requirements

        req_summary = "\n".join([f"- {r.title}: {r.requirement_type}" for r in requirements[:10]])

        user_prompt = f"""Identify all significant risks for this AI system proposal.

## AI System Proposal

**Title:** {proposal.title}
**Description:** {proposal.description}
**Organization:** {proposal.organization or "Not specified"}
**Sector:** {proposal.sector or "Not specified"}
**Deployment Context:** {proposal.deployment_context or "Not specified"}
**Technical Details:** {proposal.technical_details or "Not specified"}

## Key Governance Requirements Identified

{req_summary if req_summary else "No specific requirements identified yet."}

## Task

Identify ALL significant risks. Be specific to this proposal, not generic.
Consider the specific use case, deployment context, affected parties, and regulatory environment.

Respond with this JSON structure:
{{
  "risks": [
    {{
      "id": "risk-001",
      "title": "Employee surveillance without informed consent",
      "description": "The system monitors employee communications without clear legal basis or adequate notification mechanisms, creating significant GDPR and labor law violations.",
      "category": "legal",
      "likelihood": 0.85,
      "impact": 0.90,
      "severity": "CRITICAL",
      "affected_requirements": ["req-001", "req-003"],
      "mitigation": "Implement informed consent mechanism, conduct Data Protection Impact Assessment, establish legal basis for processing under GDPR Article 6."
    }}
  ],
  "overall_risk_level": "HIGH",
  "risk_score": 0.78,
  "reasoning": "Overall risk assessment rationale"
}}

Identify 5-12 specific, relevant risks. Each risk must have a concrete mitigation strategy.
Risk score (0.0-1.0) represents the aggregate risk exposure."""

        self.log.info("risk_agent_analyzing")

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.2,
            agent_id=self.role.value,
        )

        risks = []
        for r in raw.get("risks", []):
            try:
                risk = RiskItem(
                    id=r.get("id", f"risk-{len(risks):03d}"),
                    title=r.get("title", "Unknown Risk"),
                    description=r.get("description", ""),
                    category=r.get("category", "general"),
                    likelihood=float(r.get("likelihood", 0.5)),
                    impact=float(r.get("impact", 0.5)),
                    severity=RiskLevel(r.get("severity", "MEDIUM")),
                    affected_requirements=r.get("affected_requirements", []),
                    mitigation=r.get("mitigation", ""),
                )
                risks.append(risk)
            except Exception as e:
                self.log.warning("risk_parse_error", error=str(e), data=r)

        # Sort by severity × likelihood
        severity_order = {
            RiskLevel.CRITICAL: 4,
            RiskLevel.HIGH: 3,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 1,
        }
        risks.sort(
            key=lambda x: (severity_order.get(x.severity, 0), x.likelihood * x.impact),
            reverse=True,
        )

        try:
            overall_risk = RiskLevel(raw.get("overall_risk_level", "MEDIUM"))
        except ValueError:
            overall_risk = self._derive_overall_risk(risks)

        risk_score = float(raw.get("risk_score", 0.5))

        output = RiskAgentOutput(
            risks=risks,
            overall_risk_level=overall_risk,
            risk_score=risk_score,
            reasoning=raw.get("reasoning", ""),
        )
        context.risk_output = output

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="risk_assessment",
            content={
                "overall_risk": overall_risk.value,
                "risk_count": len(risks),
                "critical_risks": sum(1 for r in risks if r.severity == RiskLevel.CRITICAL),
            },
        )

        self.log.info(
            "risk_agent_complete",
            risk_level=overall_risk.value,
            risks=len(risks),
        )
        return output

    def _derive_overall_risk(self, risks: list[RiskItem]) -> RiskLevel:
        if not risks:
            return RiskLevel.LOW
        if any(r.severity == RiskLevel.CRITICAL for r in risks):
            return RiskLevel.CRITICAL
        if any(r.severity == RiskLevel.HIGH for r in risks):
            return RiskLevel.HIGH
        if any(r.severity == RiskLevel.MEDIUM for r in risks):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

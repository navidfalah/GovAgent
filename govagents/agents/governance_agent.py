"""Governance Agent — synthesizes all agent outputs into a final governance decision."""

from __future__ import annotations

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    DecisionType,
    EvidenceStrength,
    GovernanceReport,
    MessageType,
    RequiredAction,
    RiskLevel,
)


@registry.register_agent("GovernanceAgent")
class GovernanceAgent(BaseAgent):
    """The Governance Agent synthesizes all specialist agent outputs.

    It:
    1. Receives outputs from Policy, Risk, Technical, Compliance, and Ethics agents
    2. Identifies disagreements and key issues
    3. Applies the governance decision framework
    4. Produces the final GovernanceReport with required actions and evidence
    """

    role = AgentRole.GOVERNANCE
    description = "Synthesizes all assessments into a final governance decision"

    @property
    def system_prompt(self) -> str:
        return """You are the Governance Agent — the final decision-maker in an AI governance assessment system.

You receive structured assessments from five specialized agents:
- Policy Agent: Which requirements apply
- Compliance Agent: Whether requirements are met
- Risk Agent: What risks exist
- Ethics Agent: Ethical and sovereignty dimensions
- Technical Agent: Technical compliance gaps

Your job is to synthesize these into a single, coherent governance decision.

Decision framework:
- APPROVED: High compliance confidence, LOW or MEDIUM overall risk, ethics score > 0.7
- CONDITIONAL_APPROVAL: Moderate compliance with clear remediation path, manageable risks
- REJECTED: Critical compliance failures, CRITICAL risks, or fundamental ethics violations
- ABSTAINED: Insufficient information to make a reliable determination

Key principles:
1. Disagreement between agents is informative — explain it, don't hide it
2. Uncertainty should be communicated honestly
3. Required actions must be specific, actionable, and prioritized
4. Evidence citations must point to real policy sources cited by agents

You MUST respond with valid JSON following the exact schema specified."""

    async def run(self, context: AgentContext) -> GovernanceReport:
        proposal = context.proposal

        # Build comprehensive summary of all agent outputs
        summary = self._build_agent_summary(context)

        user_prompt = f"""Synthesize all agent assessments into a final governance decision.

## Proposal
**Title:** {proposal.title}
**Description:** {proposal.description[:500]}

## Agent Assessment Summary

{summary}

## Task

Based on ALL agent assessments, produce a final governance decision.

Respond with this JSON structure:
{{
  "decision": "CONDITIONAL_APPROVAL",
  "overall_risk": "HIGH",
  "compliance_confidence": 0.52,
  "uncertainty": "MODERATE",
  "key_issues": [
    "Employee monitoring introduces significant governance risk without adequate safeguards",
    "Transparency requirements are not addressed — no mechanism to inform affected employees",
    "Human oversight is undefined — AI decisions may be acted upon without human review",
    "No Data Protection Impact Assessment (DPIA) has been conducted as required by GDPR"
  ],
  "required_actions": [
    {{
      "priority": 1,
      "title": "Conduct Data Protection Impact Assessment",
      "description": "A DPIA is mandatory under GDPR Article 35 for systematic monitoring of employees. This must be completed before any deployment.",
      "category": "legal",
      "timeline": "before deployment"
    }},
    {{
      "priority": 2,
      "title": "Define human oversight procedure",
      "description": "Establish a documented process for human review of all AI productivity assessments before any action is taken. Define roles, responsibilities, and escalation paths.",
      "category": "process",
      "timeline": "before deployment"
    }},
    {{
      "priority": 3,
      "title": "Implement employee transparency mechanism",
      "description": "Create and deploy a written notification system informing employees of monitoring, what data is collected, how it is processed, and their rights.",
      "category": "technical",
      "timeline": "before deployment"
    }},
    {{
      "priority": 4,
      "title": "Integrate explainability into AI pipeline",
      "description": "Add explanation generation to the AI system so each productivity assessment includes human-readable reasoning that managers can review.",
      "category": "technical",
      "timeline": "before deployment"
    }},
    {{
      "priority": 5,
      "title": "Establish audit logging",
      "description": "Implement comprehensive logging of all AI inputs, outputs, model versions, and human review decisions for future audits.",
      "category": "technical",
      "timeline": "before deployment"
    }}
  ],
  "evidence_citations": [
    "EU AI Act Article 13 — Transparency of high-risk AI systems",
    "GDPR Article 22 — Automated individual decision-making",
    "GDPR Article 35 — Data Protection Impact Assessment",
    "EU AI Act Article 14 — Human oversight",
    "OECD AI Principle 1.3 — Transparency and explainability"
  ],
  "governance_reasoning": "Detailed explanation of how the decision was reached, why specific issues are critical, and the confidence level in this assessment.",
  "agent_disagreements": [
    "Technical Agent found no explainability mechanism (HIGH severity), while Compliance Agent assessed transparency as PARTIALLY_SATISFIED — this gap suggests the compliance assessment may be too lenient given the technical reality."
  ]
}}

Uncertainty values: LOW | MODERATE | HIGH (referring to uncertainty in the assessment, not risk level)
Decision must be one of: APPROVED | CONDITIONAL_APPROVAL | REJECTED | ABSTAINED

Provide 3-6 key issues, 4-8 required actions, and clear governance reasoning."""

        self.log.info("governance_agent_deciding")

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.05,
            agent_id=self.role.value,
        )

        # Parse decision
        try:
            decision = DecisionType(raw.get("decision", "ABSTAINED"))
        except ValueError:
            decision = DecisionType.ABSTAINED

        try:
            overall_risk = RiskLevel(raw.get("overall_risk", "HIGH"))
        except ValueError:
            overall_risk = context.risk_output.overall_risk_level if context.risk_output else RiskLevel.HIGH

        # Map uncertainty string to EvidenceStrength (inverted: HIGH uncertainty = WEAK evidence)
        uncertainty_map = {
            "LOW": EvidenceStrength.STRONG,
            "MODERATE": EvidenceStrength.MODERATE,
            "HIGH": EvidenceStrength.WEAK,
        }
        uncertainty = uncertainty_map.get(
            raw.get("uncertainty", "MODERATE").upper(), EvidenceStrength.MODERATE
        )

        # Parse required actions
        actions = []
        for i, a in enumerate(raw.get("required_actions", [])):
            try:
                action = RequiredAction(
                    priority=int(a.get("priority", i + 1)),
                    title=a.get("title", "Unknown Action"),
                    description=a.get("description", ""),
                    category=a.get("category", "general"),
                    timeline=a.get("timeline", "before deployment"),
                )
                actions.append(action)
            except Exception as e:
                self.log.warning("action_parse_error", error=str(e))

        # Check abstention threshold
        compliance_confidence = float(raw.get("compliance_confidence", 0.5))
        from govagents.core.config import get_settings

        settings = get_settings()
        if compliance_confidence < settings.abstention_threshold and decision not in (
            DecisionType.REJECTED,
            DecisionType.ABSTAINED,
        ):
            self.log.warning(
                "low_confidence_flagged",
                confidence=compliance_confidence,
                threshold=settings.abstention_threshold,
            )

        report = GovernanceReport(
            proposal_id=proposal.id,
            proposal_title=proposal.title,
            decision=decision,
            overall_risk=overall_risk,
            compliance_confidence=compliance_confidence,
            uncertainty=uncertainty,
            policy_output=context.policy_output,
            compliance_output=context.compliance_output,
            risk_output=context.risk_output,
            ethics_output=context.ethics_output,
            technical_output=context.technical_output,
            key_issues=raw.get("key_issues", []),
            required_actions=actions,
            evidence_citations=raw.get("evidence_citations", []),
            governance_reasoning=raw.get("governance_reasoning", ""),
            agent_disagreements=raw.get("agent_disagreements", []),
            agent_messages=context.messages,
            token_usage=self.llm.get_usage_stats(),
        )

        self._emit_message(
            context,
            type=MessageType.FINAL,
            topic="governance_decision",
            content={
                "decision": decision.value,
                "overall_risk": overall_risk.value,
                "confidence": compliance_confidence,
            },
        )

        self.log.info(
            "governance_agent_complete",
            decision=decision.value,
            risk=overall_risk.value,
            confidence=compliance_confidence,
        )
        return report

    def _build_agent_summary(self, context: AgentContext) -> str:
        """Build a concise summary of all agent outputs for the Governance Agent."""
        sections = []

        if context.policy_output:
            p = context.policy_output
            req_titles = [f"- {r.title} ({r.source_name})" for r in p.requirements[:8]]
            sections.append(
                f"### Policy Agent Output\n"
                f"Identified {len(p.requirements)} applicable requirements:\n"
                + "\n".join(req_titles)
                + f"\n\nReasoning: {p.reasoning}"
            )

        if context.compliance_output:
            c = context.compliance_output
            assessments = []
            for a in c.requirement_assessments[:8]:
                assessments.append(
                    f"- {a.requirement_title}: {a.status.value} "
                    f"(confidence: {a.confidence:.2f}) — {a.reasoning[:150]}"
                )
            sections.append(
                f"### Compliance Agent Output\n"
                f"Overall: {c.overall_status.value} (score: {c.overall_compliance_score:.2f})\n"
                + "\n".join(assessments)
                + f"\n\nReasoning: {c.reasoning}"
            )

        if context.risk_output:
            r = context.risk_output
            risks = [
                f"- {ri.title} [{ri.severity.value}]: {ri.description[:120]}"
                for ri in r.risks[:6]
            ]
            sections.append(
                f"### Risk Agent Output\n"
                f"Overall Risk: {r.overall_risk_level.value} (score: {r.risk_score:.2f})\n"
                + "\n".join(risks)
                + f"\n\nReasoning: {r.reasoning}"
            )

        if context.ethics_output:
            e = context.ethics_output
            dims = [
                f"- {d.dimension}: {d.score:.2f} ({d.status.value})"
                for d in e.dimensions
            ]
            sections.append(
                f"### Ethics & Sovereignty Agent Output\n"
                f"Overall Score: {e.overall_score:.2f}\n"
                + "\n".join(dims)
                + f"\nSovereignty Concerns: {', '.join(e.sovereignty_concerns[:3])}"
                + f"\n\nReasoning: {e.reasoning}"
            )

        if context.technical_output:
            t = context.technical_output
            findings = [
                f"- [{f.severity.value}] {f.title}: {f.implication[:100]}"
                for f in t.findings[:6]
            ]
            sections.append(
                f"### Technical Agent Output\n"
                f"Architecture Compliant: {t.architecture_compliant}\n"
                + "\n".join(findings)
                + f"\n\nReasoning: {t.reasoning}"
            )

        return "\n\n".join(sections) if sections else "No agent outputs available."

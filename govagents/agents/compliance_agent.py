from typing import Callable
"""Compliance Agent — evaluates whether the proposal satisfies policy requirements."""

from __future__ import annotations

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    ComplianceAgentOutput,
    ComplianceStatus,
    EvidenceStrength,
    MessageType,
    RequirementAssessment,
)


@registry.register_agent("ComplianceAgent")
class ComplianceAgent(BaseAgent):
    """Checks whether an AI proposal satisfies identified governance requirements.

    For each requirement from the PolicyAgent, this agent determines:
    - Whether the proposal satisfies it (status + confidence)
    - What evidence supports or contradicts compliance
    - What gaps exist
    """

    role = AgentRole.COMPLIANCE
    description = "Evaluates compliance with governance requirements"

    @property
    def system_prompt(self) -> str:
        return """You are the Compliance Agent in an AI governance assessment system.

Your job is to determine whether a given AI system or deployment proposal satisfies
specific governance requirements.

You must be rigorous, evidence-based, and honest about uncertainty.

Compliance statuses:
- SATISFIED: The proposal clearly meets the requirement with strong evidence
- PARTIALLY_SATISFIED: Some aspects are met but important gaps remain
- NOT_SATISFIED: The proposal clearly fails to meet the requirement
- UNKNOWN: Insufficient information to make a determination
- NOT_APPLICABLE: The requirement does not apply to this specific proposal

Confidence levels should reflect actual certainty (0.0-1.0):
- 0.9-1.0: Very strong evidence, clear determination
- 0.7-0.89: Good evidence, reasonable certainty
- 0.5-0.69: Moderate evidence, some uncertainty
- 0.3-0.49: Weak evidence, significant uncertainty
- 0.0-0.29: Very little evidence, mostly inference

You MUST respond with valid JSON following the exact schema specified."""

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> ComplianceAgentOutput:
        requirements = context.retrieved_requirements
        proposal = context.proposal

        if not requirements:
            return ComplianceAgentOutput(
                requirement_assessments=[],
                overall_compliance_score=0.0,
                overall_status=ComplianceStatus.UNKNOWN,
                reasoning="No requirements were identified to assess.",
            )

        # Format requirements for assessment
        req_text = self._format_requirements(requirements)

        user_prompt = f"""Evaluate this AI system proposal against the identified governance requirements.

## AI System Proposal

**Title:** {proposal.title}
**Description:** {proposal.description}
**Organization:** {proposal.organization or "Not specified"}
**Sector:** {proposal.sector or "Not specified"}
**Deployment Context:** {proposal.deployment_context or "Not specified"}
**Technical Details:** {proposal.technical_details or "Not specified"}

## Governance Requirements to Assess

{req_text}

## Task

For each requirement, determine compliance status. Be explicit about what evidence (or lack thereof)
in the proposal supports your assessment.

Respond with this JSON structure:
{{
  "requirement_assessments": [
    {{
      "requirement_id": "req-001",
      "requirement_title": "Transparency obligation",
      "status": "PARTIALLY_SATISFIED",
      "confidence": 0.72,
      "evidence_strength": "MODERATE",
      "reasoning": "The proposal mentions user notification but does not specify the mechanism or content of transparency measures. GDPR Article 13 requires specific information to be provided.",
      "evidence_citations": ["The proposal states: '...'", "The proposal lacks: '...'"],
      "gaps": ["No clear mechanism for informing affected employees", "No specification of what information will be disclosed"]
    }}
  ],
  "overall_compliance_score": 0.55,
  "overall_status": "PARTIALLY_SATISFIED",
  "reasoning": "Overall assessment rationale"
}}

Evidence strength: STRONG | MODERATE | WEAK | NONE
Status options: SATISFIED | PARTIALLY_SATISFIED | NOT_SATISFIED | UNKNOWN | NOT_APPLICABLE

Be thorough. Assess every requirement listed."""

        self.log.info(
            "compliance_agent_assessing", requirements=len(requirements)
        )

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.05,
            agent_id=self.role.value,
        )

        # Parse assessments
        assessments = []
        for a in raw.get("requirement_assessments", []):
            try:
                assessment = RequirementAssessment(
                    requirement_id=a.get("requirement_id", "unknown"),
                    requirement_title=a.get("requirement_title", "Unknown"),
                    status=ComplianceStatus(a.get("status", "UNKNOWN")),
                    confidence=float(a.get("confidence", 0.5)),
                    evidence_strength=EvidenceStrength(
                        a.get("evidence_strength", "NONE")
                    ),
                    reasoning=a.get("reasoning", ""),
                    evidence_citations=a.get("evidence_citations", []),
                    gaps=a.get("gaps", []),
                )
                assessments.append(assessment)
            except Exception as e:
                self.log.warning("assessment_parse_error", error=str(e), data=a)

        overall_score = float(raw.get("overall_compliance_score", 0.0))

        try:
            overall_status = ComplianceStatus(raw.get("overall_status", "UNKNOWN"))
        except ValueError:
            overall_status = self._derive_status(assessments)

        output = ComplianceAgentOutput(
            requirement_assessments=assessments,
            overall_compliance_score=overall_score,
            overall_status=overall_status,
            reasoning=raw.get("reasoning", ""),
        )
        context.compliance_output = output

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="compliance_assessment",
            content={
                "overall_status": overall_status.value,
                "compliance_score": overall_score,
                "assessments_count": len(assessments),
            },
        )

        self.log.info(
            "compliance_agent_complete",
            status=overall_status.value,
            score=overall_score,
        )
        return output

    def _format_requirements(self, requirements) -> str:
        lines = []
        for req in requirements:
            lines.append(
                f"**[{req.id}] {req.title}** ({req.source_name} {req.article or ''})\n"
                f"Type: {req.requirement_type}\n"
                f"Text: {req.text}\n"
            )
        return "\n".join(lines)

    def _derive_status(self, assessments: list[RequirementAssessment]) -> ComplianceStatus:
        """Derive overall status from individual assessments."""
        if not assessments:
            return ComplianceStatus.UNKNOWN
        statuses = [a.status for a in assessments]
        if all(s == ComplianceStatus.SATISFIED for s in statuses):
            return ComplianceStatus.SATISFIED
        if all(s == ComplianceStatus.NOT_SATISFIED for s in statuses):
            return ComplianceStatus.NOT_SATISFIED
        return ComplianceStatus.PARTIALLY_SATISFIED

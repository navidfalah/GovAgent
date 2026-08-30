"""Technical Agent — analyzes the proposed architecture for technical compliance gaps."""

from __future__ import annotations

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    MessageType,
    RiskLevel,
    TechnicalAgentOutput,
    TechnicalFinding,
)


@registry.register_agent("TechnicalAgent")
class TechnicalAgent(BaseAgent):
    """Analyzes the technical architecture and implementation for governance compliance.

    Evaluates:
    - Data pipeline and data governance
    - Model architecture suitability
    - Explainability and auditability infrastructure
    - Security and access control
    - Monitoring and incident response capability
    - Scalability and reliability
    - Vendor dependencies and lock-in
    """

    role = AgentRole.TECHNICAL
    description = "Analyzes technical architecture for compliance gaps"

    @property
    def system_prompt(self) -> str:
        return """You are the Technical Agent in an AI governance assessment system.

Your job is to analyze the technical architecture and implementation details of an AI system
proposal from a governance compliance perspective.

You focus on:
1. **Data Architecture**: Data lineage, quality controls, access controls, retention
2. **Model Architecture**: Explainability, auditability, bias detection capabilities
3. **Operational Infrastructure**: Monitoring, logging, alerting, incident response
4. **Security**: Authentication, authorization, data encryption, adversarial robustness
5. **Audit Trail**: Logging of decisions, inputs, outputs, model versions
6. **Human-in-the-Loop**: Technical mechanisms for human review and override
7. **Vendor & Supply Chain**: Dependencies, third-party risks, data sovereignty

For each finding, assess:
- Severity: LOW | MEDIUM | HIGH | CRITICAL
- Technical implication
- Specific recommendation

A finding is CRITICAL if it makes compliance impossible without architectural change.
A finding is HIGH if it creates significant compliance risk.

You MUST respond with valid JSON following the exact schema specified."""

    async def run(self, context: AgentContext) -> TechnicalAgentOutput:
        proposal = context.proposal
        requirements = context.retrieved_requirements

        req_types = list({r.requirement_type for r in requirements})
        req_summary = ", ".join(req_types) if req_types else "general governance"

        user_prompt = f"""Analyze the technical aspects of this AI proposal for governance compliance.

## AI System Proposal

**Title:** {proposal.title}
**Description:** {proposal.description}
**Organization:** {proposal.organization or "Not specified"}
**Sector:** {proposal.sector or "Not specified"}
**Deployment Context:** {proposal.deployment_context or "Not specified"}
**Technical Details:** {proposal.technical_details or "Not provided — analyze based on description"}

## Governance Requirements Applying to This System

Types of requirements: {req_summary}

## Task

Identify technical findings that affect governance compliance. For each finding,
explain the governance implication and provide a concrete technical recommendation.

If no technical details are provided, infer likely technical characteristics from the description
and flag what information would be needed.

Respond with this JSON structure:
{{
  "findings": [
    {{
      "title": "No explainability layer in AI decision pipeline",
      "severity": "HIGH",
      "description": "The proposal describes an AI system for analyzing employee communications but does not mention any explainability mechanism (e.g., SHAP, LIME, attention maps, rule extraction) that would allow humans to understand why a particular productivity assessment was produced.",
      "implication": "Without explainability, the system cannot satisfy transparency requirements (EU AI Act Article 13, GDPR Article 22) and managers cannot meaningfully review AI assessments.",
      "recommendation": "Integrate an explainability framework (e.g., SHAP values for tabular features, attention visualization for NLP) and expose explanation data through the user interface."
    }}
  ],
  "architecture_compliant": false,
  "technical_debt": [
    "Missing: audit logging infrastructure",
    "Missing: human review workflow",
    "Unknown: data retention and deletion mechanisms"
  ],
  "reasoning": "Technical assessment summary"
}}

Identify 4-10 specific technical findings. Focus on governance-relevant technical gaps."""

        self.log.info("technical_agent_analyzing")

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.1,
            agent_id=self.role.value,
        )

        findings = []
        for f in raw.get("findings", []):
            try:
                finding = TechnicalFinding(
                    title=f.get("title", "Unknown Finding"),
                    severity=RiskLevel(f.get("severity", "MEDIUM")),
                    description=f.get("description", ""),
                    implication=f.get("implication", ""),
                    recommendation=f.get("recommendation", ""),
                )
                findings.append(finding)
            except Exception as e:
                self.log.warning("finding_parse_error", error=str(e), data=f)

        output = TechnicalAgentOutput(
            findings=findings,
            architecture_compliant=bool(raw.get("architecture_compliant", False)),
            technical_debt=raw.get("technical_debt", []),
            reasoning=raw.get("reasoning", ""),
        )
        context.technical_output = output

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="technical_assessment",
            content={
                "findings_count": len(findings),
                "architecture_compliant": output.architecture_compliant,
                "critical_findings": sum(
                    1 for f in findings if f.severity == RiskLevel.CRITICAL
                ),
            },
        )

        self.log.info(
            "technical_agent_complete",
            findings=len(findings),
            compliant=output.architecture_compliant,
        )
        return output

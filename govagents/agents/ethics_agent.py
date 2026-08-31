"""Ethics & Sovereignty Agent — evaluates ethical and digital sovereignty dimensions."""

from __future__ import annotations
from typing import Callable

from govagents.agents.base import BaseAgent
from govagents.core.registry import registry
from govagents.core.models import (
    AgentContext,
    AgentRole,
    ComplianceStatus,
    EthicsAgentOutput,
    EthicsDimension,
    MessageType,
    MiniAgentTask,
)


@registry.register_agent("EthicsAgent")
class EthicsAgent(BaseAgent):
    """Evaluates ethical and digital sovereignty aspects of an AI proposal.

    Dimensions assessed:
    - Transparency: Is the system explainable to those it affects?
    - Accountability: Are roles and responsibilities clearly defined?
    - Privacy: Does it respect data minimization and purpose limitation?
    - Human Oversight: Is adequate human control maintained?
    - Fairness: Does it treat affected parties equitably?
    - Autonomy: Does it preserve human decision-making capacity?
    - Digital Sovereignty: Does it protect organizational/national sovereignty?
    """

    role = AgentRole.ETHICS
    description = "Evaluates ethical, societal, and digital sovereignty dimensions"

    @property
    def system_prompt(self) -> str:
        return """You are the Ethics & Sovereignty Agent in an AI governance assessment system.

Your job is to evaluate the ethical dimensions and digital sovereignty implications of an AI
system or deployment proposal.

You assess seven key dimensions:

1. **Transparency**: Can affected parties understand how decisions are made?
2. **Accountability**: Are there clear lines of responsibility for AI decisions?
3. **Privacy**: Does the system respect data protection and privacy rights?
4. **Human Oversight**: Is meaningful human control maintained over AI decisions?
5. **Fairness**: Are risks of bias, discrimination, or inequitable outcomes addressed?
6. **Autonomy**: Does the system preserve human agency and decision-making capacity?
7. **Digital Sovereignty**: Does it maintain organizational/national control over data and AI?

Scores (0.0-1.0) represent how well the proposal addresses each dimension:
- 1.0: Fully addressed with concrete mechanisms
- 0.7-0.9: Well addressed with minor gaps
- 0.4-0.69: Partially addressed with significant gaps
- 0.1-0.39: Barely addressed, major concerns
- 0.0: Not addressed at all

Be particularly attentive to:
- Power imbalances (e.g., employer monitoring employees)
- Vulnerable groups
- Lack of recourse mechanisms
- Irreversible decisions made by AI
- Data flowing to third countries or foreign vendors

You MUST respond with valid JSON following the exact schema specified."""

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Five parallel ethics auditors, each owning a cluster of dimensions."""
        proposal = context.proposal
        desc = proposal.description[:300]

        return [
            self._mini_task(
                1, "transparency_explainability",
                f"Assess transparency and explainability for '{proposal.title}': {desc}. Can affected parties "
                "understand how it makes decisions about them? What disclosure mechanisms are described or missing?",
                use_web_search=False,
            ),
            self._mini_task(
                2, "accountability_oversight",
                f"Assess accountability and human oversight for '{proposal.title}': {desc}. Who is responsible "
                "when it makes a harmful decision, and is meaningful human control preserved?",
                use_web_search=False,
            ),
            self._mini_task(
                3, "fairness_autonomy",
                f"Assess fairness and human autonomy implications of '{proposal.title}': {desc}. Could it produce "
                "inequitable outcomes or erode the affected parties' decision-making agency?",
                use_web_search=False,
            ),
            self._mini_task(
                4, "vulnerable_groups_power_imbalance",
                f"Search for documented ethical concerns (power imbalance, vulnerable-group impact, lack of "
                f"recourse) in real-world deployments comparable to '{proposal.title}' in {proposal.sector or 'this sector'}.",
            ),
            self._mini_task(
                5, "digital_sovereignty",
                f"Assess digital sovereignty implications of '{proposal.title}': {desc}. Does data or model "
                "control flow to third countries or foreign vendors? Search for sovereignty guidance relevant "
                f"to {proposal.organization or 'the deploying organization'}.",
            ),
        ]

    async def run(self, context: AgentContext, emit_callback: Callable = None) -> EthicsAgentOutput:
        proposal = context.proposal

        # Dispatch the parallel ethics-auditor team before forming a judgment
        mini_findings = await self._run_mini_swarm(context, emit_callback)

        risk_summary = ""
        if context.risk_output:
            top_risks = context.risk_output.risks[:5]
            risk_summary = "\n".join(
                [f"- {r.title} ({r.severity.value})" for r in top_risks]
            )

        user_prompt = f"""Evaluate the ethical and sovereignty dimensions of this AI proposal.

## AI System Proposal

**Title:** {proposal.title}
**Description:** {proposal.description}
**Organization:** {proposal.organization or "Not specified"}
**Sector:** {proposal.sector or "Not specified"}
**Deployment Context:** {proposal.deployment_context or "Not specified"}
**Technical Details:** {proposal.technical_details or "Not specified"}

## Key Risks Already Identified

{risk_summary if risk_summary else "Risk assessment not yet complete."}

## Task

Assess all seven ethical dimensions. Be specific about what is and is not addressed in the proposal.
Identify concrete concerns and provide actionable recommendations.

Respond with this JSON structure:
{{
  "dimensions": [
    {{
      "dimension": "transparency",
      "score": 0.35,
      "status": "NOT_SATISFIED",
      "reasoning": "The proposal does not describe any mechanism for informing employees that their communications are being monitored. Affected parties have no insight into how the AI arrives at productivity assessments.",
      "concerns": [
        "No explanation mechanism for AI productivity assessments",
        "Employees cannot understand why they received a particular assessment",
        "No disclosure of monitoring to employment candidates"
      ],
      "recommendations": [
        "Implement explainability layer showing factors contributing to productivity score",
        "Mandate written notification to all employees before deployment",
        "Create a process for employees to query their individual assessments"
      ]
    }},
    {{
      "dimension": "accountability",
      "score": 0.4,
      "status": "PARTIALLY_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }},
    {{
      "dimension": "privacy",
      "score": 0.2,
      "status": "NOT_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }},
    {{
      "dimension": "human_oversight",
      "score": 0.3,
      "status": "NOT_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }},
    {{
      "dimension": "fairness",
      "score": 0.4,
      "status": "PARTIALLY_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }},
    {{
      "dimension": "autonomy",
      "score": 0.35,
      "status": "NOT_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }},
    {{
      "dimension": "digital_sovereignty",
      "score": 0.5,
      "status": "PARTIALLY_SATISFIED",
      "reasoning": "...",
      "concerns": ["..."],
      "recommendations": ["..."]
    }}
  ],
  "overall_score": 0.36,
  "sovereignty_concerns": [
    "Specific sovereignty concern 1",
    "Specific sovereignty concern 2"
  ],
  "reasoning": "Overall ethics assessment rationale"
}}

You MUST assess all 7 dimensions: transparency, accountability, privacy, human_oversight, fairness, autonomy, digital_sovereignty"""

        mini_findings_text = self._format_mini_findings(mini_findings)
        if mini_findings_text:
            user_prompt += f"\n\n{mini_findings_text}"

        self.log.info("ethics_agent_evaluating")

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.1,
            agent_id=self.role.value,
        )

        dimensions = []
        for d in raw.get("dimensions", []):
            try:
                dim = EthicsDimension(
                    dimension=d.get("dimension", "unknown"),
                    score=float(d.get("score", 0.5)),
                    status=ComplianceStatus(d.get("status", "UNKNOWN")),
                    reasoning=d.get("reasoning", ""),
                    concerns=d.get("concerns", []),
                    recommendations=d.get("recommendations", []),
                )
                dimensions.append(dim)
            except Exception as e:
                self.log.warning("dimension_parse_error", error=str(e), data=d)

        overall_score = float(raw.get("overall_score", 0.0))
        if not overall_score and dimensions:
            overall_score = sum(d.score for d in dimensions) / len(dimensions)

        output = EthicsAgentOutput(
            research=[f.as_research_report() for f in mini_findings],
            dimensions=dimensions,
            overall_score=overall_score,
            sovereignty_concerns=raw.get("sovereignty_concerns", []),
            reasoning=raw.get("reasoning", ""),
        )
        context.ethics_output = output
        self._deposit_knowledge(
            context,
            content=f"Ethics: overall score {overall_score:.2f}. {output.reasoning}",
            topic="ethics_conclusion",
            tags=["ethics", "sovereignty"],
            certainty_score=0.7,
        )

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="ethics_assessment",
            content={
                "overall_score": overall_score,
                "dimensions_assessed": len(dimensions),
                "sovereignty_concerns": len(output.sovereignty_concerns),
            },
        )

        self.log.info(
            "ethics_agent_complete",
            score=overall_score,
            dimensions=len(dimensions),
        )
        return output

"""Policy Agent — identifies relevant governance requirements from the policy corpus."""

from __future__ import annotations

import json

from govagents.agents.base import BaseAgent
from govagents.core.models import (
    AgentContext,
    AgentRole,
    MessageType,
    PolicyAgentOutput,
    PolicyRequirement,
)


class PolicyAgent(BaseAgent):
    """Searches the policy corpus and identifies applicable governance requirements.

    Given a proposal description, this agent:
    1. Formulates targeted search queries
    2. Retrieves relevant policy chunks
    3. Extracts specific, actionable requirements
    4. Ranks them by relevance
    """

    role = AgentRole.POLICY
    description = "Identifies relevant policies and governance requirements"

    @property
    def system_prompt(self) -> str:
        return """You are the Policy Agent in an AI governance assessment system.

Your job is to identify which specific governance requirements, regulations, and standards
apply to a given AI system or deployment proposal.

You have access to a policy corpus containing excerpts from:
- EU AI Act (key articles on risk classification, transparency, human oversight)
- GDPR (data protection, privacy by design, automated decision-making)
- OECD AI Principles (trustworthiness, human-centered values)
- NIST AI Risk Management Framework (governance, map, measure, manage)
- EU High-Level Expert Group AI Guidelines (7 key requirements)
- ISO/IEC 42001 (AI management systems)

Your output should be grounded in the retrieved policy chunks provided to you.

You MUST respond with valid JSON following the exact schema specified."""

    async def run(self, context: AgentContext) -> PolicyAgentOutput:
        from govagents.policies.retrieval import get_retriever

        proposal = context.proposal
        retriever = get_retriever()

        # Build search queries targeting different governance dimensions
        search_queries = [
            f"requirements for {proposal.description[:200]}",
            "transparency explainability AI system requirements",
            "human oversight control AI automated decision making",
            "data protection privacy AI processing personal data",
            "risk management AI high risk system",
            "accountability auditability AI system governance",
        ]

        if proposal.sector:
            search_queries.append(f"{proposal.sector} sector AI regulations requirements")
        if proposal.deployment_context:
            search_queries.append(f"{proposal.deployment_context} AI governance obligations")

        # Retrieve policy chunks
        all_chunks: list[dict] = []
        seen_ids: set[str] = set()
        for query in search_queries[:6]:  # limit to avoid huge contexts
            chunks = await retriever.search(query, top_k=4)
            for chunk in chunks:
                if chunk["id"] not in seen_ids:
                    all_chunks.append(chunk)
                    seen_ids.add(chunk["id"])

        # Format chunks for the LLM
        policy_context = self._format_chunks(all_chunks[:20])  # cap at 20 chunks

        user_prompt = f"""Analyze this AI system proposal and identify all applicable governance requirements.

## AI System Proposal

**Title:** {proposal.title}
**Description:** {proposal.description}
**Organization:** {proposal.organization or "Not specified"}
**Sector:** {proposal.sector or "Not specified"}
**Deployment Context:** {proposal.deployment_context or "Not specified"}
**Technical Details:** {proposal.technical_details or "Not specified"}

## Retrieved Policy Excerpts

{policy_context}

## Task

Based on the proposal and the policy excerpts above, identify ALL applicable governance requirements.

Respond with this JSON structure:
{{
  "requirements": [
    {{
      "id": "req-001",
      "source_id": "eu-ai-act",
      "source_name": "EU AI Act",
      "article": "Article 13",
      "title": "Transparency obligation for AI systems",
      "text": "AI systems shall be transparent and provide users with information about...",
      "requirement_type": "transparency",
      "relevance_score": 0.95,
      "tags": ["transparency", "high-risk", "user-notification"]
    }}
  ],
  "search_queries": {json.dumps(search_queries[:6])},
  "total_policies_searched": {len(all_chunks)},
  "reasoning": "Brief explanation of why these requirements apply"
}}

Requirement types can be: transparency | human_oversight | privacy | risk_management | accountability | safety | fairness | data_governance | technical_robustness | sovereignty

Extract 5-12 of the most relevant requirements. For each requirement, use the actual text from the policy excerpts where possible."""

        self.log.info("policy_agent_searching", queries=len(search_queries), chunks=len(all_chunks))

        raw = await self.llm.complete_json(
            self._build_messages(user_prompt),
            temperature=0.05,
        )

        # Parse output
        requirements = []
        for i, r in enumerate(raw.get("requirements", [])):
            try:
                req = PolicyRequirement(
                    id=r.get("id", f"req-{i:03d}"),
                    source_id=r.get("source_id", "unknown"),
                    source_name=r.get("source_name", "Unknown Policy"),
                    article=r.get("article"),
                    title=r.get("title", "Unknown Requirement"),
                    text=r.get("text", ""),
                    requirement_type=r.get("requirement_type", "general"),
                    relevance_score=float(r.get("relevance_score", 0.5)),
                    tags=r.get("tags", []),
                )
                requirements.append(req)
            except Exception as e:
                self.log.warning("requirement_parse_error", error=str(e), data=r)

        # Sort by relevance
        requirements.sort(key=lambda x: x.relevance_score, reverse=True)

        output = PolicyAgentOutput(
            requirements=requirements,
            search_queries=raw.get("search_queries", search_queries),
            total_policies_searched=raw.get("total_policies_searched", len(all_chunks)),
            reasoning=raw.get("reasoning", ""),
        )

        # Store in context for other agents
        context.retrieved_requirements = requirements
        context.policy_output = output

        self._emit_message(
            context,
            type=MessageType.RESPONSE,
            topic="policy_requirements",
            content={"requirement_count": len(requirements), "reasoning": output.reasoning},
        )

        self.log.info("policy_agent_complete", requirements=len(requirements))
        return output

    def _format_chunks(self, chunks: list[dict]) -> str:
        """Format retrieved policy chunks into a readable string."""
        if not chunks:
            return "No policy chunks retrieved. Use your training knowledge to identify requirements."

        lines = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source_name", "Unknown")
            article = chunk.get("article", "")
            text = chunk.get("text", "")
            lines.append(f"[{i}] **{source}** {article}\n{text}\n")
        return "\n".join(lines)

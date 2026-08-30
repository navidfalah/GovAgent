from typing import Callable
import structlog
from govagents.agents.base import BaseAgent
from govagents.core.models import AgentContext, PrivacyAgentOutput, PrivacyFinding

log = structlog.get_logger()

class PrivacyAgent(BaseAgent):
    """Analyzes data privacy, minimization, and GDPR compliance."""

    name = "Privacy Agent"
    system_prompt = """You are the Privacy Agent for an AI Governance platform.
Your job is to identify privacy concerns, PII handling issues, and data minimization violations in the AI system proposal.
Return a valid JSON object matching the `PrivacyAgentOutput` schema.
"""
    output_schema = PrivacyAgentOutput

    async def _execute(self, context: AgentContext) -> PrivacyAgentOutput:
        log.info("privacy_agent_evaluating")
        
        prompt = f"""Evaluate the privacy aspects of this AI system proposal.
        
Title: {context.proposal.title}
Description: {context.proposal.description}
Technical Details: {context.proposal.technical_details or 'N/A'}
Deployment Context: {context.proposal.deployment_context or 'N/A'}

Analyze the data types processed, identify PII, and assess data minimization.
Provide 2-5 specific privacy findings.
"""
        return await self.llm.structured_completion(
            prompt=prompt,
            schema=self.output_schema,
            system_prompt=self.system_prompt
        )

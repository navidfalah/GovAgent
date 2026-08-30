from typing import Callable
import structlog
from govagents.agents.base import BaseAgent
from govagents.core.models import AgentContext, SecurityAgentOutput, SecurityVulnerability

log = structlog.get_logger()

class SecurityAgent(BaseAgent):
    """Analyzes security, threat models, and vulnerabilities."""

    name = "Security Agent"
    system_prompt = """You are the Security Agent for an AI Governance platform.
Your job is to identify security vulnerabilities, attack vectors, and data flow risks in the AI system proposal.
Return a valid JSON object matching the `SecurityAgentOutput` schema.
"""
    output_schema = SecurityAgentOutput

    async def _execute(self, context: AgentContext) -> SecurityAgentOutput:
        log.info("security_agent_evaluating")
        
        prompt = f"""Evaluate the security aspects of this AI system proposal.
        
Title: {context.proposal.title}
Description: {context.proposal.description}
Technical Details: {context.proposal.technical_details or 'N/A'}
Deployment Context: {context.proposal.deployment_context or 'N/A'}

Analyze the architecture for vulnerabilities, injection risks, and encryption issues.
Provide 2-5 specific security vulnerabilities.
"""
        return await self.llm.structured_completion(
            prompt=prompt,
            schema=self.output_schema,
            system_prompt=self.system_prompt
        )

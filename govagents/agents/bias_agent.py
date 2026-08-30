from typing import Callable
import structlog
from govagents.agents.base import BaseAgent
from govagents.core.models import AgentContext, BiasAgentOutput, BiasFinding

log = structlog.get_logger()

class BiasAgent(BaseAgent):
    """Analyzes algorithmic fairness and bias."""

    name = "Bias Agent"
    system_prompt = """You are the Bias and Fairness Agent for an AI Governance platform.
Your job is to identify potential algorithmic biases, discrimination vectors, and unfairness in the AI system proposal.
Return a valid JSON object matching the `BiasAgentOutput` schema.
"""
    output_schema = BiasAgentOutput

    async def _execute(self, context: AgentContext) -> BiasAgentOutput:
        log.info("bias_agent_evaluating")
        
        prompt = f"""Evaluate the fairness and bias risks of this AI system proposal.
        
Title: {context.proposal.title}
Description: {context.proposal.description}
Technical Details: {context.proposal.technical_details or 'N/A'}
Deployment Context: {context.proposal.deployment_context or 'N/A'}

Analyze the potential for disparate impact, historical bias in data, and unfair outcomes.
Provide 2-5 specific bias findings.
"""
        return await self.llm.structured_completion(
            prompt=prompt,
            schema=self.output_schema,
            system_prompt=self.system_prompt
        )

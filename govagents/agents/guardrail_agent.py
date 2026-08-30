from typing import Callable
import structlog
from govagents.agents.base import BaseAgent
from govagents.core.models import AgentContext, GuardrailAgentOutput

log = structlog.get_logger()

class GuardrailAgent(BaseAgent):
    """Final check for absolute red lines before governance decision."""

    name = "Guardrail Agent"
    system_prompt = """You are the Guardrail Agent for an AI Governance platform.
Your job is to check if the AI system proposal violates any absolute 'red lines' (e.g., social scoring, real-time biometric surveillance).
Return a valid JSON object matching the `GuardrailAgentOutput` schema.
"""
    output_schema = GuardrailAgentOutput

    async def _execute(self, context: AgentContext) -> GuardrailAgentOutput:
        log.info("guardrail_agent_evaluating")
        
        prompt = f"""Evaluate this AI system proposal against absolute unacceptable risk red lines.
        
Title: {context.proposal.title}
Description: {context.proposal.description}
Technical Details: {context.proposal.technical_details or 'N/A'}
Deployment Context: {context.proposal.deployment_context or 'N/A'}

Are there any absolute red line violations (like social scoring, subliminal manipulation, or unacceptable biometric categorization)?
Return a boolean `triggered` and a list of specific violations if any.
"""
        return await self.llm.structured_completion(
            prompt=prompt,
            schema=self.output_schema,
            system_prompt=self.system_prompt
        )

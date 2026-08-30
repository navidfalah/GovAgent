"""NLI (Natural Language Inference) checking capability."""

from __future__ import annotations

from typing import Any

from govagents.capabilities.base import Capability
from govagents.core.llm import get_llm_client
from govagents.core.registry import registry
from govagents.core.logging import get_logger

log = get_logger(__name__)


@registry.register_capability("NLIChecker")
class NLICheckerCapability(Capability):
    """Fact-checks claims against evidence using an LLM-based NLI prompt."""

    async def execute(self, claim: str, evidence: str, **kwargs: Any) -> dict:
        llm = get_llm_client()
        prompt = f"""
        Determine if the following claim is supported by the evidence.
        Respond with exactly one word: ENTAILMENT, CONTRADICTION, or NEUTRAL.

        Claim: {claim}
        Evidence: {evidence}
        """
        response = await llm.generate(prompt)
        result = response.content.strip().upper()
        
        log.debug("nli_check", claim=claim[:50], result=result)
        
        return {
            "claim": claim,
            "result": result if result in ["ENTAILMENT", "CONTRADICTION", "NEUTRAL"] else "NEUTRAL"
        }

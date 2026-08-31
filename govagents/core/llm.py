"""LiteLLM wrapper for GovAgents with retry, token tracking, and structured output."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import litellm
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from govagents.core.config import Settings, get_settings
from govagents.core.logging import get_logger

log = get_logger(__name__)

# Silence LiteLLM's own verbose logging
litellm.set_verbose = False
os.environ["LITELLM_LOG"] = "ERROR"


class LLMClient:
    """A wrapper around LiteLLM providing retry logic, token tracking, and JSON parsing."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._configure_keys()
        self.total_tokens: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0

    def _configure_keys(self) -> None:
        """Set API keys in environment for LiteLLM."""
        s = self.settings
        if s.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = s.gemini_api_key
        if s.openai_api_key:
            os.environ["OPENAI_API_KEY"] = s.openai_api_key
        if s.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = s.anthropic_api_key
        if s.groq_api_key:
            os.environ["GROQ_API_KEY"] = s.groq_api_key

    @retry(
        retry=retry_if_exception_type((litellm.RateLimitError, litellm.Timeout)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
        agent_id: str | None = None,
    ) -> str:
        """Call the LLM and return the text response."""
        from govagents.core.config_manager import get_config_manager
        
        # Pull dynamic config
        dyn_config = get_config_manager().get_config()
        
        # Determine effective config for this request
        eff_model = dyn_config.llm_model
        eff_temp = dyn_config.llm_temperature
        eff_tokens = dyn_config.llm_max_tokens
        
        if agent_id and agent_id in dyn_config.agent_configs:
            ac = dyn_config.agent_configs[agent_id]
            eff_model = ac.get("llm_model") or eff_model
            if ac.get("llm_temperature") is not None:
                eff_temp = ac["llm_temperature"]
            if ac.get("llm_max_tokens") is not None:
                eff_tokens = ac["llm_max_tokens"]
        
        # Override environment API keys based on dynamic config
        if dyn_config.gemini_api_key: os.environ["GEMINI_API_KEY"] = dyn_config.gemini_api_key
        if dyn_config.openai_api_key: os.environ["OPENAI_API_KEY"] = dyn_config.openai_api_key
        if dyn_config.anthropic_api_key: os.environ["ANTHROPIC_API_KEY"] = dyn_config.anthropic_api_key
        if dyn_config.groq_api_key: os.environ["GROQ_API_KEY"] = dyn_config.groq_api_key

        s = self.settings
        kwargs: dict[str, Any] = {
            "model": model or eff_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else eff_temp,
            "max_tokens": max_tokens or eff_tokens,
            "timeout": s.llm_timeout,
        }
        if s.llm_base_url:
            kwargs["base_url"] = s.llm_base_url
        if response_format:
            kwargs["response_format"] = response_format

        log.debug("llm_request", model=kwargs["model"], messages_count=len(messages))

        response = await litellm.acompletion(**kwargs)

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.total_tokens += response.usage.total_tokens or 0
            self.total_prompt_tokens += response.usage.prompt_tokens or 0
            self.total_completion_tokens += response.usage.completion_tokens or 0

        content = response.choices[0].message.content or ""
        log.debug("llm_response", tokens=getattr(response, "usage", {}).get("total_tokens", 0))
        return content

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        require_cot: bool = True,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Call the LLM and parse the response as JSON.
        
        Args:
            require_cot: If True, instructs the model to reason inside <thought>...</thought> blocks before outputting JSON.
        """
        enhanced = list(messages)
        system_msgs = [m for m in enhanced if m.get("role") == "system"]
        
        instructions = "IMPORTANT: You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."
        if require_cot:
            instructions = (
                "IMPORTANT: You must first reason about the problem step-by-step inside a <thought>...</thought> block. "
                "After the </thought> tag, output ONLY valid JSON matching the requested schema. No other text."
            )

        if system_msgs:
            idx = enhanced.index(system_msgs[0])
            if "IMPORTANT:" not in enhanced[idx]["content"]:
                enhanced[idx] = {
                    "role": "system",
                    "content": enhanced[idx]["content"] + f"\n\n{instructions}",
                }
        else:
            enhanced.insert(0, {"role": "system", "content": instructions})

        text = await self.complete(enhanced, model=model, temperature=temperature, agent_id=agent_id)
        return self._parse_json(text)

    async def structured_completion(
        self,
        prompt: str,
        schema: type[BaseModel],
        system_prompt: str = "",
        temperature: float | None = None,
        agent_id: str | None = None,
    ) -> BaseModel:
        """Call the LLM and parse+validate the response against a Pydantic schema.

        Falls back to an unvalidated best-effort construction (defaults filled in
        for any missing fields) if the model's JSON doesn't cleanly validate, so a
        single malformed mini-agent response never takes down the whole swarm.
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt or "Respond with valid JSON only, matching the requested schema.",
            },
            {"role": "user", "content": prompt},
        ]
        raw = await self.complete_json(messages, temperature=temperature, agent_id=agent_id)
        try:
            return schema.model_validate(raw)
        except ValidationError as e:
            log.warning(
                "structured_completion_validation_error",
                schema=schema.__name__,
                error=str(e),
            )
            return schema.model_construct(**raw)

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM output, handling Chain-of-Thought blocks."""
        # Remove <thought> blocks
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
        
        # Try to extract from ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if match:
            text = match.group(1)

        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try finding the first {...} block
        brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        log.warning("json_parse_failed", text_preview=text[:200])
        return {}

    def get_usage_stats(self) -> dict[str, int]:
        """Return cumulative token usage stats."""
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
        }


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the default LLM client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client

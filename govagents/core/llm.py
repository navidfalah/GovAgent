"""LiteLLM wrapper for GovAgents with retry, token tracking, and structured output."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import litellm
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
    ) -> str:
        """Call the LLM and return the text response."""
        s = self.settings
        kwargs: dict[str, Any] = {
            "model": model or s.get_litellm_model(),
            "messages": messages,
            "temperature": temperature if temperature is not None else s.llm_temperature,
            "max_tokens": max_tokens or s.llm_max_tokens,
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
    ) -> dict[str, Any]:
        """Call the LLM and parse the response as JSON."""
        # Append JSON instruction to system message if not already there
        enhanced = list(messages)
        system_msgs = [m for m in enhanced if m.get("role") == "system"]
        if system_msgs:
            idx = enhanced.index(system_msgs[0])
            if "JSON" not in enhanced[idx]["content"]:
                enhanced[idx] = {
                    "role": "system",
                    "content": enhanced[idx]["content"]
                    + "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.",
                }
        else:
            enhanced.insert(
                0,
                {
                    "role": "system",
                    "content": "IMPORTANT: You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.",
                },
            )

        text = await self.complete(enhanced, model=model, temperature=temperature)
        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM output, handling markdown code blocks."""
        # Try to extract from ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)

        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try finding the first {...} block
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
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

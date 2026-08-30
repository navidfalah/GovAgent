"""Abstract base class for all GovAgents agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import AgentContext, AgentMessage, AgentRole, MessageType

log = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all specialized governance agents.

    Every agent has:
    - A well-defined role
    - A system prompt
    - Access to the shared LLM client
    - The ability to emit typed AgentMessages
    """

    role: AgentRole
    description: str = ""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()
        self.log = get_logger(f"govagents.agents.{self.role.value}")

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The agent's system prompt defining its role and behavior."""
        ...

    @abstractmethod
    async def run(self, context: AgentContext) -> Any:
        """Execute the agent's analysis and return its output model."""
        ...

    def _build_messages(
        self, user_prompt: str, extra_system: str = ""
    ) -> list[dict[str, str]]:
        """Build the messages list for an LLM call."""
        from govagents.core.config_manager import get_config_manager
        
        system = self.system_prompt
        # Override with dynamic config if provided
        dyn_config = get_config_manager().get_config()
        if self.role.value in dyn_config.agent_configs:
            custom_prompt = dyn_config.agent_configs[self.role.value].get("system_prompt")
            if custom_prompt:
                system = custom_prompt

        if extra_system:
            system = f"{system}\n\n{extra_system}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

    def _emit_message(
        self,
        context: AgentContext,
        type: MessageType,
        topic: str,
        content: dict[str, Any],
        receiver: AgentRole | None = None,
        in_reply_to: str | None = None,
    ) -> AgentMessage:
        """Create and store an AgentMessage in the context."""
        msg = AgentMessage(
            sender=self.role,
            receiver=receiver,
            type=type,
            topic=topic,
            content=content,
            in_reply_to=in_reply_to,
        )
        context.messages.append(msg)
        self.log.debug(
            "agent_message",
            sender=self.role.value,
            type=type.value,
            topic=topic,
        )
        return msg

    async def _timed_run(self, context: AgentContext) -> tuple[Any, float]:
        """Run the agent and return (output, elapsed_seconds)."""
        start = time.perf_counter()
        result = await self.run(context)
        elapsed = time.perf_counter() - start
        self.log.info(
            "agent_complete",
            agent=self.role.value,
            elapsed_s=round(elapsed, 2),
        )
        return result, elapsed

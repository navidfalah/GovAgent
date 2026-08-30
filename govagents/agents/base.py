"""Abstract base class for all GovAgents agents."""

from __future__ import annotations

import time
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import AgentContext, AgentMessage, AgentRole, MessageType, AgentPlan, ResearchReport
from govagents.agents.sub_agent import ResearchSubAgent

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
    async def run(self, context: AgentContext, emit_callback: Callable[[str, str, dict], Coroutine[Any, Any, None]] | None = None) -> Any:
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

    async def _timed_run(self, context: AgentContext, emit_callback: Callable[[str, str, dict], Coroutine[Any, Any, None]] | None = None) -> tuple[Any, float]:
        """Run the agent and return (output, elapsed_seconds)."""
        start = time.perf_counter()
        result = await self.run(context, emit_callback=emit_callback)
        elapsed = time.perf_counter() - start
        self.log.info(
            "agent_complete",
            agent=self.role.value,
            elapsed_s=round(elapsed, 2),
        )
        return result, elapsed

    async def _plan_and_research(
        self, 
        context: AgentContext, 
        user_prompt: str,
        emit_callback: Callable[[str, str, dict], Coroutine[Any, Any, None]] | None = None
    ) -> list[ResearchReport]:
        """Ask LLM if it needs to search the web, and if so, spawn sub-agents."""
        plan_prompt = f"""You are in a planning phase. Before evaluating the following task, do you need to search the live internet for additional context, news, or specific facts?
Task to evaluate:
{user_prompt}

If you have enough context in the proposal, reply with needs_research = false.
If you need more information (e.g. recent regulations, technical docs, company news), reply with needs_research = true and provide a list of search_queries.
Keep queries specific. Return valid JSON matching the AgentPlan schema."""

        plan_raw = await self.llm.structured_completion(
            prompt=plan_prompt,
            schema=AgentPlan,
            system_prompt="You are a planning assistant deciding if internet research is needed."
        )

        research_reports = []
        if plan_raw.needs_research and plan_raw.search_queries:
            self.log.info("spawning_subagents", count=len(plan_raw.search_queries))
            
            # Concurrently spawn subagents
            async def _run_subagent(query: str):
                if emit_callback:
                    await emit_callback("subagent_spawned", self.role.value, {"query": query})
                
                subagent = ResearchSubAgent(query)
                report = await subagent.run()
                
                if emit_callback:
                    await emit_callback("subagent_complete", self.role.value, {
                        "query": query, 
                        "findings": len(report.findings),
                        "certainty": round(report.certainty_score, 2)
                    })
                return report

            tasks = [_run_subagent(q) for q in plan_raw.search_queries[:3]] # limit to 3 queries max
            research_reports = await asyncio.gather(*tasks)

        return research_reports

"""Abstract base class for all GovAgents agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    AgentMessage,
    AgentRole,
    KnowledgeScope,
    MessageType,
    MiniAgentFinding,
    MiniAgentTask,
)
from govagents.agents.mini_agent import MiniAgentSwarm
from govagents.orchestration.knowledge import deposit_knowledge

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

    def mini_agent_tasks(self, context: AgentContext) -> list[MiniAgentTask]:
        """Define this module's parallel mini-agent team for the given proposal.

        Every concrete agent overrides this to return several (typically 4-6)
        narrow, proposal-specific assignments. The default is an empty team —
        a module that doesn't override this simply reasons on its own.
        """
        return []

    def _mini_task(
        self, idx: int, focus: str, instruction: str, use_web_search: bool = True
    ) -> MiniAgentTask:
        """Helper for building a MiniAgentTask with a stable, namespaced id."""
        return MiniAgentTask(
            id=f"{self.role.value}-{idx}-{focus}",
            focus=focus,
            instruction=instruction,
            use_web_search=use_web_search,
        )

    async def _run_mini_swarm(
        self,
        context: AgentContext,
        emit_callback: Callable[[str, str, dict], Coroutine[Any, Any, None]] | None = None,
    ) -> list[MiniAgentFinding]:
        """Spawn this module's parallel mini-agent team and collect their findings.

        Each module fields its own small team of focused specialists that each
        investigate one narrow angle concurrently (legal precedent, a specific
        risk vector, a specific ethics dimension, ...). The module's own LLM
        call then acts as team lead, judging the whole body of findings rather
        than researching the entire domain by itself.
        """
        from govagents.core.config import get_settings

        tasks = self.mini_agent_tasks(context)
        if not tasks:
            return []

        settings = get_settings()
        swarm = MiniAgentSwarm(
            parent_role=self.role.value,
            llm_client=self.llm,
            max_concurrency=settings.mini_agent_max_concurrency,
        )
        findings = await swarm.run(tasks, context, emit_callback=emit_callback)
        context.mini_agent_findings[self.role.value] = findings
        return findings

    def _deposit_knowledge(
        self,
        context: AgentContext,
        content: str,
        topic: str = "",
        tags: list[str] | None = None,
        certainty_score: float = 0.6,
        scope: KnowledgeScope = KnowledgeScope.SHARED,
    ) -> None:
        """Deposit this module's own conclusion into the shared knowledge pool.

        Mini-agents already deposit their individual findings automatically;
        this is the module-level counterpart — one summary entry per module
        run, so other modules (and the Governance Agent) can later query it
        through the same attention-filtered access path.
        """
        deposit_knowledge(
            context,
            source_agent=self.role,
            content=content,
            topic=topic or self.role.value,
            tags=list(set((tags or []) + [self.role.value])),
            certainty_score=certainty_score,
            scope=scope,
            source_kind="module",
        )

    @staticmethod
    def _format_mini_findings(findings: list[MiniAgentFinding]) -> str:
        """Render a module's mini-agent briefs for injection into its synthesis prompt."""
        if not findings:
            return ""

        blocks = ["## Findings From Your Specialist Mini-Agent Team", ""]
        for f in findings:
            bullet_points = "\n".join(f"- {item}" for item in f.findings) or "- (no specific findings returned)"
            rec = f"\n  → Recommendation: {f.recommendation}" if f.recommendation else ""
            blocks.append(
                f"### [{f.focus}] certainty={f.certainty_score:.2f} concern={f.concern_level.value}\n"
                f"{f.summary}\n{bullet_points}{rec}"
            )
        blocks.append(
            "\nAs the module lead, weigh these findings together: note where your specialists agree, "
            "where they contradict each other, and where certainty is weak. Do not simply average their "
            "scores — reason about *why* they agree or disagree before forming your own judgment."
        )
        return "\n\n".join(blocks)

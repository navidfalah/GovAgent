"""Mini-agent swarm framework.

Every governance module (Policy, Compliance, Risk, Ethics, Technical, Privacy,
Security, Bias, Guardrail) is a "team lead" that does not investigate the
proposal alone. Instead it dispatches a small team of mini-agents that each
own exactly one narrow question — a single legal angle, a single risk vector,
a single technical concern — and run concurrently, optionally backed by a
live web search. Each mini-agent reports back a structured, evidence-scored
brief. The parent module's own LLM call then acts as the lead analyst,
judging the whole body of briefs (agreement, contradiction, gaps in
certainty) rather than trying to cover the entire domain in one shot.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from govagents.core.llm import LLMClient, get_llm_client
from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    AgentRole,
    KnowledgeScope,
    MiniAgentFinding,
    MiniAgentTask,
    Proposal,
    RiskLevel,
)
from govagents.orchestration.knowledge import (
    deposit_knowledge,
    format_knowledge_for_prompt,
    query_knowledge,
)

log = get_logger(__name__)

EmitCallback = Callable[[str, str, dict], Coroutine[Any, Any, None]]

# A mini-agent may request at most one level of recursive follow-up. This keeps
# "dig deeper when something looks off" bounded — a single specialist can spawn
# one micro-agent, but that micro-agent cannot spawn another.
MAX_RECURSION_DEPTH = 1


class MiniAgentSwarm:
    """Runs one module's mini-agent team concurrently and collects their findings.

    Findings are flat by the time `run()` returns: any micro-agent spawned by a
    mini-agent that hit something needing deeper investigation is appended
    alongside its parent's finding, not nested — the module lead judges the
    whole flat set together.
    """

    def __init__(
        self,
        parent_role: str,
        llm_client: LLMClient | None = None,
        max_concurrency: int = 8,
    ) -> None:
        self.parent_role = parent_role
        self.llm = llm_client or get_llm_client()
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run(
        self,
        tasks: list[MiniAgentTask],
        context: AgentContext,
        emit_callback: EmitCallback | None = None,
    ) -> list[MiniAgentFinding]:
        """Dispatch every task to its own mini-agent, in parallel, and gather results."""
        if not tasks:
            return []

        async def _run_one(task: MiniAgentTask) -> list[MiniAgentFinding]:
            async with self._semaphore:
                return await self._run_with_followups(task, context, emit_callback, depth=0)

        log.info("mini_swarm_start", module=self.parent_role, agents=len(tasks))
        nested = await asyncio.gather(*[_run_one(t) for t in tasks])
        findings = [f for group in nested for f in group]
        log.info(
            "mini_swarm_complete",
            module=self.parent_role,
            agents=len(tasks),
            total_findings=len(findings),
        )
        return findings

    async def _run_with_followups(
        self,
        task: MiniAgentTask,
        context: AgentContext,
        emit_callback: EmitCallback | None,
        depth: int,
    ) -> list[MiniAgentFinding]:
        """Execute one mini-agent task, then recursively spawn its requested
        follow-up (if any and depth allows), returning [self, *followups]."""
        if emit_callback:
            await emit_callback(
                "subagent_spawned",
                self.parent_role,
                {"query": task.instruction, "focus": task.focus, "task_id": task.id, "depth": depth},
            )

        finding = await self._execute_task(task, context, depth)

        if emit_callback:
            await emit_callback(
                "subagent_complete",
                self.parent_role,
                {
                    "query": task.instruction,
                    "focus": task.focus,
                    "task_id": task.id,
                    "depth": depth,
                    "findings": len(finding.findings),
                    "certainty": round(finding.certainty_score, 2),
                    "concern_level": finding.concern_level.value,
                },
            )

        results = [finding]

        if finding.needs_followup and finding.followup_question and depth < MAX_RECURSION_DEPTH:
            log.info(
                "mini_agent_spawning_followup",
                module=self.parent_role,
                parent_task=task.id,
                depth=depth + 1,
            )
            child_task = MiniAgentTask(
                id=f"{task.id}-micro-{depth + 1}",
                focus=f"{task.focus}.followup",
                instruction=finding.followup_question,
                use_web_search=task.use_web_search,
            )
            async with self._semaphore:
                results.extend(
                    await self._run_with_followups(child_task, context, emit_callback, depth + 1)
                )

        return results

    async def _execute_task(
        self, task: MiniAgentTask, context: AgentContext, depth: int = 0
    ) -> MiniAgentFinding:
        proposal = context.proposal
        research_section = "No live web research was performed for this assignment — reason from the proposal and your own knowledge."
        urls: list[str] = []

        if task.use_web_search:
            sources_text, urls = await self._web_search(task, proposal)
            if sources_text:
                research_section = sources_text

        try:
            parent_role_enum = AgentRole(self.parent_role)
        except ValueError:
            parent_role_enum = AgentRole.GOVERNANCE

        shared_knowledge = query_knowledge(
            context,
            reader_agent=parent_role_enum,
            tags=[task.focus],
            topic_contains=task.focus,
            limit=5,
        )
        knowledge_section = format_knowledge_for_prompt(shared_knowledge)

        agent_kind = "micro-agent" if depth > 0 else "mini-agent"
        followup_hint = (
            ""
            if depth >= MAX_RECURSION_DEPTH
            else (
                "\nIf, while investigating, you uncover something specific that is concerning but you "
                "cannot resolve with the information you have, you may request ONE narrower follow-up "
                "investigation: set needs_followup=true and write a precise, self-contained "
                "followup_question for a micro-agent to answer next. Only do this when genuinely warranted "
                "— most assignments should NOT need a follow-up."
            )
        )

        prompt = f"""You are a specialist {agent_kind} working inside the "{self.parent_role}" governance module.
You have exactly ONE narrow assignment. Answer it precisely — do not try to cover the whole proposal,
that is your module lead's job once your team reports back.

## Your assignment ({task.focus})
{task.instruction}

## AI System Proposal Under Review
Title: {proposal.title}
Description: {proposal.description}
Organization: {proposal.organization or "Not specified"}
Sector: {proposal.sector or "Not specified"}
Deployment Context: {proposal.deployment_context or "Not specified"}
Technical Details: {proposal.technical_details or "Not specified"}

## Research
{research_section}

{knowledge_section}

## Output
Report back to your module lead with:
- summary: one or two sentence bottom line for your assignment
- findings: 2-5 concrete, specific bullet points (facts, citations, or concrete gaps you found)
- certainty_score (0.0-1.0): how confident you are in these findings
- concern_level: LOW | MEDIUM | HIGH | CRITICAL — how serious this specific angle is for this proposal
- recommendation: one concrete, actionable recommendation tied strictly to your assignment
- sources: any URLs you relied on (empty list if none){followup_hint}

Be specific to THIS proposal. Generic boilerplate is useless to your lead."""

        try:
            finding = await self.llm.structured_completion(
                prompt=prompt,
                schema=MiniAgentFinding,
                system_prompt=(
                    "You are a precise, evidence-driven specialist analyst. Stay strictly within your "
                    "assigned focus area and be concrete. You MUST respond with valid JSON only."
                ),
                temperature=0.15,
                agent_id=f"{self.parent_role}.mini.{task.focus}",
            )
        except Exception as e:  # never let one failed mini-agent take down the swarm
            log.error("mini_agent_error", task=task.id, error=str(e))
            finding = MiniAgentFinding(
                task_id=task.id,
                focus=task.focus,
                summary=f"Mini-agent failed to complete its assignment: {e}",
                findings=[],
                certainty_score=0.0,
                concern_level=RiskLevel.LOW,
            )

        finding.task_id = task.id
        finding.focus = task.focus
        finding.depth = depth
        if depth >= MAX_RECURSION_DEPTH:
            finding.needs_followup = False
        if not finding.sources:
            finding.sources = urls

        deposit_knowledge(
            context,
            source_agent=parent_role_enum,
            content=f"{finding.summary} " + "; ".join(finding.findings[:3]),
            topic=task.focus,
            tags=[self.parent_role, task.focus],
            certainty_score=finding.certainty_score,
            scope=KnowledgeScope.SHARED,
            source_kind="micro_agent" if depth > 0 else "mini_agent",
        )

        return finding

    async def _web_search(self, task: MiniAgentTask, proposal: Proposal) -> tuple[str, list[str]]:
        """Run a live web search for this mini-agent's assignment. Best-effort; never raises."""
        from govagents.core.config import get_settings

        settings = get_settings()
        if not settings.enable_mini_agent_web_search:
            return "", []

        query = f"{task.instruction} {proposal.sector or ''}".strip()[:300]

        try:
            from duckduckgo_search import DDGS

            def _search() -> list[dict]:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=3))

            results = await asyncio.to_thread(_search)
        except Exception as e:
            log.warning("mini_agent_search_failed", query=query, error=str(e))
            return "", []

        if not results:
            return "", []

        urls = [r.get("href", "") for r in results if r.get("href")]
        text = "\n\n".join(
            f"Source: {r.get('href')}\nSnippet: {r.get('body')}" for r in results
        )
        return text, urls

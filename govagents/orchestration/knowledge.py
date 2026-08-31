"""Shared knowledge pool — attention-filtered cross-agent memory.

Mini-agents, their recursively-spawned micro-agents, and the governance
modules themselves all deposit what they learn into one pool attached to the
run's `AgentContext`. Nobody gets a blind dump of it back, though: every read
goes through `query_knowledge`, which enforces scope (who is even allowed to
see an entry) and then ranks what remains by tag/topic overlap with the
reader's own focus, returning only the most relevant handful. This is the
"attention" mechanism — it is what keeps a Compliance mini-agent from being
buried in irrelevant Security findings while still letting genuinely related
cross-module evidence surface.
"""

from __future__ import annotations

from govagents.core.logging import get_logger
from govagents.core.models import (
    AgentContext,
    AgentRole,
    KnowledgeEntry,
    KnowledgeScope,
)

log = get_logger(__name__)


def deposit_knowledge(
    context: AgentContext,
    source_agent: AgentRole,
    content: str,
    topic: str = "",
    tags: list[str] | None = None,
    certainty_score: float = 0.5,
    scope: KnowledgeScope = KnowledgeScope.SHARED,
    source_kind: str = "module",
) -> KnowledgeEntry:
    """Write one entry into the shared pool. Never raises — a failed deposit
    should never take down the agent that produced it."""
    entry = KnowledgeEntry(
        source_agent=source_agent,
        source_kind=source_kind,
        topic=topic,
        tags=tags or [],
        content=content,
        certainty_score=certainty_score,
        scope=scope,
    )
    context.knowledge_pool.append(entry)
    log.debug(
        "knowledge_deposited",
        source=source_agent.value,
        kind=source_kind,
        topic=topic,
        tags=tags,
    )
    return entry


def query_knowledge(
    context: AgentContext,
    reader_agent: AgentRole,
    tags: list[str] | None = None,
    topic_contains: str = "",
    min_certainty: float = 0.0,
    limit: int = 5,
) -> list[KnowledgeEntry]:
    """Return the most relevant pool entries visible to `reader_agent`.

    Access control (scope) is applied first and is absolute: a MODULE_PRIVATE
    entry from another module is never returned, and GOVERNANCE_ONLY entries
    are invisible to everyone except the Governance Agent. What survives that
    filter is then ranked by a simple relevance score (tag overlap + topic
    substring match), not returned in raw deposit order — this is the
    "attention" step that keeps reads focused instead of exhaustive.
    """
    reader_tags = set(t.lower() for t in (tags or []))
    topic_needle = topic_contains.lower()

    def visible(entry: KnowledgeEntry) -> bool:
        if entry.certainty_score < min_certainty:
            return False
        if entry.scope == KnowledgeScope.GOVERNANCE_ONLY:
            return reader_agent == AgentRole.GOVERNANCE
        if entry.scope == KnowledgeScope.MODULE_PRIVATE:
            return entry.source_agent == reader_agent
        return True  # SHARED

    def relevance(entry: KnowledgeEntry) -> float:
        entry_tags = set(t.lower() for t in entry.tags)
        tag_overlap = len(reader_tags & entry_tags)
        topic_hit = 1 if topic_needle and topic_needle in entry.topic.lower() else 0
        same_module_bonus = 0.25 if entry.source_agent == reader_agent else 0.0
        return (tag_overlap * 1.0) + topic_hit + same_module_bonus + entry.certainty_score

    candidates = [e for e in context.knowledge_pool if visible(e)]

    # Without any tag/topic signal, relevance degenerates to "recent + confident" —
    # still bounded by `limit`, never an unfiltered dump.
    if not reader_tags and not topic_needle:
        candidates.sort(key=lambda e: (e.certainty_score, e.created_at), reverse=True)
    else:
        candidates.sort(key=relevance, reverse=True)

    return candidates[:limit]


def format_knowledge_for_prompt(entries: list[KnowledgeEntry]) -> str:
    """Render queried entries as a compact prompt section."""
    if not entries:
        return ""
    lines = ["## Relevant Knowledge Shared By Other Agents", ""]
    for e in entries:
        lines.append(
            f"- [{e.source_agent.value}/{e.source_kind}] {e.topic or e.tags} "
            f"(certainty {e.certainty_score:.2f}): {e.content}"
        )
    return "\n".join(lines)

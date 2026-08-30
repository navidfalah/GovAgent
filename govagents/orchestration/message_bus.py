"""Message bus for agent-to-agent communication and event streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator, Callable

from govagents.core.logging import get_logger
from govagents.core.models import AgentMessage, AgentRole, SSEEvent

log = get_logger(__name__)


class MessageBus:
    """In-memory publish/subscribe message bus for agent communication.

    Supports:
    - Topic-based pub/sub
    - Agent-to-agent direct messaging
    - SSE event streaming for frontend
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Callable]] = defaultdict(list)
        self._sse_queues: list[asyncio.Queue] = []
        self._message_log: list[AgentMessage] = []
        self._sse_log: list[SSEEvent] = []

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to messages on a topic."""
        self._subscriptions[topic].append(callback)

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to all subscribers of its topic."""
        self._message_log.append(message)
        callbacks = self._subscriptions.get(message.topic, [])
        for cb in callbacks:
            if asyncio.iscoroutinefunction(cb):
                await cb(message)
            else:
                cb(message)

    def add_sse_queue(self) -> asyncio.Queue:
        """Create and register a new SSE queue."""
        q: asyncio.Queue = asyncio.Queue()
        self._sse_queues.append(q)
        return q

    def remove_sse_queue(self, q: asyncio.Queue) -> None:
        """Remove an SSE queue."""
        if q in self._sse_queues:
            self._sse_queues.remove(q)

    async def emit_sse(self, event: SSEEvent) -> None:
        """Broadcast an SSE event to all connected clients."""
        self._sse_log.append(event)
        for q in self._sse_queues:
            await q.put(event)
        log.debug("sse_event", event=event.event, agent=event.agent)

    async def stream_sse(self, queue: asyncio.Queue) -> AsyncIterator[SSEEvent]:
        """Async iterator that yields SSE events from a queue."""
        while True:
            event = await queue.get()
            yield event
            if event.event == "done" or event.event == "error":
                break

    def get_messages(self, topic: str | None = None) -> list[AgentMessage]:
        """Return message log, optionally filtered by topic."""
        if topic:
            return [m for m in self._message_log if m.topic == topic]
        return list(self._message_log)

    def get_sse_log(self) -> list[SSEEvent]:
        """Return all emitted SSE events."""
        return list(self._sse_log)

    def clear(self) -> None:
        """Reset the message bus state."""
        self._message_log.clear()
        self._sse_log.clear()
        self._subscriptions.clear()

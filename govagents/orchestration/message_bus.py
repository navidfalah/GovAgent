"""Message bus for agent-to-agent communication and event streaming (Pub/Sub)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator, Callable, Dict, Type, TypeVar

from pydantic import BaseModel, Field
import uuid
from datetime import datetime

from govagents.core.logging import get_logger
from govagents.core.models import SSEEvent, AgentMessage

log = get_logger(__name__)

E = TypeVar("E", bound="BaseEvent")


class BaseEvent(BaseModel):
    """Base class for all system events."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentCompletedEvent(BaseEvent):
    """Fired when an agent completes its analysis."""
    agent_name: str
    output: Any


class MessageBus:
    """In-memory publish/subscribe message bus for event-driven architecture.

    Supports:
    - Typed Event pub/sub
    - Agent-to-agent direct messaging (via AgentMessage)
    - SSE event streaming for frontend
    """

    def __init__(self) -> None:
        self._event_subscribers: Dict[Type[BaseEvent], list[Callable]] = defaultdict(list)
        self._topic_subscribers: Dict[str, list[Callable]] = defaultdict(list)
        
        self._sse_queues: list[asyncio.Queue] = []
        self._message_log: list[AgentMessage] = []
        self._sse_log: list[SSEEvent] = []

    def subscribe_event(self, event_type: Type[E], callback: Callable[[E], Any]) -> None:
        """Subscribe to a specific strongly-typed event."""
        self._event_subscribers[event_type].append(callback)
        log.debug("event_subscribed", event=event_type.__name__)

    async def publish_event(self, event: BaseEvent) -> None:
        """Publish a strongly-typed event to subscribers."""
        callbacks = self._event_subscribers.get(type(event), [])
        for cb in callbacks:
            if asyncio.iscoroutinefunction(cb):
                await cb(event)
            else:
                cb(event)

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a generic string topic (legacy)."""
        self._topic_subscribers[topic].append(callback)

    async def publish(self, message: AgentMessage) -> None:
        """Publish a generic AgentMessage to a string topic."""
        self._message_log.append(message)
        callbacks = self._topic_subscribers.get(message.topic, [])
        for cb in callbacks:
            if asyncio.iscoroutinefunction(cb):
                await cb(message)
            else:
                cb(message)

    def add_sse_queue(self) -> asyncio.Queue:
        self._sse_queues.append(asyncio.Queue())
        return self._sse_queues[-1]

    def remove_sse_queue(self, q: asyncio.Queue) -> None:
        if q in self._sse_queues:
            self._sse_queues.remove(q)

    async def emit_sse(self, event: SSEEvent) -> None:
        self._sse_log.append(event)
        for q in self._sse_queues:
            await q.put(event)

    async def stream_sse(self, queue: asyncio.Queue) -> AsyncIterator[SSEEvent]:
        while True:
            event = await queue.get()
            yield event
            if event.event in ("done", "error"):
                break

    def get_messages(self, topic: str | None = None) -> list[AgentMessage]:
        if topic:
            return [m for m in self._message_log if m.topic == topic]
        return list(self._message_log)

    def clear(self) -> None:
        self._message_log.clear()
        self._sse_log.clear()
        self._topic_subscribers.clear()
        self._event_subscribers.clear()

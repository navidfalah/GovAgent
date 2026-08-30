"""Component registry for GovAgents (Plugin System)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Type

from govagents.core.logging import get_logger

log = get_logger(__name__)


class ComponentRegistry:
    """A central registry for discovering and instantiating dynamic components."""

    def __init__(self):
        self._agents: Dict[str, Type[Any]] = {}
        self._capabilities: Dict[str, Type[Any]] = {}

    def register_agent(self, name: str) -> Callable:
        """Decorator to register an agent class."""
        def decorator(cls: Type[Any]) -> Type[Any]:
            if name in self._agents:
                log.warning("agent_override", name=name)
            self._agents[name] = cls
            log.debug("agent_registered", name=name, cls=cls.__name__)
            return cls
        return decorator

    def register_capability(self, name: str) -> Callable:
        """Decorator to register a capability (tool) class."""
        def decorator(cls: Type[Any]) -> Type[Any]:
            if name in self._capabilities:
                log.warning("capability_override", name=name)
            self._capabilities[name] = cls
            log.debug("capability_registered", name=name, cls=cls.__name__)
            return cls
        return decorator

    def get_agent_class(self, name: str) -> Type[Any]:
        """Retrieve an agent class by name."""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found in registry.")
        return self._agents[name]

    def get_capability_class(self, name: str) -> Type[Any]:
        """Retrieve a capability class by name."""
        if name not in self._capabilities:
            raise ValueError(f"Capability '{name}' not found in registry.")
        return self._capabilities[name]

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def list_capabilities(self) -> list[str]:
        """List all registered capability names."""
        return list(self._capabilities.keys())


# Global registry instance
registry = ComponentRegistry()

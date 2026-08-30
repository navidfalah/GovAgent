"""Dependency Injection container for GovAgents."""

from __future__ import annotations

from typing import Any, Callable, Dict, Type, TypeVar

from govagents.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T")


class DependencyContainer:
    """A lightweight Dependency Injection container."""

    def __init__(self):
        self._providers: Dict[Type, Callable[[], Any]] = {}
        self._singletons: Dict[Type, Any] = {}

    def register_singleton(self, interface: Type[T], instance: T) -> None:
        """Register a pre-instantiated singleton."""
        self._singletons[interface] = instance
        log.debug("singleton_registered", interface=interface.__name__)

    def register_provider(self, interface: Type[T], provider: Callable[[], T]) -> None:
        """Register a factory function for a dependency."""
        self._providers[interface] = provider
        log.debug("provider_registered", interface=interface.__name__)

    def resolve(self, interface: Type[T]) -> T:
        """Resolve a dependency."""
        if interface in self._singletons:
            return self._singletons[interface]
        
        if interface in self._providers:
            instance = self._providers[interface]()
            # Auto-cache singletons produced by providers
            self._singletons[interface] = instance
            return instance

        raise ValueError(f"No provider registered for {interface.__name__}")


# Global DI container instance
container = DependencyContainer()

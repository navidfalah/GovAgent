"""Base capability interface."""

from __future__ import annotations

from typing import Any, Dict


class Capability:
    """Base class for all agent capabilities (tools)."""

    def __init__(self):
        self.name = self.__class__.__name__

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the capability."""
        raise NotImplementedError

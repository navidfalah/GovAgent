"""Search capabilities."""

from __future__ import annotations

from typing import Any

from govagents.capabilities.base import Capability
from govagents.core.registry import registry
from govagents.policies.retrieval import get_retriever


@registry.register_capability("VectorSearch")
class VectorSearchCapability(Capability):
    """Semantic search over the policy corpus."""

    async def execute(self, query: str, top_k: int = 5, **kwargs: Any) -> Any:
        retriever = get_retriever()
        results = await retriever.search(query, top_k=top_k)
        return results

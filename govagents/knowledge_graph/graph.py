"""NetworkX-based governance knowledge graph."""

from __future__ import annotations

from typing import Any

import networkx as nx

from govagents.core.logging import get_logger
from govagents.knowledge_graph.entities import Entity, EntityType, Relation

log = get_logger(__name__)


class GovernanceKnowledgeGraph:
    """NetworkX-based knowledge graph for governance reasoning.

    Stores relationships between policies, requirements, risks, AI systems, and actors.
    Phase 4 extension: this provides the infrastructure for structured graph-based
    reasoning in addition to semantic vector retrieval.
    """

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    def add_entity(self, entity: Entity) -> None:
        """Add an entity node to the graph."""
        self.graph.add_node(
            entity.id,
            type=entity.type.value,
            name=entity.name,
            source_id=entity.source_id,
            **entity.properties,
        )

    def add_relation(self, relation: Relation) -> None:
        """Add a relation edge to the graph."""
        self.graph.add_edge(
            relation.source_id,
            relation.target_id,
            relation_type=relation.relation_type,
            confidence=relation.confidence,
            **relation.properties,
        )

    def get_requirements_for(self, entity_id: str) -> list[dict[str, Any]]:
        """Get all requirements that apply to a given entity."""
        results = []
        for _, target, data in self.graph.out_edges(entity_id, data=True):
            if data.get("relation_type") in ("requires", "applies_to", "contains"):
                node_data = self.graph.nodes.get(target, {})
                if node_data.get("type") == EntityType.REQUIREMENT.value:
                    results.append({"id": target, **node_data})
        return results

    def get_related(
        self,
        entity_id: str,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get entities related to a given entity."""
        results = []
        for _, target, data in self.graph.out_edges(entity_id, data=True):
            if relation_type is None or data.get("relation_type") == relation_type:
                node_data = self.graph.nodes.get(target, {})
                results.append(
                    {
                        "id": target,
                        "relation": data.get("relation_type"),
                        **node_data,
                    }
                )
        return results

    def find_conflicts(self) -> list[dict[str, Any]]:
        """Find requirements that conflict with each other."""
        conflicts = []
        for source, target, data in self.graph.edges(data=True):
            if data.get("relation_type") == "conflicts_with":
                conflicts.append(
                    {
                        "requirement_a": source,
                        "requirement_b": target,
                        "reason": data.get("reason", ""),
                    }
                )
        return conflicts

    def get_stats(self) -> dict[str, int]:
        """Return graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "components": nx.number_weakly_connected_components(self.graph),
        }

    def build_from_policy_sources(self, sources: list) -> None:
        """Populate the graph from loaded policy sources (Phase 4 full implementation)."""
        for source, chunks in sources:
            # Add policy source node
            self.add_entity(
                Entity(
                    id=source.id,
                    type=EntityType.POLICY,
                    name=source.name,
                    properties={
                        "jurisdiction": source.jurisdiction,
                        "type": source.type,
                        "version": source.version,
                    },
                )
            )
            # Add requirement nodes and link to policy
            for chunk in chunks:
                req_id = chunk.metadata.get("id", chunk.id)
                self.add_entity(
                    Entity(
                        id=req_id,
                        type=EntityType.REQUIREMENT,
                        name=chunk.metadata.get("title", ""),
                        source_id=source.id,
                        properties={
                            "requirement_type": chunk.requirement_type or "",
                            "tags": chunk.tags,
                        },
                    )
                )
                self.add_relation(
                    Relation(
                        source_id=source.id,
                        target_id=req_id,
                        relation_type="contains",
                    )
                )

        log.info("knowledge_graph_built", **self.get_stats())


_kg: GovernanceKnowledgeGraph | None = None


def get_knowledge_graph() -> GovernanceKnowledgeGraph:
    """Return the global knowledge graph instance."""
    global _kg
    if _kg is None:
        _kg = GovernanceKnowledgeGraph()
    return _kg

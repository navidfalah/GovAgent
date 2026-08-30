"""Knowledge graph package."""
from govagents.knowledge_graph.entities import Entity, EntityType, Relation
from govagents.knowledge_graph.graph import GovernanceKnowledgeGraph, get_knowledge_graph

__all__ = ["Entity", "EntityType", "Relation", "GovernanceKnowledgeGraph", "get_knowledge_graph"]

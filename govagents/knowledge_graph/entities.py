"""Knowledge graph entities for GovAgents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    POLICY = "policy"
    REGULATION = "regulation"
    REQUIREMENT = "requirement"
    ORGANIZATION = "organization"
    AI_SYSTEM = "ai_system"
    RISK = "risk"
    TECHNOLOGY = "technology"
    ACTOR = "actor"
    OBLIGATION = "obligation"
    CONTROL = "control"
    EVIDENCE = "evidence"


@dataclass
class Entity:
    """A node in the governance knowledge graph."""

    id: str
    type: EntityType
    name: str
    properties: dict = field(default_factory=dict)
    source_id: str | None = None


@dataclass
class Relation:
    """An edge in the governance knowledge graph."""

    source_id: str
    target_id: str
    relation_type: str  # contains | requires | applies_to | part_of | conflicts_with | implements
    properties: dict = field(default_factory=dict)
    confidence: float = 1.0

"""Policy document parser — loads structured YAML policy sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from govagents.core.logging import get_logger
from govagents.core.models import PolicyChunk, PolicySource

log = get_logger(__name__)


def load_policy_files(sources_path: Path) -> list[tuple[PolicySource, list[PolicyChunk]]]:
    """Load and parse all YAML policy files in a directory.

    Returns a list of (PolicySource, [PolicyChunk]) tuples.
    """
    results = []
    yaml_files = list(sources_path.glob("*.yaml")) + list(sources_path.glob("*.yml"))

    if not yaml_files:
        log.warning("no_policy_files_found", path=str(sources_path))
        return []

    for yaml_file in sorted(yaml_files):
        log.info("loading_policy_file", file=yaml_file.name)
        try:
            documents = _load_multi_document_yaml(yaml_file)
            for doc in documents:
                if doc and "source" in doc:
                    source, chunks = _parse_document(doc)
                    results.append((source, chunks))
                    log.info(
                        "policy_loaded",
                        source=source.id,
                        chunks=len(chunks),
                    )
        except Exception as e:
            log.error("policy_load_error", file=yaml_file.name, error=str(e))

    return results


def _load_multi_document_yaml(path: Path) -> list[dict[str, Any]]:
    """Load a YAML file that may contain multiple documents separated by ---."""
    with open(path) as f:
        content = f.read()
    documents = list(yaml.safe_load_all(content))
    return [d for d in documents if d is not None]


def _parse_document(doc: dict[str, Any]) -> tuple[PolicySource, list[PolicyChunk]]:
    """Parse a single YAML document into a PolicySource and its chunks."""
    src_data = doc.get("source", {})
    source = PolicySource(
        id=src_data.get("id", "unknown"),
        name=src_data.get("name", "Unknown Policy"),
        version=str(src_data.get("version", "1.0")),
        type=src_data.get("type", "policy"),
        jurisdiction=src_data.get("jurisdiction", "international"),
        effective_date=src_data.get("effective_date"),
        url=src_data.get("url"),
        description=src_data.get("description", ""),
    )

    chunks = []
    for req in doc.get("requirements", []):
        chunk = PolicyChunk(
            id=f"{source.id}::{req.get('id', 'unknown')}",
            source_id=source.id,
            source_name=source.name,
            article=req.get("article"),
            section=req.get("section"),
            requirement_type=req.get("requirement_type"),
            text=_clean_text(req.get("text", "")),
            tags=req.get("tags", []),
            metadata={
                "id": req.get("id"),
                "title": req.get("title", ""),
                "source_version": source.version,
                "jurisdiction": source.jurisdiction,
            },
        )
        chunks.append(chunk)

    return source, chunks


def _clean_text(text: str) -> str:
    """Clean whitespace from YAML multiline strings."""
    text = text.strip()
    text = re.sub(r"\n\s+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text

"""Policy ingestion — loads policy documents into ChromaDB."""

from __future__ import annotations

from pathlib import Path

from govagents.core.config import Settings, get_settings
from govagents.core.logging import get_logger
from govagents.core.models import PolicyChunk, PolicySource
from govagents.policies.parser import load_policy_files

log = get_logger(__name__)


async def ingest_policies(
    sources_path: Path | None = None,
    settings: Settings | None = None,
    force_reingest: bool = False,
) -> tuple[int, int]:
    """Load policy documents from YAML files into ChromaDB.

    Returns:
        (sources_loaded, chunks_ingested)
    """
    from govagents.policies.retrieval import get_retriever

    settings = settings or get_settings()
    sources_path = sources_path or settings.policy_sources_path

    retriever = get_retriever(settings)

    # Check if already ingested
    if not force_reingest:
        count = retriever.count()
        if count > 0:
            log.info("policies_already_ingested", chunks=count)
            return 0, count

    log.info("ingestion_start", sources_path=str(sources_path))

    documents = load_policy_files(sources_path)
    if not documents:
        log.warning("no_documents_to_ingest")
        return 0, 0

    total_chunks = 0
    sources_loaded = 0

    for source, chunks in documents:
        if not chunks:
            continue
        await retriever.add_chunks(chunks)
        total_chunks += len(chunks)
        sources_loaded += 1
        log.info(
            "source_ingested",
            source=source.name,
            chunks=len(chunks),
        )

    log.info(
        "ingestion_complete",
        sources=sources_loaded,
        chunks=total_chunks,
    )
    return sources_loaded, total_chunks


def list_policy_sources(
    sources_path: Path | None = None,
    settings: Settings | None = None,
) -> list[PolicySource]:
    """List all policy sources available in the sources directory."""
    settings = settings or get_settings()
    sources_path = sources_path or settings.policy_sources_path

    documents = load_policy_files(sources_path)
    return [source for source, _ in documents]

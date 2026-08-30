"""Policy routes — browse the policy corpus."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from govagents.api.schemas import CorpusStatusResponse, PolicySourceResponse
from govagents.core.config import get_settings
from govagents.core.logging import get_logger
from govagents.policies.ingestion import list_policy_sources
from govagents.policies.retrieval import get_retriever

log = get_logger(__name__)

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("", response_model=CorpusStatusResponse)
async def get_corpus_status() -> CorpusStatusResponse:
    """Get the status of the loaded policy corpus."""
    settings = get_settings()
    retriever = get_retriever()

    total_chunks = retriever.count()
    all_sources_in_corpus = await retriever.get_all_sources()

    # Build per-source chunk counts
    source_chunk_counts: dict[str, int] = {}
    for s in all_sources_in_corpus:
        source_chunk_counts[s["id"]] = source_chunk_counts.get(s["id"], 0) + 1

    # Load source metadata from YAML files
    policy_sources = list_policy_sources()

    source_responses = []
    for source in policy_sources:
        source_responses.append(
            PolicySourceResponse(
                id=source.id,
                name=source.name,
                version=source.version,
                type=source.type,
                jurisdiction=source.jurisdiction,
                description=source.description,
                chunk_count=source_chunk_counts.get(source.id, 0),
            )
        )

    return CorpusStatusResponse(
        total_chunks=total_chunks,
        sources=source_responses,
        embedding_model=settings.embedding_model,
        status="ready" if total_chunks > 0 else "empty",
    )


@router.post("/ingest", status_code=202)
async def trigger_ingestion(force: bool = False) -> dict:
    """Trigger policy corpus ingestion (or re-ingestion if force=True)."""
    from govagents.policies.ingestion import ingest_policies

    retriever = get_retriever()
    if force:
        retriever.reset()

    sources, chunks = await ingest_policies(force_reingest=force)
    return {
        "status": "complete",
        "sources_loaded": sources,
        "chunks_ingested": chunks,
    }


@router.get("/search")
async def search_policies(
    query: str,
    top_k: int = 5,
    requirement_type: str | None = None,
) -> dict:
    """Search the policy corpus with a natural language query."""
    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    retriever = get_retriever()
    results = await retriever.search(query, top_k=top_k, requirement_type=requirement_type)
    return {"query": query, "results": results, "count": len(results)}

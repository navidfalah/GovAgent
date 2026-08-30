"""Policy retrieval — ChromaDB-backed semantic search over the policy corpus."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from govagents.core.config import Settings, get_settings
from govagents.core.logging import get_logger
from govagents.core.models import PolicyChunk

log = get_logger(__name__)

COLLECTION_NAME = "govagents_policies"


class PolicyRetriever:
    """Semantic search over the policy corpus using ChromaDB.

    Uses sentence-transformers embeddings for semantic similarity.
    Falls back gracefully if ChromaDB is empty.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._embedding_fn: Any | None = None

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            chroma_path = self.settings.chroma_path
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            log.info("chroma_client_initialized", path=str(chroma_path))
        return self._client

    def _get_embedding_fn(self) -> Any:
        if self._embedding_fn is None:
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.settings.embedding_model
            )
            log.info("embedding_model_loaded", model=self.settings.embedding_model)
        return self._embedding_fn

    def _get_collection(self) -> chromadb.Collection:
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def count(self) -> int:
        """Return the number of documents in the collection."""
        try:
            return self._get_collection().count()
        except Exception:
            return 0

    async def add_chunks(self, chunks: list[PolicyChunk]) -> None:
        """Add policy chunks to the collection."""
        if not chunks:
            return

        collection = self._get_collection()
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "source_id": chunk.source_id,
                "source_name": chunk.source_name,
                "article": chunk.article or "",
                "requirement_type": chunk.requirement_type or "",
                "tags": ",".join(chunk.tags),
                "title": chunk.metadata.get("title", ""),
                **{k: str(v) for k, v in chunk.metadata.items()},
            }
            for chunk in chunks
        ]

        # ChromaDB upsert to handle re-ingestion
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        log.debug("chunks_added", count=len(chunks))

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        requirement_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search the policy corpus for relevant chunks.

        Args:
            query: Natural language search query
            top_k: Number of results to return
            requirement_type: Optional filter by requirement type

        Returns:
            List of result dicts with id, text, source, score, metadata
        """
        collection = self._get_collection()
        if collection.count() == 0:
            log.warning("empty_corpus", query=query[:50])
            return []

        k = top_k or self.settings.retrieval_top_k
        where = {"requirement_type": requirement_type} if requirement_type else None

        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(k, collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            log.error("search_error", error=str(e), query=query[:50])
            return []

        hits = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        for doc, meta, dist, id_ in zip(documents, metadatas, distances, ids):
            # Convert cosine distance to similarity score
            score = 1.0 - dist
            hits.append(
                {
                    "id": id_,
                    "text": doc,
                    "source_id": meta.get("source_id", ""),
                    "source_name": meta.get("source_name", ""),
                    "article": meta.get("article", ""),
                    "requirement_type": meta.get("requirement_type", ""),
                    "title": meta.get("title", ""),
                    "tags": meta.get("tags", "").split(","),
                    "score": round(score, 4),
                    "metadata": meta,
                }
            )

        log.debug("search_complete", query=query[:50], hits=len(hits))
        return hits

    async def get_all_sources(self) -> list[dict[str, str]]:
        """Return list of unique policy sources in the corpus."""
        collection = self._get_collection()
        if collection.count() == 0:
            return []

        results = collection.get(include=["metadatas"])
        sources: dict[str, dict] = {}
        for meta in results.get("metadatas", []):
            sid = meta.get("source_id", "")
            if sid and sid not in sources:
                sources[sid] = {
                    "id": sid,
                    "name": meta.get("source_name", ""),
                }
        return list(sources.values())

    def reset(self) -> None:
        """Delete and recreate the collection (for re-ingestion)."""
        client = self._get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None
        log.info("collection_reset")


_retriever: PolicyRetriever | None = None


def get_retriever(settings: Settings | None = None) -> PolicyRetriever:
    """Return the global PolicyRetriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever(settings)
    return _retriever

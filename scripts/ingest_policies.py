"""Script to ingest policy documents into the ChromaDB vector store."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main() -> None:
    from govagents.core.config import get_settings
    from govagents.core.logging import configure_logging
    from govagents.policies.ingestion import ingest_policies
    from govagents.policies.retrieval import get_retriever

    settings = get_settings()
    configure_logging(level="INFO", format="console")

    print("GovAgents — Policy Corpus Ingestion")
    print("=" * 50)
    print(f"Policy sources: {settings.policy_sources_path}")
    print(f"ChromaDB path:  {settings.chroma_path}")
    print(f"Embedding model: {settings.embedding_model}")
    print()

    # Force re-ingestion if --force flag passed
    force = "--force" in sys.argv
    if force:
        print("⚠ Force re-ingestion enabled — resetting collection...")
        retriever = get_retriever()
        retriever.reset()

    print("Loading and embedding policy documents...")
    sources, chunks = await ingest_policies(force_reingest=force)

    print(f"\n✓ Ingestion complete!")
    print(f"  Sources loaded: {sources}")
    print(f"  Chunks indexed: {chunks}")

    # Verify with a test search
    if chunks > 0:
        print("\nRunning test search: 'human oversight AI requirements'")
        retriever = get_retriever()
        results = await retriever.search("human oversight AI requirements", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  [{i}] {r['source_name']} {r.get('article', '')} — score: {r['score']:.3f}")
            print(f"      {r['text'][:120]}...")


if __name__ == "__main__":
    asyncio.run(main())

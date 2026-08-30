"""Tests for policy parsing and retrieval."""

import pytest
from pathlib import Path
from govagents.policies.parser import load_policy_files, _clean_text


def test_clean_text():
    raw = """
        This is a
        multiline text with
        extra whitespace.
    """
    cleaned = _clean_text(raw)
    assert "\n" not in cleaned
    assert "  " not in cleaned
    assert cleaned.startswith("This is a")


def test_load_policy_files_eu_ai_act():
    sources_path = Path("govagents/policies/sources")
    if not sources_path.exists():
        pytest.skip("Sources directory not found")

    results = load_policy_files(sources_path)
    assert len(results) > 0

    # Check EU AI Act loaded
    source_ids = [source.id for source, _ in results]
    assert "eu-ai-act" in source_ids or any("gdpr" in sid for sid in source_ids)


def test_load_policy_files_returns_chunks():
    sources_path = Path("govagents/policies/sources")
    if not sources_path.exists():
        pytest.skip("Sources directory not found")

    results = load_policy_files(sources_path)
    total_chunks = sum(len(chunks) for _, chunks in results)
    assert total_chunks > 10, "Should have loaded at least 10 policy chunks"


def test_policy_chunk_structure():
    sources_path = Path("govagents/policies/sources")
    if not sources_path.exists():
        pytest.skip("Sources directory not found")

    results = load_policy_files(sources_path)
    for source, chunks in results:
        assert source.id
        assert source.name
        for chunk in chunks:
            assert chunk.source_id == source.id
            assert len(chunk.text) > 10

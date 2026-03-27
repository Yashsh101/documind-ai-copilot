"""
Tests covering the core pipeline logic.
Run with: pytest tests/ -v

Uses pytest-asyncio for async tests and monkeypatching to avoid
real API calls — tests should be fast and free.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.utils.citations import clean_answer, extract_citations
from app.utils.evaluator import evaluate
from app.services.ingestion import _clean_text, chunk_text


# ── Text cleaning ─────────────────────────────────────────────────────────────

def test_clean_text_collapses_blank_lines():
    raw = "Hello\n\n\n\nWorld"
    assert "\n\n\n" not in _clean_text(raw)


def test_clean_text_rejoins_hyphenated_words():
    raw = "auto-\nmatic"
    assert "automatic" in _clean_text(raw)


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_chunk_text_produces_chunks():
    text = "Sentence one. " * 80   # ~1120 chars, should produce multiple chunks
    chunks = chunk_text(text, source="test.pdf")
    assert len(chunks) >= 2


def test_chunk_text_assigns_sequential_ids():
    text = "Word " * 200
    chunks = chunk_text(text, source="doc.pdf", start_id=10)
    ids = [c.chunk_id for c in chunks]
    assert ids == list(range(10, 10 + len(chunks)))


def test_chunk_text_skips_short_fragments():
    text = "Hi\n\n" + ("This is a real sentence with enough content. " * 30)
    chunks = chunk_text(text)
    assert all(len(c.text) >= 30 for c in chunks)


# ── Citations ─────────────────────────────────────────────────────────────────

SAMPLE_CHUNKS = [
    {"chunk_id": 0, "text": "The refund policy allows 30 days.", "score": 0.91},
    {"chunk_id": 1, "text": "Contact support at support@example.com.", "score": 0.85},
    {"chunk_id": 2, "text": "Premium members get priority support.", "score": 0.72},
]

def test_extract_citations_finds_referenced_chunks():
    answer = "You can get a refund [chunk_0]. Contact us [chunk_1]."
    citations = extract_citations(answer, SAMPLE_CHUNKS)
    cited_ids = {c.chunk_id for c in citations}
    assert cited_ids == {0, 1}


def test_extract_citations_ignores_unreferenced_chunks():
    answer = "You can get a refund [chunk_0]."
    citations = extract_citations(answer, SAMPLE_CHUNKS)
    assert all(c.chunk_id != 2 for c in citations)


def test_clean_answer_strips_chunk_tags():
    raw = "Refunds are allowed [chunk_0] within 30 days [chunk_1]."
    cleaned = clean_answer(raw)
    assert "[chunk_" not in cleaned
    assert "Refunds are allowed" in cleaned


# ── Evaluator ─────────────────────────────────────────────────────────────────

def test_evaluate_perfect_recall():
    answer = "Refunds [chunk_0]. Contact [chunk_1]. Premium [chunk_2]."
    result = evaluate(answer, SAMPLE_CHUNKS)
    assert result.context_recall == 1.0


def test_evaluate_partial_recall():
    answer = "Refunds [chunk_0]."
    result = evaluate(answer, SAMPLE_CHUNKS)
    assert result.context_recall < 1.0


def test_evaluate_faithfulness_high_for_grounded_answer():
    answer = "refund policy allows thirty days contact support"
    result = evaluate(answer, SAMPLE_CHUNKS)
    assert result.answer_faithfulness > 0.3


def test_evaluate_empty_chunks():
    result = evaluate("some answer", [])
    assert result.context_recall == 0.0
    assert result.answer_faithfulness == 0.0

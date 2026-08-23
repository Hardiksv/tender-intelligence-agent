import pytest
from unittest.mock import MagicMock
from app.services.chunking import chunk_document_pages
from app.services.embeddings import generate_embedding
from app.core.exceptions import EmbeddingDimensionMismatchException
from app.core.config import settings


def test_chunking_page_awareness():
    pages = [
        {"page_number": 1, "text": "Section 1: Notice Inviting Tender for 100 Buses in Jaipur."},
        {"page_number": 2, "text": "Section 2: Minimum fleet size 80 buses. Minimum turnover 120 Crore."}
    ]
    chunks = chunk_document_pages(pages, target_chunk_size=200)

    assert len(chunks) >= 2
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["chunk_metadata"]["page_number"] == 1
    assert chunks[1]["page_number"] == 2


def test_embedding_generation_dimension():
    vec = generate_embedding("Sample tender requirement for bus fleet size")
    assert len(vec) == settings.EMBEDDING_DIMENSION


def test_embedding_dimension_mismatch_fails_fast(monkeypatch):
    """
    TEST: Intentional dimension mismatch MUST fail fast.
    """
    monkeypatch.setattr("app.services.embeddings._call_jina_api", lambda texts, **kwargs: [[0.1] * 50] * len(texts))
    monkeypatch.setattr("app.services.embeddings.litellm.embedding", MagicMock(side_effect=RuntimeError("Mock API error")))
    monkeypatch.setattr("app.services.embeddings._get_sentence_transformer", MagicMock(side_effect=RuntimeError("Mock ST error")))

    with pytest.raises(EmbeddingDimensionMismatchException):
        generate_embedding("Sample text")

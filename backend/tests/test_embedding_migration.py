import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.db.models import Document, DocumentChunk, Tender
from app.services.embeddings import generate_embedding, generate_embeddings_batch


@pytest.fixture(autouse=True)
def mock_jina_embedding_api():
    """Mocks Jina API to return valid 768-dim embeddings offline."""
    def fake_jina(texts, task_type="retrieval.passage"):
        return [[0.05] * settings.EMBEDDING_DIMENSION for _ in texts]

    with patch("app.services.embeddings._call_jina_api", side_effect=fake_jina):
        yield


def test_gemini_embedding_dimension_768():
    """Smoke test asserting generated embedding vector length is exactly 768 dimensions."""
    sample_text = "Selection of Bus Operator for Procurement and Operation of 3,604 Electric Buses under PM-eBus Sewa."
    vec = generate_embedding(sample_text)

    assert isinstance(vec, list)
    assert len(vec) == settings.EMBEDDING_DIMENSION
    assert len(vec) == 768


def test_gemini_batch_embedding_dimension_768():
    """Smoke test asserting batch embedding vectors are all exactly 768 dimensions."""
    samples = [
        "First chunk: Technical eligibility minimum fleet size is 80 buses.",
        "Second chunk: Financial criteria requires minimum annual turnover of INR 100 Crore."
    ]
    batch_vecs = generate_embeddings_batch(samples)

    assert len(batch_vecs) == 2
    for v in batch_vecs:
        assert len(v) == settings.EMBEDDING_DIMENSION
        assert len(v) == 768


def test_document_chunk_db_insertion(test_db):
    """
    Test creating and inserting a DocumentChunk with a 768-dim vector.
    Runs against isolated SQLite test DB and verifies retrieval.
    """
    t_id = uuid.uuid4()
    t = Tender(
        id=t_id,
        title="Test Embedding Migration Tender",
        issuing_authority="Test Authority",
        category="bus_operations",
        submission_deadline=datetime.now(timezone.utc),
        timezone="Asia/Kolkata",
        raw_document_path="test_rfp.pdf",
        document_hash=uuid.uuid4().hex
    )
    test_db.add(t)
    test_db.flush()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tender_id=t.id,
        file_name="test_rfp.pdf",
        page_count=5,
        document_hash=t.document_hash
    )
    test_db.add(doc)
    test_db.flush()

    vec_768 = generate_embedding("Sample text for insertion verification")
    assert len(vec_768) == 768

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        tender_id=t.id,
        document_id=doc.id,
        chunk_text="Sample text for insertion verification",
        page_number=1,
        chunk_index=0,
        embedding=vec_768,
        chunk_metadata={"test": True}
    )
    test_db.add(chunk)
    test_db.flush()

    retrieved = test_db.query(DocumentChunk).filter(DocumentChunk.id == chunk.id).first()
    assert retrieved is not None
    assert len(retrieved.embedding) == 768

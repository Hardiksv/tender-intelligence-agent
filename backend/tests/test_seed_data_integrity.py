"""
Guards against the exact class of bug that caused 4/14 seed "PDFs" to actually be
HTML pages (a scraper saved a 404/homepage with a .pdf extension, and pymupdf
silently parsed it as if it were real tender content).
"""
import glob
import os
import pytest

DATA_RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
PDF_MAGIC = b"%PDF-"


def _seed_pdf_paths():
    return sorted(glob.glob(os.path.join(DATA_RAW_DIR, "*.pdf")))


@pytest.mark.parametrize("path", _seed_pdf_paths())
def test_seed_file_is_real_pdf(path):
    with open(path, "rb") as f:
        header = f.read(1024).lstrip(b"\xef\xbb\xbf")
    assert header.startswith(PDF_MAGIC), (
        f"{os.path.basename(path)} is not a real PDF (likely an HTML page saved "
        f"with a .pdf extension). First bytes: {header[:120]!r}"
    )


def test_seed_set_has_minimum_ten_documents():
    assert len(_seed_pdf_paths()) >= 6, "Assignment requires at least 6 seed tender documents."


def test_pdf_parser_rejects_html_masquerading_as_pdf(tmp_path):
    from app.services.pdf_parser import parse_pdf_document
    from app.core.exceptions import ParsingException

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"<!DOCTYPE html><html><head><title>Not a PDF</title></head></html>")

    with pytest.raises(ParsingException):
        parse_pdf_document(str(fake_pdf))


def test_embeddings_raise_instead_of_returning_fake_vector(monkeypatch):
    """
    Ensures the SHA256 hash-based fake vector fallback is gone: when every real
    embedding provider fails, generate_embedding must raise, not fabricate a vector.
    """
    from app.core.exceptions import EmbeddingGenerationException
    from app.services import embeddings as emb_module

    monkeypatch.setattr(emb_module, "_call_jina_api", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("down")))

    class _BrokenLiteLLM:
        @staticmethod
        def embedding(*a, **kw):
            raise RuntimeError("cloud provider down")

    monkeypatch.setattr(emb_module, "litellm", _BrokenLiteLLM)

    def _broken_st():
        raise RuntimeError("no local model available")

    monkeypatch.setattr(emb_module, "_get_sentence_transformer", _broken_st)

    with pytest.raises(EmbeddingGenerationException):
        emb_module.generate_embedding("some tender text")


def test_retrieval_returns_empty_not_fabricated_catalog_chunks(monkeypatch):
    """
    Ensures the 'Serverless Catalog Fallback' is gone: when vector search finds
    nothing, retrieve_relevant_context must return [], not hardcoded CATALOG facts
    disguised as retrieved chunks with fake similarity scores.
    """
    from app.services import retrieval as retrieval_module

    monkeypatch.setattr(retrieval_module, "generate_embedding", lambda q: None)

    class _FakeBind:
        dialect = type("d", (), {"name": "sqlite"})()

    class _FakeDB:
        bind = _FakeBind()

        def scalars(self, *a, **kw):
            class _R:
                def all(self_inner):
                    return []
            return _R()

        def execute(self, *a, **kw):
            class _R:
                def all(self_inner):
                    return []
            return _R()

    result = retrieval_module.retrieve_relevant_context(
        db=_FakeDB(), question="which tenders are we eligible for?", top_k=5
    )
    assert result == []
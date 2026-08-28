import pytest

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


def test_screening_verdict_with_profile():
    """Verify that deterministic screening logic functions properly with company profile."""
    from app.schemas.extraction import TenderEligibilitySchema
    from app.services.screening import screen_tender_eligibility
    from app.schemas.profile import CompanyProfileBase
    from app.schemas.screening import FinalVerdict
    
    profile = CompanyProfileBase(
        fleet_size=120,
        annual_turnover=150_000_000.0,
        years_experience=7,
        past_contract_sizes=[75_000_000.0, 90_000_000.0],
        preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"]
    )
    elig = TenderEligibilitySchema(
        minimum_fleet_size=50,
        minimum_annual_turnover=100_000_000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=50_000_000.0,
        required_geographies=["Rajasthan"],
        other_requirements=[]
    )
    res = screen_tender_eligibility(
        tender_id="test-tender-1",
        tender_title="Test E-Bus Tender",
        tender_state="Rajasthan",
        eligibility=elig,
        profile=profile
    )
    assert res.verdict == FinalVerdict.GO

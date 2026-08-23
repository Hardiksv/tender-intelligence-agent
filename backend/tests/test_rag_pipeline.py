import pytest
from unittest.mock import MagicMock
from app.services.rag import answer_tender_question, load_rag_prompt
from app.services.retrieval import route_query_type
from app.schemas.chat import ChatRequest

def test_query_router():
    assert route_query_type("What tenders close in the next 15 days?") == "STRUCTURED_SQL"
    assert route_query_type("What is the EMD requirement for DTC?") == "VECTOR_SEARCH"

def test_load_rag_prompt():
    prompt = load_rag_prompt()
    assert "{question}" in prompt
    assert "{context}" in prompt

def test_rag_zero_hallucination_on_empty_context(monkeypatch):
    monkeypatch.setattr("app.services.rag.retrieve_relevant_context", lambda **kwargs: [])
    
    mock_db = MagicMock()
    req = ChatRequest(question="What is the CEO's personal home phone number?")
    
    response = answer_tender_question(db=mock_db, request=req)
    assert "I could not find sufficient evidence" in response.answer
    assert len(response.citations) == 0

def test_rag_answer_with_grounded_context(monkeypatch):
    sample_context = [{
        "tender_id": "tender_001_dtc_300",
        "tender_title": "DTC Delhi 300 Electric Buses GCC",
        "document_name": "dtc_delhi_300_ebuses_gcc.pdf",
        "page_number": 1,
        "chunk_index": 0,
        "text": "Earnest Money Deposit (EMD): INR 3,000,000.00. Tender Document Fee: INR 10,000.00."
    }]
    
    monkeypatch.setattr("app.services.rag.retrieve_relevant_context", lambda **kwargs: sample_context)
    monkeypatch.setattr("app.services.rag.llm_client.generate", lambda **kwargs: {
        "content": "The EMD for DTC Delhi is INR 3,000,000.00 (₹30 Lakhs) as per Page 1.",
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "is_estimated": True},
        "model": "mock-llm"
    })
    
    mock_db = MagicMock()
    req = ChatRequest(question="What is the EMD for DTC Delhi?")
    
    response = answer_tender_question(db=mock_db, request=req)
    assert "INR 3,000,000.00" in response.answer
    assert len(response.citations) == 1
    assert response.citations[0].page_number == 1
    assert response.citations[0].document_name == "dtc_delhi_300_ebuses_gcc.pdf"

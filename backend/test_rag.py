import asyncio
from app.services.rag import answer_tender_question
from app.db.database import SessionLocal
from app.db.models import Tender
from app.schemas.chat import ChatRequest

def test_rag():
    db = SessionLocal()
    tender = db.query(Tender).filter(Tender.tender_ref.like('%PM-eBus Sewa3%')).first()
    if not tender:
        print("Tender not found")
        return
    
    req = ChatRequest(tender_id=str(tender.id), question="What is the current deadline for PM-eBus Sewa Tender 3?", history=[])
    response = answer_tender_question(db, req)
    
    with open("rag_output.txt", "w", encoding="utf-8") as f:
        f.write("RAG ANSWER:\n")
        f.write(response.answer + "\n")
        f.write("=" * 50 + "\n")
        f.write("CITATIONS:\n")
        for c in response.citations:
            f.write(f"- {c.document_name} (Page {c.page_number}): {c.snippet[:100]}...\n")

if __name__ == "__main__":
    test_rag()

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import answer_tender_question

router = APIRouter(prefix="/api/chat", tags=["RAG Chat"])


@router.post("", response_model=ChatResponse)
async def chat_qna(request: ChatRequest, db: Session = Depends(get_db)):
    return answer_tender_question(db, request)

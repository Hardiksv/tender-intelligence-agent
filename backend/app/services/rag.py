import os

from sqlalchemy.orm import Session

from app.core.logging import log_action, logger
from app.db.models import Tender
from app.llm.client import llm_client
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.retrieval import retrieve_relevant_context

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "prompts", "rag.md"
)

_FALLBACK_RAG_PROMPT = """You are a grounded Tender Intelligence AI assistant.

Answer the user's question strictly using ONLY the provided structured tender facts and tender document context.

If the context does not contain sufficient details, state:
'I could not find sufficient evidence in the stored tender documents to answer this confidently.'

CONTEXT:
{context}

QUESTION:
{question}
"""


def load_rag_prompt() -> str:
    """Loads the versioned RAG prompt template from prompts/rag.md on disk."""
    if os.path.exists(PROMPT_PATH):
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    logger.warning(f"prompts/rag.md not found at {PROMPT_PATH}; using in-code fallback prompt.")
    return _FALLBACK_RAG_PROMPT


def answer_tender_question(db: Session, request: ChatRequest) -> ChatResponse:
    """
    RAG service answering user questions grounded strictly in retrieved vector/SQL chunks
    and returning metadata-backed citations. No synthetic or hallucinated answers.
    """
    try:
        context_chunks = retrieve_relevant_context(
            db=db,
            question=request.question,
            tender_id_filter=request.tender_id,
            top_k=12
        )
    except Exception as e:
        logger.warning(f"Error in retrieve_relevant_context: {e}")
        context_chunks = []

    tender = None
    if request.tender_id:
        tender = db.query(Tender).filter(Tender.id == request.tender_id).first()

    if not context_chunks and not tender:
        return ChatResponse(
            question=request.question,
            answer="I could not find sufficient evidence in the stored tender documents to answer this confidently.",
            citations=[],
            model_used="none",
            usage={
                "model": "none",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "is_estimated": True
            }
        )

    formatted_context_list = []
    citations: list[Citation] = []

    if tender:
        structured_context = f"""
--- STRUCTURED TENDER FACTS ---
Tender ID: {tender.id}
Tender Title: {tender.title}

Original bus quantity: {tender.original_bus_quantity}
Latest bus quantity: {tender.latest_bus_quantity}
Latest quantity source: {tender.latest_quantity_source}

Original deadline: {tender.original_deadline}
Latest deadline: {tender.latest_deadline}
Latest deadline source: {tender.latest_deadline_source}

Original EMD amount: {tender.original_emd_amount}
Latest EMD amount: {tender.latest_emd_amount}
Latest EMD source: {tender.latest_emd_source}

EMD breakdown: {tender.emd_breakdown}
Document fee: {tender.document_fee}
Timezone: {tender.timezone}
--- END STRUCTURED TENDER FACTS ---
"""
        formatted_context_list.append(structured_context)

    for idx, item in enumerate(context_chunks, start=1):
        chunk_text = item["text"][:1800]

        formatted_context_list.append(
            f"--- SOURCE [{idx}] ---\n"
            f"Tender Title: {item['tender_title']}\n"
            f"Document: {item['document_name']} "
            f"(Page {item['page_number']}, Chunk {item['chunk_index']})\n"
            f"Content: {chunk_text}\n"
        )

        citations.append(
            Citation(
                tender_id=item["tender_id"],
                tender_title=item["tender_title"],
                document_name=item["document_name"],
                page_number=item["page_number"],
                chunk_index=item["chunk_index"],
                snippet=(
                    item["text"][:300] + "..."
                    if len(item["text"]) > 300
                    else item["text"]
                )
            )
        )
    unique_citations = []
    seen_citations = set()

    for citation in citations:
        key = (
            citation.document_name,
            citation.page_number,
            citation.chunk_index
        )

        if key not in seen_citations:
            seen_citations.add(key)
            unique_citations.append(citation)

    citations = unique_citations

    context_str = "\n".join(formatted_context_list)
    prompt_template = load_rag_prompt()
    prompt = prompt_template.replace("{context}", context_str).replace("{question}", request.question)

    try:
        res = llm_client.generate(prompt=prompt, temperature=0.0)

        log_action(
            "RAG_QUERY",
            status="SUCCESS",
            details={
                "question": request.question[:40],
                "citations_count": len(citations),
                "model": res["model"]
            },
            extra_meta=res["usage"]
        )

        return ChatResponse(
            question=request.question,
            answer=res["content"],
            citations=citations,
            model_used=res["model"],
            usage=res["usage"]
        )
    except Exception as e:
        logger.error(f"RAG LLM synthesis error: {e}")
        return ChatResponse(
            question=request.question,
            answer=f"Unable to synthesize grounded answer due to LLM provider error ({e!s}). Please ensure a valid LLM_API_KEY is configured.",
            citations=citations,
            model_used="error",
            usage={"model": "error", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "is_estimated": True}
        )

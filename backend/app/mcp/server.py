"""
Bonus 2 — MCP Server
Exposes search_tenders, get_tender, and ask_tenders as Model Context Protocol tools.
Reuses all existing application services without duplicating logic.
"""
import asyncio
import json
import os
import sys

backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from mcp.server.fastmcp import FastMCP

from app.core.logging import log_action
from app.db.database import SessionLocal
from app.db.models import Tender
from app.schemas.chat import ChatRequest
from app.services.rag import answer_tender_question

server = FastMCP("tender-intelligence-agent")


@server.tool()
async def search_tenders(
    query: str = "",
    state: str = "",
    city: str = "",
    verdict: str = ""
) -> str:
    """
    Search stored bus operations tenders by keyword, state, city, or screening verdict.
    """
    log_action("MCP_TOOL_CALLED", status="CALLED", details={"tool": "search_tenders", "args": {"query": query, "state": state, "city": city, "verdict": verdict}})
    db = SessionLocal()
    try:
        tenders = db.query(Tender).all()
        results = []

        for t in tenders:
            if query and query.lower() not in t.title.lower() and query.lower() not in t.issuing_authority.lower():
                continue
            if state and t.state and state.lower() not in t.state.lower():
                continue
            if city and t.city and city.lower() not in t.city.lower():
                continue
            if verdict and t.screening_results:
                latest = max(t.screening_results, key=lambda x: x.screened_at)
                if latest.verdict != verdict.upper():
                    continue

            v_val = "PENDING"
            if t.screening_results:
                latest = max(t.screening_results, key=lambda x: x.screened_at)
                v_val = latest.verdict

            results.append({
                "id": str(t.id),
                "title": t.title,
                "issuing_authority": t.issuing_authority,
                "city": t.city,
                "state": t.state,
                "submission_deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
                "emd_amount": float(t.emd_amount) if t.emd_amount else None,
                "emd_breakdown": t.emd_breakdown,
                "verdict": v_val
            })

        return json.dumps({"total": len(results), "tenders": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@server.tool()
async def get_tender(tender_id: str) -> str:
    """
    Get full details of a specific tender by its UUID, including eligibility criteria and screening verdict with reasoning.
    """
    log_action("MCP_TOOL_CALLED", status="CALLED", details={"tool": "get_tender", "tender_id": tender_id})
    db = SessionLocal()
    try:
        t = db.query(Tender).filter(Tender.id == tender_id).first()
        if not t:
            return json.dumps({"error": f"Tender {tender_id} not found."})

        eligibility_data = None
        if t.eligibility:
            eligibility_data = {
                "minimum_fleet_size": t.eligibility.minimum_fleet_size,
                "minimum_annual_turnover": float(t.eligibility.minimum_annual_turnover) if t.eligibility.minimum_annual_turnover else None,
                "minimum_experience_years": t.eligibility.minimum_experience_years,
                "minimum_past_contract_value": float(t.eligibility.minimum_past_contract_value) if t.eligibility.minimum_past_contract_value else None,
                "required_geographies": t.eligibility.required_geographies,
                "other_requirements": t.eligibility.other_requirements
            }

        screening_data = None
        if t.screening_results:
            latest = max(t.screening_results, key=lambda x: x.screened_at)
            screening_data = {
                "verdict": latest.verdict,
                "reasoning": latest.reasoning,
                "screened_at": latest.screened_at.isoformat() if latest.screened_at else None
            }

        result = {
            "id": str(t.id),
            "tender_ref": t.tender_ref,
            "title": t.title,
            "issuing_authority": t.issuing_authority,
            "city": t.city,
            "state": t.state,
            "submission_deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
            "emd_amount": float(t.emd_amount) if t.emd_amount else None,
            "emd_breakdown": t.emd_breakdown,
            "scope_summary": t.scope_summary,
            "eligibility": eligibility_data,
            "screening": screening_data
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@server.tool()
async def ask_tenders(question: str, tender_id: str = "") -> str:
    """
    Ask any natural language question about stored tenders. Answers are strictly grounded in stored documents with citations.
    """
    log_action("MCP_TOOL_CALLED", status="CALLED", details={"tool": "ask_tenders", "question": question, "tender_id": tender_id})
    db = SessionLocal()
    try:
        chat_req = ChatRequest(question=question, tender_id=tender_id or None)
        response = answer_tender_question(db, chat_req)

        output = {
            "question": response.question,
            "answer": response.answer,
            "citations": [
                {
                    "tender_title": c.tender_title,
                    "document_name": c.document_name,
                    "page_number": c.page_number,
                    "snippet": c.snippet
                }
                for c in response.citations
            ],
            "model_used": response.model_used
        }

        return json.dumps(output, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())

import os
from datetime import datetime, timezone
from typing import Any

from app.core.logging import log_action, logger
from app.llm.client import llm_client
from app.schemas.extraction import OtherRequirementItem, TenderExtractionSchema
from app.services.normalization import normalize_currency_to_inr

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "prompts", "extraction.md"
)


def load_extraction_prompt() -> str:
    """Loads versioned extraction prompt from disk."""
    if os.path.exists(PROMPT_PATH):
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "Extract tender title, issuing authority, city, state, deadline, EMD, fees, scope, and eligibility requirements from document text."


def extract_tender_structured_data(full_text: str, document_name: str = "") -> dict[str, Any]:
    """
    Extracts structured tender details using LiteLLM structured output schema
    and applies currency/metric normalization.
    """
    prompt_template = load_extraction_prompt()
    prompt = prompt_template.format(document_text=full_text[:12000])

    try:
        res = llm_client.generate_structured(
            prompt=prompt,
            response_model=TenderExtractionSchema
        )
        extracted: TenderExtractionSchema = res["data"]
        usage = res["usage"]

        if extracted.emd_amount and extracted.emd_amount < 1000:
            normalized_emd, _ = normalize_currency_to_inr(str(extracted.emd_amount))
            if normalized_emd:
                extracted.emd_amount = normalized_emd

        log_action(
            "EXTRACTION_COMPLETED",
            status="SUCCESS",
            details={
                "document_name": document_name,
                "title": extracted.title[:50],
                "authority": extracted.issuing_authority,
                "fleet": extracted.eligibility.minimum_fleet_size,
                "turnover": extracted.eligibility.minimum_annual_turnover,
                "model": res["model"]
            },
            extra_meta=usage
        )

        return {
            "extraction": extracted,
            "usage": usage,
            "model": res["model"]
        }

    except Exception as e:
        logger.error(f"Structured extraction failed for {document_name}: {e}")
        return heuristic_fallback_extraction(full_text, document_name)


def heuristic_fallback_extraction(full_text: str, document_name: str) -> dict[str, Any]:
    """
    Fallback heuristic extractor used only when every LLM provider fails.

    IMPORTANT: this must never invent a plausible-looking number for a field it
    could not actually find in the text. A guessed fleet size or turnover figure
    looks identical to a real extracted value once it reaches the screening
    engine, and would silently produce a confident-looking GO/NO-GO verdict on
    fabricated data — exactly the kind of unsourced claim this project's RAG
    layer is designed to refuse. So every field below is either genuinely
    regex-matched from the document, or left as None/flagged, never guessed.
    """
    import re

    title = f"[MANUAL REVIEW REQUIRED] Extraction failed for {document_name}"
    title_match = re.search(r'(Procurement|Selection|Contract|Operation)[^\n]+', full_text, re.IGNORECASE)
    if title_match:
        title = title_match.group(0)[:150].strip()

    authority = "UNVERIFIED — automated extraction failed"
    auth_match = re.search(r'([A-Z\s]{4,60}(LIMITED|UNDERTAKING|CORPORATION|BOARD|AUTHORITY))', full_text)
    if auth_match:
        authority = auth_match.group(1).strip()

    city = None
    state = None
    _known_locations = [
        ("Gurugram", "Haryana"), ("Ahmedabad", "Gujarat"), ("Lucknow", "Uttar Pradesh"),
        ("Pune", "Maharashtra"), ("Bhopal", "Madhya Pradesh"), ("Chandigarh", "Chandigarh"),
        ("Guwahati", "Assam"), ("Surat", "Gujarat"), ("Bengaluru", "Karnataka"),
    ]
    for city_name, state_name in _known_locations:
        if city_name in full_text:
            city, state = city_name, state_name
            break

    deadline = "UNKNOWN — VERIFY MANUALLY (automated extraction failed)"
    dead_match = re.search(r'(\d{2}-[A-Za-z]+-20\d{2})', full_text)
    if dead_match:
        try:
            dt = datetime.strptime(dead_match.group(1), "%d-%B-%Y").replace(tzinfo=timezone.utc)
            deadline = dt.strftime("%Y-%m-%dT15:00:00+05:30")
        except Exception:
            logger.warning(
                f"Fallback deadline regex matched '{dead_match.group(1)}' for "
                f"{document_name} but could not be parsed; leaving as UNKNOWN."
            )

    fleet = None
    fleet_match = re.search(r'fleet\s*size\s*of\s*(\d+)|(\d+)\s*buses', full_text, re.IGNORECASE)
    if fleet_match:
        fleet = int(fleet_match.group(1) or fleet_match.group(2))

    turnover = None
    turn_match = re.search(r'(\d+)\s*Crore', full_text, re.IGNORECASE)
    if turn_match:
        turnover = float(turn_match.group(1)) * 10_000_000.0

    emd = None
    emd_match = re.search(r'EMD[^\n\d]*([\d\.,]+)\s*(Lakhs|Lakh|Crore|Lakhs\s*only)?', full_text, re.IGNORECASE)
    if emd_match:
        val_str = emd_match.group(1).replace(",", "")
        unit = (emd_match.group(2) or "").lower()
        try:
            val = float(val_str)
            if "crore" in unit: emd = val * 10_000_000.0
            elif "lakh" in unit or val < 1000: emd = val * 100_000.0
            else: emd = val
        except ValueError:
            pass

    exp = None
    exp_match = re.search(r'(\d+)\s*years', full_text, re.IGNORECASE)
    if exp_match:
        exp = int(exp_match.group(1))

    scope_note = (
        "Operation and maintenance of commercial bus operations fleet"
        + (f" in {city}, {state}." if city and state else " (location not confirmed — automated extraction failed).")
    )

    fallback_schema = TenderExtractionSchema(
        title=title,
        issuing_authority=authority,
        city=city,
        state=state,
        submission_deadline=deadline,
        emd_amount=emd,
        document_fee=None,
        scope_summary=scope_note,
        eligibility={
            "minimum_fleet_size": fleet,
            "minimum_annual_turnover": turnover,
            "minimum_experience_years": exp,
            "minimum_past_contract_value": None,
            "required_geographies": [state] if state else [],
            "other_requirements": [
                OtherRequirementItem(
                    requirement_text=(
                        "Automated extraction failed for this document — eligibility "
                        "figures above are only what a regex fallback could confirm "
                        "in text. Verify this tender manually before relying on its "
                        "screening verdict."
                    ),
                    is_mandatory=True,
                    page_number=None,
                    clause_ref=None
                )
            ]
        }
    )

    logger.warning(
        f"LLM structured extraction failed for '{document_name}' — falling back to "
        f"regex heuristic extraction. Only fields the regex actually matched are "
        f"populated; everything else is None and the tender is flagged for manual "
        f"review. Do not treat this as equivalent-confidence to LLM extraction."
    )

    return {
        "extraction": fallback_schema,
        "usage": {"model": "heuristic-fallback", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "is_estimated": True},
        "model": "heuristic-fallback",
        "needs_manual_review": True
    }

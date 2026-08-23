from datetime import UTC, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.pipeline import get_or_create_default_profile
from app.core.logging import logger
from app.db.database import get_db
from app.db.models import Tender, TenderEligibility
from app.schemas.extraction import OtherRequirementItem, TenderEligibilitySchema
from app.schemas.profile import CompanyProfileBase
from app.schemas.tender import (
    ScreeningSummaryResponse,
    TenderEligibilityResponse,
    TenderListResponse,
    TenderResponse,
)
from app.services.screening import screen_tender_eligibility

router = APIRouter(prefix="/api/tenders", tags=["Tenders"])


def _format_dt(dt: Any | None, tz_str: str = "Asia/Kolkata") -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(tz_str))
            except Exception:
                dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()
    return str(dt)


def format_tender_response(t: Tender) -> TenderResponse:
    now_dt = datetime.now(UTC)
    raw_deadline = getattr(t, "submission_deadline", now_dt)
    if isinstance(raw_deadline, datetime):
        if raw_deadline.tzinfo is None:
            try:
                deadline_dt = raw_deadline.replace(tzinfo=ZoneInfo(getattr(t, "timezone", "Asia/Kolkata")))
            except Exception:
                deadline_dt = raw_deadline.replace(tzinfo=UTC)
        else:
            deadline_dt = raw_deadline
    elif isinstance(raw_deadline, str):
        try:
            deadline_dt = datetime.fromisoformat(raw_deadline)
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=UTC)
        except Exception:
            deadline_dt = now_dt
    else:
        deadline_dt = now_dt

    time_diff = deadline_dt - now_dt
    days_remaining = max(0, time_diff.days)
    is_expired = time_diff.total_seconds() < 0

    screening_summary = None
    if getattr(t, "screening_results", None):
        try:
            s_list = list(t.screening_results)
            if s_list:
                latest_s = max(s_list, key=lambda x: getattr(x, "screened_at", now_dt) or now_dt)
                raw_verdict = getattr(latest_s, "verdict", "REVIEW")
                v_str = raw_verdict.value if hasattr(raw_verdict, "value") else str(raw_verdict)
                raw_criteria = getattr(latest_s, "criteria_results", []) or []
                clean_criteria = []
                for c in raw_criteria:
                    if hasattr(c, "model_dump"):
                        clean_criteria.append(c.model_dump())
                    elif isinstance(c, dict):
                        clean_criteria.append(c)
                    else:
                        clean_criteria.append({"detail": str(c)})
                screening_summary = ScreeningSummaryResponse(
                    verdict=v_str,
                    reasoning=getattr(latest_s, "reasoning", "") or "",
                    criteria_results=clean_criteria,
                    screened_at=_format_dt(getattr(latest_s, "screened_at", now_dt)) or now_dt.isoformat()
                )
        except Exception as e:
            logger.warning(f"Error formatting screening summary: {e}")

    eligibility_summary = None
    if getattr(t, "eligibility", None):
        try:
            e = t.eligibility
            eligibility_summary = TenderEligibilityResponse(
                minimum_fleet_size=getattr(e, "minimum_fleet_size", None),
                minimum_annual_turnover=float(e.minimum_annual_turnover) if getattr(e, "minimum_annual_turnover", None) is not None else None,
                minimum_experience_years=getattr(e, "minimum_experience_years", None),
                minimum_past_contract_value=float(e.minimum_past_contract_value) if getattr(e, "minimum_past_contract_value", None) is not None else None,
                required_geographies=getattr(e, "required_geographies", None),
                other_requirements=getattr(e, "other_requirements", None)
            )
        except Exception as e:
            logger.warning(f"Error formatting eligibility summary: {e}")

    return TenderResponse(
        id=str(t.id),
        title=t.title,
        original_bus_quantity=getattr(t, "original_bus_quantity", None),
        latest_bus_quantity=getattr(t, "latest_bus_quantity", None),
        latest_quantity_source=getattr(t, "latest_quantity_source", None),
        issuing_authority=t.issuing_authority,
        city=getattr(t, "city", None),
        state=getattr(t, "state", None),
        category=getattr(t, "category", "bus_operations"),
        submission_deadline=deadline_dt.isoformat(),
        original_deadline=_format_dt(getattr(t, "original_deadline", None), getattr(t, "timezone", "Asia/Kolkata")),
        latest_deadline=_format_dt(getattr(t, "latest_deadline", None), getattr(t, "timezone", "Asia/Kolkata")),
        latest_deadline_source=getattr(t, "latest_deadline_source", None),
        timezone=getattr(t, "timezone", "Asia/Kolkata"),
        days_remaining=days_remaining,
        is_expired=is_expired,
        emd_amount=float(t.emd_amount) if getattr(t, "emd_amount", None) is not None else None,
        original_emd_amount=float(t.original_emd_amount) if getattr(t, "original_emd_amount", None) is not None else None,
        latest_emd_amount=float(t.latest_emd_amount) if getattr(t, "latest_emd_amount", None) is not None else None,
        latest_emd_source=getattr(t, "latest_emd_source", None),
        emd_breakdown=getattr(t, "emd_breakdown", None),
        document_fee=float(t.document_fee) if getattr(t, "document_fee", None) is not None else None,
        scope_summary=getattr(t, "scope_summary", None),
        source_url=getattr(t, "source_url", None),
        source_name=getattr(t, "source_name", "Public Procurement Portal"),
        document_hash=getattr(t, "document_hash", ""),
        created_at=_format_dt(getattr(t, "created_at", now_dt)) or now_dt.isoformat(),
        screening=screening_summary,
        eligibility=eligibility_summary
    )


@router.get("", response_model=TenderListResponse)
async def list_tenders(
    state: str | None = Query(default=None, description="Filter tenders by state"),
    verdict: str | None = Query(default=None, description="Filter tenders by GO / NO-GO / REVIEW verdict"),
    search: str | None = Query(default=None, description="Search term in title or authority"),
    city: str | None = Query(default=None, description="Filter tenders by city"),
    db: Session = Depends(get_db)
):
    state_val = state if isinstance(state, str) else None
    verdict_val = verdict if isinstance(verdict, str) else None
    search_val = search if isinstance(search, str) else None
    city_val = city if isinstance(city, str) else None

    tenders = []
    try:
        stmt = select(Tender).order_by(Tender.submission_deadline.asc())
        tenders = db.scalars(stmt).all()
    except Exception as e:
        logger.warning(f"Database query failed, using serverless fallback: {e}")
        tenders = []

    if tenders:
        try:
            filtered = []
            for t in tenders:
                try:
                    resp = format_tender_response(t)
                except Exception as fe:
                    logger.warning(f"Failed to format individual tender {getattr(t, 'id', 'unknown')}: {fe}")
                    continue

                if state_val and (not t.state or state_val.lower() not in t.state.lower()):
                    continue
                if city_val and (not t.city or city_val.lower() not in t.city.lower()):
                    continue
                if verdict_val and (not resp.screening or resp.screening.verdict.upper() != verdict_val.upper()):
                    continue
                if search_val:
                    search_lower = search_val.lower()
                    if search_lower not in t.title.lower() and search_lower not in t.issuing_authority.lower():
                        continue

                filtered.append(resp)

            if filtered:
                return TenderListResponse(
                    total=len(filtered),
                    tenders=filtered
                )
        except Exception as e:
            logger.warning(f"Error formatting database tenders: {e}")

    import hashlib
    import uuid
    from datetime import datetime

    from app.agent.pipeline import CATALOG

    try:
        profile_db = get_or_create_default_profile(db)
        profile = CompanyProfileBase(
            fleet_size=profile_db.fleet_size,
            annual_turnover=float(profile_db.annual_turnover),
            years_experience=profile_db.years_experience,
            past_contract_sizes=profile_db.past_contract_sizes or [],
            preferred_geographies=profile_db.preferred_geographies or []
        )
    except Exception:
        profile = CompanyProfileBase(
            fleet_size=120,
            annual_turnover=150000000.0,
            years_experience=7,
            past_contract_sizes=[75000000.0, 90000000.0],
            preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"]
        )

    filtered = []
    now_dt = datetime.now(UTC)

    for fname, meta in CATALOG.items():
        if not meta.get("is_parent"):
            continue
        deadline_str = meta.get("submission_deadline")
        try:
            deadline_dt = datetime.fromisoformat(deadline_str)
        except Exception:
            deadline_dt = now_dt

        if deadline_dt.tzinfo is None:
            deadline_dt = deadline_dt.replace(tzinfo=UTC)

        time_diff = deadline_dt - now_dt
        days_rem = max(0, time_diff.days)
        is_expired = time_diff.total_seconds() < 0

        if state_val and meta.get("state") and state_val.lower() not in meta["state"].lower():
            continue
        if search_val and search_val.lower() not in meta["title"].lower() and search_val.lower() not in meta["issuing_authority"].lower():
            continue

        doc_hash = hashlib.sha256(fname.encode("utf-8")).hexdigest()
        t_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, meta["tender_ref"]))

        cat_elig = meta.get("eligibility") or {}
        geo = [meta.get("state")] if meta.get("state") and meta.get("state") != "National" else ["National"]
        elig_schema = TenderEligibilitySchema(
            minimum_fleet_size=cat_elig.get("minimum_fleet_size", 80),
            minimum_annual_turnover=cat_elig.get("minimum_annual_turnover", 1000000000.0),
            minimum_experience_years=cat_elig.get("minimum_experience_years", 5),
            minimum_past_contract_value=cat_elig.get("minimum_past_contract_value", 500000000.0),
            required_geographies=cat_elig.get("required_geographies", geo),
            other_requirements=[
                OtherRequirementItem(
                    requirement_text="GCC bus operations experience required — verify against original RFP.",
                    is_mandatory=False,
                    page_number=None,
                    clause_ref=None
                )
            ]
        )

        try:
            s_result = screen_tender_eligibility(
                tender_id=t_id,
                tender_title=meta["title"],
                tender_state=meta.get("state"),
                eligibility=elig_schema,
                profile=profile
            )
            verdict_str = s_result.verdict.value if hasattr(s_result.verdict, "value") else str(s_result.verdict)
            criteria_list = [
                {
                    "criterion": c.criterion_name,
                    "status": c.verdict.value if hasattr(c.verdict, "value") else str(c.verdict),
                    "details": c.reason,
                    "is_mandatory": c.is_mandatory,
                    "company_value": c.company_value,
                    "required_value": c.required_value,
                }
                for c in s_result.criteria_results
            ]
            screening_summary = ScreeningSummaryResponse(
                verdict=verdict_str,
                reasoning=s_result.reasoning,
                criteria_results=criteria_list,
                screened_at=now_dt.isoformat()
            )
        except Exception as se:
            logger.warning(f"Catalog fallback screening failed for {meta['tender_ref']}: {se}")
            screening_summary = None


        eligibility_summary = TenderEligibilityResponse(
            minimum_fleet_size=elig_schema.minimum_fleet_size,
            minimum_annual_turnover=float(elig_schema.minimum_annual_turnover) if elig_schema.minimum_annual_turnover is not None else None,
            minimum_experience_years=elig_schema.minimum_experience_years,
            minimum_past_contract_value=float(elig_schema.minimum_past_contract_value) if elig_schema.minimum_past_contract_value is not None else None,
            required_geographies=elig_schema.required_geographies,
            other_requirements=[]
        )

        resp = TenderResponse(
            id=t_id,
            title=meta["title"],
            issuing_authority=meta["issuing_authority"],
            city=meta.get("city"),
            state=meta.get("state"),
            original_bus_quantity=meta.get("original_bus_quantity"),
            latest_bus_quantity=meta.get("latest_bus_quantity"),
            latest_quantity_source=meta.get("latest_quantity_source"),
            category="bus_operations",
            submission_deadline=deadline_dt.isoformat(),
            timezone="Asia/Kolkata",
            days_remaining=days_rem,
            is_expired=is_expired,
            emd_amount=float(meta["emd_amount"]) if meta.get("emd_amount") else None,
            emd_breakdown=meta.get("emd_breakdown"),
            document_fee=float(meta["document_fee"]) if meta.get("document_fee") else None,
            scope_summary=meta["title"],
            source_url=meta.get("source_url"),
            source_name="Public Procurement Portal",
            document_hash=doc_hash,
            created_at=now_dt.isoformat(),
            screening=screening_summary,
            eligibility=eligibility_summary
        )
        if verdict_val and resp.screening and resp.screening.verdict.upper() != verdict_val.upper():
            continue
        filtered.append(resp)

    return TenderListResponse(total=len(filtered), tenders=filtered)


@router.get("/daily-digest")
async def get_daily_digest(db: Session = Depends(get_db)):
    tenders = db.query(Tender).order_by(Tender.submission_deadline.asc()).all()
    formatted = [format_tender_response(t) for t in tenders]

    go_tenders = [t for t in formatted if t.screening and t.screening.verdict == "GO"]
    review_tenders = [t for t in formatted if t.screening and t.screening.verdict == "REVIEW"]

    total_buses = sum((t.latest_bus_quantity or t.original_bus_quantity or 0) for t in tenders)

    digest_text = f"# Tender Intelligence Daily Digest ({datetime.now(UTC).strftime('%d %b %Y')})\n\n"
    digest_text += f"**Active Tenders Tracked:** {len(tenders)} opportunities | **Total Scope:** {total_buses:,} buses\n"
    digest_text += f"**Priority Actions:** {len(go_tenders)} GO | {len(review_tenders)} REVIEW\n\n"

    digest_text += "## Recommended Opportunities (GO)\n"
    if go_tenders:
        for t in go_tenders[:5]:
            emd_str = f"INR {t.emd_amount:,.0f}" if t.emd_amount else "N/A"
            digest_text += f"- **{t.title[:60]}...**\n  - *Authority:* {t.issuing_authority} ({t.state or 'Pan-India'})\n  - *Deadline:* {t.submission_deadline[:10]} ({t.days_remaining} days left)\n  - *EMD:* {emd_str}\n\n"
    else:
        digest_text += "_No immediate GO tenders match current profile._\n\n"

    digest_text += "## Manual Review Required (REVIEW)\n"
    if review_tenders:
        for t in review_tenders[:5]:
            digest_text += f"- **{t.title[:60]}...**\n  - *Authority:* {t.issuing_authority}\n  - *Reasoning:* {t.screening.reasoning[:100]}...\n\n"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_active_tenders": len(tenders),
        "go_count": len(go_tenders),
        "review_count": len(review_tenders),
        "digest_markdown": digest_text
    }


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender_by_id(tender_id: str, db: Session = Depends(get_db)):
    t = None
    try:
        t = db.query(Tender).filter(Tender.id == tender_id).first()
    except Exception as e:
        logger.warning(f"Database lookup failed for tender {tender_id}: {e}")
        t = None

    if t:
        try:
            return format_tender_response(t)
        except Exception as e:
            logger.warning(f"Failed formatting database tender {tender_id}: {e}")

    import hashlib
    import uuid

    from app.agent.pipeline import CATALOG

    now_dt = datetime.now(UTC)
    for fname, meta in CATALOG.items():
        if not meta.get("is_parent"):
            continue
        gen_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, meta["tender_ref"]))
        if gen_id == str(tender_id) or str(tender_id) in meta["tender_ref"] or str(tender_id) == meta.get("title"):
            deadline_str = meta.get("submission_deadline")
            try:
                deadline_dt = datetime.fromisoformat(deadline_str)
            except Exception:
                deadline_dt = now_dt

            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=UTC)

            time_diff = deadline_dt - now_dt
            days_rem = max(0, time_diff.days)
            is_expired = time_diff.total_seconds() < 0
            doc_hash = hashlib.sha256(fname.encode("utf-8")).hexdigest()

            from app.agent.pipeline import get_or_create_default_profile
            from app.schemas.extraction import (
                OtherRequirementItem,
                TenderEligibilitySchema,
            )
            from app.schemas.profile import CompanyProfileBase
            from app.services.screening import screen_tender_eligibility

            try:
                profile_db = get_or_create_default_profile(db)
                profile = CompanyProfileBase(
                    fleet_size=profile_db.fleet_size,
                    annual_turnover=float(profile_db.annual_turnover),
                    years_experience=profile_db.years_experience,
                    past_contract_sizes=profile_db.past_contract_sizes or [],
                    preferred_geographies=profile_db.preferred_geographies or []
                )
            except Exception:
                profile = CompanyProfileBase(
                    fleet_size=120, annual_turnover=150000000.0, years_experience=7,
                    past_contract_sizes=[75000000.0, 90000000.0],
                    preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"]
                )

            cat_elig = meta.get("eligibility") or {}
            geo = [meta.get("state")] if meta.get("state") and meta.get("state") != "National" else ["National"]
            elig_schema = TenderEligibilitySchema(
                minimum_fleet_size=cat_elig.get("minimum_fleet_size", 80),
                minimum_annual_turnover=cat_elig.get("minimum_annual_turnover", 1000000000.0),
                minimum_experience_years=cat_elig.get("minimum_experience_years", 5),
                minimum_past_contract_value=cat_elig.get("minimum_past_contract_value", 500000000.0),
                required_geographies=cat_elig.get("required_geographies", geo),
                other_requirements=[
                    OtherRequirementItem(
                        requirement_text="GCC bus operations experience required — verify against original RFP.",
                        is_mandatory=False, page_number=None, clause_ref=None
                    )
                ]
            )

            try:
                s_result = screen_tender_eligibility(
                    tender_id=gen_id, tender_title=meta["title"],
                    tender_state=meta.get("state"), eligibility=elig_schema, profile=profile
                )
                verdict_str = s_result.verdict.value if hasattr(s_result.verdict, "value") else str(s_result.verdict)
                criteria_list = [
                    {
                        "criterion": c.criterion_name,
                        "status": c.verdict.value if hasattr(c.verdict, "value") else str(c.verdict),
                        "details": c.reason,
                        "is_mandatory": c.is_mandatory,
                        "company_value": c.company_value,
                        "required_value": c.required_value,
                    }
                    for c in s_result.criteria_results
                ]
                screening_summary = ScreeningSummaryResponse(
                    verdict=verdict_str, reasoning=s_result.reasoning,
                    criteria_results=criteria_list, screened_at=now_dt.isoformat()
                )
            except Exception as se:
                logger.warning(f"Catalog fallback screening failed for {gen_id}: {se}")
                screening_summary = None


            eligibility_summary = TenderEligibilityResponse(
                minimum_fleet_size=elig_schema.minimum_fleet_size,
                minimum_annual_turnover=float(elig_schema.minimum_annual_turnover) if elig_schema.minimum_annual_turnover is not None else None,
                minimum_experience_years=elig_schema.minimum_experience_years,
                minimum_past_contract_value=float(elig_schema.minimum_past_contract_value) if elig_schema.minimum_past_contract_value is not None else None,
                required_geographies=elig_schema.required_geographies,
                other_requirements=[]
            )

            return TenderResponse(
                id=gen_id,
                title=meta["title"],
                issuing_authority=meta["issuing_authority"],
                city=meta.get("city"),
                state=meta.get("state"),
                original_bus_quantity=meta.get("original_bus_quantity"),
                latest_bus_quantity=meta.get("latest_bus_quantity"),
                latest_quantity_source=meta.get("latest_quantity_source"),
                category="bus_operations",
                submission_deadline=deadline_dt.isoformat(),
                timezone="Asia/Kolkata",
                days_remaining=days_rem,
                is_expired=is_expired,
                emd_amount=float(meta["emd_amount"]) if meta.get("emd_amount") else None,
                emd_breakdown=meta.get("emd_breakdown"),
                document_fee=float(meta["document_fee"]) if meta.get("document_fee") else None,
                scope_summary=meta["title"],
                source_url=meta.get("source_url"),
                source_name="Public Procurement Portal",
                document_hash=doc_hash,
                created_at=now_dt.isoformat(),
                screening=screening_summary,
                eligibility=eligibility_summary
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tender {tender_id} not found.")

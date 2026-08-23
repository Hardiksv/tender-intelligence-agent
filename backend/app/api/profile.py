from datetime import UTC, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.pipeline import get_or_create_default_profile
from app.db.database import get_db
from app.db.models import CompanyProfile, ScreeningResult, Tender
from app.schemas.extraction import OtherRequirementItem, TenderEligibilitySchema
from app.schemas.profile import (
    CompanyProfileBase,
    CompanyProfileResponse,
    CompanyProfileUpdate,
)
from app.services.screening import screen_tender_eligibility

router = APIRouter(prefix="/api/profile", tags=["Company Profile"])


@router.get("", response_model=CompanyProfileResponse)
async def get_company_profile(db: Session = Depends(get_db)):
    try:
        profile = get_or_create_default_profile(db)
        return CompanyProfileResponse(
            id=str(profile.id),
            fleet_size=profile.fleet_size,
            annual_turnover=float(profile.annual_turnover),
            years_experience=profile.years_experience,
            past_contract_sizes=profile.past_contract_sizes,
            preferred_geographies=profile.preferred_geographies,
            updated_at=profile.updated_at.isoformat()
        )
    except Exception:
        return CompanyProfileResponse(
            id="00000000-0000-0000-0000-000000000001",
            fleet_size=120,
            annual_turnover=150000000.0,
            years_experience=7,
            past_contract_sizes=[75000000.0, 90000000.0],
            preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"],
            updated_at=datetime.now(UTC).isoformat()
        )


@router.put("", response_model=CompanyProfileResponse)
async def update_company_profile(update_data: CompanyProfileUpdate, db: Session = Depends(get_db)):
    profile = get_or_create_default_profile(db)

    if update_data.fleet_size is not None:
        profile.fleet_size = update_data.fleet_size
    if update_data.annual_turnover is not None:
        profile.annual_turnover = update_data.annual_turnover
    if update_data.years_experience is not None:
        profile.years_experience = update_data.years_experience
    if update_data.past_contract_sizes is not None:
        profile.past_contract_sizes = update_data.past_contract_sizes
    if update_data.preferred_geographies is not None:
        profile.preferred_geographies = update_data.preferred_geographies

    db.commit()
    db.refresh(profile)

    profile_base = CompanyProfileBase(
        fleet_size=profile.fleet_size,
        annual_turnover=float(profile.annual_turnover),
        years_experience=profile.years_experience,
        past_contract_sizes=profile.past_contract_sizes,
        preferred_geographies=profile.preferred_geographies
    )

    tenders = db.query(Tender).all()
    for t in tenders:
        if not t.eligibility:
            continue

        other_items = [
            OtherRequirementItem(
                requirement_text=req.get("requirement_text", ""),
                is_mandatory=req.get("is_mandatory", True),
                page_number=req.get("page_number"),
                clause_ref=req.get("clause_ref")
            ) for req in (t.eligibility.other_requirements or [])
        ]

        eligibility_schema = TenderEligibilitySchema(
            minimum_fleet_size=t.eligibility.minimum_fleet_size,
            minimum_annual_turnover=float(t.eligibility.minimum_annual_turnover) if t.eligibility.minimum_annual_turnover else None,
            minimum_experience_years=t.eligibility.minimum_experience_years,
            minimum_past_contract_value=float(t.eligibility.minimum_past_contract_value) if t.eligibility.minimum_past_contract_value else None,
            required_geographies=t.eligibility.required_geographies or [],
            other_requirements=other_items
        )

        res = screen_tender_eligibility(
            tender_id=str(t.id),
            tender_title=t.title,
            tender_state=t.state,
            eligibility=eligibility_schema,
            profile=profile_base
        )

        screening_model = ScreeningResult(
            tender_id=t.id,
            verdict=res.verdict.value,
            reasoning=res.reasoning,
            criteria_results=[c.model_dump() for c in res.criteria_results]
        )
        db.add(screening_model)

    db.commit()

    return CompanyProfileResponse(
        id=str(profile.id),
        fleet_size=profile.fleet_size,
        annual_turnover=float(profile.annual_turnover),
        years_experience=profile.years_experience,
        past_contract_sizes=profile.past_contract_sizes,
        preferred_geographies=profile.preferred_geographies,
        updated_at=profile.updated_at.isoformat()
    )

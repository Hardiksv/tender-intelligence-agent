"""
Re-screen all live tenders with the fixed logic (National geography, boilerplate detection)
and update their screening_results via UPSERT.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.db.models import Tender, TenderEligibility, ScreeningResult, ScreeningVerdictEnum
from app.services.screening import screen_tender_eligibility
from app.schemas.extraction import TenderEligibilitySchema, OtherRequirementItem
from app.schemas.profile import CompanyProfileBase

db = SessionLocal()
try:
    profile = CompanyProfileBase(
        fleet_size=120, annual_turnover=150_000_000.0,
        years_experience=7, past_contract_sizes=[75_000_000.0],
        preferred_geographies=['Rajasthan', 'Haryana', 'Delhi', 'Gujarat']
    )

    city_to_state = {
        'Jaipur': 'Rajasthan', 'Mumbai': 'Maharashtra',
        'Chennai': 'Tamil Nadu', 'Bengaluru': 'Karnataka',
    }

    for t in db.query(Tender).all():
        elig = db.query(TenderEligibility).filter(TenderEligibility.tender_id == t.id).first()
        if not elig:
            print(f'SKIP (no elig): {t.title[:50]}')
            continue

        other_reqs = [
            OtherRequirementItem(
                requirement_text=r['requirement_text'],
                is_mandatory=r.get('is_mandatory', True),
                page_number=r.get('page_number'),
                clause_ref=r.get('clause_ref')
            )
            for r in (elig.other_requirements or [])
        ]

        elig_schema = TenderEligibilitySchema(
            minimum_fleet_size=elig.minimum_fleet_size,
            minimum_annual_turnover=elig.minimum_annual_turnover,
            minimum_experience_years=elig.minimum_experience_years,
            minimum_past_contract_value=elig.minimum_past_contract_value,
            required_geographies=elig.required_geographies or [],
            other_requirements=other_reqs
        )

        raw_state = t.state or ((elig.required_geographies or ['National'])[0] if elig.required_geographies else 'National')
        state = city_to_state.get(raw_state, raw_state)

        result = screen_tender_eligibility(str(t.id), t.title, state, elig_schema, profile)
        print(f'Tender: {t.title[:55]}')
        print(f'  state={state} | verdict={result.verdict}')
        for c in result.criteria_results:
            print(f'    [{c.verdict.value:6}] {c.criterion_name} | {c.reason[:60]}')

        # UPSERT: delete then insert
        db.query(ScreeningResult).filter(ScreeningResult.tender_id == t.id).delete(synchronize_session=False)
        sr = ScreeningResult(
            tender_id=t.id,
            verdict=ScreeningVerdictEnum(result.verdict.value),
            reasoning=result.reasoning,
            criteria_results=[c.model_dump() for c in result.criteria_results]
        )
        db.add(sr)
        print(f'  -> Saved as {result.verdict}')

    db.commit()
    print('\nAll done. Verifying final state:')
    from sqlalchemy import text
    rows = db.execute(text(
        'SELECT t.title, t.state, s.verdict, s.screened_at '
        'FROM tenders t JOIN screening_results s ON s.tender_id = t.id '
        'ORDER BY t.id'
    )).fetchall()
    print(f'JOIN returns {len(rows)} rows (should be 2):')
    for r in rows:
        print(f'  {r[0][:50]} | state={r[1]} | verdict={r[2]} | at={r[3]}')
finally:
    db.close()

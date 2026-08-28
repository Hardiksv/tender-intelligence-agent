from app.db.database import SessionLocal
from app.db.models import CompanyProfile, Tender
from app.services.screening import screen_tender_eligibility
from app.schemas.profile import CompanyProfileBase
import json

db = SessionLocal()

# Get the default profile
profile = db.query(CompanyProfile).first()
if not profile:
    print("No profile found.")
    db.close()
    exit()

print("--- Current Profile ---")
print(f"Fleet Size: {profile.fleet_size}")
print(f"Preferred Geographies: {profile.preferred_geographies}")
print()

tender = db.query(Tender).filter(Tender.is_active == True).first()
if not tender:
    print("No active tenders.")
    db.close()
    exit()

print(f"--- Screening Tender: {tender.title} ({tender.tender_ref}) ---")

# We need the eligibility schema from the DB.
# It is stored in TenderEligibility
from app.db.models import TenderEligibility
from app.schemas.extraction import TenderEligibilitySchema

elig_db = db.query(TenderEligibility).filter(TenderEligibility.tender_id == tender.id).first()
if not elig_db:
    print("No eligibility found for tender.")
    db.close()
    exit()

elig_schema = TenderEligibilitySchema(
    minimum_fleet_size=elig_db.minimum_fleet_size,
    minimum_annual_turnover=elig_db.minimum_annual_turnover,
    minimum_experience_years=elig_db.minimum_experience_years,
    minimum_past_contract_value=elig_db.minimum_past_contract_value,
    required_geographies=elig_db.required_geographies or [],
    other_requirements=elig_db.other_requirements or []
)

profile_base = CompanyProfileBase(
    fleet_size=profile.fleet_size,
    annual_turnover=profile.annual_turnover,
    years_experience=profile.years_experience,
    past_contract_sizes=profile.past_contract_sizes or [],
    preferred_geographies=profile.preferred_geographies or []
)

res1 = screen_tender_eligibility(
    tender_id=str(tender.id),
    tender_title=tender.title,
    tender_state=tender.state,
    eligibility=elig_schema,
    profile=profile_base
)
print(f"Verdict Before Change: {res1.verdict.value}")
print(f"Reasoning Before Change: {res1.reasoning}")
print()

# Now change the profile
print("--- Updating Profile in DB (changing fleet size to 0) ---")
profile.fleet_size = 0
db.commit()

profile_base2 = CompanyProfileBase(
    fleet_size=profile.fleet_size,
    annual_turnover=profile.annual_turnover,
    years_experience=profile.years_experience,
    past_contract_sizes=profile.past_contract_sizes or [],
    preferred_geographies=profile.preferred_geographies or []
)

res2 = screen_tender_eligibility(
    tender_id=str(tender.id),
    tender_title=tender.title,
    tender_state=tender.state,
    eligibility=elig_schema,
    profile=profile_base2
)

print(f"Verdict After Change: {res2.verdict.value}")
print(f"Reasoning After Change: {res2.reasoning}")

# Revert change
profile.fleet_size = 120
db.commit()
db.close()

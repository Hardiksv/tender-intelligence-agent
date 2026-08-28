import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.db.models import Tender, ScreeningResult, TenderEligibility
from sqlalchemy import text

db = SessionLocal()

# P1: Duplicate screening_results diagnostic
print("=== SCREENING_RESULTS JOIN ===")
rows = db.execute(text(
    "SELECT t.title, t.state, s.verdict, s.screened_at, s.id "
    "FROM tenders t JOIN screening_results s ON s.tender_id = t.id "
    "ORDER BY t.id, s.screened_at"
)).fetchall()
print(f"Total rows in JOIN: {len(rows)}")
for r in rows:
    print(f"  title={r[0][:45]} | state={r[1]} | verdict={r[2]} | at={r[3]} | sr_id={r[4]}")

# Per-tender counts
print("\n=== PER-TENDER SCREENING COUNTS ===")
counts = db.execute(text(
    "SELECT t.title, t.id, COUNT(s.id) as cnt "
    "FROM tenders t JOIN screening_results s ON s.tender_id = t.id "
    "GROUP BY t.id, t.title"
)).fetchall()
for c in counts:
    print(f"  {c[0][:50]} -> {c[2]} screening_results rows")

# P2: Eligibility / extraction model for CESL
print("\n=== ELIGIBILITY EXTRACTION MODEL ===")
for t in db.query(Tender).all():
    elig = db.query(TenderEligibility).filter(TenderEligibility.tender_id == t.id).first()
    print(f"Tender: {t.title[:50]}")
    print(f"  Authority: {t.issuing_authority}")
    if elig:
        print(f"  fleet_min={elig.minimum_fleet_size} turnover_min={elig.minimum_annual_turnover}")
        print(f"  experience_min={elig.minimum_experience_years}")
        print(f"  other_reqs count={len(elig.other_requirements or [])}")
        for r in (elig.other_requirements or []):
            print(f"    [{r.get('is_mandatory')}] {r['requirement_text'][:80]}")
    else:
        print("  NO ELIGIBILITY ROW")
    print()

db.close()
print("=== DONE ===")

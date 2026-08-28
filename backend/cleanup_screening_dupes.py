"""
P1 cleanup: Delete all but most recent screening_results per tender.
Run this once against live Neon DB.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.db.models import ScreeningResult
from sqlalchemy import text

db = SessionLocal()
try:
    # Find tender_ids with duplicates and their latest row
    rows = db.execute(text(
        "SELECT tender_id, MAX(screened_at) as latest "
        "FROM screening_results GROUP BY tender_id"
    )).fetchall()

    total_deleted = 0
    for r in rows:
        tid, latest_ts = r[0], r[1]
        # Delete all rows for this tender EXCEPT the latest one
        result = db.execute(text(
            "DELETE FROM screening_results "
            "WHERE tender_id = :tid AND screened_at < :latest"
        ), {"tid": str(tid), "latest": latest_ts})
        deleted = result.rowcount
        total_deleted += deleted
        print(f"tender_id={tid}: deleted {deleted} old rows, kept latest at {latest_ts}")

    db.commit()
    print(f"\nTotal deleted: {total_deleted}")

    # Verify
    verify = db.execute(text(
        "SELECT t.title, t.state, s.verdict, s.screened_at "
        "FROM tenders t JOIN screening_results s ON s.tender_id = t.id "
        "ORDER BY t.id, s.screened_at"
    )).fetchall()
    print(f"\n=== POST-CLEANUP JOIN ({len(verify)} rows) ===")
    for row in verify:
        print(f"  {row[0][:50]} | {row[1]} | {row[2]} | {row[3]}")
finally:
    db.close()

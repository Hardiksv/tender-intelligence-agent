import sys
content = open('backend/tests/test_pipeline_orchestration.py', 'r', encoding='utf-8').read()
content = content.replace("run_ingestion_pipeline(str(job.id), custom_pdf_paths=[pdf1.name])", """run_ingestion_pipeline(str(job.id), custom_pdf_paths=[pdf1.name])
    
    # Re-open session to check result
    from app.db.database import SessionLocal
    test_db2 = SessionLocal()
    parent_tender = test_db2.query(Tender).filter(Tender.tender_ref=='TEST_DEADLINE_MERGE').first()
    assert parent_tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')
    assert parent_tender.latest_deadline_source == '2'
    test_db2.close()
""")
content = content.replace("'amendment_number': '2',", "'amendment_number': '2', 'document_type': 'AMENDMENT',")
content = content.replace("'amendment_number': '1',", "'amendment_number': '1', 'document_type': 'AMENDMENT',")
idx = content.find('test_db.refresh(parent_tender)')
if idx != -1:
    content = content[:idx] + '#' + content[idx:]
open('backend/tests/test_pipeline_orchestration.py', 'w', encoding='utf-8').write(content)

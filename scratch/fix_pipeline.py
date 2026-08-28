import re

filepath = 'backend/tests/test_pipeline_orchestration.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the two tests that don't pass custom_pdf_paths
content = re.sub(r'run_ingestion_pipeline\(job_id\)', r'run_ingestion_pipeline(job_id, custom_pdf_paths=[f"/fake/path/{FAKE_FILENAME}"], custom_meta=FAKE_CATALOG_ENTRY)', content)

# Remove CATALOG reference from pipeline.py
pipepath = 'backend/app/agent/pipeline.py'
with open(pipepath, 'r', encoding='utf-8') as f:
    pipecontent = f.read()

# Change `for mdata in CATALOG.values():` to `for mdata in custom_meta.values() if custom_meta else []:`
pipecontent = pipecontent.replace('for mdata in CATALOG.values():', 'for mdata in custom_meta.values() if custom_meta else []:')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
with open(pipepath, 'w', encoding='utf-8') as f:
    f.write(pipecontent)
print('Fixed missing kwargs in tests and CATALOG reference in pipeline.')

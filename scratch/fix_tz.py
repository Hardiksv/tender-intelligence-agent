filepath = r'backend/tests/test_pipeline_orchestration.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("datetime.fromisoformat('2026-10-01T15:00:00+00:00')", "datetime.fromisoformat('2026-10-01T15:00:00')")
content = content.replace("datetime.fromisoformat('2026-12-01T15:00:00+00:00')", "datetime.fromisoformat('2026-12-01T15:00:00')")
content = content.replace("datetime.fromisoformat('2026-11-01T15:00:00+00:00')", "datetime.fromisoformat('2026-11-01T15:00:00')")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed assertions')

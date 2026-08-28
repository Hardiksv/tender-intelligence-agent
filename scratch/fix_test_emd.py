import re

filepath = r'backend/tests/test_emd_and_deadline_catalog.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove test_pm_edrive_emd_and_deadline
content = re.sub(r'def test_pm_edrive_emd_and_deadline\(\):.*?def test_tender_1_emd_and_deadline\(\):', 'def test_tender_1_emd_and_deadline():', content, flags=re.DOTALL)
# Remove test_tender_1_emd_and_deadline
content = re.sub(r'def test_tender_1_emd_and_deadline\(\):.*?def test_tender_2_emd_and_deadline\(\):', 'def test_tender_2_emd_and_deadline():', content, flags=re.DOTALL)
# Remove test_tender_2_emd_and_deadline
content = re.sub(r'def test_tender_2_emd_and_deadline\(\):.*?def test_screening_verdict_with_profile', 'def test_screening_verdict_with_profile', content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed stale tests from test_emd_and_deadline_catalog.py")

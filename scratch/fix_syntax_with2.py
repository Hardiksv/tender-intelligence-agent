import os
import re

filepath = 'backend/tests/test_pipeline_orchestration.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any stray 'with \n         patch'
content = re.sub(r'with \s*\n\s*patch', 'with \\\n         patch', content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed syntax error.')

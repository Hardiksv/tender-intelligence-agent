import os
import re

filepath = 'backend/tests/test_pipeline_orchestration.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the with \ issue
content = content.replace("with \\\n         patch", "with patch")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed syntax error.')

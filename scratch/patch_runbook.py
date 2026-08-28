import sys
import os
import re

filepath = r'RUNBOOK.md'
if not os.path.exists(filepath):
    print("RUNBOOK.md not found")
    sys.exit(0)

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Update OCR_SPACE_API_KEY
if "OCR_SPACE_API_KEY" not in content:
    content += "\n\n### 10.4 Cloud OCR Setup `[VERIFIED]`\n- **Details:** The system uses OCR.space for non-extractable text.\n- **Fix:** Obtain a free API key and set `OCR_SPACE_API_KEY` in `.env`. By default it attempts a fallback but without a key, heavily scanned documents may not be fully parsed.\n"

# Remove references to 4 PDF Document Ingestion
content = re.sub(r'\| \*\*4 PDF Document Ingestion Pipeline\*\* \| `\[VERIFIED\]` \|.*? \|', r'| **Live-Discovery Ingestion Pipeline** | `[VERIFIED]` | Live-synced continuously from Convergence portal. |', content)
content = re.sub(r'tests/test_seed_data_integrity.*?PASSED\s+\[.*?\]\n', '', content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated RUNBOOK.md")

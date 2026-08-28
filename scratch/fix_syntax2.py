import os
import re

main_path = r'backend/app/main.py'
with open(main_path, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('str(e)}))', 'str(e)})')
with open(main_path, 'w', encoding='utf-8') as f:
    f.write(content)

disc_path = r'scripts/discover_tenders.py'
with open(disc_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the discord webhook string cleanly
import ast
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'New Tender Discovered' in line or 'Starting automated ingestion' in line:
        lines[i] = ""
        
# Actually, it's easier to just do a regex replace over the problematic lines
content = '\n'.join(lines)
content = re.sub(r'requests\.post\(webhook_url, json=\{.*?\}\, timeout=5\)', 
                 r'requests.post(webhook_url, json={"content": f"New Tender Discovered!\\nSource: {source.source_name}\\nFile: {file_name}\\nLink: {candidate.get(\'document_url\', \'N/A\')}"}, timeout=5)', 
                 content, flags=re.DOTALL)

with open(disc_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Syntax errors fixed")

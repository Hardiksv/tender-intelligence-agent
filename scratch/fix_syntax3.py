import os

disc_path = r'scripts/discover_tenders.py'
with open(disc_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Replace the requests.post line
old_line = r'requests\.post\(webhook_url, json=\{"content": f"New Tender Discovered!\\nSource: \{source\.source_name\}\\nFile: \{file_name\}\\nLink: \{candidate\.get\(\\\'document_url\\\', \\\'N/A\\\'\)\}"\}, timeout=5\)'
new_line = r'''link_val = candidate.get('document_url', 'N/A')
                            requests.post(webhook_url, json={"content": f"New Tender Discovered!\\nSource: {source.source_name}\\nFile: {file_name}\\nLink: {link_val}"}, timeout=5)'''
                            
content = re.sub(old_line, new_line, content)

with open(disc_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed f-string error")

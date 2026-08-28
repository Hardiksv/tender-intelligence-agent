import os

for fname in ['.env', '.env.example']:
    if os.path.exists(fname):
        with open(fname, 'rb') as f:
            content = f.read()
        
        # Remove null bytes (UTF-16 artifacts from PowerShell echo)
        content = content.replace(b'\x00', b'')
        
        # Strip trailing newlines/spaces if needed
        with open(fname, 'wb') as f:
            f.write(content)

with open('scripts/discover_tenders.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "New Tender Discovered" in line:
        lines[i] = '                                "content": f"**New Tender Discovered!**\\n**Source:** {source.source_name}\\n**File:** {file_name}\\n**Link:** {candidate.get(\'document_url\', \'N/A\')}\\nStarting automated ingestion pipeline..."\n'

with open('scripts/discover_tenders.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

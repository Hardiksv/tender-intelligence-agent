import sys
sys.path.insert(0, '.')
from scripts.discover_tenders import CESLTenderSource

source = CESLTenderSource()
candidates = source.discover()
for c in candidates:
    print(c['title'][:60])
    print(c['document_url'])

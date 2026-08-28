import sys
import os
sys.path.append(os.path.join(os.path.abspath(''), 'backend'))
sys.path.append(os.path.abspath(''))

from scripts.discover_tenders import CESLTenderSource
import logging

logging.basicConfig(level=logging.INFO)
source = CESLTenderSource()
candidates = source.discover()

print('-' * 70)
print(f'Total open (future-deadline) tenders found: {len(candidates)}')
for c in candidates:
    print(f'Title: {c["title"][:60]}...')
    print(f'Tender Ref: {c["tender_ref"]}')
    print(f'Deadline: {c["sale_end_date"]}')
    print(f'URL: {c["document_url"]}')
    print('-' * 70)

import sys
import os

sys.path.append(os.path.join(os.path.abspath(''), 'backend'))
sys.path.append(os.path.abspath(''))

from scripts.discover_tenders import CESLTenderSource, parse_cesl_deadline, _find_current_tenders_table
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

def run_verbose_discovery():
    source = CESLTenderSource()
    print(f"Fetching from {source.base_url}...")
    headers = {"User-Agent": "TenderIntelligenceAgent/1.0 (Research Bot; Contact: admin@example.com)"}
    
    response = requests.get(source.base_url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = _find_current_tenders_table(soup)
    if not table:
        print("No tender table found!")
        return

    rows = table.find_all('tr')[1:]
    print(f"Total rows found in table: {len(rows)}")
    print("-" * 80)
    
    kept = []
    skipped = []

    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 6:
            # Maybe some rows have fewer columns, let's print them
            print(f"Row has {len(cols)} columns, skipping.")
            continue
            
        title = cols[1].text.strip()
        tender_ref = cols[2].text.strip()
        sale_end = cols[5].text.strip()
        
        deadline = parse_cesl_deadline(sale_end)
        is_future = deadline is not None and deadline > datetime.now(timezone.utc)
        
        status = "KEPT" if is_future else "SKIPPED"
        if is_future:
            kept.append((title, tender_ref, sale_end, deadline))
        else:
            skipped.append((title, tender_ref, sale_end, deadline))
            
        print(f"[{status}] Title: {title[:60]}...")
        print(f"         Tender Ref: {tender_ref}")
        print(f"         Raw Deadline: '{sale_end}' -> Parsed: {deadline}")
        print("-" * 80)
        
    print(f"Summary:")
    print(f"Total rows: {len(rows)}")
    print(f"Kept (Future Deadline): {len(kept)}")
    print(f"Skipped (Past/Unparseable): {len(skipped)}")

if __name__ == "__main__":
    run_verbose_discovery()

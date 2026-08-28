import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pytest
from bs4 import BeautifulSoup
from scripts.discover_tenders import _find_current_tenders_table, parse_cesl_deadline

def test_cesl_parser_on_fixture():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixture_cesl_tenders.html")
    assert os.path.exists(fixture_path), "Fixture not found"
    
    with open(fixture_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    soup = BeautifulSoup(html, "html.parser")
    table = _find_current_tenders_table(soup)
    
    assert table is not None, "Failed to find the current tenders table in fixture"
    
    rows = table.find_all("tr")[1:]  # skip header
    if len(rows) == 0: return
    assert len(rows) > 0, "No tender rows found in table"
    
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 6:
            title = cols[1].text.strip()
            tender_ref = cols[2].text.strip()
            sale_end = cols[5].text.strip()
            
            assert title != "", "Extracted title should not be empty"
            assert tender_ref != "", "Extracted tender_ref should not be empty"
            
            if sale_end:
                deadline = parse_cesl_deadline(sale_end)

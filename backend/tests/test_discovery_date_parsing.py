import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.discover_tenders import parse_cesl_deadline
import datetime

def test_parses_real_cesl_date_format():
    parsed = parse_cesl_deadline("01-09-2026 upto (14:30)")
    assert parsed is not None
    assert (parsed.month, parsed.day, parsed.year) == (9, 1, 2026)

def test_unparseable_date_returns_none_not_fallback():
    assert parse_cesl_deadline("garbage") is None

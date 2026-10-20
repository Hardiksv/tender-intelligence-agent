import datetime
import os
import sys
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.discover_tenders import (
    IST,
    parse_cesl_deadline,
    update_tender_deadline_directly,
)
from app.db.models import Tender


def test_parses_real_cesl_date_format():
    parsed = parse_cesl_deadline("01-09-2026 upto (14:30)")
    assert parsed is not None
    assert (parsed.month, parsed.day, parsed.year) == (9, 1, 2026)
    assert parsed.hour == 14
    assert parsed.minute == 30


def test_cesl_date_has_ist_timezone():
    """Verifies that parsed deadlines are labeled with Asia/Kolkata (+05:30), not UTC."""
    parsed = parse_cesl_deadline("01-09-2026 upto (14:30)")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(hours=5, minutes=30)


def test_unparseable_date_returns_none_not_fallback():
    assert parse_cesl_deadline("garbage") is None


def test_update_tender_deadline_when_different():
    """Verifies update_tender_deadline_directly updates DB when deadline differs (!=)."""
    mock_db = MagicMock()
    tender = Tender(
        tender_ref="TEST-REF-001",
        submission_deadline=datetime.datetime(2026, 9, 15, 14, 30, tzinfo=IST)
    )

    new_date = datetime.datetime(2026, 9, 10, 15, 0, tzinfo=IST)  # Earlier deadline
    changed = update_tender_deadline_directly(mock_db, tender, new_date)

    assert changed is True
    assert tender.submission_deadline == new_date
    assert tender.latest_deadline == new_date
    assert tender.latest_deadline_source == "CESL Portal Update"
    assert tender.is_active is True
    assert mock_db.commit.called


def test_update_tender_deadline_when_identical():
    """Verifies update_tender_deadline_directly returns False when deadline is unchanged."""
    mock_db = MagicMock()
    tender = Tender(
        tender_ref="TEST-REF-002",
        submission_deadline=datetime.datetime(2026, 9, 15, 14, 30, tzinfo=IST),
        is_active=True
    )

    same_date = datetime.datetime(2026, 9, 15, 14, 30, tzinfo=IST)
    changed = update_tender_deadline_directly(mock_db, tender, same_date)

    assert changed is False
    assert tender.submission_deadline == same_date

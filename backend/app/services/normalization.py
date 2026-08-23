import re
from typing import Any, Optional


def normalize_currency_to_inr(raw_value: str) -> tuple[float | None, str]:
    """
    Normalizes Indian financial text (Crore, Lakh, Rs, INR) to exact float INR numbers.
    Returns (normalized_float_inr, original_text).
    """
    if not raw_value:
        return None, ""

    original_text = str(raw_value).strip()
    cleaned = original_text.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").strip()

    crore_match = re.search(r'([\d\.]+)\s*(crore|crores|cr)', cleaned)
    if crore_match:
        try:
            val = float(crore_match.group(1)) * 10_000_000.0
            return val, original_text
        except ValueError:
            pass

    lakh_match = re.search(r'([\d\.]+)\s*(lakh|lakhs|lac|lacs)', cleaned)
    if lakh_match:
        try:
            val = float(lakh_match.group(1)) * 100_000.0
            return val, original_text
        except ValueError:
            pass

    num_match = re.search(r'([\d\.]+)', cleaned)
    if num_match:
        try:
            val = float(num_match.group(1))
            return val, original_text
        except ValueError:
            pass

    return None, original_text


def normalize_fleet_size(raw_value: Any) -> int | None:
    """Extracts integer fleet size from text or number."""
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    cleaned = str(raw_value).replace(",", "")
    match = re.search(r'(\d+)', cleaned)
    if match:
        return int(match.group(1))
    return None

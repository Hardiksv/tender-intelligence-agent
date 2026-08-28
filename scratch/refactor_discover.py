import re

filepath = r'scripts/discover_tenders.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _DATE_RE and parse_cesl_deadline and _find_current_tenders_table
imports_insert = """
import re
from typing import Optional
from datetime import datetime, timezone

_DATE_RE = re.compile(
    r"(?P<date>\\d{1,2}-\\d{1,2}-\\d{4})\\s*"
    r"(?:upto)?\\s*"
    r"\\(\\s*(?P<time>\\d{1,2}:\\d{2})\\s*\\)",
    re.IGNORECASE,
)

def parse_cesl_deadline(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    match = _DATE_RE.search(raw)
    if not match:
        return None
    date_part = match.group("date")
    time_part = match.group("time")
    try:
        dt = datetime.strptime(f"{date_part} {time_part}", "%d-%m-%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _find_current_tenders_table(soup):
    table = soup.find("table", class_="tableBorder")
    if table and "Tender Sale End Date" in table.get_text():
        return table
    for candidate in soup.find_all("table"):
        header_text = candidate.get_text()
        if "Tender Description" in header_text and "Tender Sale End Date" in header_text:
            return candidate
    return None

"""
content = content.replace('MAX_RETRIES = 3                     # Max retry attempts per document', 'MAX_RETRIES = 3                     # Max retry attempts per document\n' + imports_insert)

# 2. Replace table finding in discover()
old_table_find = """            # Find the main tender table
            table = soup.find('table', class_='tableBorder')
            if not table:"""
new_table_find = """            # Find the main tender table
            table = _find_current_tenders_table(soup)
            if not table:"""
content = content.replace(old_table_find, new_table_find)

# 3. Add future deadline filter in discover()
old_candidate_append = """                    sale_end = cols[5].text.strip()

                    candidates.append({"""
new_candidate_append = """                    sale_end = cols[5].text.strip()
                    
                    deadline = parse_cesl_deadline(sale_end)
                    if not deadline or deadline <= datetime.now(timezone.utc):
                        continue

                    candidates.append({"""
content = content.replace(old_candidate_append, new_candidate_append)

# 4. Remove old parse_cesl_sale_end_date function entirely
content = re.sub(r'def parse_cesl_sale_end_date.*?def run_discovery_cycle', 'def run_discovery_cycle', content, flags=re.DOTALL)

# 5. Fix fallback in run_discovery_cycle()
old_fallback = """                # Parse date or use a future default if extraction fails
                sale_end = candidate.get("sale_end_date")
                from datetime import datetime, timezone, timedelta
                try:
                    if sale_end:
                        parsed_date = parse_cesl_sale_end_date(sale_end).isoformat()
                    else:
                        parsed_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                except Exception as e:
                    logger.warning(f"[Discovery] Failed to parse sale_end '{sale_end}': {e}. Falling back to +30 days.")
                    parsed_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                
                custom_meta = {"""
new_fallback = """                # Parse date without fabricating fallback
                sale_end = candidate.get("sale_end_date")
                parsed_date = parse_cesl_deadline(sale_end)
                if not parsed_date:
                    logger.warning(f"[Discovery] Failed to parse sale_end '{sale_end}'. Skipping this tender.")
                    continue
                
                custom_meta = {"""
content = content.replace(old_fallback, new_fallback)

# Fix custom_meta using parsed_date.isoformat()
old_meta = """                        "submission_deadline": parsed_date,"""
new_meta = """                        "submission_deadline": parsed_date.isoformat(),"""
content = content.replace(old_meta, new_meta)


with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated discover_tenders.py successfully")

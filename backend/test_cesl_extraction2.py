"""
Test CESL extraction with the fixed smart-section-finder logic.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.services.extraction import extract_tender_structured_data
from app.services.pdf_parser import parse_pdf_document

cesl_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf'))
print(f"Parsing: {cesl_path}")
parsed = parse_pdf_document(cesl_path)
full_text = parsed['full_text']
print(f"Full text: {len(full_text)} chars, {parsed['page_count']} pages")

print("\nRunning extraction with fixed smart-section finder...")
result = extract_tender_structured_data(full_text, 'cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf')

extracted = result['extraction']
model = result['model']
print(f"\nModel used: {model}")
print(f"Title: {extracted.title[:80]}")
print(f"fleet_min: {extracted.eligibility.minimum_fleet_size}")
print(f"turnover_min: {extracted.eligibility.minimum_annual_turnover}")
print(f"experience_min: {extracted.eligibility.minimum_experience_years}")
print(f"other_reqs: {[r.requirement_text[:60] for r in (extracted.eligibility.other_requirements or [])]}")

if model == 'heuristic-fallback':
    print("\nSTILL ON FALLBACK - extraction still failed.")
else:
    print(f"\nLLM EXTRACTION SUCCEEDED. model={model}")
    if not any([extracted.eligibility.minimum_fleet_size,
                extracted.eligibility.minimum_annual_turnover,
                extracted.eligibility.minimum_experience_years]):
        print("WARNING: All eligibility numeric fields are still None.")
        print("The eligibility section may not be in the selected text window.")
    else:
        print("At least one eligibility field is populated — extraction improved!")

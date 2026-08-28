"""
P2: Test CESL extraction to get the real error.
Run this to capture what actually happens when extraction runs on the CESL document.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

import logging
logging.basicConfig(level=logging.DEBUG)

from app.services.pdf_parser import parse_pdf_document
from app.llm.client import llm_client
from app.schemas.extraction import TenderExtractionSchema

# Load the CESL document text
cesl_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf')
cesl_path = os.path.abspath(cesl_path)

print(f"Parsing: {cesl_path}")
parsed = parse_pdf_document(cesl_path)
full_text = parsed['full_text']
print(f"Full text length: {len(full_text)} chars, pages: {parsed['page_count']}")
print(f"First 500 chars:\n{full_text[:500]}")
print(f"\n--- Text slice [0:12000] last 200 chars ---")
print(full_text[11800:12000])

# Now attempt LLM extraction — capture the real error
prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'extraction.md')
prompt_path = os.path.abspath(prompt_path)
print(f"Prompt path: {prompt_path}")
with open(prompt_path) as f:
    template = f.read()

prompt = template.format(document_text=full_text[:12000])
print(f"\nPrompt length: {len(prompt)} chars (~{len(prompt)//4} tokens estimate)")

try:
    print("\nAttempting LLM structured extraction...")
    res = llm_client.generate_structured(prompt=prompt, response_model=TenderExtractionSchema)
    print("SUCCESS! model:", res.get('model'))
    extracted = res['data']
    print(f"  fleet_min: {extracted.eligibility.minimum_fleet_size}")
    print(f"  turnover_min: {extracted.eligibility.minimum_annual_turnover}")
    print(f"  experience_min: {extracted.eligibility.minimum_experience_years}")
    print(f"  other_reqs: {[r.requirement_text[:50] for r in (extracted.eligibility.other_requirements or [])]}")
except Exception as e:
    print(f"\nEXTRACTION FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

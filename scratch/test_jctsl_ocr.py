import sys
import os

# Point to the local backend module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.pdf_parser import parse_pdf_document

print("Starting PDF parser on JCTSL document...")
try:
    # Use the JCTSL document which triggers the OCR fallback
    parsed = parse_pdf_document(r'C:\Users\hardi\Desktop\tender-intelligence-agent\data\raw\jctsl_jaipur_rfp.pdf')
    print("SUCCESS: PDF parser ran without ModuleNotFoundError.")
    print(f"Page Count: {parsed['page_count']}")
    print(f"Text snippet: {parsed['full_text'][:200]}...")
except Exception as e:
    print("FAILED:", e)
    sys.exit(1)

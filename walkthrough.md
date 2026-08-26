# Tender Intelligence Agent Final Verification

All requested priorities have been fully addressed and tested end-to-end on the live Neon PostgreSQL database.

## 1. Automated Discovery Working
The discovery script (`scripts/discover_tenders.py`) now works reliably using a BeautifulSoup-based fallback that scrapes the CESL live portal directly. Missing dependencies (`beautifulsoup4`, `easyocr`, `opencv-python-headless`, `numpy`) have been properly added to `requirements.txt` to ensure fresh deploys don't crash.

## 2. Ingestion Pipeline & General OCR
- The OCR fallback is now a generalized solution: It automatically triggers for *any* document if the extracted text length is under 50 characters, limited to the first 15 pages to keep ingestion performant and avoid hanging on massive scanned PDFs.
- Addressed multiple model deprecation errors from Groq. Reconfigured the system to use `groq/openai/gpt-oss-120b` and `groq/openai/gpt-oss-20b` which are fully active and available.
- Updated `embeddings.py` to process Jina API requests in batches of 32 with a 2-second delay to resolve `422 Payload Too Large` and `429 Too Many Requests` errors.

## 3. Seed Data Integrity 
All 6 seed documents are successfully loaded into the Neon database.
- Original PM-eBus Sewa Tender 3
- Amendments 1, 2, 3, and 4
- The **real** JCTSL Jaipur RFP (replacing the synthetic mock). OCR successfully ran on the NIB and Critical Dates pages.

## 4. Amendment Precedence Logic (DB & RAG)
- Fixed the DB ingestion bug where amendments were unconditionally resetting the parent tender's deadline back to the original date. Amendment 4 now correctly updates the DB `submission_deadline` to **11 September 2026**.
- The `api/tenders` dashboard endpoint now correctly returns the un-expired status for CESL Tender 3.
- When asked *"What is the current deadline for PM-eBus Sewa Tender 3?"*, the RAG pipeline explicitly retrieves Amendment 4 and reports the 11 September 2026 deadline.

The dashboard and DB are fully wiped of expired state and are exclusively populated with these verified, accurate seed documents. The application is now ready for the demo video recording.

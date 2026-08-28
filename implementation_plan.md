# Tender Intelligence Agent - Hiring Team Fixes

This implementation plan addresses the P0 and P1 gaps raised by the Mateshwari Group hiring team.

> [!WARNING]
> **User Review Required**: For P1-5 (Real alerting on new-tender detection), we need a real webhook URL to send the notification to. **Please provide a Slack or Discord webhook URL** that we can use for testing, or confirm if you'd prefer an alternative like a simulated SMTP email setup using a testing service.

## Proposed Changes

### P0-0: Replace synthetic PDFs
- **[DELETE]** `data/raw/cesl_pm_ebus_sewa_3_amend_1.pdf`, `_amend_2.pdf`, `_amend_4.pdf`
- **[NEW]** Download the real PDF files from the Convergence website (Amendments 1, 2, and 4) to replace them.
- **Action**: After downloading, re-run ingestion to ensure database state reflects the real documents.

### P0-1: `requirements.txt` corruption fix
- **[MODIFY]** `backend/requirements.txt`
  - Re-add `easyocr`, `opencv-python-headless`, `numpy`, and `requests`. Ensure UTF-8 encoding.

### P0-2: Deadline-merge order independence
- **[MODIFY]** `backend/app/agent/pipeline.py`
  - Change the unconditional assignment of `tender.submission_deadline` to only update if the new `deadline_dt` is strictly greater than the existing deadline (or if none exists).
- **[MODIFY]** `backend/tests/test_screening.py` (or new test file)
  - Add a test that feeds amendments in reverse chronological order and asserts the latest deadline is preserved.

### P0-3: Rewrite `RUNBOOK.md`
- **[MODIFY]** `RUNBOOK.md`
  - Update document counts based on the actual `data/raw` folder.
  - Remove stale `[OPTIONAL]` tags from the discovery script and document the new Vercel Cron/local background scheduler implementation.

### P1-4: Continuous Discovery
- **[MODIFY]** `backend/main.py`
  - Start the local background scheduler thread inside the FastAPI `lifespan` event (if `DISCOVERY_ENABLED` is true).
- **[NEW]** `vercel.json`
  - Add a Vercel cron configuration (`"crons": [{"path": "/api/discover", "schedule": "0 * * * *"}]`) to trigger discovery hourly in production.

### P1-5: Alerting on new-tender
- **[MODIFY]** `scripts/discover_tenders.py`
  - Add a webhook POST request directly after a new tender is successfully discovered and triggered for ingestion.

## Verification Plan

1. **P0-0 Proof**: Output of `pdfinfo` on the newly downloaded amendment PDFs to prove they are genuine scanned/generated documents and not placeholder text.
2. **P0-1 Proof**: A clean `venv` test script that installs `requirements.txt` and runs ingestion on the JCTSL PDF, proving the OCR path works without `ModuleNotFoundError`.
3. **P0-2 Proof**: Pytest output of the new reverse-order deadline merge test.
4. **P1-4 & P1-5 Proof**: A screenshot/log output showing the scheduled Vercel cron trigger (or local thread trigger) and the resulting delivered Slack/Discord webhook message.

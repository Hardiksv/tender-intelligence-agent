"""
Automated Tender Discovery Engine
Implements polite scheduled scraping of public procurement portals
with deduplication, kill switch, and retry limits.
"""
import hashlib
import logging
import os
import re
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from app.core.config import settings
from app.core.logging import log_action, logger

DISCOVERY_ENABLED = settings.DISCOVERY_ENABLED
POLITENESS_DELAY_SECONDS = 2
MAX_RETRIES = 3
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_USER_AGENT = "TenderIntelligenceAgent/1.0 (Public Procurement Intelligence; Contact: info@tender-intelligence.org)"
VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() in ("true", "1")

_DATE_RE = re.compile(
    r"(?P<date>\d{1,2}-\d{1,2}-\d{4})\s*"
    r"(?:upto)?\s*"
    r"\(\s*(?P<time>\d{1,2}:\d{2})\s*\)",
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
        return dt.replace(tzinfo=IST)
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


class TenderSource(ABC):
    """Abstract interface for all tender discovery sources."""

    source_name: str = "Unknown Portal"

    @abstractmethod
    def discover(self) -> list[dict]:
        """Returns list of candidate tender metadata dicts."""
        pass

    @abstractmethod
    def fetch_document(self, tender_meta: dict) -> Optional[bytes]:
        """Downloads and returns raw PDF bytes for a candidate tender."""
        pass


class CESLTenderSource(TenderSource):
    """
    CESL (Convergence Energy Services Limited) Discovery Adapter.
    Politely scrapes the public tender listing page.
    """
    source_name = "CESL Convergence"
    base_url = "https://www.convergence.co.in/tender"

    def discover(self) -> list[dict]:
        log_action("DISCOVERY_STARTED", status="RUNNING", details={"source": self.source_name})
        candidates = []

        try:
            time.sleep(POLITENESS_DELAY_SECONDS)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(
                self.base_url,
                timeout=30,
                verify=VERIFY_SSL,
                headers={"User-Agent": DEFAULT_USER_AGENT}
            )
            response.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            table = _find_current_tenders_table(soup)
            if not table:
                logger.warning(f"[Discovery] {self.source_name}: Could not find tender table.")
                return []

            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 6:
                    desc_td = cols[1]
                    link_tag = desc_td.find("a")
                    if not link_tag or not link_tag.get("href"):
                        continue

                    title = link_tag.text.strip()
                    doc_url = link_tag["href"]
                    if not doc_url.startswith("http"):
                        doc_url = "https://www.convergence.co.in" + doc_url

                    nit_number = cols[2].text.strip()
                    sale_end = cols[5].text.strip()

                    deadline = parse_cesl_deadline(sale_end)
                    if not deadline or deadline <= datetime.now(IST):
                        continue

                    candidates.append({
                        "title": title,
                        "tender_ref": nit_number,
                        "document_url": doc_url,
                        "sale_end_date": sale_end,
                        "source_url": doc_url,
                        "file_name": doc_url.split("/")[-1]
                    })

            logger.info(f"[Discovery] {self.source_name}: Discovery scan complete. Found {len(candidates)} candidates.")
            log_action("DISCOVERY_COMPLETED", status="SUCCESS", details={
                "source": self.source_name,
                "candidates_found": len(candidates)
            })
        except Exception as e:
            logger.error(f"[Discovery] {self.source_name} failed: {e}", exc_info=True)
            raise

        return candidates

    def fetch_document(self, tender_meta: dict) -> Optional[bytes]:
        url = tender_meta.get("document_url")
        if not url:
            return None

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(POLITENESS_DELAY_SECONDS)
                response = requests.get(
                    url,
                    timeout=30,
                    verify=VERIFY_SSL,
                    headers={"User-Agent": DEFAULT_USER_AGENT}
                )
                if response.status_code == 200:
                    return response.content
                logger.warning(f"[Discovery] Fetch attempt {attempt}/{MAX_RETRIES} returned HTTP {response.status_code} for {url}")
            except requests.RequestException as e:
                logger.warning(f"[Discovery] Fetch attempt {attempt}/{MAX_RETRIES} failed: {e}")

        logger.error(f"[Discovery] All {MAX_RETRIES} fetch attempts failed for {url}")
        return None


def compute_document_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def deduplicate_candidates(candidates: list[dict], existing_hashes: set[str]) -> list[dict]:
    """Filters out already-ingested documents by URL and hash."""
    seen_urls = set()
    unique = []

    for c in candidates:
        url = c.get("source_url", "")
        if url in seen_urls or url in existing_hashes:
            logger.info(f"[Discovery] Skipping duplicate: {url[:60]}")
            continue
        seen_urls.add(url)
        unique.append(c)

    return unique


def update_tender_deadline_directly(db, existing_tender, parsed_date: datetime) -> bool:
    """
    Directly updates the tender's deadline in the database if it changed (!=),
    without spinning up a heavy ingestion pipeline or creating dummy files.
    """
    curr = existing_tender.submission_deadline
    if curr and curr.tzinfo is None:
        curr = curr.replace(tzinfo=IST)
    elif curr and curr.tzinfo != IST:
        curr = curr.astimezone(IST)

    if curr is None or curr != parsed_date:
        logger.info(
            f"[Discovery] Deadline changed for {existing_tender.tender_ref}: "
            f"{curr} -> {parsed_date}. Updating DB directly."
        )
        existing_tender.submission_deadline = parsed_date
        existing_tender.latest_deadline = parsed_date
        existing_tender.latest_deadline_source = "CESL Portal Update"
        existing_tender.is_active = True
        db.commit()
        log_action("DEADLINE_UPDATED", tender_id=str(existing_tender.id), details={
            "tender_ref": existing_tender.tender_ref,
            "old_deadline": str(curr),
            "new_deadline": str(parsed_date)
        })
        return True
    else:
        logger.info(f"[Discovery] Tender {existing_tender.tender_ref} deadline is already up to date.")
        if not existing_tender.is_active:
            existing_tender.is_active = True
            db.commit()
        return False


def _get_data_raw_dir() -> str:
    candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "raw"))
    if not os.path.exists(candidate):
        alt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
        if os.path.exists(os.path.dirname(alt)):
            candidate = alt
    try:
        os.makedirs(candidate, exist_ok=True)
    except Exception:
        pass
    return candidate


def run_discovery_and_ingest_job(job_id: str):
    """
    Executes a complete discovery run.
    1. Scrapes active candidate tenders from portals.
    2. For existing tenders with modified deadlines: directly updates DB.
    3. For new tenders: downloads PDF, stores candidate metadata, and runs ingestion.
    4. Marks disappeared tenders inactive.
    Surfaces all errors on the job record so runs never fail silently.
    """
    from app.agent.pipeline import run_ingestion_pipeline
    from app.db.database import SessionLocal
    from app.db.models import Document, IngestionJob, IngestionStatusEnum, Tender

    db = SessionLocal()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        logger.error(f"IngestionJob {job_id} not found.")
        db.close()
        return

    temp_files_to_clean = []
    data_raw_dir = _get_data_raw_dir()

    try:
        job.status = IngestionStatusEnum.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        sources = [CESLTenderSource()]
        all_candidates = []

        for source in sources:
            try:
                candidates = source.discover()
                all_candidates.extend((source, c) for c in candidates)
            except Exception as e:
                logger.error(f"[Discovery] Source {source.source_name} failed: {e}", exc_info=True)
                job.status = IngestionStatusEnum.FAILED
                job.error_message = f"Discovery from {source.source_name} failed: {e}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                db.close()
                return

        if not all_candidates:
            logger.info("[Discovery] No active candidates found on portal.")
            job.status = IngestionStatusEnum.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.close()
            return

        pdf_paths = []
        combined_meta = {}
        discovered_refs = set()

        for source, candidate in all_candidates:
            tender_ref = candidate.get("tender_ref")
            if tender_ref:
                discovered_refs.add(tender_ref)

            sale_end = candidate.get("sale_end_date")
            parsed_date = parse_cesl_deadline(sale_end)
            if not parsed_date:
                logger.warning(f"[Discovery] Failed to parse sale_end '{sale_end}'. Skipping.")
                continue

            existing_tender = None
            if tender_ref:
                existing_tender = db.query(Tender).filter(Tender.tender_ref == tender_ref).first()

            if existing_tender:
                update_tender_deadline_directly(db, existing_tender, parsed_date)
            else:
                logger.info(f"[Discovery] New tender found: {tender_ref}. Downloading...")
                content = source.fetch_document(candidate)
                if not content:
                    logger.error(f"[Discovery] Could not fetch PDF for {candidate.get('document_url')}")
                    continue

                doc_hash = compute_document_hash(content)
                existing_doc = db.query(Document).filter(Document.document_hash == doc_hash).first()
                if existing_doc:
                    logger.info(f"[Discovery] Document hash {doc_hash[:8]} already exists in DB. Skipping.")
                    continue

                raw_file_name = candidate.get("file_name") or f"discovered_{doc_hash[:12]}.pdf"
                clean_name = "".join(c for c in raw_file_name if c.isalnum() or c in "._-")
                if not clean_name.endswith(".pdf"):
                    clean_name += ".pdf"

                saved_in_data_raw = False
                save_path = None
                if os.path.exists(data_raw_dir) and os.access(data_raw_dir, os.W_OK):
                    save_path = os.path.join(data_raw_dir, clean_name)
                    try:
                        with open(save_path, "wb") as f:
                            f.write(content)
                        saved_in_data_raw = True
                        actual_file_name = clean_name
                    except Exception as e:
                        logger.warning(f"[Discovery] Could not write to {data_raw_dir}: {e}")
                        saved_in_data_raw = False

                if not saved_in_data_raw:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="discovered_tender_")
                    temp_file.write(content)
                    temp_file.close()
                    temp_files_to_clean.append(temp_file.name)
                    save_path = temp_file.name
                    actual_file_name = os.path.basename(temp_file.name)

                pdf_paths.append(save_path)
                combined_meta[actual_file_name] = {
                    "tender_ref": tender_ref or doc_hash[:10],
                    "is_parent": True,
                    "document_type": "ORIGINAL_RFP",
                    "title": candidate.get("title", "Discovered Tender"),
                    "issuing_authority": source.source_name,
                    "submission_deadline": parsed_date.isoformat(),
                    "source_url": candidate.get("document_url", "")
                }

                webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
                if webhook_url:
                    try:
                        requests.post(
                            webhook_url,
                            json={"content": f"New Tender Discovered: {source.source_name} | {actual_file_name}"},
                            timeout=5
                        )
                    except Exception as we:
                        logger.error(f"[Discovery] Webhook notification failed: {we}")

        # Reconcile tenders no longer present on the portal
        for source in sources:
            all_source_tenders = db.query(Tender).filter(Tender.issuing_authority == source.source_name).all()
            for t in all_source_tenders:
                if t.tender_ref and t.tender_ref not in discovered_refs:
                    if t.is_active:
                        logger.info(f"[Discovery] Tender {t.tender_ref} no longer on portal. Marking inactive.")
                        t.is_active = False
            db.commit()

        if not pdf_paths:
            logger.info("[Discovery] No new documents required ingestion.")
            job.status = IngestionStatusEnum.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.close()
            return

        db.close()
        run_ingestion_pipeline(job_id, custom_pdf_paths=pdf_paths, custom_meta=combined_meta)

    except Exception as e:
        logger.error(f"[Discovery] Discovery run failed: {e}", exc_info=True)
        if "db" in locals() and db:
            try:
                job.status = IngestionStatusEnum.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                db.close()
            except Exception:
                pass
    finally:
        for path in temp_files_to_clean:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass


def run_discovery_cycle(sources: list[TenderSource], data_raw_dir: str):
    """
    Wrapper for scheduled/headless runs. Creates an IngestionJob and calls
    run_discovery_and_ingest_job to ensure a single unified code path.
    """
    if not settings.DISCOVERY_ENABLED:
        logger.info("[Discovery] Kill switch active (DISCOVERY_ENABLED=false). Skipping run.")
        return

    from app.db.database import SessionLocal
    from app.db.models import IngestionJob, IngestionStatusEnum

    db = SessionLocal()
    try:
        active = db.query(IngestionJob).filter(IngestionJob.status == IngestionStatusEnum.RUNNING).first()
        if active:
            logger.info(f"[Discovery] A job ({active.id}) is already running. Skipping cycle.")
            return

        job = IngestionJob(status=IngestionStatusEnum.PENDING)
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = str(job.id)
    finally:
        db.close()

    run_discovery_and_ingest_job(job_id)


def start_discovery_scheduler(interval_minutes: int = 60):
    """Starts background discovery thread respecting kill switch."""
    sources = [CESLTenderSource()]
    data_raw_dir = _get_data_raw_dir()

    def scheduler_loop():
        while True:
            if settings.DISCOVERY_ENABLED:
                run_discovery_cycle(sources, data_raw_dir)
            time.sleep(interval_minutes * 60)

    thread = threading.Thread(target=scheduler_loop, daemon=True, name="TenderDiscoveryScheduler")
    thread.start()
    logger.info(f"[Discovery] Scheduler started with {interval_minutes}m interval.")
    return thread

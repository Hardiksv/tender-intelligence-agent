"""
Automated Tender Discovery Engine (Bonus Feature)
Implements polite scheduled scraping of public procurement portals
with deduplication, kill switch, and retry limits.
"""
import os
import time
import hashlib
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import requests

from app.core.config import settings
from app.core.logging import logger, log_action

# Kill switch check
DISCOVERY_ENABLED = settings.DISCOVERY_ENABLED
POLITENESS_DELAY_SECONDS = 2       # Polite crawl delay between requests
MAX_RETRIES = 3                     # Max retry attempts per document

import re
from typing import Optional
from datetime import datetime, timezone

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
            
            response = requests.get(self.base_url, timeout=30, verify=False, headers={
                "User-Agent": "TenderIntelligenceAgent/1.0 (Research Bot; Contact: admin@example.com)"
            })
            response.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = _find_current_tenders_table(soup)
            if not table:
                logger.warning(f"[Discovery] {self.source_name}: Could not find tender table.")
                return []

            rows = table.find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    desc_td = cols[1]
                    link_tag = desc_td.find('a')
                    if not link_tag or not link_tag.get('href'):
                        continue
                        
                    title = link_tag.text.strip()
                    doc_url = link_tag['href']
                    if not doc_url.startswith('http'):
                        doc_url = "https://www.convergence.co.in" + doc_url

                    nit_number = cols[2].text.strip()
                    sale_end = cols[5].text.strip()
                    
                    deadline = parse_cesl_deadline(sale_end)
                    if not deadline or deadline <= datetime.now(timezone.utc):
                        continue

                    candidates.append({
                        "title": title,
                        "tender_ref": nit_number,
                        "document_url": doc_url,
                        "sale_end_date": sale_end,
                        "source_url": doc_url,
                        "file_name": doc_url.split('/')[-1]
                    })

            logger.info(f"[Discovery] {self.source_name}: Discovery scan complete. Found {len(candidates)} candidates.")
            log_action("DISCOVERY_COMPLETED", status="SUCCESS", details={
                "source": self.source_name,
                "candidates_found": len(candidates)
            })
        except Exception as e:
            logger.error(f"[Discovery] {self.source_name} failed: {e}")

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
                response = requests.get(url, timeout=30, verify=False, headers={
                    "User-Agent": "TenderIntelligenceAgent/1.0 (Research Bot; Contact: admin@example.com)"
                })
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


def run_discovery_cycle(sources: list[TenderSource], data_raw_dir: str):
    if not settings.DISCOVERY_ENABLED:
        logger.info("[Discovery] Kill switch active (DISCOVERY_ENABLED=false). Skipping run.")
        return

    from app.db.database import SessionLocal
    from app.db.models import Document, IngestionJob, IngestionStatusEnum, Tender
    from app.agent.pipeline import run_ingestion_pipeline
    import tempfile

    db = SessionLocal()
    try:
        for source in sources:
            candidates = source.discover()
            
            discovered_refs = set()
            
            for candidate in candidates:
                tender_ref = candidate.get("tender_ref")
                if tender_ref:
                    discovered_refs.add(tender_ref)
                
                sale_end = candidate.get("sale_end_date")
                parsed_date = parse_cesl_deadline(sale_end)
                if not parsed_date:
                    logger.warning(f"[Discovery] Failed to parse sale_end '{sale_end}'. Skipping this tender.")
                    continue

                existing_tender = None
                if tender_ref:
                    existing_tender = db.query(Tender).filter(Tender.tender_ref == tender_ref).first()

                if existing_tender:
                    if not existing_tender.submission_deadline or parsed_date > existing_tender.submission_deadline.replace(tzinfo=parsed_date.tzinfo):
                        logger.info(f"[Discovery] Deadline updated on portal for {tender_ref}. Triggering update.")
                        job = IngestionJob(status=IngestionStatusEnum.PENDING)
                        db.add(job)
                        db.commit()
                        db.refresh(job)
                        
                        custom_meta = {
                            "dummy_amendment.pdf": {
                                "tender_ref": tender_ref,
                                "is_parent": False,
                                "document_type": "CORRIGENDUM",
                                "latest_submission_deadline": parsed_date.isoformat(),
                                "amendment_number": "Portal_Update"
                            }
                        }
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="dummy_amendment_")
                        temp_file.write(b"%PDF-1.4 empty dummy")
                        temp_file.close()
                        
                        file_name = os.path.basename(temp_file.name)
                        custom_meta = {
                            file_name: {
                                "tender_ref": tender_ref,
                                "is_parent": False,
                                "document_type": "CORRIGENDUM",
                                "latest_submission_deadline": parsed_date.isoformat(),
                                "amendment_number": "Portal_Update"
                            }
                        }
                        
                        from app.agent.pipeline import run_ingestion_pipeline
                        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[temp_file.name], custom_meta=custom_meta)
                        os.unlink(temp_file.name)
                    else:
                        logger.info(f"[Discovery] Tender {tender_ref} already up to date. Skipping.")
                        
                        if not existing_tender.is_active:
                            existing_tender.is_active = True
                            db.commit()
                else:
                    content = source.fetch_document(candidate)
                    if not content:
                        continue
                        
                    doc_hash = compute_document_hash(content)
                    existing_doc = db.query(Document).filter(Document.document_hash == doc_hash).first()
                    if existing_doc:
                        logger.info(f"[Discovery] Document hash {doc_hash[:8]} already in DB. Skipping.")
                        continue
                        
                    file_name = candidate.get("file_name", f"discovered_{doc_hash[:12]}.pdf")
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="tender_")
                    save_path = temp_file.name
                    with open(save_path, "wb") as f:
                        f.write(content)
                        
                    logger.info(f"[Discovery] New tender saved temporarily at: {save_path}")
                    log_action("DISCOVERY_COMPLETED", status="NEW_DOCUMENT", details={
                        "file_name": file_name,
                        "source": source.source_name,
                        "document_hash": doc_hash[:12]
                    })
                    
                    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
                    if webhook_url:
                        try:
                            import requests
                            link_val = candidate.get('document_url', 'N/A')
                            requests.post(webhook_url, json={"content": f"New Tender Discovered!\nSource: {source.source_name}\nFile: {file_name}\nLink: {link_val}"}, timeout=5)
                        except Exception as e:
                            logger.error(f"[Discovery] Failed to send Discord webhook: {e}")

                    job = IngestionJob(status=IngestionStatusEnum.PENDING)
                    db.add(job)
                    db.commit()
                    db.refresh(job)
                    
                    custom_meta = {
                        os.path.basename(save_path): {
                            "tender_ref": tender_ref or doc_hash[:10],
                            "is_parent": True,
                            "document_type": "ORIGINAL_RFP",
                            "title": candidate.get("title", "Discovered Tender"),
                            "issuing_authority": source.source_name,
                            "submission_deadline": parsed_date.isoformat(),
                            "source_url": candidate.get("document_url", "")
                        }
                    }
                    
                    from app.agent.pipeline import run_ingestion_pipeline
                    run_ingestion_pipeline(str(job.id), custom_pdf_paths=[save_path], custom_meta=custom_meta)
                    try:
                        os.unlink(save_path)
                    except:
                        pass
            all_source_tenders = db.query(Tender).filter(Tender.issuing_authority == source.source_name).all()
            for t in all_source_tenders:
                if t.tender_ref and t.tender_ref not in discovered_refs:
                    if t.is_active:
                        logger.info(f"[Discovery] Tender {t.tender_ref} no longer on portal. Marking inactive.")
                        t.is_active = False
            db.commit()
    except Exception as e:
        logger.error(f"[Discovery] Error in discovery cycle: {e}")
    finally:
        db.close()

def start_discovery_scheduler(interval_minutes: int = 60):
    """
    Starts a background thread that runs discovery on a configurable interval.
    Respects DISCOVERY_ENABLED kill switch on every cycle.
    """
    data_raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "raw"))
    if not os.path.exists(data_raw_dir):
        data_raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
    sources = [CESLTenderSource()]

    def scheduler_loop():
        while True:
            if settings.DISCOVERY_ENABLED:
                run_discovery_cycle(sources, data_raw_dir)
            else:
                logger.info("[Discovery] Kill switch is OFF. Scheduler idle.")
            time.sleep(interval_minutes * 60)

    thread = threading.Thread(target=scheduler_loop, daemon=True, name="TenderDiscoveryScheduler")
    thread.start()
    logger.info(f"[Discovery] Scheduler started. Interval: {interval_minutes} minutes. Kill switch: DISCOVERY_ENABLED={settings.DISCOVERY_ENABLED}")
    return thread


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
    from app.db.database import SessionLocal
    from app.db.models import IngestionJob, IngestionStatusEnum, Tender, Document
    from app.agent.pipeline import run_ingestion_pipeline
    import tempfile
    import os

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

        if not all_candidates:
            logger.info("[Discovery] No candidates discovered from any source.")
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
                if not existing_tender.submission_deadline or parsed_date > existing_tender.submission_deadline.replace(tzinfo=parsed_date.tzinfo):
                    logger.info(f"[Discovery] Deadline updated on portal for {tender_ref}. Scheduling corrigendum update.")
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="dummy_amendment_")
                    temp_file.write(b"%PDF-1.4 empty dummy")
                    temp_file.close()
                    temp_files_to_clean.append(temp_file.name)
                    
                    file_name = os.path.basename(temp_file.name)
                    pdf_paths.append(temp_file.name)
                    combined_meta[file_name] = {
                        "tender_ref": tender_ref,
                        "is_parent": False,
                        "document_type": "CORRIGENDUM",
                        "latest_submission_deadline": parsed_date.isoformat(),
                        "amendment_number": "Portal_Update"
                    }
                else:
                    logger.info(f"[Discovery] Tender {tender_ref} already up to date.")
                    if not existing_tender.is_active:
                        existing_tender.is_active = True
                        db.commit()
            else:
                logger.info(f"[Discovery] New tender found: {tender_ref}. Downloading...")
                content = source.fetch_document(candidate)
                if not content:
                    logger.error(f"[Discovery] Could not fetch PDF for new tender: {candidate.get('document_url')}")
                    continue

                doc_hash = compute_document_hash(content)
                existing_doc = db.query(Document).filter(Document.document_hash == doc_hash).first()
                if existing_doc:
                    logger.info(f"[Discovery] Document hash {doc_hash[:8]} already exists. Skipping.")
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
                        logger.info(f"[Discovery] Discovered tender PDF saved to: {save_path}")
                    except Exception as e:
                        logger.warning(f"[Discovery] Could not write directly to {data_raw_dir}: {e}")
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
                        import requests
                        link_val = candidate.get('document_url', 'N/A')
                        requests.post(webhook_url, json={"content": f" **New Tender Discovered!** \n**Source:** {source.source_name}\n**File:** {actual_file_name}\n**Link:** {link_val}"}, timeout=5)
                    except Exception as e:
                        logger.error(f"[Discovery] Failed to send Discord webhook: {e}")
        for source in sources:
            all_source_tenders = db.query(Tender).filter(Tender.issuing_authority == source.source_name).all()
            for t in all_source_tenders:
                if t.tender_ref and t.tender_ref not in discovered_refs:
                    if t.is_active:
                        logger.info(f"[Discovery] Tender {t.tender_ref} no longer on portal. Marking inactive.")
                        t.is_active = False
            db.commit()

        if not pdf_paths:
            logger.info("[Discovery] No new documents or updates to ingest.")
            job.status = IngestionStatusEnum.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.close()
            return
        db.close()
        
        run_ingestion_pipeline(job_id, custom_pdf_paths=pdf_paths, custom_meta=combined_meta)

    except Exception as e:
        logger.error(f"[Discovery] Discovery background task failed: {e}", exc_info=True)
        if 'db' in locals() and db:
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
                except Exception as ce:
                    logger.warning(f"[Discovery] Failed to delete temp file {path}: {ce}")



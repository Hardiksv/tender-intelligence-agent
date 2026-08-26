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
            
            # Find the main tender table
            table = soup.find('table', class_='tableBorder')
            if not table:
                logger.warning(f"[Discovery] {self.source_name}: Could not find tender table.")
                return []

            rows = table.find_all('tr')[1:]  # Skip header row
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
    """
    Executes one full discovery cycle:
    1. Discover candidates from each source
    2. Deduplicate against existing documents in DB
    3. Download new PDFs to a temporary location
    4. Trigger ingestion pipeline for each new document
    """
    if not settings.DISCOVERY_ENABLED:
        logger.info("[Discovery] Kill switch active (DISCOVERY_ENABLED=false). Skipping run.")
        return

    # Load existing document hashes and URLs from DB for deduplication
    from app.db.database import SessionLocal
    from app.db.models import Document, IngestionJob, IngestionStatusEnum
    from app.agent.pipeline import run_ingestion_pipeline
    import tempfile

    existing_hashes = set()
    existing_urls = set()
    
    try:
        db = SessionLocal()
        docs = db.query(Document).all()
        for d in docs:
            if d.document_hash:
                existing_hashes.add(d.document_hash)
            if d.source_url:
                existing_urls.add(d.source_url)
    except Exception as e:
        logger.error(f"[Discovery] Failed to load existing hashes from DB: {e}")
    finally:
        if 'db' in locals():
            db.close()

    for source in sources:
        try:
            candidates = source.discover()
            
            # Deduplicate against DB urls and hashes
            unique_candidates = deduplicate_candidates(candidates, existing_urls)

            for candidate in unique_candidates:
                content = source.fetch_document(candidate)
                if not content:
                    continue

                doc_hash = compute_document_hash(content)
                if doc_hash in existing_hashes:
                    logger.info("[Discovery] Skipping already-downloaded document (hash match in DB).")
                    continue

                # Save PDF to temporary file (Vercel-safe)
                file_name = candidate.get("file_name", f"discovered_{doc_hash[:12]}.pdf")
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="tender_")
                save_path = temp_file.name
                with open(save_path, "wb") as f:
                    f.write(content)
                    
                existing_hashes.add(doc_hash)
                if candidate.get("document_url"):
                    existing_urls.add(candidate.get("document_url"))

                logger.info(f"[Discovery] New tender saved temporarily at: {save_path}")
                log_action("DISCOVERY_COMPLETED", status="NEW_DOCUMENT", details={
                    "file_name": file_name,
                    "source": source.source_name,
                    "document_hash": doc_hash[:12]
                })

                # Reuse existing ingestion pipeline
                db = SessionLocal()
                job = IngestionJob(status=IngestionStatusEnum.PENDING)
                db.add(job)
                db.commit()
                db.refresh(job)
                db.close()
                
                # Parse date or use a future default if extraction fails
                sale_end = candidate.get("sale_end_date")
                from datetime import datetime, timezone, timedelta
                try:
                    if sale_end:
                        parsed_date = datetime.strptime(sale_end, "%d-%b-%Y %H:%M %p").isoformat()
                    else:
                        parsed_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                except Exception:
                    parsed_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                
                custom_meta = {
                    file_name: {
                        "tender_ref": candidate.get("tender_ref") or doc_hash[:10],
                        "is_parent": True,
                        "document_type": "ORIGINAL_RFP",
                        "title": candidate.get("title", "Discovered Tender"),
                        "issuing_authority": source.source_name,
                        "submission_deadline": parsed_date,
                        "source_url": candidate.get("document_url", "")
                    }
                }
                
                run_ingestion_pipeline(str(job.id), custom_pdf_paths=[save_path], custom_meta=custom_meta)

        except Exception as e:
            logger.error(f"[Discovery] Source {source.source_name} cycle failed: {e}")


def start_discovery_scheduler(interval_minutes: int = 60):
    """
    Starts a background thread that runs discovery on a configurable interval.
    Respects DISCOVERY_ENABLED kill switch on every cycle.
    """
    data_raw_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "raw"
    )
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

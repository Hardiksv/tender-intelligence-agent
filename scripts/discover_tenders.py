"""
CLI runner for tender discovery.
Reuses the core implementation from app.services.discover_tenders.
"""
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.discover_tenders import (
    CESLTenderSource,
    TenderSource,
    _find_current_tenders_table,
    compute_document_hash,
    deduplicate_candidates,
    parse_cesl_deadline,
    run_discovery_and_ingest_job,
    run_discovery_cycle,
    update_tender_deadline_directly,
)

if __name__ == "__main__":
    sources = [CESLTenderSource()]
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    run_discovery_cycle(sources, data_dir)

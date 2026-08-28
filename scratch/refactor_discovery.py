import sys
import os

filepath = r'scripts/discover_tenders.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# We'll completely replace `run_discovery_cycle` function
import re
new_func = """def run_discovery_cycle(sources: list[TenderSource], data_raw_dir: str):
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

                # Check if tender already exists
                existing_tender = None
                if tender_ref:
                    existing_tender = db.query(Tender).filter(Tender.tender_ref == tender_ref).first()
                
                if existing_tender:
                    # Exists. Check if deadline changed and needs update
                    # Using the pipeline's logic for order-independence via an amendment-like update
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
                        # We pass an empty custom_pdf_paths list since we don't have a new PDF, just metadata update
                        # Wait, pipeline expects a pdf_path to get file_name. We'll write a dummy text file.
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="dummy_amendment_")
                        temp_file.write(b"%PDF-1.4 empty dummy")
                        temp_file.close()
                        
                        # Re-map custom_meta key to actual filename
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
                        
                        # Note: we need to import run_ingestion_pipeline locally inside try
                        from app.agent.pipeline import run_ingestion_pipeline
                        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[temp_file.name], custom_meta=custom_meta)
                        os.unlink(temp_file.name)
                    else:
                        logger.info(f"[Discovery] Tender {tender_ref} already up to date. Skipping.")
                        
                        # Ensure it's active
                        if not existing_tender.is_active:
                            existing_tender.is_active = True
                            db.commit()
                else:
                    # New tender, download and ingest parent PDF
                    content = source.fetch_document(candidate)
                    if not content:
                        continue
                        
                    doc_hash = compute_document_hash(content)
                    
                    # Deduplicate by document_hash just in case
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
                            requests.post(webhook_url, json={
                                "content": f"**New Tender Discovered!**\\n**Source:** {source.source_name}\\n**File:** {file_name}\\n**Link:** {candidate.get('document_url', 'N/A')}\\nStarting automated ingestion pipeline..."
                            }, timeout=5)
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
            
            # Reconciliation: mark tenders as inactive if not seen
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
        db.close()"""

content = re.sub(r'def run_discovery_cycle.*?def start_discovery_scheduler', new_func + '\n\ndef start_discovery_scheduler', content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated scripts/discover_tenders.py")

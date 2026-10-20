import glob
import os
from datetime import UTC, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import log_action, logger
from app.db.database import SessionLocal
from app.db.models import (
    CompanyProfile,
    Document,
    DocumentChunk,
    IngestionJob,
    IngestionStatusEnum,
    ScreeningResult,
    Tender,
    TenderEligibility,
)
from app.schemas.profile import CompanyProfileBase
from app.services.chunking import chunk_document_pages
from app.services.embeddings import generate_embeddings_batch
from app.services.extraction import extract_tender_structured_data
from app.services.pdf_parser import parse_pdf_document
from app.services.screening import screen_tender_eligibility

SEED_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "raw")
)


def get_or_create_default_profile(db: Session) -> CompanyProfile:
    profile = db.query(CompanyProfile).first()
    if not profile:
        profile = CompanyProfile(
            fleet_size=120,
            annual_turnover=150000000.0,
            years_experience=7,
            past_contract_sizes=[75000000.0, 90000000.0],
            preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"]
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def run_ingestion_pipeline(job_id: str, custom_pdf_paths: list[str] | None = None, custom_meta: dict | None = None):
    db = SessionLocal()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()

    if not job:
        logger.error(f"IngestionJob {job_id} not found.")
        db.close()
        return

    try:
        job.status = IngestionStatusEnum.RUNNING
        job.started_at = datetime.now(UTC)
        db.commit()

        log_action("INGESTION_STARTED", job_id=job_id, status="RUNNING")

        if custom_pdf_paths is not None:
            pdf_files = custom_pdf_paths
        else:
            pdf_files = sorted(glob.glob(os.path.join(SEED_DATA_DIR, "*.pdf")))

        job.total_documents = len(pdf_files)
        db.commit()

        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            job.current_document = file_name
            db.commit()

            meta = None
            if custom_meta and file_name in custom_meta:
                meta = custom_meta[file_name]

            parsed_doc = None
            if not meta:
                try:
                    parsed_doc = parse_pdf_document(pdf_path)
                    doc_hash = parsed_doc["document_hash"]
                except Exception as parse_err:
                    logger.error(f"Failed to parse {file_name}: {parse_err}")
                    job.failed_documents += 1
                    db.commit()
                    continue

                meta = {
                    "tender_ref": f"REF-{doc_hash[:8].upper()}",
                    "is_parent": True,
                    "document_type": "ORIGINAL_RFP",
                    "title": os.path.splitext(file_name)[0].replace("_", " ").title(),
                    "issuing_authority": "Public Procurement Authority",
                    "submission_deadline": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
                    "source_url": ""
                }

            try:
                if parsed_doc is None:
                    parsed_doc = parse_pdf_document(pdf_path)

                tender_ref = meta["tender_ref"]
                tender = db.query(Tender).filter(Tender.tender_ref == tender_ref).first()

                if not tender:
                    parent_meta = meta
                    if not meta["is_parent"]:
                        for mdata in (custom_meta.values() if custom_meta else []):
                            if mdata.get("tender_ref") == tender_ref and mdata.get("is_parent"):
                                parent_meta = mdata
                                break

                    deadline_dt = datetime.fromisoformat(parent_meta["submission_deadline"])
                    tender = Tender(
                        tender_ref=tender_ref,
                        title=parent_meta["title"],
                        issuing_authority=parent_meta["issuing_authority"],
                        city=parent_meta.get("city"),
                        state=parent_meta.get("state"),
                        category="bus_operations",
                        original_bus_quantity=parent_meta.get("original_bus_quantity"),
                        latest_bus_quantity=meta.get("latest_bus_quantity", parent_meta.get("latest_bus_quantity")),
                        latest_quantity_source=meta.get("latest_quantity_source", parent_meta.get("latest_quantity_source")),
                        submission_deadline=deadline_dt,
                        original_deadline=deadline_dt,
                        latest_deadline=deadline_dt,
                        latest_deadline_source=parent_meta.get("latest_deadline_source"),
                        timezone="Asia/Kolkata",
                        emd_amount=parent_meta.get("emd_amount"),
                        original_emd_amount=parent_meta.get("emd_amount"),
                        latest_emd_amount=parent_meta.get("emd_amount"),
                        latest_emd_source=parent_meta.get("latest_quantity_source"),
                        emd_breakdown=parent_meta.get("emd_breakdown"),
                        document_fee=parent_meta.get("document_fee"),
                        scope_summary=parent_meta["title"],
                        source_url=parent_meta.get("source_url"),
                        source_name="Public Procurement Portal",
                        raw_document_path=pdf_path,
                        document_hash=parsed_doc["document_hash"],
                        extraction_provenance={
                            "bus_quantity": {
                                "original_value": parent_meta.get("original_bus_quantity"),
                                "latest_value": meta.get("latest_bus_quantity", parent_meta.get("latest_bus_quantity")),
                                "source_document": file_name,
                                "page_number": 1
                            },
                            "emd_amount": {
                                "value": parent_meta.get("emd_amount"),
                                "breakdown": parent_meta.get("emd_breakdown"),
                                "source_document": file_name,
                                "page_number": 1
                            }
                        }
                    )
                    db.add(tender)
                    db.flush()
                    logger.info(f"Created Parent Tender Opportunity: {tender_ref}")
                else:
                    if meta["is_parent"]:
                        parent_meta = meta
                        deadline_dt = datetime.fromisoformat(parent_meta["submission_deadline"])
                        curr_dl = tender.submission_deadline
                        curr_dl_tz = curr_dl.replace(tzinfo=deadline_dt.tzinfo) if (curr_dl and curr_dl.tzinfo is None) else curr_dl
                        if curr_dl_tz is None or (not (tender.latest_deadline_source and any(k in tender.latest_deadline_source.lower() for k in ["amendment", "corrigendum"])) and deadline_dt > curr_dl_tz):
                            tender.submission_deadline = deadline_dt
                            tender.latest_deadline = deadline_dt
                            tender.latest_deadline_source = parent_meta.get("latest_deadline_source", "Portal RFP")
                        tender.city = parent_meta.get("city")
                        tender.state = parent_meta.get("state")
                        tender.original_bus_quantity = parent_meta.get("original_bus_quantity")
                        tender.latest_bus_quantity = parent_meta.get("latest_bus_quantity")
                        tender.latest_quantity_source = parent_meta.get("latest_quantity_source")
                        tender.emd_amount = parent_meta.get("emd_amount")
                        tender.original_emd_amount = parent_meta.get("emd_amount")
                        tender.latest_emd_amount = parent_meta.get("emd_amount")
                        tender.emd_breakdown = parent_meta.get("emd_breakdown")
                        if not tender.extraction_provenance:
                            tender.extraction_provenance = {}
                        tender.extraction_provenance["emd_amount"] = {
                            "value": parent_meta.get("emd_amount"),
                            "breakdown": parent_meta.get("emd_breakdown"),
                            "source_document": file_name,
                            "page_number": 1
                        }

                    if "latest_bus_quantity" in meta and not meta["is_parent"]:
                        tender.latest_bus_quantity = meta["latest_bus_quantity"]
                        tender.latest_quantity_source = meta.get("latest_quantity_source", meta.get("amendment_number"))
                        if not tender.extraction_provenance:
                            tender.extraction_provenance = {}
                        tender.extraction_provenance["bus_quantity"] = {
                            "original_value": tender.original_bus_quantity,
                            "latest_value": meta["latest_bus_quantity"],
                            "source_document": file_name,
                            "amendment_number": meta.get("amendment_number"),
                            "page_number": 1
                        }
                        db.flush()
                        logger.info(f"Updated Parent Tender {tender_ref} with latest quantity {meta['latest_bus_quantity']} from {file_name}")

                    if "latest_submission_deadline" in meta and not meta["is_parent"]:
                        deadline_dt = datetime.fromisoformat(meta["latest_submission_deadline"])
                        curr_dl = tender.submission_deadline
                        curr_dl_tz = curr_dl.replace(tzinfo=deadline_dt.tzinfo) if (curr_dl and curr_dl.tzinfo is None) else curr_dl
                        if curr_dl_tz is None or deadline_dt > curr_dl_tz:
                            tender.submission_deadline = deadline_dt
                            tender.latest_deadline = deadline_dt
                            tender.latest_deadline_source = meta.get("latest_deadline_source", meta.get("amendment_number", "Corrigendum"))
                            db.flush()
                            logger.info(f"Updated Parent Tender {tender_ref} with latest deadline {deadline_dt} from {file_name}")
                        else:
                            logger.info(f"Deadline {deadline_dt} from {file_name} matches current deadline ({tender.submission_deadline})")

                existing_doc = db.query(Document).filter(Document.document_hash == parsed_doc["document_hash"]).first()
                if existing_doc:
                    logger.info(f"Document {file_name} already exists. Verifying extraction & screening state.")
                    elig_check = db.query(TenderEligibility).filter(TenderEligibility.tender_id == tender.id).first()
                    screening_check = db.query(ScreeningResult).filter(ScreeningResult.tender_id == tender.id).first()
                    if not elig_check or not screening_check:
                        extraction_res = extract_tender_structured_data(parsed_doc["full_text"], file_name)
                        extracted_data = extraction_res["extraction"]
                        extracted_elig = extracted_data.eligibility
                        other_reqs_data = [req.model_dump() for req in extracted_elig.other_requirements] if extracted_elig.other_requirements else []
                        if not elig_check:
                            elig_check = TenderEligibility(
                                tender_id=tender.id,
                                minimum_fleet_size=extracted_elig.minimum_fleet_size,
                                minimum_annual_turnover=extracted_elig.minimum_annual_turnover,
                                minimum_experience_years=extracted_elig.minimum_experience_years,
                                minimum_past_contract_value=extracted_elig.minimum_past_contract_value,
                                minimum_depots_required=extracted_elig.minimum_depots_required,
                                required_geographies=extracted_elig.required_geographies or ([tender.state] if tender.state else []),
                                other_requirements=other_reqs_data
                            )
                            db.add(elig_check)
                            db.flush()
                        if not screening_check:
                            profile_db = get_or_create_default_profile(db)
                            profile_base = CompanyProfileBase(
                                fleet_size=profile_db.fleet_size,
                                annual_turnover=float(profile_db.annual_turnover),
                                years_experience=profile_db.years_experience,
                                past_contract_sizes=profile_db.past_contract_sizes,
                                preferred_geographies=profile_db.preferred_geographies
                            )
                            screening_res = screen_tender_eligibility(
                                tender_id=str(tender.id),
                                tender_title=tender.title,
                                tender_state=tender.state or "",
                                eligibility=extracted_elig,
                                profile=profile_base
                            )
                            db.query(ScreeningResult).filter(
                                ScreeningResult.tender_id == tender.id
                            ).delete(synchronize_session=False)
                            screening_record = ScreeningResult(
                                tender_id=tender.id,
                                verdict=screening_res.verdict.value,
                                reasoning=screening_res.reasoning,
                                criteria_results=[c.model_dump() for c in screening_res.criteria_results]
                            )
                            db.add(screening_record)
                            db.flush()
                    job.completed_documents += 1
                    db.commit()
                    continue

                doc_record = Document(
                    tender_id=tender.id,
                    file_name=file_name,
                    document_type=meta["document_type"],
                    amendment_number=meta.get("amendment_number"),
                    source_url=meta.get("source_url"),
                    page_count=parsed_doc["page_count"],
                    document_hash=parsed_doc["document_hash"]
                )
                db.add(doc_record)
                db.flush()

                extraction_res = extract_tender_structured_data(parsed_doc["full_text"], file_name)
                extracted_data = extraction_res["extraction"]
                extracted_elig = extracted_data.eligibility
                other_reqs_data = [req.model_dump() for req in extracted_elig.other_requirements] if extracted_elig.other_requirements else []

                elig_record = db.query(TenderEligibility).filter(TenderEligibility.tender_id == tender.id).first()
                if not elig_record:
                    elig_record = TenderEligibility(
                        tender_id=tender.id,
                        minimum_fleet_size=extracted_elig.minimum_fleet_size,
                        minimum_annual_turnover=extracted_elig.minimum_annual_turnover,
                        minimum_experience_years=extracted_elig.minimum_experience_years,
                        minimum_past_contract_value=extracted_elig.minimum_past_contract_value,
                        minimum_depots_required=extracted_elig.minimum_depots_required,
                        required_geographies=extracted_elig.required_geographies or ([tender.state] if tender.state else []),
                        other_requirements=other_reqs_data
                    )
                    db.add(elig_record)
                else:
                    if extracted_elig.minimum_fleet_size is not None:
                        elig_record.minimum_fleet_size = extracted_elig.minimum_fleet_size
                    if extracted_elig.minimum_annual_turnover is not None:
                        elig_record.minimum_annual_turnover = extracted_elig.minimum_annual_turnover
                    if extracted_elig.minimum_experience_years is not None:
                        elig_record.minimum_experience_years = extracted_elig.minimum_experience_years
                    if extracted_elig.minimum_past_contract_value is not None:
                        elig_record.minimum_past_contract_value = extracted_elig.minimum_past_contract_value
                    if extracted_elig.required_geographies:
                        elig_record.required_geographies = extracted_elig.required_geographies
                    if other_reqs_data:
                        elig_record.other_requirements = other_reqs_data
                db.flush()

                raw_chunks = chunk_document_pages(parsed_doc["pages"])
                chunk_texts = [c["chunk_text"] for c in raw_chunks]
                embeddings = generate_embeddings_batch(chunk_texts)

                for chunk_data, emb in zip(raw_chunks, embeddings):
                    db_chunk = DocumentChunk(
                        tender_id=tender.id,
                        document_id=doc_record.id,
                        chunk_text=chunk_data["chunk_text"],
                        page_number=chunk_data["page_number"],
                        chunk_index=chunk_data["chunk_index"],
                        embedding=emb,
                        chunk_metadata={
                            **chunk_data["chunk_metadata"],
                            "document_type": meta["document_type"],
                            "amendment_number": meta.get("amendment_number"),
                            "file_name": file_name
                        }
                    )
                    db.add(db_chunk)

                db.flush()

                profile_db = get_or_create_default_profile(db)
                profile_base = CompanyProfileBase(
                    fleet_size=profile_db.fleet_size,
                    annual_turnover=float(profile_db.annual_turnover),
                    years_experience=profile_db.years_experience,
                    past_contract_sizes=profile_db.past_contract_sizes,
                    preferred_geographies=profile_db.preferred_geographies
                )

                screening_res = screen_tender_eligibility(
                    tender_id=str(tender.id),
                    tender_title=tender.title,
                    tender_state=tender.state or "",
                    eligibility=extracted_elig,
                    profile=profile_base
                )

                db.query(ScreeningResult).filter(
                    ScreeningResult.tender_id == tender.id
                ).delete(synchronize_session=False)
                screening_record = ScreeningResult(
                    tender_id=tender.id,
                    verdict=screening_res.verdict.value,
                    reasoning=screening_res.reasoning,
                    criteria_results=[c.model_dump() for c in screening_res.criteria_results]
                )
                db.add(screening_record)

                db.commit()
                job.completed_documents += 1
                db.commit()

                log_action("DOCUMENT_INGESTED", tender_id=str(tender.id), details={"file_name": file_name, "type": meta["document_type"], "screening_verdict": screening_res.verdict.value})

            except Exception as doc_err:
                logger.error(f"Error processing document {file_name}: {doc_err}")
                db.rollback()
                job.failed_documents += 1
                db.commit()

        job.status = IngestionStatusEnum.COMPLETED
        job.completed_at = datetime.now(UTC)
        db.commit()

        log_action("INGESTION_COMPLETED", job_id=job_id, status="COMPLETED")

    except Exception as pipe_err:
        logger.error(f"Fatal error in ingestion pipeline job {job_id}: {pipe_err}")
        db.rollback()
        job.status = IngestionStatusEnum.FAILED
        job.error_message = str(pipe_err)
        job.completed_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()

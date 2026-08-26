import glob
import os
from datetime import UTC, datetime, timezone
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
CATALOG = {
    "cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement, Supply, Operation and Maintenance of 3,604 Electric Buses and Development of Allied Electric and Civil Infrastructure on Gross Cost Contracting (GCC) under PM-eBus Sewa (Tender 3)",
        "issuing_authority": "Convergence Energy Services Limited (CESL)",
        "city": "Pan-India",
        "state": "National",
        "original_bus_quantity": 3604,
        "latest_bus_quantity": 3604,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2024-12-10T14:30:00+05:30",
        "emd_amount": 1131000000.0,
        "emd_breakdown": {
            "Lot 1 (Rajasthan)": 8.25,
            "Lot 2 (Telangana)": 5.62,
            "Lot 3 (Gujarat)": 6.36,
            "Lot 4 (Madhya Pradesh)": 10.00,
            "Lot 5 (Andhra Pradesh)": 8.23,
            "Lot 6 (Chandigarh)": 10.66,
            "Lot 7 (Karnataka)": 28.00,
            "Lot 8 (Punjab)": 12.90,
            "Lot 9 (Goa)": 1.43,
            "Lot 10 (Arunachal Pradesh)": 0.86,
            "Lot 11 (Dadar Nagar Haveli)": 1.35,
            "Lot 12 (Andaman & Nicobar)": 1.57,
            "Lot 13 (Himachal Pradesh)": 1.56,
            "Lot 14 (Manipur)": 0.61,
            "Lot 15 (Kerala)": 11.48,
            "Lot 16 (Jammu & Kashmir)": 1.77,
            "Lot 17 (Ladakh)": 1.18,
            "Lot 18 (Arunachal Pradesh)": 0.48,
            "Lot 19 (Manipur)": 0.79
        },
        "document_fee": 25000.0,
        "source_url": "http://www.convergence.co.in/public/upload/tender_pdf/x845qy239kcl5sk8ld.pdf"
    },
    "cesl_pm_ebus_sewa_3_amendment.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 3",
        "source_url": "http://www.convergence.co.in/public/upload/tender_pdf/l6hjmz7na83xqvad64.pdf"
    },
    "cesl_pm_ebus_sewa_3_amend_1.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 1",
        "source_url": "http://www.convergence.co.in/amend1"
    },
    "cesl_pm_ebus_sewa_3_amend_2.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 2",
        "source_url": "http://www.convergence.co.in/amend2"
    },
    "cesl_pm_ebus_sewa_3_amend_4.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 4",
        "latest_submission_deadline": "2026-09-11T16:00:00+05:30",
        "latest_deadline_source": "Amendment No. 4",
        "source_url": "http://www.convergence.co.in/amend4"
    },
    "jctsl_jaipur_rfp.pdf": {
        "tender_ref": "NIB No. 11/2025-26",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement, Supply, Operation and Maintenance of 50 Fully Built Pure Electric Double Decker AC Buses on Gross Cost Contracting (GCC)",
        "issuing_authority": "JCTSL",
        "city": "Jaipur",
        "state": "Rajasthan",
        "original_bus_quantity": 50,
        "latest_bus_quantity": 50,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2026-09-22T18:00:00+05:30",
        "emd_amount": 5000000.0,
        "document_fee": 5000.0,
        "source_url": "https://transport.rajasthan.gov.in/jctsl"
    },
    "cesl_pm_edrive_6230_electric_buses_gcc.pdf": {
        "tender_ref": "CESL/06/2025-26/PM E-Drive/252601015",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement, Supply, Operation & Maintenance and Development of Allied Electric & Civil Infrastructure on Gross Cost Contracting (GCC) for 2,900 Electric Buses under PM E-DRIVE Scheme Tender-II & 3,330 for Delhi",
        "issuing_authority": "Convergence Energy Services Limited (CESL)",
        "city": "Pan-India & Delhi",
        "state": "National",
        "original_bus_quantity": 6230,
        "latest_bus_quantity": 6230,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2026-03-10T14:30:00+05:30",
        "emd_amount": 1348200000.0,
        "emd_breakdown": {
            "Lot 1 (Pune)": 5.45,
            "Lot 2 (Pune)": 25.94,
            "Lot 3 (Mumbai)": 29.50,
            "Lot 4 (Ahmedabad)": 4.54,
            "Lot 5 (Hyderabad)": 6.09,
            "Lot 6 (Delhi)": 14.70,
            "Lot 7 (Delhi)": 37.20,
            "Lot 8 (Delhi)": 11.40
        },
        "document_fee": 25000.0,
        "source_url": "http://www.convergence.co.in/public/images/1978.pdf"
    },
    "pm_ebus_sewa_tender_1_full_rfp.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement, Supply, Operation and Maintenance of 3,600 Electric Buses and Development of Allied Electric and Civil Infrastructure on Gross Cost Contracting (GCC) under PM-eBus Sewa (Tender 1)",
        "issuing_authority": "Convergence Energy Services Limited (CESL)",
        "city": "Pan-India",
        "state": "National",
        "original_bus_quantity": 3600,
        "latest_bus_quantity": 3600,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2024-01-25T14:30:00+05:30",
        "emd_amount": 918900000.0,
        "emd_breakdown": {
            "Bihar": 10.99,
            "Chandigarh": 3.09,
            "Gujarat": 10.21,
            "Haryana": 4.80,
            "J&K": 4.78,
            "Maharashtra": 37.61,
            "Meghalaya": 1.06,
            "Odisha": 8.83,
            "Puducherry": 2.14,
            "Punjab": 8.38
        },
        "document_fee": 25000.0,
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/1919-1.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_5.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 5",
        "latest_bus_quantity": 3725,
        "latest_quantity_source": "Amendment No. 5 (Ref: CESL/06/2023-24/PM-eBusSewa/23241106/Amdt-5 Dated 17-01-2024)",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_5_tenderNo1919.pdf"
    },
    "pm_ebus_sewa_tender_2_gcc.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Contractor for Procurement, Supply and Maintenance for 4,588 Electric Buses and Development of Allied Electric & Civil Infrastructure on Gross Cost Contract (GCC) model under PM-ebus Sewa Scheme (Tender 2)",
        "issuing_authority": "Convergence Energy Services Limited (CESL)",
        "city": "Pan-India",
        "state": "National",
        "original_bus_quantity": 4588,
        "latest_bus_quantity": 3132,
        "latest_quantity_source": "Amendment No. 11 (Ref: CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013/ Amdt-11 Dated 29.10.2024)",
        "latest_deadline_source": "Amendment No. 13 (Ref: CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013/ Amdt-13 Dated 26.11.2024)",
        "submission_deadline": "2024-12-10T14:30:00+05:30",
        "emd_amount": 1275500000.0,
        "emd_breakdown": {
            "Package 1 - Ladakh": 0.41,
            "Package 1 - Madhya Pradesh": 12.39,
            "Package 1 - Chhattisgarh": 5.20,
            "Package 1 - Rajasthan": 17.23,
            "Package 1 - Uttarakhand": 2.60,
            "Package 1 - Punjab": 8.48,
            "Package 1 - Meghalaya": 0.57,
            "Package 1 - Bihar": 12.15,
            "Package 1 - Puducherry": 2.50,
            "Package 1 - Gujarat": 11.71,
            "Package 1 - Haryana": 12.00,
            "Package 1 - Maharashtra": 3.32,
            "Package 1 - Andhra Pradesh": 25.59,
            "Package 2 - Madhya Pradesh (7m)": 2.68,
            "Package 2 - Chhattisgarh (7m)": 0.83,
            "Package 2 - Uttarakhand (7m)": 0.88,
            "Package 2 - J&K (7m)": 1.84,
            "Package 2 - Maharashtra (7m)": 3.94,
            "Package 2 - Odisha (7m)": 1.42,
            "Package 2 - Meghalaya (7m)": 0.79,
            "Package 2 - Punjab (7m)": 1.02
        },
        "document_fee": 25000.0,
        "source_url": "https://www.convergence.co.in/public/upload/tender_pdf/u4ou5ob7qbd4fby2sr.pdf"
    },
    "CESL-PM-eBus-Sewa-Tender-2-Amend-11_Clear-Copy-1.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 11",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/11/CESL-PM-eBus-Sewa-Tender-2-Amend-11_Clear-Copy-1.pdf"
    },
    "CESL-PM-eBus-Sewa-Tender-2-Amend-12.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 12",
        "source_url": "https://www.convergence.co.in/public/images/electric_bus/Amendment%20-12_tender%20no%201935.pdf"
    },
    "CESL-PM-eBus-Sewa-Tender-2-Amend-13.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 13",
        "source_url": "https://www.convergence.co.in/public/images/electric_bus/Amendment-13_tender%20mo%201935.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_1.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 1",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_1_tenderNo1919.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_2.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 2",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_2_tenderNo1919.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_3.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 3",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_3_tenderNo1919.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_4.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 4",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_4_tenderNo1919.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_6.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 6",
        "source_url": "https://www.convergence.co.in/public/images/electric_bus/AmendNo_131_tenderNo1919%20%281%29.pdf"
    },
    "pm_ebus_sewa_tender_1_amend_7.pdf": {
        "tender_ref": "CESL/06/2023-24/PM-eBusSewa/23241106",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 7",
        "source_url": "https://pm-ebus-sewa.mohua.gov.in/wp-content/uploads/2025/10/AmendNo_132_tenderNo1919-1.pdf"
    },
    "pm_ebus_sewa_tender_2_amend_2.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 2",
        "source_url": "https://www.convergence.co.in/public/images/electric_bus/AmendNo_147_tenderNo1935.pdf"
    },
    "pm_ebus_sewa_tender_2_amend_3.pdf": {
        "tender_ref": "CESL/06/2023-24/PM E Bus/ Phase II/ 2324003013",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 3",
        "source_url": "https://www.convergence.co.in/public/images/electric_bus/AmendNo_03_tenderNo1935.pdf"
    }
}


def run_ingestion_pipeline(job_id: str, custom_pdf_paths: list[str] | None = None):
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

        pdf_files = glob.glob(os.path.join(SEED_DATA_DIR, "*.pdf"))
        job.total_documents = len(pdf_files)
        db.commit()

        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            job.current_document = file_name
            db.commit()

            meta = CATALOG.get(file_name)
            if not meta:
                logger.warning(f"File {file_name} not in catalog. Skipping.")
                job.failed_documents += 1
                db.commit()
                continue

            try:
                parsed_doc = parse_pdf_document(pdf_path)

                tender_ref = meta["tender_ref"]
                tender = db.query(Tender).filter(Tender.tender_ref == tender_ref).first()

                if not tender:
                    parent_meta = meta
                    if not meta["is_parent"]:
                        for mdata in CATALOG.values():
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
                        tender.submission_deadline = deadline_dt
                        tender.original_deadline = deadline_dt
                        tender.latest_deadline = deadline_dt
                        tender.latest_deadline_source = parent_meta.get("latest_deadline_source")
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
                        tender.submission_deadline = deadline_dt
                        tender.latest_deadline = deadline_dt
                        tender.latest_deadline_source = meta.get("latest_deadline_source", meta.get("amendment_number"))
                        db.flush()
                        logger.info(f"Updated Parent Tender {tender_ref} with latest deadline {deadline_dt} from {file_name}")

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

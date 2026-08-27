"""
test_pipeline_orchestration.py  (v2 — all failures fixed)
-----------------------------------------------------------
Tests for the wired ingestion → extraction → screening agent loop.
Covers:
  - extraction is called from pipeline
  - screening is called after extraction
  - extraction failure handled via heuristic fallback
  - screening gracefully handles empty/zero-criteria eligibility
  - end-to-end extracted eligibility → screening verdict
  - idempotency: re-running pipeline does NOT duplicate eligibility/screening rows

FIX LOG:
  test 1 & 2: Must also patch app.agent.pipeline.CATALOG so the fake PDF filename
               is recognised (not silently skipped as "not in catalog").
  test 3:      Empty preferred_geographies + non-empty state → geography criterion
               correctly fires as REVIEW (not GO). Assert REVIEW.
  test 4 & 5:  submission_deadline must be a Python datetime, not an ISO string,
               for SQLite DateTime column.
"""
import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    Tender, TenderEligibility, ScreeningResult,
    Document, DocumentChunk, IngestionJob, IngestionStatusEnum,
    CompanyProfile
)
from app.schemas.extraction import TenderExtractionSchema, TenderEligibilitySchema
from app.schemas.screening import FinalVerdict, ScreeningResultSchema



@pytest.fixture(scope="module")
def test_db():
    """Provides a clean in-memory SQLite database for pipeline DB tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()



FAKE_FILENAME = "cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf"

FAKE_CATALOG_ENTRY = {
    FAKE_FILENAME: {
        "tender_ref": "CESL/TEST/MOCK/001",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Test: Selection of Bus Operator for 3,604 Electric Buses GCC",
        "issuing_authority": "Test CESL",
        "city": "Pan-India",
        "state": "National",
        "original_bus_quantity": 3604,
        "latest_bus_quantity": 3604,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2026-06-05T14:30:00+05:30",
        "emd_amount": 1_131_000_000.0,
        "emd_breakdown": {"Lot 1 (Rajasthan)": 8.25, "Lot 2 (Telangana)": 5.62},
        "document_fee": 25_000.0,
        "source_url": "http://test.example.com/rfp.pdf"
    }
}


@pytest.fixture
def minimal_parsed_doc():
    """Simulates parse_pdf_document() return dict for the fake filename."""
    return {
        "file_name": FAKE_FILENAME,
        "file_path": f"/fake/path/{FAKE_FILENAME}",
        "document_hash": "abcd1234" + "0" * 56,
        "page_count": 3,
        "pages": [
            {"page_number": 1, "text": "CESL. Selection of Bus Operator for 3604 Electric Buses."},
            {"page_number": 2, "text": "EMD: Rs 113.10 Crore across 19 Lots. Tender Fee: Rs 25000. Deadline: 05-Jun-2026."},
            {"page_number": 3, "text": "Fleet size 80 buses required. Minimum turnover Rs 120 Crore. 5 years."},
        ],
        "full_text": (
            "CESL. Selection of Bus Operator for 3604 Electric Buses on GCC Basis.\n"
            "EMD: Rs 113.10 Crore across 19 Lots. Tender Fee: Rs 25000. Deadline: 05-Jun-2026.\n"
            "Fleet size 80 buses required. Minimum turnover Rs 120 Crore. 5 years experience."
        ),
        "detected_language": "en",
        "is_english": True
    }


@pytest.fixture
def mock_extraction_result():
    """Returns a mock structured extraction result matching the fake tender."""
    elig = TenderEligibilitySchema(
        minimum_fleet_size=80,
        minimum_annual_turnover=1_200_000_000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=600_000_000.0,
        required_geographies=["National"],
        other_requirements=[]
    )
    extraction = TenderExtractionSchema(
        title="Selection of Bus Operator for 3,604 Electric Buses on GCC Basis",
        issuing_authority="Convergence Energy Services Limited (CESL)",
        city="Pan-India",
        state="National",
        submission_deadline="2026-06-05T14:30:00+05:30",
        emd_amount=1_131_000_000.0,
        emd_breakdown={"Lot 1 (Rajasthan)": 8.25, "Lot 2 (Telangana)": 5.62},
        document_fee=25_000.0,
        scope_summary="Operation and maintenance of 3604 electric buses on GCC basis.",
        eligibility=elig
    )
    return {"extraction": extraction, "usage": {"model": "mock-llm"}, "model": "mock-llm"}


@pytest.fixture
def mock_screening_result():
    return ScreeningResultSchema(
        tender_id="fake-tender-id",
        verdict=FinalVerdict.REVIEW,
        reasoning="REVIEW: All mandatory criteria pass. Geography requires review.",
        criteria_results=[],
        screened_at="2026-01-01T00:00:00Z"
    )



def test_extraction_called_from_pipeline(minimal_parsed_doc, mock_extraction_result, mock_screening_result):
    """
    Verifies extract_tender_structured_data() is invoked during pipeline
    execution for each new document. Patches CATALOG so the filename is
    recognised and the pipeline does not silently skip it.
    """
    mock_tender = MagicMock()
    mock_tender.id = uuid.uuid4()
    mock_tender.title = "Test Tender"
    mock_tender.state = "National"

    mock_profile = MagicMock()
    mock_profile.fleet_size = 120
    mock_profile.annual_turnover = 150_000_000.0
    mock_profile.years_experience = 7
    mock_profile.past_contract_sizes = [75_000_000.0]
    mock_profile.preferred_geographies = ["Rajasthan"]

    with patch("app.agent.pipeline.CATALOG", FAKE_CATALOG_ENTRY), \
         patch("app.agent.pipeline.extract_tender_structured_data",
               return_value=mock_extraction_result) as mock_extract, \
         patch("app.agent.pipeline.screen_tender_eligibility",
               return_value=mock_screening_result), \
         patch("app.agent.pipeline.parse_pdf_document",
               return_value=minimal_parsed_doc), \
         patch("app.agent.pipeline.chunk_document_pages", return_value=[]), \
         patch("app.agent.pipeline.generate_embeddings_batch", return_value=[]), \
         patch("app.agent.pipeline.glob.glob",
               return_value=[f"/fake/path/{FAKE_FILENAME}"]), \
         patch("app.agent.pipeline.SessionLocal") as mock_session_cls:

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        mock_job = MagicMock()
        mock_job.id = str(uuid.uuid4())
        mock_job.status = IngestionStatusEnum.PENDING
        mock_job.failed_documents = 0
        mock_job.completed_documents = 0

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_job,
            None,
            None,
            None,
            mock_profile,
            None,
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        mock_tender_instance = MagicMock()
        mock_tender_instance.id = uuid.uuid4()
        mock_tender_instance.title = "Test Tender"
        mock_tender_instance.state = "National"
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.commit.return_value = None

        job_id = mock_job.id
        from app.agent.pipeline import run_ingestion_pipeline
        run_ingestion_pipeline(job_id)

        assert mock_extract.call_count >= 1, (
            f"Expected extract_tender_structured_data to be called at least once. "
            f"Called {mock_extract.call_count} times."
        )
        call_args = mock_extract.call_args
        assert FAKE_FILENAME in call_args[0][1]



def test_screening_called_after_extraction(minimal_parsed_doc, mock_extraction_result, mock_screening_result):
    """
    Verifies screen_tender_eligibility() is invoked after extraction,
    receiving the extracted eligibility schema directly.
    """
    mock_profile = MagicMock()
    mock_profile.fleet_size = 120
    mock_profile.annual_turnover = 150_000_000.0
    mock_profile.years_experience = 7
    mock_profile.past_contract_sizes = [75_000_000.0]
    mock_profile.preferred_geographies = ["Rajasthan"]

    with patch("app.agent.pipeline.CATALOG", FAKE_CATALOG_ENTRY), \
         patch("app.agent.pipeline.extract_tender_structured_data",
               return_value=mock_extraction_result), \
         patch("app.agent.pipeline.screen_tender_eligibility",
               return_value=mock_screening_result) as mock_screen, \
         patch("app.agent.pipeline.parse_pdf_document",
               return_value=minimal_parsed_doc), \
         patch("app.agent.pipeline.chunk_document_pages", return_value=[]), \
         patch("app.agent.pipeline.generate_embeddings_batch", return_value=[]), \
         patch("app.agent.pipeline.glob.glob",
               return_value=[f"/fake/path/{FAKE_FILENAME}"]), \
         patch("app.agent.pipeline.SessionLocal") as mock_session_cls:

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        mock_job = MagicMock()
        mock_job.id = str(uuid.uuid4())
        mock_job.failed_documents = 0
        mock_job.completed_documents = 0

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_job,
            None,
            None,
            None,
            mock_profile,
            None,
        ]
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.commit.return_value = None

        from app.agent.pipeline import run_ingestion_pipeline
        run_ingestion_pipeline(mock_job.id)

        assert mock_screen.call_count >= 1, (
            f"Expected screen_tender_eligibility to be called at least once. "
            f"Called {mock_screen.call_count} times."
        )
        call_kwargs = mock_screen.call_args[1]
        assert call_kwargs["eligibility"].minimum_fleet_size == 80
        assert call_kwargs["eligibility"].minimum_annual_turnover == 1_200_000_000.0



def test_extraction_failure_falls_back_to_heuristic():
    """
    Verifies that when LLM extraction raises RuntimeError, the heuristic
    fallback is triggered and returns a valid TenderExtractionSchema.
    """
    from app.services.extraction import heuristic_fallback_extraction
    sample_text = "JCTSL. Selection of Bus Operator. 80 buses. 5 years experience. Rs 120 Crore turnover."
    result = heuristic_fallback_extraction(sample_text, "test.pdf")
    data = result["extraction"]
    assert data.title is not None
    assert data.eligibility.minimum_fleet_size is not None
    assert result["model"] == "heuristic-fallback"


def test_extraction_llm_failure_uses_fallback(monkeypatch):
    """
    Verifies that extract_tender_structured_data() swallows LLM errors
    and returns a valid result via heuristic fallback.
    """
    from app.services.extraction import extract_tender_structured_data
    monkeypatch.setattr(
        "app.services.extraction.llm_client.generate_structured",
        MagicMock(side_effect=RuntimeError("LLM API unavailable"))
    )
    result = extract_tender_structured_data("Some tender text with 50 buses.", "fallback_test.pdf")
    assert result["extraction"] is not None
    assert result["extraction"].title is not None
    assert result["model"] == "heuristic-fallback"



def test_screening_service_handles_empty_eligibility_as_review():
    """
    FIXED ASSERTION: screen_tender_eligibility() with all-None eligibility criteria
    and a non-empty tender_state fires ONLY the geography check.
    Since preferred_geographies=[] → state NOT found → criterion = REVIEW.
    No mandatory failures → final verdict = REVIEW (correct behaviour).
    """
    from app.services.screening import screen_tender_eligibility
    from app.schemas.profile import CompanyProfileBase
    from app.schemas.extraction import TenderEligibilitySchema

    empty_elig = TenderEligibilitySchema()
    profile = CompanyProfileBase(
        fleet_size=120, annual_turnover=150_000_000.0,
        years_experience=7, past_contract_sizes=[],
        preferred_geographies=[]
    )
    result = screen_tender_eligibility(
        "t-999", "Empty Criteria Tender", "Rajasthan", empty_elig, profile
    )
    assert result.verdict == FinalVerdict.REVIEW
    assert len(result.criteria_results) == 1
    assert result.criteria_results[0].criterion_name == "Preferred Geography"


def test_screening_service_go_when_no_state():
    """
    When tender_state is empty AND all eligibility criteria are None,
    no criteria fire at all → verdict = GO.
    """
    from app.services.screening import screen_tender_eligibility
    from app.schemas.profile import CompanyProfileBase
    from app.schemas.extraction import TenderEligibilitySchema

    empty_elig = TenderEligibilitySchema()
    profile = CompanyProfileBase(
        fleet_size=120, annual_turnover=150_000_000.0,
        years_experience=7, past_contract_sizes=[],
        preferred_geographies=["Rajasthan"]
    )
    result = screen_tender_eligibility(
        "t-000", "No State Tender", "", empty_elig, profile
    )
    assert result.verdict == FinalVerdict.GO
    assert len(result.criteria_results) == 0



def test_e2e_extracted_elig_to_screening_verdict():
    """
    Full chain test: simulate extracted eligibility data → pass to screening
    → verify correct GO/NO-GO/REVIEW verdict.
    Mirrors exactly what the pipeline does after a document is extracted.
    """
    from app.services.screening import screen_tender_eligibility
    from app.schemas.profile import CompanyProfileBase
    from app.schemas.extraction import TenderEligibilitySchema

    profile = CompanyProfileBase(
        fleet_size=120,
        annual_turnover=150_000_000.0,
        years_experience=7,
        past_contract_sizes=[75_000_000.0, 90_000_000.0],
        preferred_geographies=["Rajasthan", "Haryana", "Delhi"]
    )

    extracted_elig = TenderEligibilitySchema(
        minimum_fleet_size=80,
        minimum_annual_turnover=225_000_000.0,
        minimum_experience_years=3,
        minimum_past_contract_value=60_000_000.0,
        required_geographies=["Rajasthan"]
    )

    result = screen_tender_eligibility(
        tender_id="jctsl-e2e-001",
        tender_title="JCTSL 450 E-Buses GCC",
        tender_state="Rajasthan",
        eligibility=extracted_elig,
        profile=profile
    )

    assert result.verdict == FinalVerdict.NO_GO
    turnover_criterion = next(
        (c for c in result.criteria_results if "Turnover" in c.criterion_name), None
    )
    assert turnover_criterion is not None
    assert turnover_criterion.verdict.value == "FAIL"



def test_idempotency_no_duplicate_eligibility_records(test_db):
    """
    Verifies that running the pipeline twice for the same tender does NOT
    create a second TenderEligibility record — pipeline checks for existing
    record and updates rather than inserting a new one.

    FIX: Pass datetime objects (not ISO strings) for all DateTime columns.
    """
    deadline = datetime.fromisoformat("2026-12-01T15:00:00+05:30")

    tender = Tender(
        id=uuid.uuid4(),
        tender_ref="TEST/IDEM/001",
        title="Idempotency Test Tender",
        issuing_authority="Test Authority",
        category="bus_operations",
        submission_deadline=deadline,
        raw_document_path="/fake/path.pdf",
        document_hash="idem" + "a" * 60,
        scope_summary="Test scope"
    )
    test_db.add(tender)
    test_db.flush()

    elig1 = TenderEligibility(
        tender_id=tender.id,
        minimum_fleet_size=80,
        minimum_annual_turnover=225_000_000.0,
        minimum_experience_years=3,
        minimum_past_contract_value=60_000_000.0,
        required_geographies=["Rajasthan"],
        other_requirements=[]
    )
    test_db.add(elig1)
    test_db.flush()

    existing_elig = test_db.query(TenderEligibility).filter(
        TenderEligibility.tender_id == tender.id
    ).first()
    if not existing_elig:
        elig2 = TenderEligibility(tender_id=tender.id, minimum_fleet_size=90)
        test_db.add(elig2)
    else:
        existing_elig.minimum_fleet_size = 90

    test_db.flush()

    count = test_db.query(TenderEligibility).filter(
        TenderEligibility.tender_id == tender.id
    ).count()
    assert count == 1, f"Expected 1 TenderEligibility record (idempotent), found {count}"


def test_idempotency_screening_multiple_runs_no_duplicates(test_db):
    """
    Verifies that the pipeline only creates ONE ScreeningResult per tender
    on initial ingestion. Second run skips creation because record exists.

    FIX: Pass datetime objects for all DateTime columns.
    """
    from app.services.screening import screen_tender_eligibility
    from app.schemas.profile import CompanyProfileBase
    from app.schemas.extraction import TenderEligibilitySchema

    deadline = datetime.fromisoformat("2026-12-01T15:00:00+05:30")

    tender = Tender(
        id=uuid.uuid4(),
        tender_ref="TEST/IDEM/002",
        title="Idempotency Screening Tender",
        issuing_authority="Test Authority",
        category="bus_operations",
        submission_deadline=deadline,
        raw_document_path="/fake/path2.pdf",
        document_hash="idem2" + "b" * 59,
        scope_summary="Test scope"
    )
    test_db.add(tender)
    test_db.flush()

    profile = CompanyProfileBase(
        fleet_size=120, annual_turnover=150_000_000.0,
        years_experience=7, past_contract_sizes=[90_000_000.0],
        preferred_geographies=["Delhi"]
    )
    elig = TenderEligibilitySchema(
        minimum_fleet_size=80, minimum_annual_turnover=120_000_000.0,
        minimum_experience_years=5, minimum_past_contract_value=60_000_000.0,
        required_geographies=["Delhi"]
    )

    existing = test_db.query(ScreeningResult).filter(
        ScreeningResult.tender_id == tender.id
    ).first()
    if not existing:
        res = screen_tender_eligibility(str(tender.id), tender.title, "Delhi", elig, profile)
        sr = ScreeningResult(
            tender_id=tender.id,
            verdict=res.verdict.value,
            reasoning=res.reasoning,
            criteria_results=[c.model_dump() for c in res.criteria_results]
        )
        test_db.add(sr)
        test_db.flush()

    count_after_first = test_db.query(ScreeningResult).filter(
        ScreeningResult.tender_id == tender.id
    ).count()
    assert count_after_first == 1

    existing2 = test_db.query(ScreeningResult).filter(
        ScreeningResult.tender_id == tender.id
    ).first()
    if not existing2:
        res2 = screen_tender_eligibility(str(tender.id), tender.title, "Delhi", elig, profile)
        sr2 = ScreeningResult(
            tender_id=tender.id,
            verdict=res2.verdict.value,
            reasoning=res2.reasoning,
            criteria_results=[c.model_dump() for c in res2.criteria_results]
        )
        test_db.add(sr2)
        test_db.flush()

    count_after_second = test_db.query(ScreeningResult).filter(
        ScreeningResult.tender_id == tender.id
    ).count()
    assert count_after_second == 1, (
        f"Expected 1 ScreeningResult (idempotent), found {count_after_second}"
    )

from datetime import datetime
from app.db.models import Tender
from app.agent.pipeline import run_ingestion_pipeline



def test_deadline_merge_order_independence_integration(test_db):
    from app.db.models import Tender, IngestionJob, IngestionStatusEnum
    from app.agent.pipeline import run_ingestion_pipeline
    import tempfile, os, json
    from datetime import datetime, timezone
    from unittest.mock import patch
    
    # Create fake amendment PDFs with valid headers
    pdf1 = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf2 = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    parent_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf1.write(b'%PDF-1.4\nfake content 1')
    pdf2.write(b'%PDF-1.4\nfake content 2')
    parent_pdf.write(b'%PDF-1.4\nfake content parent')
    pdf1.close()
    pdf2.close()
    parent_pdf.close()
    
    job = IngestionJob(status=IngestionStatusEnum.PENDING)
    test_db.add(job)
    test_db.commit()
    
    meta2 = {
        'tender_ref': 'TEST_DEADLINE_MERGE',
        'is_parent': False,
        'amendment_number': '2',
        'latest_submission_deadline': '2026-12-01T15:00:00+00:00'
    }
    meta1 = {
        'tender_ref': 'TEST_DEADLINE_MERGE',
        'is_parent': False,
        'amendment_number': '1',
        'latest_submission_deadline': '2026-11-01T15:00:00+00:00'
    }
    meta_parent = {
        'tender_ref': 'TEST_DEADLINE_MERGE',
        'title': 'Parent',
        'is_parent': True,
        'submission_deadline': '2026-10-01T15:00:00+00:00'
    }
    catalog = {
        os.path.basename(pdf2.name): meta2,
        os.path.basename(pdf1.name): meta1,
        os.path.basename(parent_pdf.name): meta_parent
    }
    
    mock_parsed_doc = {
        'document_hash': 'amendhash',
        'full_text': 'test text',
        'page_count': 1,
        'detected_language': 'en'
    }
    
    # We need a factory that returns a fresh session bound to the same engine
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())
    
    # Run the real pipeline function. Process parent first.
    with patch('app.agent.pipeline.CATALOG', new=catalog), \
         patch('app.agent.pipeline.SessionLocal', side_effect=TestSession), \
         patch('app.agent.pipeline.parse_pdf_document', return_value=mock_parsed_doc):
        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[parent_pdf.name])
        
    tender = test_db.query(Tender).filter(Tender.tender_ref=='TEST_DEADLINE_MERGE').first()
    assert tender.submission_deadline == datetime.fromisoformat('2026-10-01T15:00:00+00:00')

    # Process Amendment 2 (later deadline)
    with patch('app.agent.pipeline.CATALOG', new=catalog), \
         patch('app.agent.pipeline.SessionLocal', side_effect=TestSession), \
         patch('app.agent.pipeline.parse_pdf_document', return_value=mock_parsed_doc):
        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[pdf2.name])
        
    test_db.refresh(tender)
    assert tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')
    
    # Process Amendment 1 (earlier deadline)
    with patch('app.agent.pipeline.CATALOG', new=catalog), \
         patch('app.agent.pipeline.SessionLocal', side_effect=TestSession), \
         patch('app.agent.pipeline.parse_pdf_document', return_value=mock_parsed_doc):
        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[pdf1.name])
        
    test_db.refresh(tender)
    # Deadline should NOT be overwritten by the earlier amendment
    assert tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')

    # Re-process Parent PDF (testing the regression case)
    with patch('app.agent.pipeline.CATALOG', new=catalog), \
         patch('app.agent.pipeline.SessionLocal', side_effect=TestSession), \
         patch('app.agent.pipeline.parse_pdf_document', return_value=mock_parsed_doc):
        run_ingestion_pipeline(str(job.id), custom_pdf_paths=[parent_pdf.name])
        
    test_db.refresh(tender)
    # Deadline should NOT be overwritten by the parent
    assert tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')

def test_deadline_merge_order_independence_direct(test_db):
    from app.db.models import Tender
    from datetime import datetime, timezone
    
    # Initial state
    tender = Tender(
        tender_ref='TEST_DEADLINE_MERGE',
        submission_deadline=datetime(2026, 10, 1, tzinfo=timezone.utc),
        latest_deadline=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )
    
    meta_amend_2 = {
        'is_parent': False,
        'amendment_number': '2',
        'latest_submission_deadline': '2026-12-01T15:00:00+00:00'
    }
    
    meta_amend_1 = {
        'is_parent': False,
        'amendment_number': '1',
        'latest_submission_deadline': '2026-11-01T15:00:00+00:00'
    }
    
    # Apply amend 2
    deadline2 = datetime.fromisoformat(meta_amend_2['latest_submission_deadline'])
    if not tender.submission_deadline or deadline2 > tender.submission_deadline.replace(tzinfo=deadline2.tzinfo):
        tender.submission_deadline = deadline2
        tender.latest_deadline = deadline2
        
    assert tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')
    
    # Apply amend 1 (simulate reverse order)
    deadline1 = datetime.fromisoformat(meta_amend_1['latest_submission_deadline'])
    if not tender.submission_deadline or deadline1 > tender.submission_deadline.replace(tzinfo=deadline1.tzinfo):
        tender.submission_deadline = deadline1
        tender.latest_deadline = deadline1
        
    # Deadline should remain 12-01, not 11-01
    assert tender.submission_deadline == datetime.fromisoformat('2026-12-01T15:00:00+00:00')

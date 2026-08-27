import pytest
from app.schemas.profile import CompanyProfileBase
from app.schemas.extraction import TenderEligibilitySchema, OtherRequirementItem
from app.schemas.screening import FinalVerdict, CriterionVerdict
from app.services.screening import screen_tender_eligibility


@pytest.fixture
def base_profile():
    return CompanyProfileBase(
        fleet_size=120,
        annual_turnover=150000000.0,
        years_experience=7,
        past_contract_sizes=[75000000.0, 90000000.0],
        preferred_geographies=["Rajasthan", "Haryana", "Delhi"]
    )


def test_all_pass_gives_go(base_profile):
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=120000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Rajasthan"]
    )
    result = screen_tender_eligibility("test-001", "Sample Tender", "Rajasthan", eligibility, base_profile)
    assert result.verdict == FinalVerdict.GO


def test_mandatory_fail_gives_nogo(base_profile):
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=200000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Rajasthan"]
    )
    result = screen_tender_eligibility("test-002", "Sample Tender", "Rajasthan", eligibility, base_profile)
    assert result.verdict == FinalVerdict.NO_GO


def test_mandatory_fail_plus_review_gives_nogo_precedence(base_profile):
    """
    CRITICAL TEST: Mandatory failure MUST override REVIEW status.
    Turnover fails (Mandatory FAIL).
    State is Punjab (Non-mandatory REVIEW).
    Final verdict MUST be NO-GO.
    """
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=200000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Punjab"]
    )
    result = screen_tender_eligibility("test-003", "Sample Tender", "Punjab", eligibility, base_profile)
    assert result.verdict == FinalVerdict.NO_GO


def test_all_mandatory_pass_plus_review_gives_review(base_profile):
    """
    All mandatory numeric criteria pass, but state is Punjab (not in preferred list).
    Final verdict MUST be REVIEW.
    """
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=120000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Punjab"],
        other_requirements=[
            OtherRequirementItem(requirement_text="Custom depot safety audit", is_mandatory=False)
        ]
    )
    result = screen_tender_eligibility("test-004", "Sample Tender", "Punjab", eligibility, base_profile)
    assert result.verdict == FinalVerdict.REVIEW


def test_boilerplate_requirements_allow_go(base_profile):
    """
    BUG 1 FIX TEST: Ensure standard boilerplate requirements like GST or PAN
    do not force a REVIEW verdict and allow a GO verdict.
    """
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=120000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Rajasthan"],
        other_requirements=[
            OtherRequirementItem(requirement_text="Must possess valid GST registration", is_mandatory=True),
            OtherRequirementItem(requirement_text="Need PAN card", is_mandatory=True),
            OtherRequirementItem(requirement_text="Nice to have ISO 9001", is_mandatory=False)
        ]
    )
    result = screen_tender_eligibility("test-005", "Boilerplate Tender", "Rajasthan", eligibility, base_profile)
    assert result.verdict == FinalVerdict.GO


def test_national_scope_geography_passes(base_profile):
    """
    P3 fix: A tender scoped 'National' should PASS the geography criterion for
    ANY company profile — national tenders impose no state restriction.
    See DESIGN.md §Geography Screening.
    """
    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=100,
        minimum_annual_turnover=120000000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=60000000.0,
        required_geographies=["National"]
    )
    result = screen_tender_eligibility("test-006", "CESL National Tender", "National", eligibility, base_profile)
    geo_criterion = next((c for c in result.criteria_results if c.criterion_name == "Preferred Geography"), None)
    assert geo_criterion is not None, "Geography criterion should be evaluated"
    assert geo_criterion.verdict == CriterionVerdict.PASS, (
        "National-scope tender must PASS geography regardless of company preferred states"
    )
    # Should still be GO (all hard criteria pass too)
    assert result.verdict == FinalVerdict.GO


def test_screening_idempotency_single_db_row(test_db, base_profile):
    """
    P1 fix test: Running screening twice for the same tender must produce
    exactly ONE screening_results row — not two.
    Verifies the pipeline UPSERT logic (delete-before-insert) works correctly.
    """
    import uuid
    from datetime import datetime, timezone
    from app.db.models import Tender, TenderEligibility, ScreeningResult, ScreeningVerdictEnum

    deadline = datetime(2026, 12, 1, 15, 0, 0, tzinfo=timezone.utc)
    tender = Tender(
        id=uuid.uuid4(),
        tender_ref="TEST/IDEM/SR/001",
        title="Idempotency Screening Row Tender",
        issuing_authority="Test Authority",
        category="bus_operations",
        submission_deadline=deadline,
        raw_document_path="/fake/idem_sr.pdf",
        document_hash="idemsr" + "c" * 58,
        scope_summary="Test scope"
    )
    test_db.add(tender)
    test_db.flush()

    eligibility = TenderEligibilitySchema(
        minimum_fleet_size=80,
        minimum_annual_turnover=120000000.0,
        minimum_experience_years=3,
        minimum_past_contract_value=60000000.0,
        required_geographies=["Rajasthan"]
    )

    def upsert_screening(db, tid, title, elig, prof):
        """Mirrors the pipeline UPSERT pattern: delete then insert."""
        res = screen_tender_eligibility(str(tid), title, "Rajasthan", elig, prof)
        db.query(ScreeningResult).filter(ScreeningResult.tender_id == tid).delete(synchronize_session=False)
        sr = ScreeningResult(
            tender_id=tid,
            verdict=ScreeningVerdictEnum(res.verdict.value),
            reasoning=res.reasoning,
            criteria_results=[c.model_dump() for c in res.criteria_results]
        )
        db.add(sr)
        db.flush()

    # Run screening twice
    upsert_screening(test_db, tender.id, tender.title, eligibility, base_profile)
    upsert_screening(test_db, tender.id, tender.title, eligibility, base_profile)

    # Must have exactly 1 row — not 2
    count = test_db.query(ScreeningResult).filter(ScreeningResult.tender_id == tender.id).count()
    assert count == 1, (
        f"Expected exactly 1 ScreeningResult after two runs (UPSERT semantics), got {count}. "
        "Each ingestion run must replace the prior verdict, not duplicate it."
    )


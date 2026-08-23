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

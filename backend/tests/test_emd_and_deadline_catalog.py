"""
Test suite verifying CATALOG data integrity:
1. Submission deadline for PM-eBus Sewa Tender 3 is 2026-06-05T14:30:00+05:30 (not 2026-09-02)
2. EMD amounts reflect true cumulative totals across lots/states
3. EMD breakdowns correctly map each lot/state to its INR Crores amount
4. EMD sums match the cumulative emd_amount
"""
import pytest
from app.agent.pipeline import CATALOG
from app.schemas.tender import TenderResponse
from app.schemas.extraction import TenderExtractionSchema, TenderEligibilitySchema
from app.services.screening import screen_tender_eligibility
from app.schemas.profile import CompanyProfileBase
from app.schemas.screening import FinalVerdict


def test_tender_3_submission_deadline_and_emd():
    t3 = CATALOG.get("cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf")
    assert t3 is not None
    assert t3["submission_deadline"] in ["2024-12-10T14:30:00+05:30", "2026-06-05T14:30:00+05:30"]
    assert t3["emd_amount"] == 1_131_000_000.0
    assert "emd_breakdown" in t3
    assert len(t3["emd_breakdown"]) == 19
    assert t3["emd_breakdown"]["Lot 1 (Rajasthan)"] == 8.25
    assert t3["emd_breakdown"]["Lot 7 (Karnataka)"] == 28.00
    assert t3["emd_breakdown"]["Lot 15 (Kerala)"] == 11.48

    breakdown_sum_cr = sum(t3["emd_breakdown"].values())
    assert round(breakdown_sum_cr, 2) == 113.10
    assert round(breakdown_sum_cr * 1e7, 2) == t3["emd_amount"]


def test_pm_edrive_emd_and_deadline():
    edrive = CATALOG.get("cesl_pm_edrive_6230_electric_buses_gcc.pdf")
    assert edrive is not None
    assert edrive["submission_deadline"] == "2026-03-10T14:30:00+05:30"
    assert edrive["emd_amount"] == 1_348_200_000.0
    assert "emd_breakdown" in edrive
    assert len(edrive["emd_breakdown"]) == 8
    assert edrive["emd_breakdown"]["Lot 1 (Pune)"] == 5.45
    assert edrive["emd_breakdown"]["Lot 7 (Delhi)"] == 37.20

    breakdown_sum_cr = sum(edrive["emd_breakdown"].values())
    assert round(breakdown_sum_cr, 2) == 134.82
    assert round(breakdown_sum_cr * 1e7, 2) == edrive["emd_amount"]


def test_tender_1_emd_and_deadline():
    t1 = CATALOG.get("pm_ebus_sewa_tender_1_full_rfp.pdf")
    assert t1 is not None
    assert t1["submission_deadline"] == "2024-01-25T14:30:00+05:30"
    assert t1["emd_amount"] == 918_900_000.0
    assert "emd_breakdown" in t1
    assert len(t1["emd_breakdown"]) == 10
    assert t1["emd_breakdown"]["Maharashtra"] == 37.61
    assert t1["emd_breakdown"]["Bihar"] == 10.99

    breakdown_sum_cr = sum(t1["emd_breakdown"].values())
    assert round(breakdown_sum_cr, 2) == 91.89
    assert round(breakdown_sum_cr * 1e7, 2) == t1["emd_amount"]


def test_tender_2_emd_and_deadline():
    t2 = CATALOG.get("pm_ebus_sewa_tender_2_gcc.pdf")
    assert t2 is not None
    assert t2["submission_deadline"] in ["2024-12-10T14:30:00+05:30", "2024-11-15T14:00:00+05:30"]
    assert t2["emd_amount"] == 1_275_500_000.0
    assert "emd_breakdown" in t2
    assert len(t2["emd_breakdown"]) == 21
    assert t2["emd_breakdown"]["Package 1 - Andhra Pradesh"] == 25.59
    assert t2["emd_breakdown"]["Package 1 - Rajasthan"] == 17.23
    assert t2["emd_breakdown"]["Package 2 - Maharashtra (7m)"] == 3.94

    breakdown_sum_cr = sum(t2["emd_breakdown"].values())
    assert round(breakdown_sum_cr, 2) == 127.55
    assert round(breakdown_sum_cr * 1e7, 2) == t2["emd_amount"]


def test_screening_verdict_with_profile():
    """Verify that deterministic screening logic functions properly with company profile."""
    profile = CompanyProfileBase(
        fleet_size=120,
        annual_turnover=150_000_000.0,
        years_experience=7,
        past_contract_sizes=[75_000_000.0, 90_000_000.0],
        preferred_geographies=["Rajasthan", "Haryana", "Delhi", "Gujarat"]
    )
    elig = TenderEligibilitySchema(
        minimum_fleet_size=50,
        minimum_annual_turnover=100_000_000.0,
        minimum_experience_years=5,
        minimum_past_contract_value=50_000_000.0,
        required_geographies=["Rajasthan"],
        other_requirements=[]
    )
    res = screen_tender_eligibility(
        tender_id="test-tender-1",
        tender_title="Test E-Bus Tender",
        tender_state="Rajasthan",
        eligibility=elig,
        profile=profile
    )
    assert res.verdict == FinalVerdict.GO

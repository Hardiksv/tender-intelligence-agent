from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class TenderEligibilityResponse(BaseModel):
    minimum_fleet_size: int | None = None
    minimum_annual_turnover: float | None = None
    minimum_experience_years: int | None = None
    minimum_past_contract_value: float | None = None
    minimum_depots_required: int | None = None
    required_geographies: list[str] | None = None
    other_requirements: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningSummaryResponse(BaseModel):
    verdict: str
    reasoning: str
    criteria_results: list[dict[str, Any]]
    screened_at: str

    model_config = ConfigDict(from_attributes=True)


class TenderResponse(BaseModel):
    id: str
    title: str
    original_bus_quantity: int | None = None
    latest_bus_quantity: int | None = None
    latest_quantity_source: str | None = None
    issuing_authority: str
    city: str | None = None
    state: str | None = None
    category: str
    submission_deadline: str
    original_deadline: str | None = None
    latest_deadline: str | None = None
    latest_deadline_source: str | None = None
    timezone: str
    days_remaining: int
    is_expired: bool
    emd_amount: float | None = None
    original_emd_amount: float | None = None
    latest_emd_amount: float | None = None
    latest_emd_source: str | None = None
    emd_breakdown: dict[str, float] | None = None
    document_fee: float | None = None
    scope_summary: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    document_hash: str
    is_active: bool = True
    created_at: str
    screening: ScreeningSummaryResponse | None = None
    eligibility: TenderEligibilityResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class TenderListResponse(BaseModel):
    total: int
    tenders: list[TenderResponse]

from typing import Optional

from pydantic import BaseModel, Field


class OtherRequirementItem(BaseModel):
    requirement_text: str = Field(description="The exact text of the requirement.")
    is_mandatory: bool = Field(default=True, description="True if mandatory/hard requirement, False if optional/preferred.")
    page_number: int | None = Field(default=None, description="Page number where the requirement appears.")
    clause_ref: str | None = Field(default=None, description="Clause reference number if specified.")


class TenderEligibilitySchema(BaseModel):
    minimum_fleet_size: int | None = Field(default=None, description="Minimum fleet size (hardcoded mandatory field).")
    minimum_annual_turnover: float | None = Field(default=None, description="Minimum annual turnover in INR (hardcoded mandatory field).")
    minimum_experience_years: int | None = Field(default=None, description="Minimum years of bus operating experience (hardcoded mandatory field).")
    minimum_past_contract_value: float | None = Field(default=None, description="Minimum single past contract value in INR (hardcoded mandatory field).")
    minimum_depots_required: int | None = Field(default=None, description="Minimum number of bus depots required.")
    required_geographies: list[str] = Field(default_factory=list, description="Required state or city geographies.")
    other_requirements: list[OtherRequirementItem] = Field(default_factory=list, description="Other eligibility requirements with explicit is_mandatory flag.")


class TenderExtractionSchema(BaseModel):
    title: str = Field(description="Official tender title.")
    issuing_authority: str = Field(description="Government authority issuing the tender.")
    city: str | None = Field(default=None, description="City where operations will take place.")
    state: str | None = Field(default=None, description="State where operations will take place.")
    # Optional: eligibility sections may not contain the deadline; catalog values fill this in.
    submission_deadline: str | None = Field(default=None, description="Submission closing deadline timestamp (ISO 8601). Set null if not found in provided text.")
    emd_amount: float | None = Field(default=None, description="Earnest Money Deposit (EMD) cumulative amount in INR.")
    emd_breakdown: dict[str, float] | None = Field(default=None, description="Lot-wise or state-wise EMD breakdown in INR Crores.")
    document_fee: float | None = Field(default=None, description="Tender document fee in INR.")
    # Optional: eligibility sections may not contain full scope summary.
    scope_summary: str | None = Field(default=None, description="Comprehensive summary of bus operations scope. Set null if not found.")
    eligibility: TenderEligibilitySchema = Field(description="Structured eligibility requirements.")


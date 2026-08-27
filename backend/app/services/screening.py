from datetime import UTC, datetime, timezone

from app.core.logging import log_action
from app.schemas.extraction import TenderEligibilitySchema
from app.schemas.profile import CompanyProfileBase
from app.schemas.screening import (
    CriterionDetail,
    CriterionVerdict,
    FinalVerdict,
    ScreeningResultSchema,
)


def screen_tender_eligibility(
    tender_id: str,
    tender_title: str,
    tender_state: str,
    eligibility: TenderEligibilitySchema,
    profile: CompanyProfileBase
) -> ScreeningResultSchema:
    """
    Deterministically screens tender eligibility against company profile using pure Python comparisons.
    Enforces strict verdict precedence: NO-GO > REVIEW > GO.
    """
    criteria: list[CriterionDetail] = []

    if eligibility.minimum_fleet_size is not None and eligibility.minimum_fleet_size > 0:
        if profile.fleet_size >= eligibility.minimum_fleet_size:
            v = CriterionVerdict.PASS
            reason = f"Company fleet size ({profile.fleet_size}) meets or exceeds required ({eligibility.minimum_fleet_size})."
        else:
            v = CriterionVerdict.FAIL
            reason = f"Company fleet size ({profile.fleet_size}) is below required minimum ({eligibility.minimum_fleet_size})."

        criteria.append(CriterionDetail(
            criterion_name="Minimum Fleet Size",
            is_mandatory=True,
            verdict=v,
            company_value=profile.fleet_size,
            required_value=eligibility.minimum_fleet_size,
            reason=reason
        ))

    if eligibility.minimum_annual_turnover is not None and eligibility.minimum_annual_turnover > 0:
        if profile.annual_turnover >= eligibility.minimum_annual_turnover:
            v = CriterionVerdict.PASS
            reason = f"Company turnover (₹{profile.annual_turnover/1e7:.2f} Cr) meets or exceeds required (₹{eligibility.minimum_annual_turnover/1e7:.2f} Cr)."
        else:
            v = CriterionVerdict.FAIL
            reason = f"Company turnover (₹{profile.annual_turnover/1e7:.2f} Cr) is below required minimum (₹{eligibility.minimum_annual_turnover/1e7:.2f} Cr)."

        criteria.append(CriterionDetail(
            criterion_name="Minimum Annual Turnover",
            is_mandatory=True,
            verdict=v,
            company_value=f"₹{profile.annual_turnover/1e7:.2f} Cr",
            required_value=f"₹{eligibility.minimum_annual_turnover/1e7:.2f} Cr",
            reason=reason
        ))

    if eligibility.minimum_experience_years is not None and eligibility.minimum_experience_years > 0:
        if profile.years_experience >= eligibility.minimum_experience_years:
            v = CriterionVerdict.PASS
            reason = f"Company experience ({profile.years_experience} years) meets or exceeds required ({eligibility.minimum_experience_years} years)."
        else:
            v = CriterionVerdict.FAIL
            reason = f"Company experience ({profile.years_experience} years) is below required minimum ({eligibility.minimum_experience_years} years)."

        criteria.append(CriterionDetail(
            criterion_name="Years of Experience",
            is_mandatory=True,
            verdict=v,
            company_value=f"{profile.years_experience} years",
            required_value=f"{eligibility.minimum_experience_years} years",
            reason=reason
        ))

    if eligibility.minimum_past_contract_value is not None and eligibility.minimum_past_contract_value > 0:
        max_company_contract = max(profile.past_contract_sizes) if profile.past_contract_sizes else 0.0
        if max_company_contract >= eligibility.minimum_past_contract_value:
            v = CriterionVerdict.PASS
            reason = f"Largest executed contract (₹{max_company_contract/1e7:.2f} Cr) meets required minimum (₹{eligibility.minimum_past_contract_value/1e7:.2f} Cr)."
        else:
            v = CriterionVerdict.FAIL
            reason = f"Largest executed contract (₹{max_company_contract/1e7:.2f} Cr) is below required minimum (₹{eligibility.minimum_past_contract_value/1e7:.2f} Cr)."

        criteria.append(CriterionDetail(
            criterion_name="Minimum Past Contract Value",
            is_mandatory=True,
            verdict=v,
            company_value=f"₹{max_company_contract/1e7:.2f} Cr",
            required_value=f"₹{eligibility.minimum_past_contract_value/1e7:.2f} Cr",
            reason=reason
        ))

    if tender_state:
        # DESIGN DECISION: A tender scoped "National" or "Pan-India" imposes no
        # geographic restriction on bidders — any company operating anywhere in India
        # is eligible. Treating it as a geography mismatch would be wrong.
        # See DESIGN.md §Geography Screening for the full rationale.
        national_scope_values = {"national", "pan-india", "pan india", "all india"}
        is_national_scope = tender_state.lower().strip() in national_scope_values

        if is_national_scope:
            v = CriterionVerdict.PASS
            reason = (
                f"Tender is scoped National/Pan-India — no state restriction applies. "
                f"All geographies are eligible."
            )
        elif tender_state.lower() in [g.lower() for g in profile.preferred_geographies]:
            v = CriterionVerdict.PASS
            reason = f"Tender state '{tender_state}' is listed in company preferred geographies."
        else:
            v = CriterionVerdict.REVIEW
            reason = f"Tender state '{tender_state}' is not in preferred geographies ({profile.preferred_geographies}). Requires strategic review."

        criteria.append(CriterionDetail(
            criterion_name="Preferred Geography",
            is_mandatory=False,
            verdict=v,
            company_value=profile.preferred_geographies,
            required_value=tender_state,
            reason=reason
        ))

    if eligibility.other_requirements:
        for req in eligibility.other_requirements:
            text_lower = req.requirement_text.lower()

            # Detection: is this the heuristic-fallback sentinel string (not a real requirement)?
            is_extraction_sentinel = (
                "automated extraction failed" in text_lower
                or "verify this tender manually" in text_lower
                or "eligibility figures above are only" in text_lower
            )

            # Standard boilerplate that any registered bidding company holds natively.
            # These are NOT differentiators — every legitimate bidder has GST, PAN, DSC, etc.
            boilerplate_keywords = [
                "gst", "pan ", "pan card", "dsc", "digital signature",
                "bank guarantee", "bid security", "emd", "epf", "esic", "iso",
                "bid bond", "earnest money", "registration certificate",
                "income tax", "income-tax",
            ]
            is_boilerplate = any(kw in text_lower for kw in boilerplate_keywords)

            if is_extraction_sentinel:
                # Flag extraction failures as REVIEW — but using a clear name so the UI shows WHY
                v = CriterionVerdict.REVIEW
                c_val = "Extraction Warning"
                reason_text = (
                    "LLM extraction fell back to regex heuristics for this document. "
                    "Hard criteria (fleet, turnover, experience) may be incomplete — "
                    "manual verification recommended before bid submission."
                )
            elif is_boilerplate:
                v = CriterionVerdict.PASS
                c_val = "Satisfied (Standard Compliance)"
                reason_text = f"Boilerplate compliance clause '{req.requirement_text}' is satisfied."
            elif not req.is_mandatory:

                v = CriterionVerdict.PASS
                c_val = "Not Mandatory"
                reason_text = f"Non-mandatory qualitative clause: '{req.requirement_text}' does not block eligibility."
            else:
                v = CriterionVerdict.REVIEW
                c_val = "Under Review"
                reason_text = f"Mandatory qualitative clause: '{req.requirement_text}'. Flagged for manual review."

            criteria.append(CriterionDetail(
                criterion_name="Special Tender Requirement",
                is_mandatory=req.is_mandatory,
                verdict=v,
                company_value=c_val,
                required_value=req.requirement_text,
                reason=reason_text
            ))

    has_mandatory_failure = any(c.verdict == CriterionVerdict.FAIL and c.is_mandatory for c in criteria)
    has_any_review = any(c.verdict == CriterionVerdict.REVIEW for c in criteria)

    if has_mandatory_failure:
        final_verdict = FinalVerdict.NO_GO

        failed_criteria = [
        c.reason
        for c in criteria
        if c.verdict == CriterionVerdict.FAIL and c.is_mandatory
    ]

        summary = "NO-GO: " + " ".join(failed_criteria)

    elif has_any_review:
        final_verdict = FinalVerdict.REVIEW

        review_reasons = [
            c.reason
            for c in criteria
            if c.verdict == CriterionVerdict.REVIEW
        ]

        summary = (
            "REVIEW: All mandatory eligibility criteria passed, "
            "but manual review is required. "
            + " ".join(review_reasons)
        )

    else:
        final_verdict = FinalVerdict.GO
        summary = "GO: All evaluated eligibility criteria are satisfied."

    result = ScreeningResultSchema(
        tender_id=str(tender_id),
        verdict=final_verdict,
        reasoning=summary,
        criteria_results=criteria,
        screened_at=datetime.now(UTC).isoformat()
    )

    log_action(
        "SCREENING_COMPLETED",
        tender_id=tender_id,
        status="SUCCESS",
        details={
            "tender_title": tender_title[:40],
            "verdict": final_verdict.value,
            "has_mandatory_fail": has_mandatory_failure,
            "criteria_count": len(criteria)
        }
    )

    return result

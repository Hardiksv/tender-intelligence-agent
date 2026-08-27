# Tender Intelligence Agent — Design Decisions

## Geography Screening

### Decision: National / Pan-India scope tenders automatically PASS geography criterion

**Implemented in:** `backend/app/services/screening.py` — `screen_tender_eligibility()`

**Rationale:**

A tender whose `required_geographies` resolves to `"National"`, `"Pan-India"`,
`"Pan India"`, or `"All India"` imposes **no geographic restriction on bidders**.
The central government (or CESL) is procuring buses across multiple states
simultaneously; any company registered and capable anywhere in India may bid.

Treating `"National"` as a geography mismatch against a company profile's
state list (e.g. `["Rajasthan", "Delhi"]`) would be **wrong by design**:
- It would surface a false REVIEW for every national tender, regardless of how
  well-matched the company is on every other dimension.
- It conflates "the tender is scoped nationally" with "the company doesn't
  operate there" — which are opposite statements.

**Implementation:**

```python
national_scope_values = {"national", "pan-india", "pan india", "all india"}
if tender_state.lower().strip() in national_scope_values:
    verdict = PASS  # no state restriction → geography criterion is satisfied
elif tender_state in preferred_geographies:
    verdict = PASS
else:
    verdict = REVIEW  # state-restricted tender, company not covering that state
```

**What this is NOT:**

This is not a blanket "ignore geography". State-specific tenders (Rajasthan,
Delhi, Jaipur etc.) are still evaluated normally. Only the literal
National/Pan-India values trigger the bypass.

---

## Screening Result Uniqueness

### Decision: One `screening_results` row per tender, enforced structurally

**Implemented in:** `backend/app/db/models.py` (UniqueConstraint) and
`backend/app/agent/pipeline.py` (delete-before-insert UPSERT).

Re-running ingestion or re-screening should update the verdict for a tender,
not accumulate multiple rows. The original code inserted unconditionally,
causing N rows after N ingestion runs. This was fixed with:

1. `UniqueConstraint("tender_id", name="uq_screening_results_tender_id")` on
   the model — the DB will reject any duplicate inserts structurally.
2. A delete-before-insert pattern in the pipeline so the intent is explicit
   even before a migration applies the constraint to an existing DB.

---

## Extraction Fallback Sentinel

### Decision: Heuristic fallback is visibly flagged, not silently swallowed

**Implemented in:** `backend/app/services/extraction.py` and
`backend/app/services/screening.py`

When LLM structured extraction fails, the pipeline falls back to regex
heuristics. This fallback is never equivalent-confidence to LLM extraction.
To prevent this from producing falsely confident GO verdicts on fabricated
data, the fallback:

1. Injects an `other_requirement` sentinel text that marks the document as
   needing manual review.
2. The screening engine detects this sentinel string and surfaces a named
   `"Extraction Warning"` REVIEW criterion rather than a blocking FAIL.
3. The model field is set to `"heuristic-fallback"` so logs are queryable.

**Why REVIEW, not NO-GO?**

Extraction failure is an infrastructure problem, not an eligibility failure.
The correct action is human review, not automatic rejection. A tender that
genuinely qualifies should not be auto-rejected because Groq had a rate limit.

---

## max_tokens Budget (Groq free tier)

### Decision: max_tokens = 3000 for all LLM calls

Groq free tier enforces **8,000 tokens-per-minute** calculated as
`prompt_tokens + max_tokens` (requested budget, not actual usage). A typical
RAG prompt is ~4,800 tokens. Setting max_tokens > 3,200 would request more
than 8,000 total and trigger an immediate RateLimitError before the model
generates a single token. 3,000 is the safe upper bound that prevents both
truncation (< 2,000 failed for reasoning models) and rate limiting.
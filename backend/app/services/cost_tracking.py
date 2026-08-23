from typing import Any

INPUT_TOKEN_PRICE_PER_1M = 0.30
OUTPUT_TOKEN_PRICE_PER_1M = 2.50
USD_TO_INR = 85.0


def calculate_llm_cost(usage: dict[str, Any]) -> dict[str, Any]:
    """
    Calculates cost based on token usage metadata from LiteLLM.
    Uses verified Gemini 2.5 Flash pricing.
    """
    if not usage:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            "is_estimated": True,
            "pricing_source": "Verified Gemini 2.5 Flash Rates"
        }

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens) or 0
    is_estimated = usage.get("is_estimated", False)

    input_cost = (prompt_tokens / 1_000_000.0) * INPUT_TOKEN_PRICE_PER_1M
    output_cost = (completion_tokens / 1_000_000.0) * OUTPUT_TOKEN_PRICE_PER_1M
    total_cost_usd = input_cost + output_cost
    total_cost_inr = total_cost_usd * USD_TO_INR

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(total_cost_usd, 6),
        "cost_inr": round(total_cost_inr, 4),
        "is_estimated": is_estimated,
        "pricing_source": "Verified Gemini 2.5 Flash Rates ($0.30/1M input, $2.50/1M output)"
    }

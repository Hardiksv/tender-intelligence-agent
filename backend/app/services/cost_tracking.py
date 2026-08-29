from typing import Any
import litellm

USD_TO_INR = 85.0


def calculate_llm_cost(usage: dict[str, Any]) -> dict[str, Any]:
    """
    Calculates cost based on token usage metadata using actual LiteLLM pricing maps
    for the specific model invoked (e.g. Groq models), rather than hardcoded rates.
    """
    if not usage:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            "is_estimated": True,
            "pricing_source": "Unknown"
        }

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens) or 0
    is_estimated = usage.get("is_estimated", False)
    model = usage.get("model", "")

    try:
        # returns (prompt_cost, completion_cost)
        prompt_cost, comp_cost = litellm.cost_per_token(model, prompt_tokens, completion_tokens)
        total_cost_usd = prompt_cost + comp_cost
        pricing_source = f"LiteLLM Cost Map ({model})"
    except Exception:
        # Fallback if model not in litellm's pricing map
        fallback_rates = {
            "groq/openai/gpt-oss-120b": {"p": 0.0015, "c": 0.002},
            "groq/qwen/qwen3.6-27b": {"p": 0.0005, "c": 0.001}
        }
        if model in fallback_rates:
            rates = fallback_rates[model]
            total_cost_usd = (prompt_tokens / 1000.0) * rates["p"] + (completion_tokens / 1000.0) * rates["c"]
            pricing_source = f"Manual Fallback ({model})"
        else:
            total_cost_usd = 0.0
            pricing_source = f"Unpriced Model ({model})"

    total_cost_inr = total_cost_usd * USD_TO_INR

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(total_cost_usd, 6),
        "cost_inr": round(total_cost_inr, 4),
        "is_estimated": is_estimated,
        "pricing_source": pricing_source
    }

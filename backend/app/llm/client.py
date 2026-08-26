import json
import os
from typing import Any, Optional, TypeVar

import litellm
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.llm.base import AbstractLLMClient

T = TypeVar("T", bound=BaseModel)

litellm.drop_params = True


class LiteLLMClient(AbstractLLMClient):
    """
    LiteLLM Abstraction implementation supporting primary & fallback model failover,
    usage tracking, and zero direct vendor SDK imports.
    """

    def __init__(self):
        self.primary_model = settings.LLM_MODEL
        self.fallback_model = settings.LLM_FALLBACK_MODEL
        self.api_key = settings.LLM_API_KEY

    def _extract_usage(self, response: Any, model_used: str, request_type: str) -> dict[str, Any]:
        """Extracts token usage metadata from LiteLLM response."""
        usage_meta = {
            "model": model_used,
            "request_type": request_type,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "is_estimated": True
        }

        if hasattr(response, "usage") and response.usage:
            usage_meta["prompt_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
            usage_meta["completion_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0
            usage_meta["total_tokens"] = getattr(response.usage, "total_tokens", 0) or 0
            usage_meta["is_estimated"] = False

        return usage_meta

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2000
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if settings.LLM_API_KEY:
            if settings.LLM_API_KEY.startswith("gsk_") or "groq" in self.primary_model:
                os.environ["GROQ_API_KEY"] = settings.LLM_API_KEY
            else:
                os.environ["GEMINI_API_KEY"] = settings.LLM_API_KEY
                os.environ["GOOGLE_API_KEY"] = settings.LLM_API_KEY

        models_to_try = [
            self.primary_model,
            self.fallback_model,
            "groq/qwen/qwen3.6-27b"
        ]
        models_to_try = list(dict.fromkeys(models_to_try))
        last_error = None

        for model in models_to_try:
            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=self.api_key if (self.api_key and self.api_key != "mock_key_for_testing") else None
                )
                content = response.choices[0].message.content
                if "<think" in content and "</think>" not in content:
                    raise RuntimeError("Model output was truncated mid-reasoning (missing </think> tag).")
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()
                usage = self._extract_usage(response, model, "completion")

                return {
                    "content": content,
                    "model": model,
                    "usage": usage
                }
            except Exception as e:
                last_error = e
                logger.warning(f"LiteLLM call to model '{model}' failed: {e}. Trying fallback if available.")

        logger.error(
            f"ALL LLM MODELS FAILED. "
            f"LAST ERROR TYPE={type(last_error).__name__}, "
            f"ERROR={last_error!r}"
        )

        raise RuntimeError(
            f"All configured LLM models failed. "
            f"Last error: {last_error}"
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        instructions = f"\n\nRespond ONLY with a valid JSON object strictly matching this schema:\n{json.dumps(response_model.model_json_schema())}"
        messages.append({"role": "user", "content": prompt + instructions})

        if settings.LLM_API_KEY:
            if settings.LLM_API_KEY.startswith("gsk_") or "groq" in self.primary_model:
                os.environ["GROQ_API_KEY"] = settings.LLM_API_KEY
            else:
                os.environ["GEMINI_API_KEY"] = settings.LLM_API_KEY
                os.environ["GOOGLE_API_KEY"] = settings.LLM_API_KEY

        models_to_try = [self.primary_model, self.fallback_model, "groq/qwen/qwen3.6-27b"]
        models_to_try = list(dict.fromkeys(models_to_try))
        last_error = None

        for model in models_to_try:
            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    api_key=self.api_key if self.api_key != "mock_key_for_testing" else None
                )
                raw_text = response.choices[0].message.content
                if "<think" in raw_text and "</think>" not in raw_text:
                    raise RuntimeError("Model output was truncated mid-reasoning (missing </think> tag).")
                if "</think>" in raw_text:
                    raw_text = raw_text.split("</think>")[-1].strip()
                parsed_json = json.loads(raw_text)
                validated_obj = response_model.model_validate(parsed_json)
                usage = self._extract_usage(response, model, "structured_extraction")

                return {
                    "data": validated_obj,
                    "raw_json": parsed_json,
                    "model": model,
                    "usage": usage
                }
            except Exception as e:
                logger.warning(f"Structured LiteLLM call failed with model '{model}': {e}")
                last_error = e

        logger.error(
            f"ALL STRUCTURED LLM MODELS FAILED. "
            f"LAST ERROR TYPE={type(last_error).__name__}, "
            f"ERROR={last_error!r}"
        )

        raise RuntimeError(
            f"All configured LLM models failed for structured generation. "
            f"Last error: {last_error}"
        )


llm_client = LiteLLMClient()

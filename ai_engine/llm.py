"""LLM client wrapper using Google Gemini API with rate-limit handling and honest fallback."""

from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    mode: str  # "gemini" | "openai" | "demo_fallback"
    model: str
    fallback_reason: Optional[str] = None


class LLMClient:
    """Unified LLM wrapper supporting Gemini API (primary) and transparent demo fallback."""

    def __init__(self) -> None:
        self._runtime_gemini_key: Optional[str] = None

    def set_runtime_api_key(self, api_key: str) -> None:
        self._runtime_gemini_key = api_key.strip() if api_key else ""

    @property
    def gemini_api_key(self) -> str:
        if self._runtime_gemini_key is not None:
            return self._runtime_gemini_key
        return settings.gemini_api_key.strip()

    def is_live_configured(self) -> bool:
        return bool(self.gemini_api_key)

    def get_status(self) -> Dict[str, Any]:
        if self.gemini_api_key:
            return {
                "active_mode": "gemini",
                "model": settings.gemini_model,
                "is_demo_mode": False,
                "message": f"Connected to Gemini API ({settings.gemini_model})",
            }
        return {
            "active_mode": "demo_fallback",
            "model": "rule-based-sales-simulator",
            "is_demo_mode": True,
            "message": "GEMINI_API_KEY not configured. Running in transparent Demo Fallback Mode.",
        }

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> LLMResponse:
        """Generate a conversational response via Gemini API, with retry and honest fallback."""
        api_key = self.gemini_api_key
        if not api_key:
            return LLMResponse(
                text="",
                mode="demo_fallback",
                model="rule-based-sales-simulator",
                fallback_reason="GEMINI_API_KEY is not set.",
            )

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("Gemini returned an empty response.")
                return LLMResponse(
                    text=text,
                    mode="gemini",
                    model=settings.gemini_model,
                )
            except Exception as exc:
                last_error = str(exc)
                is_rate_limit = "429" in last_error or "RESOURCE_EXHAUSTED" in last_error
                logger.warning(
                    "Gemini call failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries + 1,
                    last_error,
                )
                if is_rate_limit and attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        return LLMResponse(
            text="",
            mode="demo_fallback",
            model="rule-based-sales-simulator",
            fallback_reason=last_error or "Gemini API unavailable.",
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """Invoke Gemini expecting a JSON object; returns None if unavailable or unparseable."""
        api_key = self.gemini_api_key
        if not api_key:
            return None

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            raw = (response.text or "").strip()
            if not raw:
                return None
            # Strip optional markdown code fences
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.warning("Gemini JSON generation failed (%s); using local fallback.", exc)
            return None


llm_client = LLMClient()

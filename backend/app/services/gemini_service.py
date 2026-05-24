"""
Reusable Gemini AI service — uses google.genai (current SDK).
Reads credentials from app.core.config.settings (pydantic-settings loads .env).
"""

import logging
import time

from google import genai

logger = logging.getLogger(__name__)

_SLOW_CALL_THRESHOLD_S = 20.0


class GeminiService:
    """Thin wrapper around the Gemini API (google.genai SDK)."""

    def __init__(self, system_instruction: str | None = None) -> None:
        self.system_instruction = system_instruction

    def generate(self, prompt: str, trace_id: str | None = None) -> str:
        """
        Call Gemini and return the text response.
        Raises RuntimeError on API failure.
        """
        # Import here to avoid circular imports at module load time
        from app.core.config import settings

        full_prompt = f"{self.system_instruction}\n\n{prompt}" if self.system_instruction else prompt

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        start = time.monotonic()

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=full_prompt,
            )
            elapsed = time.monotonic() - start

            if elapsed > _SLOW_CALL_THRESHOLD_S:
                logger.warning("Slow Gemini call | trace=%s elapsed=%.2fs", trace_id, elapsed)
            else:
                logger.debug("Gemini OK | trace=%s model=%s elapsed=%.2fs",
                             trace_id, settings.GEMINI_MODEL, elapsed)

            return response.text

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error("Gemini error | trace=%s elapsed=%.2fs error=%s", trace_id, elapsed, exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc

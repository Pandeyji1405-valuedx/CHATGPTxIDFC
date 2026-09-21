"""
Gemini Generator — Phase 4 RAG Pipeline.

Sends the regulatory prompt to Gemini and parses the structured JSON response.

Architecture decisions:
  - Uses the current google-genai Python SDK (google.genai client pattern).
  - Model is configured via GEMINI_MODEL environment variable.
  - Deprecated sampling parameters (temperature, top_p, top_k, candidate_count)
    are NOT sent; only supported thinking configuration is used.
  - Structured output is enforced via Pydantic schema passed as response_schema
    to the Gemini API.
  - citation_ids from Gemini are treated as UNTRUSTED until validated by
    grounding.py against the actual retrieved evidence set.
  - MockLLMGenerator provides deterministic offline behaviour for unit tests.
"""

import json
import logging
from typing import List, Optional

from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton Gemini client (initialized lazily)
_gemini_client = None


def _get_client():
    """Lazy-initialize the Google GenAI client."""
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Google GenAI client initialized with model: %s", settings.GEMINI_MODEL)
    return _gemini_client


# ------------------------------------------------------------------ #
# Response schema (Gemini enforces this via response_schema)
# ------------------------------------------------------------------ #

class GeminiStructuredResponse(BaseModel):
    """
    Expected structured JSON output from Gemini.

    answer:       The regulatory answer grounded in the provided evidence.
    citation_ids: Chunk IDs cited by Gemini. Must be validated against
                  the actual retrieved set; invalid IDs are discarded.
    """

    answer: str
    citation_ids: List[str] = []


# ------------------------------------------------------------------ #
# Production Generator
# ------------------------------------------------------------------ #

class GeminiGenerator:
    """
    Calls the Gemini API and returns a parsed structured response.
    """

    async def generate(self, prompt: str) -> GeminiStructuredResponse:
        """
        Send the prompt to Gemini and parse the JSON response.

        Args:
            prompt: Full regulatory prompt (system instruction + evidence + question).

        Returns:
            GeminiStructuredResponse with answer and citation_ids.

        Raises:
            RuntimeError: On API failure or invalid JSON response.
        """
        try:
            from google import genai
            from google.genai import types

            client = _get_client()

            # Build thinking config (no deprecated sampling params)
            thinking_config = types.ThinkingConfig(
                thinking_budget=_thinking_budget(settings.GEMINI_THINKING_LEVEL)
            )

            generate_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiStructuredResponse,
                thinking_config=thinking_config,
            )

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=generate_config,
            )

            raw_text = response.text or ""
            logger.debug("Gemini raw response length: %d chars", len(raw_text))

            parsed = _parse_response(raw_text)
            return parsed

        except Exception as exc:
            logger.error("Gemini generation failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Gemini generation error: {exc}") from exc


def _thinking_budget(level: str) -> Optional[int]:
    """
    Map thinking level string to a token budget integer.

    Gemini thinking_budget controls how many tokens the model may use
    for reasoning before producing the final response.
    Returns None for "none" (disables thinking entirely).
    """
    level = (level or "low").lower()
    mapping = {
        "none": 0,
        "low": 1024,
        "medium": 8192,
        "high": 24576,
    }
    return mapping.get(level, 1024)


def _parse_response(raw_text: str) -> GeminiStructuredResponse:
    """
    Parse the structured JSON text from Gemini into a validated schema.

    Attempts:
      1. Direct JSON parse of the full text.
      2. JSON extracted from a markdown code block.
      3. Fallback: answer = raw_text, citation_ids = [].
    """
    # Attempt 1: direct JSON
    text = raw_text.strip()
    try:
        data = json.loads(text)
        return GeminiStructuredResponse(**data)
    except (json.JSONDecodeError, Exception):
        pass

    # Attempt 2: code-fenced JSON block
    import re
    code_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if code_match:
        try:
            data = json.loads(code_match.group(1))
            return GeminiStructuredResponse(**data)
        except (json.JSONDecodeError, Exception):
            pass

    # Fallback
    logger.warning("Could not parse Gemini response as JSON; using raw text as answer.")
    return GeminiStructuredResponse(answer=text or "Unable to generate a response.", citation_ids=[])


# ------------------------------------------------------------------ #
# Mock Generator for Unit Tests
# ------------------------------------------------------------------ #

class MockLLMGenerator:
    """
    Deterministic offline generator for unit tests.

    Returns a canned answer citing the first chunk_id in the prompt.
    """

    async def generate(self, prompt: str) -> GeminiStructuredResponse:
        # Extract first Source ID from the prompt if present
        import re
        ids = re.findall(r"\[Source ID: ([^\]]+)\]", prompt)
        return GeminiStructuredResponse(
            answer="Mock regulatory answer based on provided evidence.",
            citation_ids=ids[:2] if ids else [],
        )

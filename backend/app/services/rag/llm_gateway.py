"""
Phase 5 LLM Gateway Abstraction Layer.

Decouples RAG pipeline generation from concrete LLM providers.
Provides interface abstraction: FastAPI -> LLM Gateway -> TP LLM / Gemini.
"""

from abc import ABC, abstractmethod
import logging
from typing import List, Optional

from pydantic import BaseModel

from app.core.config import get_settings
from app.services.rag.generator import GeminiGenerator, MockLLMGenerator

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMResponse(BaseModel):
    """Normalized response schema returned by LLM Gateway adapters."""
    answer: str
    citation_ids: List[str] = []
    raw_response: str = ""


class LLMGatewayInterface(ABC):
    """Abstract interface for LLM generation providers."""

    @abstractmethod
    async def generate(self, prompt: str) -> LLMResponse:
        """Send prompt to LLM provider and return normalized LLMResponse."""
        pass


class GeminiLLMAdapter(LLMGatewayInterface):
    """
    Adapter wrapping the Phase 4 GeminiGenerator.
    Preserves structured JSON Pydantic schema and low-thinking configuration.
    """

    def __init__(self, generator: Optional[GeminiGenerator] = None):
        self.generator = generator or GeminiGenerator()

    async def generate(self, prompt: str) -> LLMResponse:
        result = await self.generator.generate(prompt)
        return LLMResponse(
            answer=result.answer,
            citation_ids=result.citation_ids,
            raw_response=result.answer,
        )


class MockLLMAdapter(LLMGatewayInterface):
    """
    Adapter wrapping MockLLMGenerator for offline unit tests.
    """

    def __init__(self, generator: Optional[MockLLMGenerator] = None):
        self.generator = generator or MockLLMGenerator()

    async def generate(self, prompt: str) -> LLMResponse:
        result = await self.generator.generate(prompt)
        return LLMResponse(
            answer=result.answer,
            citation_ids=result.citation_ids,
            raw_response=result.answer,
        )


def get_llm_gateway() -> LLMGatewayInterface:
    """
    Factory function returning the active LLM Gateway adapter.
    """
    provider = (settings.LLM_GATEWAY_PROVIDER or "gemini").lower()
    if provider == "mock":
        return MockLLMAdapter()
    return GeminiLLMAdapter()

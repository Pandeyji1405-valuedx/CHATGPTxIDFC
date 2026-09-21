"""
Phase 5 Deterministic & Context-Aware Query Contextualizer.

Responsible for deciding if a user's follow-up prompt requires previous-turn context,
and contextualizing it into a canonical standalone regulatory query.

Core Rules:
  - Does NOT call an LLM for standalone queries.
  - Uses deterministic regex heuristics to detect pronouns or follow-up phrases.
  - Preserves original_user_query verbatim for chat storage.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Heuristic triggers indicating context dependency
CONTEXT_PATTERNS = [
    r"\b(it|they|these|those|this|that|same)\b",
    r"\b(what about|how regarding|any update on|does this apply|is it required|and for|what of|the same|above|following)\b",
]

PRONOUN_REGEX = re.compile("|".join(CONTEXT_PATTERNS), re.IGNORECASE)


class QueryContextualizer:
    """
    Contextualizes user follow-up questions using active session memory.
    """

    def needs_context(self, prompt: str, session_history: List[Dict[str, Any]]) -> bool:
        """
        Determine whether the prompt depends on prior conversation history.

        Returns True ONLY if:
          1. session_history is non-empty, AND
          2. The prompt matches pronoun/follow-up heuristic triggers OR is very short without domain terms.
        """
        if not session_history:
            return False

        prompt_clean = prompt.strip()

        # Check regex trigger match
        if PRONOUN_REGEX.search(prompt_clean):
            return True

        # Check short query without regulatory identifiers
        words = prompt_clean.split()
        if len(words) <= 5:
            # Check if common domain keywords exist
            has_domain_term = any(
                term in prompt_clean.lower()
                for term in ["kyc", "rbi", "nbfc", "ucb", "circular", "master direction", "capital", "exposure", "lending"]
            )
            if not has_domain_term:
                return True

        return False

    async def contextualize(
        self,
        prompt: str,
        session_history: List[Dict[str, Any]],
        llm_gateway: Optional[Any] = None,
    ) -> Tuple[str, bool]:
        """
        Contextualize prompt if required; otherwise return prompt verbatim.

        Returns:
            Tuple of (canonical_query, was_contextualized)
        """
        if not self.needs_context(prompt, session_history):
            return prompt.strip(), False

        logger.info("Query '%s' requires contextualization against %d turn(s)", prompt, len(session_history))

        # Build context summary string from session history
        history_str = ""
        for turn in session_history[-2:]:  # Last 2 turns
            history_str += f"User: {turn.get('user_query', '')}\n"
            history_str += f"Assistant Answer Excerpt: {turn.get('summary_answer', '')[:200]}\n"

        # Deterministic fallback rewriting if LLM gateway is not provided
        if not llm_gateway:
            last_turn = session_history[-1]
            topic = last_turn.get("canonical_query") or last_turn.get("user_query", "")
            canonical = f"{prompt.strip()} regarding {topic}"
            return canonical, True

        # LLM-based query rewriting
        prompt_instruction = (
            "You are a regulatory query contextualizer for RBI banking compliance.\n"
            "Below is a recent conversation history followed by a user's follow-up question.\n"
            "Rewrite the follow-up question into a SINGLE, standalone, canonical regulatory question "
            "that contains all necessary subject context. Do NOT answer the question.\n\n"
            f"Conversation History:\n{history_str}\n"
            f"Follow-up Question: {prompt}\n\n"
            "Canonical Question:"
        )

        try:
            response = await llm_gateway.generate(prompt_instruction)
            canonical = response.answer.strip()
            if canonical and len(canonical) > 5:
                logger.info("Contextualized query: '%s' -> '%s'", prompt, canonical)
                return canonical, True
        except Exception as exc:
            logger.warning("LLM contextualization failed: %s; using deterministic fallback", exc)

        # Fallback
        last_turn = session_history[-1]
        topic = last_turn.get("canonical_query") or last_turn.get("user_query", "")
        return f"{prompt.strip()} regarding {topic}", True

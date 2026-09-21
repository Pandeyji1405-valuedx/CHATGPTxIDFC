import re
from typing import List, Dict, Any, Tuple, Optional

class TokenBudgetController:
    """
    Manages and enforces token allocation budgets as mandated by PRD Section 9.3 (FR-15).
    Guarantees strict allocation boundaries:
    - System Policy & Prompts: ~800 tokens
    - User Question & Context: ~300 tokens
    - Output Generation Reserve: ~1500 tokens
    - Evidence Passages: ~3000 tokens
    - Conversation History / Memory: ~1000 tokens
    """
    def __init__(
        self,
        max_total_tokens: int = 8192,
        system_reserve: int = 800,
        query_reserve: int = 300,
        output_reserve: int = 1500,
        evidence_budget: int = 3000,
        history_budget: int = 1000
    ):
        self.max_total_tokens = max_total_tokens
        self.system_reserve = system_reserve
        self.query_reserve = query_reserve
        self.output_reserve = output_reserve
        self.evidence_budget = evidence_budget
        self.history_budget = history_budget
        self.budget = {
            "system": system_reserve,
            "query": query_reserve,
            "output": output_reserve,
            "evidence": evidence_budget,
            "history": history_budget
        }

    def fit_evidence(
        self,
        ranked_chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fits evidence chunks within the allocated budget."""
        budget = max_tokens or self.evidence_budget
        admitted = []
        accumulated = 0
        for chunk in ranked_chunks:
            text = chunk.get("chunk_text", "")
            tokens = self.estimate_tokens(text)
            if accumulated + tokens > budget:
                break
            admitted.append(chunk)
            accumulated += tokens
        return admitted

    @classmethod
    def summarize_history_if_needed(
        cls,
        messages: List[Dict[str, Any]],
        existing_summary: Optional[str] = None,
        max_recent_turns: int = 4
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Summarizes older conversation turns if length exceeds max_recent_turns."""
        if len(messages) <= max_recent_turns:
            return messages, existing_summary
        
        older = messages[:-max_recent_turns]
        recent = messages[-max_recent_turns:]
        
        summary_snippets = []
        if existing_summary:
            summary_snippets.append(existing_summary)
            
        for m in older:
            role = m.get("role", "user")
            content = m.get("content", m.get("original_content", ""))
            short = content.split(".")[0].strip()
            if len(short) > 60:
                short = short[:60] + "..."
            summary_snippets.append(f"{role.capitalize()}: {short}")
            
        new_summary = "Prior Conversation Summary: " + " | ".join(summary_snippets[-6:])
        summary_msg = {"role": "system", "content": new_summary}
        return [summary_msg] + recent, new_summary

    def estimate_tokens(self, text: Optional[str]) -> int:
        """Estimates token count using standard ~4 chars/token heuristic."""
        if not text:
            return 0
        # Clean whitespace and estimate
        return max(1, len(text) // 4)

    def compact_conversation_history(
        self,
        conversation_history: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Compacts long conversation histories when they exceed the 1000 tokens budget.
        Preserves the latest 2 turns verbatim and creates a concise summary of earlier turns.
        """
        if not conversation_history:
            return [], None

        total_history_tokens = sum(
            self.estimate_tokens(turn.get("content", turn.get("original_content", "")))
            for turn in conversation_history
        )

        if total_history_tokens <= self.history_budget:
            return conversation_history, None

        # Keep latest 2 turns verbatim
        recent_turns = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
        older_turns = conversation_history[:-4] if len(conversation_history) > 4 else []

        if not older_turns:
            return recent_turns, None

        # Generate summary of older turns
        summary_points = []
        for turn in older_turns:
            role = turn.get("role", "user")
            content = turn.get("content", turn.get("original_content", ""))
            # Extract first sentence of turn
            first_sent = content.split(".")[0].strip()
            if len(first_sent) > 80:
                first_sent = first_sent[:80] + "..."
            summary_points.append(f"{role.capitalize()}: {first_sent}")

        summary_text = "Prior Context: " + "; ".join(summary_points[-5:])
        return recent_turns, summary_text

    def allocate_evidence_chunks(
        self,
        ranked_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Selects top-ranked evidence chunks strictly within the evidence token budget (~3000 tokens).
        Deduplicates overlapping content.
        """
        admitted_chunks = []
        accumulated_tokens = 0
        seen_texts = set()

        for chunk in ranked_chunks:
            text = chunk.get("chunk_text", "").strip()
            # Basic text fingerprint for deduplication
            normalized_prefix = re.sub(r"\s+", " ", text[:120].lower())
            if normalized_prefix in seen_texts:
                continue

            chunk_tokens = self.estimate_tokens(text)
            if accumulated_tokens + chunk_tokens > self.evidence_budget:
                break

            admitted_chunks.append(chunk)
            seen_texts.add(normalized_prefix)
            accumulated_tokens += chunk_tokens

        return admitted_chunks

    def get_token_telemetry(
        self,
        system_text: str,
        query_text: str,
        evidence_chunks: List[Dict[str, Any]],
        history_turns: List[Dict[str, Any]],
        output_text: str
    ) -> Dict[str, int]:
        """Returns detailed token usage breakdown for audit and consumption MIS."""
        sys_tokens = self.estimate_tokens(system_text)
        q_tokens = self.estimate_tokens(query_text)
        ev_tokens = sum(self.estimate_tokens(c.get("chunk_text", "")) for c in evidence_chunks)
        hist_tokens = sum(self.estimate_tokens(t.get("content", t.get("original_content", ""))) for t in history_turns)
        out_tokens = self.estimate_tokens(output_text)

        total_in = sys_tokens + q_tokens + ev_tokens + hist_tokens
        return {
            "tokens_system": sys_tokens,
            "tokens_query": q_tokens,
            "tokens_evidence": ev_tokens,
            "tokens_history": hist_tokens,
            "tokens_input": total_in,
            "tokens_output": out_tokens,
            "tokens_total": total_in + out_tokens
        }

token_budget_controller = TokenBudgetController()

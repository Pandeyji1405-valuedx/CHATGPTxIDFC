"""
Regulatory Prompt Builder — Phase 4 RAG Pipeline.

Constructs the structured prompt that is sent to Gemini.

Key design decisions:
  - Each evidence chunk is labeled with an unambiguous [Source ID: <chunk_id>]
    header so that Gemini can cite sources by their backend-verifiable ID.
  - The system instruction strictly confines Gemini to answering ONLY from
    the provided evidence excerpts.
  - Page numbers, document titles, and circular numbers in the evidence block
    come from the retrieval system -- Gemini must not invent new metadata.
  - The expected response format (JSON with answer + citation_ids) is stated
    explicitly in the prompt.
"""

from typing import List

from app.services.rag.retriever import RetrievedChunk

SYSTEM_INSTRUCTION = """You are an expert RBI (Reserve Bank of India) regulatory compliance analyst.

STRICT INSTRUCTIONS:
1. Answer ONLY from the evidence excerpts provided below. Do not use prior knowledge.
2. If the evidence does not contain enough information to answer, state clearly that the
   provided regulatory documents do not address this question.
3. When referencing evidence, use the exact Source ID provided in brackets.
4. Do NOT invent document titles, circular numbers, page numbers, or section references.
   These values are provided in the evidence and must be quoted, never created.
5. Respond ONLY in valid JSON matching this exact schema:
   {
     "answer": "<your detailed regulatory answer>",
     "citation_ids": ["<Source ID 1>", "<Source ID 2>", ...]
   }
   Include only the chunk IDs from the evidence that directly support your answer.
"""


def build_prompt(query: str, chunks: List[RetrievedChunk]) -> str:
    """
    Construct the Gemini prompt with evidence blocks and user question.

    Args:
        query:  Normalized user regulatory question.
        chunks: Top-K ranked evidence chunks (from BGE reranker).

    Returns:
        Full prompt string ready to send to Gemini.
    """
    evidence_lines: List[str] = []

    for i, chunk in enumerate(chunks, start=1):
        circular = f" | Circular: {chunk.circular_number}" if chunk.circular_number else ""
        section = f" | Section: {chunk.section}" if chunk.section else ""
        evidence_lines.append(
            f"[Source ID: {chunk.chunk_id}]\n"
            f"Document: {chunk.document_title}"
            f"{circular}"
            f" | Version: v{chunk.version_number}"
            f" | Page: {chunk.page_number}"
            f"{section}\n"
            f"Excerpt:\n{chunk.text}"
        )

    evidence_block = "\n\n---\n\n".join(evidence_lines)

    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"=== REGULATORY EVIDENCE ({len(chunks)} excerpts) ===\n\n"
        f"{evidence_block}\n\n"
        f"=== USER QUESTION ===\n"
        f"{query}\n\n"
        f"=== YOUR RESPONSE (JSON only) ==="
    )

    return prompt

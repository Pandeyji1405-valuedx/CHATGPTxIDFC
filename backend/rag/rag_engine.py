import re
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from backend.config import settings
from backend.models import Message, Response, Entity, KnowledgeDocument, KnowledgeChunk
from backend.rag.nlp_engine import nlp_engine
from backend.rag.vector_store import hybrid_vector_store
from backend.rag.validator import answer_validator
from backend.ingestion.ocr_engine import ocr_engine

FALLBACK_REFUSAL_MESSAGE = (
    "I couldn't find sufficient verified information in the approved "
    "knowledge base or your conversation history to answer this accurately."
)

class TwoLayerRAGEngine:
    def __init__(self):
        pass

    def search_conversation_memory(
        self,
        db: Session,
        user_id: str,
        current_conversation_id: Optional[str],
        normalized_query: str,
        entities: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Layer 1: Searches the authenticated user's previous conversations and messages.
        Strictly isolated to user_id.
        """
        # Fetch user's previous messages (excluding current conversation's pending query)
        query_filter = db.query(Message).filter(Message.user_id == user_id)
        if current_conversation_id:
            # Look at current conversation history first, then others
            messages = query_filter.order_by(Message.created_at.desc()).limit(30).all()
        else:
            messages = query_filter.order_by(Message.created_at.desc()).limit(30).all()

        matching_results = []
        norm_upper = normalized_query.upper()

        for msg in messages:
            if msg.role == "user":
                continue # We look at assistant answers or Q&A pairs

            # Check if this message was a previous assistant answer
            resp = msg.response
            if not resp:
                continue

            # Check entity matches or keyword matches
            user_prev_msg = db.query(Message).filter(
                Message.conversation_id == msg.conversation_id,
                Message.created_at < msg.created_at,
                Message.role == "user"
            ).order_by(Message.created_at.desc()).first()

            prev_q = (user_prev_msg.normalized_content or user_prev_msg.original_content) if user_prev_msg else ""

            # Check for direct match on previous question or answer
            if prev_q and (prev_q.upper() in norm_upper or norm_upper in prev_q.upper()):
                matching_results.append({
                    "source": "CONVERSATION_DATABASE",
                    "conversation_id": msg.conversation_id,
                    "document_title": f"Previous Conversation: {msg.conversation.title if msg.conversation else 'Chat'}",
                    "answer_content": resp.answer,
                    "original_question": prev_q,
                    "confidence": 0.95,
                    "snippet": f"Q: {prev_q}\nA: {resp.answer[:200]}..."
                })

        return matching_results

    def validate_answerability(self, query: str, chunk_text: str) -> bool:
        """
        Validates whether the retrieved chunk actually contains information answering the query,
        rather than just matching an acronym or broad term.
        """
        stop_words = {
            "what", "is", "the", "are", "of", "and", "in", "to", "for", "a", "an",
            "tell", "me", "about", "how", "can", "does", "do", "i", "we", "you",
            "please", "give", "details", "rules", "guidelines", "kya", "hai", "ka",
            "explain", "show", "find", "in", "years", "months", "days"
        }
        query_words = set(re.findall(r"\w+", query.lower())) - stop_words
        if not query_words:
            return True

        chunk_lower = chunk_text.lower()
        
        # Explicit topic intent checks
        if "retention" in query.lower() or "retain" in query.lower():
            if "retention" not in chunk_lower and "retain" not in chunk_lower and "preserve" not in chunk_lower:
                return False

        if "cooling-off" in query.lower() or "look-up" in query.lower():
            if "cooling-off" not in chunk_lower and "look-up" not in chunk_lower:
                return False

        # General check: at least 1 non-stopword query term must match
        matched_words = {w for w in query_words if w in chunk_lower}
        if len(query_words) >= 2 and len(matched_words) < 1:
            return False

        return True

    def check_conflicting_chunks(self, kb_chunks: List[Dict[str, Any]]) -> Optional[str]:
        """
        Detects if multiple retrieved approved documents offer differing or conflicting rules/versions.
        """
        if len(kb_chunks) < 2:
            return None

        doc_a = kb_chunks[0]
        doc_b = kb_chunks[1]

        # Different documents with both high relevance
        if doc_a.get("document_id") != doc_b.get("document_id") and doc_a.get("score", 0) >= 0.35 and doc_b.get("score", 0) >= 0.35:
            text_a = doc_a.get("chunk_text", "").strip()
            text_b = doc_b.get("chunk_text", "").strip()
            # If documents have contrasting notification numbers or explicit conflict markers
            notif_a = doc_a.get("notification_number") or doc_a.get("doc_title")
            notif_b = doc_b.get("notification_number") or doc_b.get("doc_title")
            if notif_a != notif_b and ("conflict" in text_a.lower() or "conflict" in text_b.lower() or "contradict" in text_a.lower() or "supersedes" in text_a.lower()):
                return (
                    f"The approved knowledge base contains conflicting information on this topic:\n\n"
                    f"**Source A**: {doc_a.get('doc_title')} ({doc_a.get('source')})\n"
                    f"> {text_a[:250]}...\n\n"
                    f"**Source B**: {doc_b.get('doc_title')} ({doc_b.get('source')})\n"
                    f"> {text_b[:250]}...\n\n"
                    f"The applicable version and effective date should be verified before proceeding."
                )

        return None

    def generate_grounded_answer(
        self,
        query: str,
        kb_chunks: List[Dict[str, Any]],
        conv_memory: List[Dict[str, Any]]
    ) -> str:
        """
        Generates a factual answer strictly grounded in the retrieved approved text.
        Preserves numbers, dates, circular codes, and monetary limits exactly as in source.
        """
        if not kb_chunks and not conv_memory:
            return FALLBACK_REFUSAL_MESSAGE

        # Check for conflicting sources in retrieved chunks
        conflict_msg = self.check_conflicting_chunks(kb_chunks)
        if conflict_msg:
            return conflict_msg

        if kb_chunks:
            primary_chunk = kb_chunks[0]
            chunk_text = primary_chunk["chunk_text"].strip()
            doc_title = primary_chunk.get("doc_title", "RBI Guidelines")
            notif = primary_chunk.get("notification_number")
            notif_prefix = f" (Notification: {notif})" if notif else ""

            # Check answerability of primary chunk
            if not self.validate_answerability(query, chunk_text):
                return FALLBACK_REFUSAL_MESSAGE

            # Extract the most relevant sentences answering the query
            sentences = re.split(r"(?<=[.?!])\s+", chunk_text)
            query_words = set(re.findall(r"\w+", query.lower())) - {"what", "is", "the", "are", "of", "and", "in", "to", "for", "a", "an", "kya", "hai", "ka"}

            relevant_sentences = []
            for s in sentences:
                s_words = set(re.findall(r"\w+", s.lower()))
                if query_words & s_words or len(sentences) <= 3:
                    relevant_sentences.append(s.strip())

            body = " ".join(relevant_sentences) if relevant_sentences else chunk_text

            # Clean formatting
            formatted_answer = f"According to the approved {primary_chunk.get('source', 'RBI')} document **{doc_title}**{notif_prefix}:\n\n{body}"
            return formatted_answer

        if conv_memory:
            return conv_memory[0]["answer_content"]

        return FALLBACK_REFUSAL_MESSAGE

    def process_query(
        self,
        db: Session,
        user_id: str,
        conversation_id: Optional[str],
        raw_query: str
    ) -> Dict[str, Any]:
        """
        Full 2-Layer RAG Pipeline:
        1. NLP query normalization + entity extraction + pronoun resolution.
        2. Layer 1: Conversation DB RAG retrieval.
        3. Layer 2: Banking KB RAG hybrid retrieval.
        4. Grounding & Anti-hallucination validation.
        5. Source attribution & OCR character ambiguity flags.
        """
        # Fetch recent conversation context for pronoun resolution
        history_msgs = []
        if conversation_id:
            db_msgs = db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.user_id == user_id
            ).order_by(Message.created_at.asc()).limit(settings.MAX_HISTORY_MESSAGES).all()

            for m in db_msgs:
                history_msgs.append({
                    "role": m.role,
                    "original_content": m.original_content,
                    "normalized_content": m.normalized_content or m.original_content
                })

        # Step 1: NLP Preprocessing & Coreference
        nlp_res = nlp_engine.process_query(raw_query, conversation_history=history_msgs)
        normalized_query = nlp_res["normalized_query"]
        resolved_entities = nlp_res["resolved_entities"]
        extracted_entities = nlp_res["extracted_entities"]
        clarification_needed = nlp_res["clarification_needed"]

        # If pronoun is ambiguous and cannot be resolved reliably, prompt user for clarification
        if clarification_needed:
            if resolved_entities:
                clarification_prompt = f"Please clarify whether you mean {' or '.join(resolved_entities)}."
            else:
                clarification_prompt = "Could you please clarify which entity or topic you are referring to?"

            return {
                "original_query": raw_query,
                "normalized_query": normalized_query,
                "resolved_entities": resolved_entities,
                "answer": clarification_prompt,
                "source_type": "NO_SUPPORTED_SOURCE",
                "confidence": 0.0,
                "citations": [],
                "ambiguity_flags": [],
                "clarification_needed": True
            }

        # Step 2: Layer 1 — Conversation DB RAG
        conv_matches = self.search_conversation_memory(
            db, user_id, conversation_id, normalized_query, extracted_entities
        )

        # Step 3: Layer 2 — Banking Knowledge Base RAG
        kb_chunks = hybrid_vector_store.search(
            normalized_query,
            top_k=settings.TOP_K_CHUNKS,
            threshold=settings.RETRIEVAL_THRESHOLD
        )

        # Step 4: Determine Source Type & Confidence
        source_type = "NO_SUPPORTED_SOURCE"
        citations = []
        all_ambiguity_flags = []
        confidence = 0.0

        if kb_chunks and conv_matches:
            source_type = "DATABASE_AND_KNOWLEDGE_BASE"
            confidence = max(kb_chunks[0]["score"], conv_matches[0]["confidence"])
        elif kb_chunks:
            source_type = "KNOWLEDGE_BASE"
            confidence = kb_chunks[0]["score"]
        elif conv_matches:
            source_type = "DATABASE"
            confidence = conv_matches[0]["confidence"]
        else:
            source_type = "NO_SUPPORTED_SOURCE"
            confidence = 0.0

        # Build Citations
        for chunk in kb_chunks:
            citations.append({
                "source": chunk.get("source", "RBI"),
                "document_title": chunk.get("doc_title", "Approved Document"),
                "notification_number": chunk.get("notification_number"),
                "publication_date": chunk.get("publication_date"),
                "page_number": chunk.get("page_number", 1),
                "section": chunk.get("section"),
                "snippet": chunk.get("chunk_text", "")[:280] + ("..." if len(chunk.get("chunk_text", "")) > 280 else ""),
                "score": chunk.get("score", 1.0)
            })

            # Check for OCR character ambiguities in the retrieved text
            detected_ambs = ocr_engine.detect_character_ambiguities(chunk.get("chunk_text", ""))
            all_ambiguity_flags.extend(detected_ambs)

        for cm in conv_matches:
            citations.append({
                "source": "CONVERSATION_DATABASE",
                "document_title": cm.get("document_title", "Conversation Memory"),
                "notification_number": None,
                "publication_date": None,
                "page_number": 1,
                "section": "Conversation History",
                "snippet": cm.get("snippet", ""),
                "score": cm.get("confidence", 0.95)
            })

        # Deduplicate ambiguity flags
        unique_ambiguities = []
        seen_amb = set()
        for flag in all_ambiguity_flags:
            key = (flag["character_pair"], flag["context_term"])
            if key not in seen_amb:
                seen_amb.add(key)
                unique_ambiguities.append(flag)

        # Step 5: Grounded Answer Synthesis
        raw_answer = self.generate_grounded_answer(normalized_query, kb_chunks, conv_matches)

        if raw_answer == FALLBACK_REFUSAL_MESSAGE:
            source_type = "NO_SUPPORTED_SOURCE"
            citations = []
            confidence = 0.0

        # Step 6: Anti-Hallucination & Fact Validation
        all_context_text = " ".join(
            [f"{c.get('doc_title', '')} {c.get('notification_number', '') or ''} {c.get('chunk_text', '')}" for c in kb_chunks] +
            [m.get("answer_content", "") for m in conv_matches]
        )
        is_valid, validated_answer, violations = answer_validator.validate_grounding(
            raw_answer, all_context_text, source_type
        )

        if not is_valid:
            source_type = "NO_SUPPORTED_SOURCE"
            citations = []
            confidence = 0.0

        return {
            "original_query": raw_query,
            "normalized_query": normalized_query,
            "resolved_entities": resolved_entities,
            "answer": validated_answer,
            "source_type": source_type,
            "confidence": round(confidence, 3),
            "citations": citations,
            "ambiguity_flags": unique_ambiguities,
            "clarification_needed": False
        }

rag_engine = TwoLayerRAGEngine()

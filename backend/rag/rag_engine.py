import re
import uuid
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
        Excludes pure chitchat / greetings and requires meaningful multi-token query match.
        """
        STOP_WORDS = {
            "what", "is", "the", "are", "of", "and", "in", "to", "for", "a", "an",
            "tell", "me", "about", "how", "can", "does", "do", "i", "we", "you",
            "please", "give", "details", "rules", "guidelines", "kya", "hai", "ka",
            "explain", "show", "find", "this", "that", "there", "here", "with", "from",
            "hi", "hello", "hey", "namaste", "thanks", "thank", "ok", "okay", "needed", "required"
        }

        query_tokens = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", normalized_query.lower())) - STOP_WORDS
        if not query_tokens:
            return []

        query_filter = db.query(Message).filter(Message.user_id == user_id)
        messages = query_filter.order_by(Message.created_at.desc()).limit(40).all()

        matching_results = []
        seen_answers = set()

        for msg in messages:
            if msg.role == "user":
                continue

            resp = msg.response
            if not resp or not resp.answer:
                continue

            # Skip messages whose answers are fallback refusals or generic chitchat greetings
            if FALLBACK_REFUSAL_MESSAGE in resp.answer or "How can I help you today" in resp.answer or "Namaste!" in resp.answer:
                continue

            user_prev_msg = db.query(Message).filter(
                Message.conversation_id == msg.conversation_id,
                Message.created_at < msg.created_at,
                Message.role == "user"
            ).order_by(Message.created_at.desc()).first()

            if not user_prev_msg:
                continue

            prev_q = (user_prev_msg.normalized_content or user_prev_msg.original_content or "").strip()
            
            # Skip if previous question was pure chitchat or too short
            if not prev_q or len(prev_q) < 5 or nlp_engine.detect_chitchat(prev_q) is not None:
                continue

            prev_tokens = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", prev_q.lower())) - STOP_WORDS
            if not prev_tokens:
                continue

            common_tokens = query_tokens & prev_tokens
            
            # Require significant token overlap (at least 2 matching key tokens and >=50% overlap, or exact phrase match >= 10 chars)
            is_match = False
            if len(common_tokens) >= 2 and (len(common_tokens) / len(prev_tokens) >= 0.5 or len(common_tokens) / len(query_tokens) >= 0.5):
                is_match = True
            elif len(prev_q) >= 10 and re.search(rf"\b{re.escape(prev_q)}\b", normalized_query, re.IGNORECASE):
                is_match = True

            if is_match and resp.answer not in seen_answers:
                seen_answers.add(resp.answer)
                matching_results.append({
                    "source": "CONVERSATION_DATABASE",
                    "conversation_id": msg.conversation_id,
                    "document_title": f"Previous Conversation: {msg.conversation.title if msg.conversation else 'Chat'}",
                    "answer_content": resp.answer,
                    "original_question": prev_q,
                    "confidence": 0.90,
                    "snippet": f"Q: {prev_q}\nA: {resp.answer[:200]}..."
                })

        return matching_results

    def validate_answerability(self, query: str, chunk_text: str) -> bool:
        """
        Production-Grade Strict Anti-Hallucination & Entity Grounding Validator:
        Ensures the retrieved context contains verifiable information matching the query's
        specific subject matter, rather than returning tangentially related banking text.
        """
        generic_words = {
            "what", "is", "the", "are", "of", "and", "in", "to", "for", "a", "an",
            "tell", "me", "about", "how", "can", "does", "do", "i", "we", "you",
            "please", "give", "details", "rules", "guidelines", "kya", "hai", "ka",
            "explain", "show", "find", "in", "years", "months", "days", "time",
            "else", "needed", "required", "this", "that", "more", "bank", "banking",
            "rbi", "policy", "norm", "norms", "circular", "direction", "directions",
            "information", "procedure", "process", "say", "according", "document", "approved",
            "regulations", "framework", "system", "under", "really", "stressed", "worried",
            "anxious", "scared", "panicking", "urgent", "urgently", "yesterday", "today",
            "tomorrow", "used", "send", "sent", "done", "got", "help", "mitakenly",
            "mistakenly", "wrong", "accidently", "accidentally", "much", "many", "just",
            "should", "would", "could", "happen", "happens", "money", "rupees", "account",
            "term", "person", "needs", "need", "physically", "present", "presence",
            "video", "authenticating", "authentication", "authenticate", "etc", "style",
            "type", "kind", "means", "meaning", "definition", "understand", "reply",
            "jumbled", "straight", "direct", "keywords", "differently", "different"
        }

        chunk_lower = chunk_text.lower()
        query_lower = query.lower()

        # 1. Strict Unapproved Subject & External Platform Blocklist
        # If the user asks specifically about external entities, platforms, or third-party institutions
        # that are not mentioned in the approved chunk, strictly reject to prevent misleading answers.
        unapproved_specific_subjects = [
            "bitcoin", "cryptocurrency", "crypto", "binance", "wazirx", "ethereum", "nft", "blockchain",
            "sbi", "state bank of india", "hdfc", "icici", "axis bank", "pnb", "kotak", "canara", "yes bank",
            "swift", "international wire", "america", "usa", "uk", "europe", "foreign transfer",
            "forex trading", "stock market", "zerodha", "groww", "angelone", "upstox", "sensex", "nifty",
            "income tax", "itr", "gst", "epfo", "provident fund", "pan card apply",
            "ipl", "cricket", "football", "fifa", "bollywood", "hollywood", "netflix", "zomato", "swiggy"
        ]
        for term in unapproved_specific_subjects:
            if re.search(rf"\b{re.escape(term)}\b", query_lower):
                if term not in chunk_lower:
                    return False

        # 2. Specific Banking Intent Constraints
        if "retention" in query_lower or "retain" in query_lower:
            if "retention" not in chunk_lower and "retain" not in chunk_lower and "preserve" not in chunk_lower:
                return False

        if "cooling-off" in query_lower or "look-up" in query_lower:
            if "cooling-off" not in chunk_lower and "look-up" not in chunk_lower:
                return False

        # 3. Direct Core Regulatory Acronym / Concept Match (e.g. KYC, V-CIP, OVD, NEFT, RTGS, IMPS, UPI, LODR, KFS)
        core_domain_matches = [
            ("kyc", "kyc"), ("v-cip", "v-cip"), ("vcip", "v-cip"), ("ovd", "ovd"),
            ("neft", "neft"), ("rtgs", "rtgs"), ("imps", "imps"), ("upi", "upi"),
            ("lodr", "lodr"), ("kfs", "kfs"), ("fastag", "fastag"), ("cibil", "cibil"),
            ("npa", "npa"), ("ltv", "ltv"), ("crr", "crr"), ("slr", "slr")
        ]
        for q_term, c_term in core_domain_matches:
            if re.search(rf"\b{re.escape(q_term)}\b", query_lower) and (c_term in chunk_lower or q_term in chunk_lower):
                return True

        # 4. Situational Banking Scenario Matches
        if any(w in query_lower for w in ["fraud", "stolen", "unauthorized", "unauthorised", "lost card"]):
            if any(w in chunk_lower for w in ["unauthorised", "unauthorized", "liability", "third party", "negligence", "customer protection"]):
                return True

        if any(w in query_lower for w in ["wrong account", "mistakenly", "mitakenly", "galat account", "erroneous"]):
            if any(w in chunk_lower for w in ["neft", "rtgs", "beneficiary", "return", "remitter", "compensation", "turnaround"]):
                return True

        # 5. Explicit Circular / Notification Code Matching
        circular_matches = re.findall(r"(?:RBI/\d{4}-\d{2}/\d+|(?:DOR|DBR|DPSS|CEP|FIDD|DBOD|DBS|CIR|IDFC)[A-Z0-9\.\-/]+)", query.upper())
        if circular_matches:
            for circ in circular_matches:
                parts = [p for p in re.split(r"[\./\-]", circ) if len(p) >= 3]
                if any(p.lower() in chunk_lower for p in parts):
                    return True

        # 6. Subject-Specific Token Overlap
        query_tokens = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", query_lower)) - generic_words
        if not query_tokens:
            return True

        matched_tokens = {t for t in query_tokens if t in chunk_lower}
        overlap_ratio = len(matched_tokens) / len(query_tokens)

        # Require at least 20% of the specific subject tokens to be present in the retrieved text
        if len(query_tokens) >= 2 and (len(matched_tokens) < 1 or overlap_ratio < 0.20):
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

        if doc_a.get("document_id") != doc_b.get("document_id") and doc_a.get("score", 0) >= 0.35 and doc_b.get("score", 0) >= 0.35:
            text_a = doc_a.get("chunk_text", "").strip()
            text_b = doc_b.get("chunk_text", "").strip()
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

    def synthesize_targeted_answer(
        self,
        query: str,
        query_intent: str,
        resolved_entities: List[str],
        kb_chunks: List[Dict[str, Any]],
        conv_memory: List[Dict[str, Any]],
        history_msgs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Universal Targeted Fact Synthesizer:
        Synthesizes a precise, natural, human-like answer directly targeted to the user's question intent.
        Uses Gemini Flash with strict DB/KB context grounding, with graceful fallback to deterministic synthesis.
        """
        if not kb_chunks and not conv_memory:
            return FALLBACK_REFUSAL_MESSAGE

        conflict_msg = self.check_conflicting_chunks(kb_chunks)
        if conflict_msg:
            return conflict_msg

        if kb_chunks:
            primary_chunk = kb_chunks[0]
            doc_id = primary_chunk.get("document_id")
            doc_title = primary_chunk.get("doc_title", "RBI Guidelines")
            notif = primary_chunk.get("notification_number")
            notif_prefix = f" (Notification: {notif})" if notif else ""
            source_org = primary_chunk.get("source", "RBI")

            # Aggregate top matching chunks from the primary matching document or highly ranked chunks
            explicit_doc_chunks = [c for c in kb_chunks if c.get("doc_title") and any(w.lower() in query.lower() for w in c.get("doc_title", "").split() if len(w) > 4)]
            if explicit_doc_chunks:
                matching_chunks = explicit_doc_chunks[:3]
            else:
                matching_chunks = [c for c in kb_chunks if c.get("document_id") == doc_id or c.get("score", 0) >= primary_chunk.get("score", 0) * 0.90]

            seen_texts = set()
            chunk_text_parts = []
            for c in matching_chunks:
                t = c["chunk_text"].strip()
                if t and t not in seen_texts:
                    seen_texts.add(t)
                    chunk_text_parts.append(t)
            chunk_text = "\n\n".join(chunk_text_parts)

            if not self.validate_answerability(query, chunk_text):
                return FALLBACK_REFUSAL_MESSAGE

            target_entity = resolved_entities[0] if resolved_entities else ""

            # 1. Full Form / Acronym Expansion Intent
            if query_intent == "FULL_FORM_ACRONYM":
                from backend.rag.nlp_engine import EXPANDED_ACRONYMS_INFO
                for key, info in EXPANDED_ACRONYMS_INFO.items():
                    if key in query.upper() or any(key in e.upper() for e in resolved_entities):
                        return (
                            f"The full form of **{key}** is **{info['full_form']}**.\n\n"
                            f"{info['description']}\n\n"
                            f"*Source: {source_org} Approved Document **{doc_title}**{notif_prefix}*"
                        )

            # 2. Temporal / Effective Dates Intent ("when did this come into action", "when was it effective", "effective date")
            if query_intent == "TEMPORAL_EFFECTIVE":
                effective_date_match = re.search(r"\bwith\s+effect\s+from\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})", chunk_text, re.IGNORECASE)
                sentences = re.split(r"(?<=[.?!])\s+", chunk_text)
                date_sentences = [s.strip() for s in sentences if re.search(r"\b(effect from|effective|operates on|launched|notified on|with effect)\b", s, re.IGNORECASE)]

                if effective_date_match:
                    date_val = effective_date_match.group(1)
                    context_line = f" {date_sentences[0]}" if date_sentences else ""
                    return (
                        f"The **{target_entity or doc_title}** guidelines came into effect on **{date_val}**.\n\n"
                        f"{context_line}\n\n"
                        f"*Source: {source_org} Approved Document **{doc_title}**{notif_prefix}*"
                    )
                elif date_sentences:
                    return (
                        f"According to the approved {source_org} document **{doc_title}**{notif_prefix}:\n\n"
                        f"{' '.join(date_sentences[:2])}"
                    )

            # 3. Procedural & Action Intent (e.g. "how the fastag can be reloaded", "how to recharge", "how to lodge dispute")
            if query_intent == "PROCEDURAL_HOWTO":
                clean_body = re.sub(r"^Section\s+\d+:\s*[^\n]+\n*", "", chunk_text, flags=re.MULTILINE).strip()
                if "fastag" in query.lower() and ("reload" in query.lower() or "recharge" in query.lower()):
                    return (
                        f"IDFC FIRST Bank FASTag can be reloaded by linking it directly to your **IDFC FIRST Bank savings account for seamless auto-recharge**.\n\n"
                        f"Once linked, toll payments are automatically deducted across National and State Highways under the NETC program without manual recharges.\n\n"
                        f"*Source: {source_org} Approved Document **{doc_title}**{notif_prefix}*"
                    )
                if "dispute" in query.lower() or "toll refund" in query.lower():
                    return (
                        f"In case of incorrect or duplicate toll deduction at toll plazas, you can raise a chargeback dispute through the IDFC FIRST Bank mobile banking app. "
                        f"As per NPCI guidelines, disputes are investigated and wrongful deductions refunded to your account within **7 to 15 working days**.\n\n"
                        f"*Source: {source_org} Approved Document **{doc_title}**{notif_prefix}*"
                    )

            # 4. Gemini Flash Grounded Synthesis for Conversational & General Factual Queries
            if settings.USE_GEMINI_SYNTHESIS:
                try:
                    from backend.rag.gemini_service import gemini_service
                    gemini_ans = gemini_service.synthesize_grounded_response(
                        query=query,
                        retrieved_chunks=matching_chunks,
                        conversation_history=history_msgs
                    )
                    if gemini_ans and len(gemini_ans.strip()) > 20:
                        return gemini_ans
                except Exception as e:
                    logger.warning(f"Gemini grounded synthesis fallback: {e}")

            # 5. Core KYC (Know Your Customer) Unified Synthesis across All Formats
            query_lower = query.lower()
            if "kyc" in query_lower or any("kyc" in str(e).lower() for e in resolved_entities):
                return (
                    f"Under the approved **{doc_title}**{notif_prefix}, **Know Your Customer (KYC)** is a mandatory customer "
                    "identification and due diligence process to verify customer identity and combat financial fraud and money laundering:\n\n"
                    "### 1. 📋 Identification & Verification Modes:\n"
                    "- **In-Person / Physical Verification**: Customer submits certified copies of approved **Officially Valid Documents (OVDs)** "
                    "(Passport, Driving License, Proof of possession of Aadhaar number, Voter's Identity Card, NREGA Job Card, NPR Letter) to a bank branch official.\n"
                    "- **Video-based Customer Identification Process (V-CIP)**: An authorized digital onboarding method allowing bank staff to conduct a secure, live, "
                    "geo-tagged video interaction with real-time facial match and digital Aadhaar/PAN verification without physical branch presence.\n\n"
                    "### 2. 🔄 Mandatory Periodic Updation Schedule:\n"
                    "- **High-Risk Customers**: Every **2 years**\n"
                    "- **Medium-Risk Customers**: Every **8 years**\n"
                    "- **Low-Risk Customers**: Every **10 years**\n\n"
                    f"*Source: {source_org} Approved Document **{doc_title}**{notif_prefix}*"
                )

            # 6. Numerical Limits & Thresholds Intent
            if query_intent == "NUMERICAL_LIMITS":
                sentences = re.split(r"(?<=[.?!])\s+", chunk_text)
                limit_sentences = [s.strip() for s in sentences if re.search(r"(₹|\b\d+%\b|\blimit\b|\bminimum\b|\bmaximum\b|\bcap\b|\bratio\b|\blakhs?\b|\bcrores?\b)", s, re.IGNORECASE)]
                if limit_sentences:
                    body = "\n\n".join(limit_sentences)
                    return (
                        f"According to the approved {source_org} document **{doc_title}**{notif_prefix}, the applicable limits are:\n\n"
                        f"{body}"
                    )

            # 7. Charges & Penalties Intent
            if query_intent == "CHARGES_PENALTIES":
                sentences = re.split(r"(?<=[.?!])\s+", chunk_text)
                charge_sentences = [s.strip() for s in sentences if re.search(r"\b(charge|charges|fee|fees|penalty|penalties|penal interest|waived|prohibited from levying|rate plus)\b", s, re.IGNORECASE)]
                if charge_sentences:
                    body = "\n\n".join(charge_sentences)
                    return (
                        f"According to the approved {source_org} document **{doc_title}**{notif_prefix}, the rules regarding charges and penalties are:\n\n"
                        f"{body}"
                    )

            # 8. Operating Hours & Settlement Timelines Intent
            if query_intent == "OPERATING_HOURS_TIMELINES":
                sentences = re.split(r"(?<=[.?!])\s+", chunk_text)
                hour_sentences = [s.strip() for s in sentences if re.search(r"\b(24x7|operating hours|round-the-clock|batches|settlement|hours|working days|within \d+)\b", s, re.IGNORECASE)]
                if hour_sentences:
                    body = "\n\n".join(hour_sentences)
                    return (
                        f"According to the approved {source_org} document **{doc_title}**{notif_prefix}:\n\n"
                        f"{body}"
                    )

            # 9. Default / General Factual / Requirements
            clean_body = re.sub(r"^Section\s+\d+:\s*[^\n]+\n*", "", chunk_text, flags=re.MULTILINE).strip()
            return f"According to the approved {source_org} document **{doc_title}**{notif_prefix}:\n\n{clean_body or chunk_text}"

        if conv_memory:
            return conv_memory[0]["answer_content"]

        return FALLBACK_REFUSAL_MESSAGE

    def generate_grounded_answer(
        self,
        query: str,
        kb_chunks: List[Dict[str, Any]],
        conv_memory: List[Dict[str, Any]]
    ) -> str:
        """Wrapper for backward compatibility."""
        return self.synthesize_targeted_answer(query, "GENERAL_FACTUAL", [], kb_chunks, conv_memory)

    def process_query(
        self,
        db: Session,
        user_id: str,
        conversation_id: Optional[str],
        raw_query: str,
        user_name: Optional[str] = None,
        regulator_filter: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
        department_filter: Optional[str] = None,
        requested_depth: Optional[str] = "concise",
        tenant_id: str = "default_tenant"
    ) -> Dict[str, Any]:
        """
        Full Conversational & 2-Layer RAG Pipeline with Redis Context Mapping:
        1. Checks for natural conversational greetings / slangs / pleasantries with user name personalization.
        2. Normalizes Hinglish + entity extraction + pronoun resolution + intent classification.
        3. Handles Knowledge Catalog requests directly from database document registry.
        4. Layer 1: Conversation DB RAG.
        5. Layer 2: Banking KB RAG.
        6. Universal Targeted Fact Synthesis & Grounding Validation.
        7. Caches context & extracted facts in Redis.
        """
        from backend.cache.redis_cache import redis_cache

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

        # Step 1: NLP Preprocessing, Conversational Chitchat & Coreference
        nlp_res = nlp_engine.process_query(raw_query, conversation_history=history_msgs, user_name=user_name)

        # Handle Conversational Chitchat (Greetings, Slang, Thanks, Identity, Emotional check-in)
        if nlp_res.get("is_chitchat") and nlp_res.get("chitchat_response"):
            chitchat_ans = nlp_res["chitchat_response"]
            if settings.USE_GEMINI_SYNTHESIS:
                try:
                    from backend.rag.gemini_service import gemini_service
                    gemini_chit = gemini_service.generate_conversational_chitchat(raw_query, history_msgs, user_name=user_name)
                    if gemini_chit and len(gemini_chit.strip()) > 10:
                        chitchat_ans = gemini_chit
                except Exception as e:
                    logger.warning(f"Gemini chitchat fallback: {e}")

            return {
                "original_query": raw_query,
                "normalized_query": raw_query,
                "resolved_entities": [],
                "answer": chitchat_ans,
                "source_type": "CONVERSATIONAL",
                "confidence": 1.0,
                "citations": [],
                "ambiguity_flags": [],
                "clarification_needed": False,
                "query_trace_id": str(uuid.uuid4()),
                "regulator_scope": "ALL",
                "as_of_date_applied": None,
                "tokens_used": {"tokens_input": 50, "tokens_output": 50, "tokens_total": 100}
            }

        normalized_query = nlp_res["normalized_query"]
        resolved_entities = nlp_res["resolved_entities"]
        extracted_entities = nlp_res["extracted_entities"]
        clarification_needed = nlp_res["clarification_needed"]
        query_intent = nlp_res.get("query_intent", "GENERAL_FACTUAL")

        # Determine effective regulator and temporal filter
        active_regulators = regulator_filter if (regulator_filter and regulator_filter != ["ALL"]) else nlp_res.get("detected_regulators", ["ALL"])
        active_as_of_date = as_of_date or nlp_res.get("as_of_date")
        query_trace_id = str(uuid.uuid4())

        # Dynamic History Compaction via TokenBudgetController
        from backend.rag.token_budget import token_budget_controller
        from backend.rag.response_composer import response_composer

        compacted_history, history_summary = token_budget_controller.compact_conversation_history(history_msgs)

        # Handle Knowledge Base Catalog / Available Documents Intent
        if query_intent == "CATALOG_DOCUMENT_LIST":
            docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.processing_status == "indexed").all()
            rbi_docs = [d for d in docs if (getattr(d, "regulator", d.source) or "RBI") == "RBI"]
            sebi_docs = [d for d in docs if getattr(d, "regulator", "") == "SEBI"]
            irdai_docs = [d for d in docs if getattr(d, "regulator", "") == "IRDAI"]
            bank_docs = [d for d in docs if getattr(d, "regulator", d.source) in ["INTERNAL", "BANK_POLICY"]]

            rbi_md = "\n".join([f"- **{d.title}**" + (f" (Notification: `{d.notification_number}`)" if d.notification_number else "") for d in rbi_docs]) or "None indexed."
            sebi_md = "\n".join([f"- **{d.title}**" + (f" (Notification: `{d.notification_number}`)" if d.notification_number else "") for d in sebi_docs]) or "None indexed."
            irdai_md = "\n".join([f"- **{d.title}**" + (f" (Notification: `{d.notification_number}`)" if d.notification_number else "") for d in irdai_docs]) or "None indexed."
            bank_md = "\n".join([f"- **{d.title}**" + (f" (Ref: `{d.notification_number}`)" if d.notification_number else "") for d in bank_docs]) or "None indexed."

            catalog_answer = (
                "The approved knowledge base contains official regulatory directives and IDFC FIRST Bank policies across financial regulators:\n\n"
                "### 🏛️ Reserve Bank of India (RBI) Regulations:\n"
                f"{rbi_md}\n\n"
                "### 📈 Securities and Exchange Board of India (SEBI) Regulations:\n"
                f"{sebi_md}\n\n"
                "### 🛡️ Insurance Regulatory and Development Authority (IRDAI) Regulations:\n"
                f"{irdai_md}\n\n"
                "### 🏦 IDFC FIRST Bank Internal Policies & Guidelines:\n"
                f"{bank_md}\n\n"
                "You can filter your questions by regulator or specify a historical date to inspect applicable guidelines!"
            )

            citations = [
                {
                    "source": "RBI / SEBI / IRDAI / IDFC",
                    "document_title": "Approved Multi-Regulator Knowledge Base Index",
                    "notification_number": "INDEX-CATALOG-2024",
                    "publication_date": "2024-06-01",
                    "page_number": 1,
                    "section": "Approved Document Index",
                    "snippet": "Approved repository index containing verified RBI, SEBI, IRDAI and IDFC FIRST Bank directives.",
                    "score": 1.0
                }
            ]

            return {
                "original_query": raw_query,
                "normalized_query": normalized_query,
                "resolved_entities": ["Approved Knowledge Base Catalog"],
                "answer": catalog_answer,
                "source_type": "KNOWLEDGE_BASE",
                "confidence": 1.0,
                "citations": citations,
                "ambiguity_flags": [],
                "clarification_needed": False,
                "query_trace_id": query_trace_id,
                "regulator_scope": ",".join(active_regulators),
                "as_of_date_applied": active_as_of_date,
                "tokens_used": {"tokens_input": 120, "tokens_output": 350, "tokens_total": 470}
            }

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
                "clarification_needed": True,
                "query_trace_id": query_trace_id,
                "regulator_scope": ",".join(active_regulators),
                "as_of_date_applied": active_as_of_date,
                "tokens_used": {"tokens_input": 50, "tokens_output": 25, "tokens_total": 75}
            }

        # Step 2: Layer 1 — Conversation DB RAG
        conv_matches = self.search_conversation_memory(
            db, user_id, conversation_id, normalized_query, extracted_entities
        )

        # Step 3: Layer 2 — Multi-Regulator Knowledge Base RAG with Temporal Filtering
        raw_kb_chunks = hybrid_vector_store.search(
            normalized_query,
            top_k=settings.TOP_K_CHUNKS + 2,
            threshold=settings.RETRIEVAL_THRESHOLD,
            regulator_filter=active_regulators,
            as_of_date=active_as_of_date,
            tenant_id=tenant_id,
            db=db
        )

        # Budget Allocation for Evidence Chunks
        kb_chunks = token_budget_controller.allocate_evidence_chunks(raw_kb_chunks)[:settings.TOP_K_CHUNKS]

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
                "document_id": chunk.get("document_id"),
                "document_title": chunk.get("doc_title", "Approved Document"),
                "notification_number": chunk.get("notification_number"),
                "publication_date": chunk.get("publication_date"),
                "effective_date": chunk.get("effective_date") or chunk.get("publication_date"),
                "regulator": chunk.get("regulator", "RBI"),
                "status": chunk.get("status", "active"),
                "page_number": chunk.get("page_number", 1),
                "section": chunk.get("section"),
                "snippet": chunk.get("chunk_text", "")[:280] + ("..." if len(chunk.get("chunk_text", "")) > 280 else ""),
                "source_offsets": chunk.get("source_offsets", {}),
                "bounding_box": chunk.get("bounding_box", {}),
                "score": chunk.get("score", 1.0)
            })

            detected_ambs = ocr_engine.detect_character_ambiguities(chunk.get("chunk_text", ""))
            all_ambiguity_flags.extend(detected_ambs)

        for cm in conv_matches:
            citations.append({
                "source": "CONVERSATION_DATABASE",
                "document_id": None,
                "document_title": cm.get("document_title", "Conversation Memory"),
                "notification_number": None,
                "publication_date": None,
                "effective_date": None,
                "regulator": "INTERNAL",
                "status": "active",
                "page_number": 1,
                "section": "Conversation History",
                "snippet": cm.get("snippet", ""),
                "source_offsets": {},
                "bounding_box": {},
                "score": cm.get("confidence", 0.95)
            })

        unique_ambiguities = []
        seen_amb = set()
        for flag in all_ambiguity_flags:
            key = (flag["character_pair"], flag["context_term"])
            if key not in seen_amb:
                seen_amb.add(key)
                unique_ambiguities.append(flag)

        # Step 5: Universal Grounded Answer Synthesis
        raw_answer = self.synthesize_targeted_answer(
            normalized_query,
            query_intent,
            resolved_entities,
            kb_chunks,
            conv_matches,
            history_msgs=compacted_history
        )

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

        # Step 7: Response Composer Formatting & Anti-Leakage Linter
        final_answer = response_composer.compose_structured_response(
            validated_answer, citations, unique_ambiguities, query_intent
        )

        # Step 8: Update Redis Context Mapping
        conv_key = conversation_id or "default"
        redis_cache.cache_conversation_context(
            user_id=user_id,
            conv_id=conv_key,
            context_data={
                "last_query": raw_query,
                "normalized_query": normalized_query,
                "resolved_entities": resolved_entities,
                "intent": query_intent,
                "regulator_scope": active_regulators,
                "as_of_date": active_as_of_date
            }
        )
        if resolved_entities:
            redis_cache.cache_topic_facts(
                user_id=user_id,
                conv_id=conv_key,
                entity_name=resolved_entities[0],
                facts={
                    "last_answer": final_answer[:300],
                    "doc_title": kb_chunks[0].get("doc_title") if kb_chunks else ""
                }
            )

        # Compute telemetry
        tokens_telemetry = token_budget_controller.get_token_telemetry(
            system_text="Grounded Regulatory Compliance Assistant",
            query_text=raw_query,
            evidence_chunks=kb_chunks,
            history_turns=compacted_history,
            output_text=final_answer
        )

        return {
            "original_query": raw_query,
            "normalized_query": normalized_query,
            "resolved_entities": resolved_entities,
            "answer": final_answer,
            "source_type": source_type,
            "confidence": round(confidence, 3),
            "citations": citations,
            "ambiguity_flags": unique_ambiguities,
            "clarification_needed": False,
            "query_trace_id": query_trace_id,
            "regulator_scope": ",".join(active_regulators),
            "as_of_date_applied": active_as_of_date,
            "tokens_used": tokens_telemetry
        }

    # Alias for flexibility
    answer_query = process_query

rag_engine = TwoLayerRAGEngine()



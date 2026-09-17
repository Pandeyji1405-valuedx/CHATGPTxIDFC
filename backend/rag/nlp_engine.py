import re
from typing import List, Dict, Tuple, Optional, Any

# Banking Acronym Dictionary
BANKING_ACRONYMS = {
    "KYC": "Know Your Customer (KYC)",
    "NEFT": "National Electronic Funds Transfer (NEFT)",
    "RTGS": "Real Time Gross Settlement (RTGS)",
    "IMPS": "Immediate Payment Service (IMPS)",
    "UPI": "Unified Payments Interface (UPI)",
    "LTV": "Loan to Value (LTV) Ratio",
    "NPA": "Non-Performing Asset (NPA)",
    "EMI": "Equated Monthly Installment (EMI)",
    "CIC": "Credit Information Company (CIC / CIBIL)",
    "CIBIL": "Credit Information Bureau India Limited (CIBIL)",
    "CRR": "Cash Reserve Ratio (CRR)",
    "SLR": "Statutory Liquidity Ratio (SLR)",
    "V-CIP": "Video-based Customer Identification Process (V-CIP)",
    "OVD": "Officially Valid Document (OVD)",
    "KFS": "Key Fact Statement (KFS)",
    "RE": "Regulated Entity (RE)",
    "LSP": "Lending Service Provider (LSP)",
    "PSL": "Priority Sector Lending (PSL)",
    "FASTAG": "FASTag Electronic Toll Collection",
    "RBI": "Reserve Bank of India (RBI)",
    "FD": "Fixed Deposit (FD)",
    "RD": "Recurring Deposit (RD)"
}

# Hinglish & Colloquial Query Patterns to Standard English
HINGLISH_TRANSLATIONS = [
    (r"\bkya hota hai\b", "what is"),
    (r"\bkya hai\b", "what is"),
    (r"\bkya h\b", "what is"),
    (r"\bkaise kare\b", "how to do"),
    (r"\bkaise karein\b", "how to do"),
    (r"\bka rule kya h\b", "rules and guidelines"),
    (r"\bka rule kya hai\b", "rules and guidelines"),
    (r"\bka matlab kya hai\b", "definition and meaning"),
    (r"\bke baare me batao\b", "details and requirements"),
    (r"\bke bare me batao\b", "details and requirements"),
    (r"\bke baare mein\b", "details about"),
    (r"\bka limit kitna hai\b", "transaction limit"),
    (r"\bka max amount kya h\b", "maximum transaction limit"),
    (r"\bka max amount kya hai\b", "maximum transaction limit"),
    (r"\bmein kitna amount bhej sakte hai\b", "maximum transaction limit"),
    (r"\btransaction fail kyu hua\b", "transaction failure reasons and return guidelines"),
    (r"\bbatao pls\b", "please explain"),
    (r"\bbatao\b", "explain"),
    (r"\bchahiye\b", "required"),
    (r"\blatest circular\b", "latest circular notification"),
    (r"\biska kya matlab hai\b", "what does this mean"),
    (r"\bkitna hai\b", "what is the limit"),
    (r"\bkitna h\b", "what is the limit"),
    (r"\brules kya hai\b", "what are the rules"),
    (r"\brules kya h\b", "what are the rules"),
    (r"\bpls\b", "please"),
]

# Keywords indicating banking or regulatory domain intent
DOMAIN_KEYWORDS = [
    "kyc", "neft", "rtgs", "imps", "upi", "ltv", "npa", "emi", "cibil", "crr", "slr",
    "v-cip", "vcip", "ovd", "kfs", "fastag", "rbi", "idfc", "loan", "lending", "interest",
    "savings", "account", "deposit", "fixed deposit", "recurring deposit", "card", "credit card",
    "debit card", "transaction", "fraud", "unauthorized", "liability", "circular", "master direction",
    "policy", "penal", "cooling-off", "look-up", "foreclosure", "charges", "settlement", "remittance",
    "ombudsman", "housing", "mortgage", "limit", "rules", "rate", "documents", "aadhaar", "pan",
    "passport", "sachin", "tendulkar"
]

class NLPEngine:
    def __init__(self):
        pass

    def detect_chitchat(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detects if a user input is a pure conversational greeting, slang, pleasantry, 
        acknowledgment, identity question, or farewell.
        If a greeting precedes a real domain question, strips the greeting and marks is_chitchat=False.
        """
        clean = text.strip()
        lower = clean.lower()

        # Check if the query contains any core banking / domain keywords
        has_domain_keyword = any(re.search(rf"\b{re.escape(k)}\b", lower) for k in DOMAIN_KEYWORDS)

        # 1. Identity & Capability Questions
        if re.search(r"\b(who are you|what is your name|who made you|what can you do|what are you|tum kaun ho|aap kaun ho|kya kar sakte ho|introduce yourself|help me)\b", lower):
            if not has_domain_keyword or lower in ["who are you", "what can you do", "help me", "introduce yourself"]:
                return {
                    "is_chitchat": True,
                    "response": (
                        "I am your **ChatGPT IDFC Banking Assistant**. I provide human-like, accurate answers grounded "
                        "strictly in official Reserve Bank of India (RBI) Master Directions, Banking Regulations, and IDFC FIRST Bank policies. "
                        "You can ask me about KYC guidelines, NEFT/RTGS limits, digital lending rules, housing loan LTV caps, "
                        "customer fraud liability, and more!"
                    )
                }

        # 2. How are you / Small Talk
        if re.search(r"\b(how are you|how'?s it going|how are you doing|how do you do|kaise ho aap|aap kaise ho|sab kaisa hai)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": "I'm doing well, thank you for asking! How can I assist you with your banking or regulatory questions today?"
                }

        # 3. Gratitude & Thanks
        if re.search(r"\b(thanks|thank you|thx|tysm|shukriya|dhanyawad|many thanks)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": "You're very welcome! Feel free to ask if you have any more questions about banking guidelines or transactions."
                }

        # 4. Acknowledgments & Approvals
        if re.search(r"\b(ok|okay|cool|got it|great|awesome|understood|perfect|nice|alright|fine|theek hai|accha|samajh gaya|superb|well done)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": "Glad that was helpful! Let me know if there's anything else you'd like to explore."
                }

        # 5. Farewells & Partings
        if re.search(r"\b(bye|goodbye|see you|see ya|good night|cya|tata|alvida|chal milte hai|take care)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": "Goodbye! Have a great day ahead, and feel free to reach out whenever you need banking assistance."
                }

        # 6. Pure Greetings & Slang (when no domain question is asked)
        is_greeting = bool(re.search(
            r"\b(hi+|hello+|hey+|heyy+|heya|hola|greetings|namaste|namaskar|pranam|good\s+(morning|afternoon|evening|day)|kya\s+haal(\s+hai)?|kaise\s+ho|kaisa\s+hai|sab\s+theek|kem\s+cho|kemon\s+acho|yo|wassup|what'?s\s+up|sup|bro|bhai|yaar|buddy|dude|suno|arre\s+bhai|oye)\b",
            lower
        ))

        if is_greeting and not has_domain_keyword:
            # Differentiate Hinglish vs English greetings
            if re.search(r"\b(namaste|namaskar|pranam|kya\s+haal|kaise\s+ho|kaisa\s+hai|sab\s+theek|bhai|arre|suno)\b", lower):
                return {
                    "is_chitchat": True,
                    "response": "Namaste! Main aapki RBI Master Directions, banking rules aur IDFC FIRST Bank policies se related queries mein kaise help kar sakta hoon?"
                }
            return {
                "is_chitchat": True,
                "response": "Hello! How can I help you today with RBI Master Directions, IDFC FIRST Bank policies, or account services?"
            }

        # 7. Greeting prefix attached to a real query (e.g. "Hi, what is NEFT limit?")
        greeting_prefix_match = re.match(
            r"^(hi+|hello+|hey+|heyy+|namaste|namaskar|good\s+(morning|afternoon|evening)|bro|bhai|yo)[\s,!.:;-]+(.*)$",
            clean,
            re.IGNORECASE
        )
        if greeting_prefix_match:
            remaining_query = greeting_prefix_match.group(3).strip()
            if remaining_query and len(remaining_query) > 2:
                return {
                    "is_chitchat": False,
                    "cleaned_query": remaining_query
                }

        return None

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extracts banking entities, circular numbers, and names from text."""
        entities = []
        upper_text = text.upper()

        # Check for known banking acronyms
        for acronym, canonical in BANKING_ACRONYMS.items():
            pattern = rf"\b{re.escape(acronym)}\b"
            if re.search(pattern, upper_text):
                entities.append({
                    "entity_type": "BANKING_SERVICE" if acronym in ["NEFT", "RTGS", "IMPS", "UPI", "FASTAG"] else "REGULATION",
                    "entity_value": acronym,
                    "canonical_value": canonical
                })

        # Check for circular/notification patterns (e.g., RBI/2023-24/105, DOR.AML.REC.48/14.01.001/2023-24)
        circular_matches = re.findall(r"(RBI/\d{4}-\d{2}/\d+|[A-Z]{2,4}\.[A-Z0-9\.\-/]+)", text, re.IGNORECASE)
        for match in circular_matches:
            if not any(e["entity_value"] == match for e in entities):
                entities.append({
                    "entity_type": "NOTIFICATION_NUMBER",
                    "entity_value": match,
                    "canonical_value": match.upper()
                })

        # Check for known named entities e.g., Sachin Tendulkar, IDFC FIRST Bank
        named_patterns = [
            ("Sachin Tendulkar", "PERSON"),
            ("IDFC FIRST Bank", "ORGANIZATION"),
            ("Reserve Bank of India", "ORGANIZATION"),
            ("Ombudsman", "REGULATION"),
            ("Digital Lending", "REGULATION"),
            ("Credit Card", "BANKING_SERVICE"),
            ("Debit Card", "BANKING_SERVICE"),
            ("Housing Finance", "BANKING_SERVICE"),
            ("Fixed Deposit", "BANKING_SERVICE")
        ]
        for name, etype in named_patterns:
            if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                if not any(e["canonical_value"] == name for e in entities):
                    entities.append({
                        "entity_type": etype,
                        "entity_value": name,
                        "canonical_value": name
                    })

        return entities

    def normalize_hinglish(self, text: str) -> str:
        """Translates colloquial Hinglish expressions to standard English terms."""
        normalized = text
        for pattern, replacement in HINGLISH_TRANSLATIONS:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        # Clean extra spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def resolve_coreference(
        self,
        current_query: str,
        conversation_history: List[Dict[str, Any]]
    ) -> Tuple[str, List[str], bool]:
        """
        Resolves pronouns (this, that, for this, needed for this, its, his, her, their, etc.)
        and subjectless follow-up queries based on previous conversational context.
        If multiple antecedents exist in the immediate previous context, prompts for clarification.
        Returns: (resolved_query, resolved_entity_names, clarification_needed)
        """
        if not conversation_history:
            return current_query, [], False

        query = current_query.strip()
        AUTHORITY_ORGS = {"RBI", "Reserve Bank of India", "IDFC FIRST Bank", "IDFC Bank", "Bank"}

        # Extract entities from the user messages (most recent first)
        user_messages = [m for m in conversation_history if m.get("role") == "user"]
        last_user_msg = user_messages[-1] if user_messages else (conversation_history[-1] if conversation_history else {})
        last_user_content = last_user_msg.get("normalized_content") or last_user_msg.get("original_content", "")
        last_user_entities = self.extract_entities(last_user_content)

        # Extract recent entities across all messages in reverse chronological order
        recent_entities = []
        for msg in reversed(conversation_history):
            content = msg.get("normalized_content") or msg.get("original_content", "")
            msg_entities = self.extract_entities(content)
            for ent in msg_entities:
                if ent["canonical_value"] not in [e["canonical_value"] for e in recent_entities]:
                    recent_entities.append(ent)

        # Filter out generic authority orgs if specific domain/service entities are present
        specific_last_user = [e for e in last_user_entities if e["canonical_value"] not in AUTHORITY_ORGS]
        specific_recent = [e for e in recent_entities if e["canonical_value"] not in AUTHORITY_ORGS]
        candidate_entities = specific_last_user or specific_recent or last_user_entities or recent_entities

        if not candidate_entities:
            return current_query, [], False

        # 1. Person coreference: "What is his / her age?" / "Tell me about him"
        if re.search(r"\b(his|her|him)\b", query, re.IGNORECASE):
            last_persons = [e for e in last_user_entities if e["entity_type"] == "PERSON"]
            all_persons = [e for e in recent_entities if e["entity_type"] == "PERSON"]

            if len(last_persons) > 1:
                return query, [p["canonical_value"] for p in last_persons], True
            elif len(last_persons) == 1:
                person = last_persons[0]["canonical_value"]
                resolved_query = re.sub(r"\b(his|her)\b", f"{person}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bhim\b", person, resolved_query, flags=re.IGNORECASE)
                return resolved_query, [person], False
            elif len(all_persons) == 1:
                person = all_persons[0]["canonical_value"]
                resolved_query = re.sub(r"\b(his|her)\b", f"{person}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bhim\b", person, resolved_query, flags=re.IGNORECASE)
                return resolved_query, [person], False
            elif len(all_persons) > 1:
                return query, [p["canonical_value"] for p in all_persons[:2]], True

        # 2. Demonstrative Phrases with Prepositions & Verbs ("for this", "needed for this", "about this", "in this", "explain this")
        demonstrative_prep_pattern = r"\b(needed for this|required for this|needed for that|required for that|for this|for that|about this|about that|in this|in that|of this|of that|under this|under that|with this|with that|to this|to that|on this|on that|into this|from this)\b"
        if re.search(demonstrative_prep_pattern, query, re.IGNORECASE):
            if len(candidate_entities) > 1 and len(specific_last_user) > 1:
                return query, [e["entity_value"] for e in candidate_entities[:2]], True
            target = candidate_entities[0]["entity_value"]
            
            def prep_sub(m):
                matched = m.group(0).lower()
                if "needed for" in matched:
                    return f"needed for {target}"
                elif "required for" in matched:
                    return f"required for {target}"
                elif "for" in matched:
                    return f"for {target}"
                elif "about" in matched:
                    return f"about {target}"
                elif "in" in matched:
                    return f"in {target}"
                elif "of" in matched:
                    return f"of {target}"
                elif "under" in matched:
                    return f"under {target}"
                elif "with" in matched:
                    return f"with {target}"
                elif "to" in matched:
                    return f"to {target}"
                elif "on" in matched:
                    return f"on {target}"
                elif "into" in matched:
                    return f"into {target}"
                elif "from" in matched:
                    return f"from {target}"
                return f"for {target}"

            resolved_query = re.sub(demonstrative_prep_pattern, prep_sub, query, flags=re.IGNORECASE)
            return resolved_query, [target], False

        # 3. Demonstrative Phrases with Verbs / Nouns ("this rule", "this policy", "explain this", "details of this")
        demonstrative_noun_pattern = r"\b(this|that)\s+(rule|rules|circular|circulars|policy|policies|scheme|schemes|limit|limits|process|service|services|guideline|guidelines|directive|directives|requirement|requirements|document|documents)\b"
        if re.search(demonstrative_noun_pattern, query, re.IGNORECASE):
            if len(candidate_entities) > 1 and len(specific_last_user) > 1:
                return query, [e["entity_value"] for e in candidate_entities[:2]], True
            target = candidate_entities[0]["entity_value"]
            resolved_query = re.sub(demonstrative_noun_pattern, rf"{target} \2", query, flags=re.IGNORECASE)
            return resolved_query, [target], False

        if re.search(r"\b(explain this|explain that|details of this|details of that|how does this work|how does that work|how to do this|how to do that|tell me about this|tell me about that)\b", query, re.IGNORECASE):
            if len(candidate_entities) > 1 and len(specific_last_user) > 1:
                return query, [e["entity_value"] for e in candidate_entities[:2]], True
            target = candidate_entities[0]["entity_value"]
            resolved_query = re.sub(r"\b(explain this|explain that)\b", f"explain {target}", query, flags=re.IGNORECASE)
            resolved_query = re.sub(r"\b(details of this|details of that)\b", f"details of {target}", resolved_query, flags=re.IGNORECASE)
            resolved_query = re.sub(r"\b(how does this work|how does that work)\b", f"how does {target} work", resolved_query, flags=re.IGNORECASE)
            resolved_query = re.sub(r"\b(how to do this|how to do that)\b", f"how to do {target}", resolved_query, flags=re.IGNORECASE)
            resolved_query = re.sub(r"\b(tell me about this|tell me about that)\b", f"tell me about {target}", resolved_query, flags=re.IGNORECASE)
            return resolved_query, [target], False

        # 4. Service / Regulation coreference: "What is its limit?" / "What is their limit?" / "is it mandatory"
        if re.search(r"\b(its|it's|it|their|theirs)\b", query, re.IGNORECASE):
            last_services = [e for e in last_user_entities if e["entity_type"] in ["BANKING_SERVICE", "REGULATION"] and e["canonical_value"] not in AUTHORITY_ORGS]
            all_services = [e for e in recent_entities if e["entity_type"] in ["BANKING_SERVICE", "REGULATION"] and e["canonical_value"] not in AUTHORITY_ORGS]

            if len(last_services) > 1:
                candidate_names = [e["entity_value"] for e in last_services]
                return query, candidate_names, True
            elif len(last_services) == 1:
                target = last_services[0]["entity_value"]
                resolved_query = re.sub(r"\b(its|it's|their|theirs)\b", f"{target}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\babout it\b", f"about {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bfor it\b", f"for {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bis it\b", f"is {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\b\bit\b", target, resolved_query, flags=re.IGNORECASE)
                return resolved_query, [target], False
            elif len(all_services) == 1:
                target = all_services[0]["entity_value"]
                resolved_query = re.sub(r"\b(its|it's|their|theirs)\b", f"{target}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\babout it\b", f"about {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bfor it\b", f"for {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bis it\b", f"is {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\b\bit\b", target, resolved_query, flags=re.IGNORECASE)
                return resolved_query, [target], False
            elif len(all_services) > 1:
                return query, [e["entity_value"] for e in all_services[:2]], True

        # 5. Standalone demonstrative "this" / "that" in questions (e.g. "what is this?", "is this mandatory?", "what about this?")
        if re.search(r"\b(this|that)\b", query, re.IGNORECASE):
            if candidate_entities:
                target = candidate_entities[0]["entity_value"]
                resolved_query = re.sub(r"\b(this|that)\b", target, query, flags=re.IGNORECASE)
                return resolved_query, [target], False

        # 6. Subjectless follow-up queries (Ellipsis / Zero Anaphora)
        # e.g., "what else is needed", "what else is required", "what documents are required", "what are the charges", "what is the limit"
        ellipsis_patterns = [
            r"^(what else is needed|what else is required|what else do i need|what else)\??$",
            r"^(what documents are required|what documents are needed|documents required|documents needed|what paperwork|required documents)\??$",
            r"^(what is the eligibility|who is eligible|what are the requirements|eligibility criteria)\??$",
            r"^(what is the limit|what is the maximum limit|what is the transaction limit|transaction limit)\??$",
            r"^(what are the charges|what is the penalty|what are the penalties|what is the fee)\??$",
            r"^(how to apply|how to do|where to apply|where to submit|process|procedure)\??$"
        ]
        has_ellipsis = any(re.search(p, query, re.IGNORECASE) for p in ellipsis_patterns)
        
        # Also check if query has document/requirement terms without mentioning any specific banking entity
        has_doc_terms = bool(re.search(r"\b(documents|doc|docs|paperwork|eligibility|requirements|penalty|charges|limit)\b", query, re.IGNORECASE))
        has_no_entity_in_query = not any(re.search(rf"\b{re.escape(k)}\b", query, re.IGNORECASE) for k in BANKING_ACRONYMS)

        if (has_ellipsis or has_doc_terms) and has_no_entity_in_query and candidate_entities:
            target = candidate_entities[0]["entity_value"]
            if not re.search(rf"\b{re.escape(target)}\b", query, re.IGNORECASE):
                resolved_query = f"{query} for {target}"
                return resolved_query, [target], False

        return current_query, [], False

    def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Complete query understanding pipeline:
        1. Check conversational intent (greetings, slang, gratitude).
        2. Normalize Hinglish / colloquial phrasing.
        3. Coreference / pronoun resolution against conversation history.
        4. Entity extraction.
        """
        conversation_history = conversation_history or []
        original_query = query.strip()

        # Step 1: Check Chitchat Intent
        chitchat = self.detect_chitchat(original_query)
        if chitchat and chitchat.get("is_chitchat"):
            return {
                "original_query": original_query,
                "normalized_query": original_query,
                "resolved_entities": [],
                "extracted_entities": [],
                "clarification_needed": False,
                "is_chitchat": True,
                "chitchat_response": chitchat["response"]
            }

        target_query = chitchat["cleaned_query"] if (chitchat and "cleaned_query" in chitchat) else original_query

        # Step 2: Normalize Hinglish
        hinglish_normalized = self.normalize_hinglish(target_query)

        # Step 3: Coreference resolution
        resolved_query, resolved_entities, clarification_needed = self.resolve_coreference(
            hinglish_normalized, conversation_history
        )

        # Step 4: Extract entities
        entities = self.extract_entities(resolved_query)
        all_resolved_names = list(set(resolved_entities + [e["canonical_value"] for e in entities] + [e["entity_value"] for e in entities]))

        return {
            "original_query": original_query,
            "normalized_query": resolved_query,
            "resolved_entities": all_resolved_names,
            "extracted_entities": entities,
            "clarification_needed": clarification_needed,
            "is_chitchat": False,
            "chitchat_response": None
        }

nlp_engine = NLPEngine()

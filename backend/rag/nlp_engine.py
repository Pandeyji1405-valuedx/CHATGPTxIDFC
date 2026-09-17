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

# Pronouns to resolve
PRONOUNS = ["its", "his", "her", "their", "this", "that", "these", "those", "it"]

class NLPEngine:
    def __init__(self):
        pass

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
        Resolves pronouns (its, his, her, their, this rule, etc.) based on previous messages.
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

        # Extract recent entities across all messages
        recent_entities = []
        for msg in reversed(conversation_history):
            content = msg.get("normalized_content") or msg.get("original_content", "")
            msg_entities = self.extract_entities(content)
            for ent in msg_entities:
                if ent["canonical_value"] not in [e["canonical_value"] for e in recent_entities]:
                    recent_entities.append(ent)

        if not recent_entities and not last_user_entities:
            return current_query, [], False

        # 1. Person coreference: "What is his / her age?"
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

        # 2. Service / Regulation coreference: "What is its limit?" / "What is their limit?"
        if re.search(r"\b(its|it's|it|their|theirs)\b", query, re.IGNORECASE):
            last_services = [e for e in last_user_entities if e["entity_type"] in ["BANKING_SERVICE", "REGULATION"] and e["canonical_value"] not in AUTHORITY_ORGS]
            all_services = [e for e in recent_entities if e["entity_type"] in ["BANKING_SERVICE", "REGULATION"] and e["canonical_value"] not in AUTHORITY_ORGS]

            if len(last_services) > 1:
                # Multiple antecedents mentioned in the same user turn (e.g. NEFT and RTGS)
                candidate_names = [e["entity_value"] for e in last_services]
                return query, candidate_names, True
            elif len(last_services) == 1:
                target = last_services[0]["entity_value"]
                resolved_query = re.sub(r"\b(its|it's|their|theirs)\b", f"{target}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\babout it\b", f"about {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bfor it\b", f"for {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bis it\b", f"is {target}", resolved_query, flags=re.IGNORECASE)
                return resolved_query, [target], False
            elif len(all_services) == 1:
                target = all_services[0]["entity_value"]
                resolved_query = re.sub(r"\b(its|it's|their|theirs)\b", f"{target}'s", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\babout it\b", f"about {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bfor it\b", f"for {target}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bis it\b", f"is {target}", resolved_query, flags=re.IGNORECASE)
                return resolved_query, [target], False
            elif len(all_services) > 1:
                return query, [e["entity_value"] for e in all_services[:2]], True

        # 3. "What documents are required?" / "documents required"
        if re.search(r"\b(documents|doc|docs|paperwork|eligibility)\b", query, re.IGNORECASE) and not any(k in query.upper() for k in BANKING_ACRONYMS):
            target_candidates = last_msg_entities or recent_entities
            if target_candidates:
                target = target_candidates[0]["entity_value"]
                resolved_query = f"{query} for {target}"
                return resolved_query, [target], False

        # 4. "this rule" / "this circular" / "this policy" / "explain this"
        if re.search(r"\b(this rule|this circular|this policy|this scheme|this limit|explain this)\b", query, re.IGNORECASE):
            target_candidates = last_msg_entities or recent_entities
            if target_candidates:
                target = target_candidates[0]["entity_value"]
                resolved_query = re.sub(r"\b(this rule|this circular|this policy|this scheme|this limit)\b", f"{target} guidelines", query, flags=re.IGNORECASE)
                resolved_query = re.sub(r"\bexplain this\b", f"explain {target}", resolved_query, flags=re.IGNORECASE)
                return resolved_query, [target], False

        return current_query, [], False

    def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Complete query understanding pipeline:
        1. Clean and normalize punctuation / casing.
        2. Normalize Hinglish / colloquial phrasing.
        3. Coreference / pronoun resolution against conversation history.
        4. Entity extraction.
        5. Returns structured normalized representation.
        """
        conversation_history = conversation_history or []
        original_query = query.strip()

        # Step 1 & 2: Normalize Hinglish
        hinglish_normalized = self.normalize_hinglish(original_query)

        # Step 3: Coreference resolution
        resolved_query, resolved_entities, clarification_needed = self.resolve_coreference(
            hinglish_normalized, conversation_history
        )

        # Step 4: Extract entities from both original and resolved queries
        entities = self.extract_entities(resolved_query)
        all_resolved_names = list(set(resolved_entities + [e["canonical_value"] for e in entities]))

        return {
            "original_query": original_query,
            "normalized_query": resolved_query,
            "resolved_entities": all_resolved_names,
            "extracted_entities": entities,
            "clarification_needed": clarification_needed
        }

nlp_engine = NLPEngine()

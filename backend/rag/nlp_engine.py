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

EXPANDED_ACRONYMS_INFO = {
    "NEFT": {
        "full_form": "National Electronic Funds Transfer",
        "description": "An electronic funds transfer system maintained and operated by the Reserve Bank of India (RBI) that operates round-the-clock (24x7x365) in 48 half-hourly settlement batches daily."
    },
    "RTGS": {
        "full_form": "Real Time Gross Settlement",
        "description": "A continuous, real-time gross settlement system operated 24x7x365 by RBI for large-value payments with a minimum threshold of ₹2,00,000 and no upper limit."
    },
    "IMPS": {
        "full_form": "Immediate Payment Service",
        "description": "An instant 24x7 interbank electronic fund transfer service operated by National Payments Corporation of India (NPCI)."
    },
    "UPI": {
        "full_form": "Unified Payments Interface",
        "description": "An instant real-time payment architecture developed by NPCI facilitating seamless peer-to-peer (P2P) and person-to-merchant (P2M) transactions on mobile apps."
    },
    "KYC": {
        "full_form": "Know Your Customer",
        "description": "A mandatory customer identification and due diligence process mandated by RBI under KYC Directions, 2016 to prevent money laundering and fraud."
    },
    "V-CIP": {
        "full_form": "Video-based Customer Identification Process",
        "description": "An official digital customer identification method permitted by RBI allowing bank staff to conduct live, geo-tagged video interaction and real-time Aadhaar/PAN verification."
    },
    "OVD": {
        "full_form": "Officially Valid Document",
        "description": "The six approved identity documents recognized by RBI: Passport, Driving License, Proof of possession of Aadhaar number, Voter's Identity Card, NREGA Job Card, and NPR Letter."
    },
    "LTV": {
        "full_form": "Loan to Value Ratio",
        "description": "The ratio of the housing loan amount to the property value, capped by RBI at 90% for loans up to ₹30 Lakhs, 80% for ₹30L–₹75L, and 75% for loans above ₹75 Lakhs."
    },
    "NPA": {
        "full_form": "Non-Performing Asset",
        "description": "A loan or credit facility where the principal or interest payment has remained overdue for a period exceeding 90 days."
    },
    "EMI": {
        "full_form": "Equated Monthly Installment",
        "description": "A fixed monthly payment made by a borrower to a lender combining principal repayment and interest charges."
    },
    "KFS": {
        "full_form": "Key Fact Statement",
        "description": "A standardized disclosure sheet mandated under RBI Digital Lending rules outlining the all-inclusive Annual Percentage Rate (APR), cooling-off period, and grievance contacts."
    },
    "CIBIL": {
        "full_form": "Credit Information Bureau (India) Limited",
        "description": "A premier Credit Information Company (CIC) licensed by RBI that tracks credit history and generates credit scores for retail and corporate borrowers."
    },
    "CRR": {
        "full_form": "Cash Reserve Ratio",
        "description": "The minimum percentage of Net Demand and Time Liabilities (NDTL) that commercial banks must maintain in liquid cash with the RBI."
    },
    "SLR": {
        "full_form": "Statutory Liquidity Ratio",
        "description": "The minimum reserve percentage of NDTL that commercial banks must maintain in the form of gold, cash, or approved government securities."
    },
    "PSL": {
        "full_form": "Priority Sector Lending",
        "description": "RBI statutory target requiring domestic commercial banks to lend 40% of Adjusted Net Bank Credit (ANBC) to priority sectors including Agriculture, MSME, Education, and Housing."
    },
    "FASTAG": {
        "full_form": "FASTag Electronic Toll Collection",
        "description": "An electronic toll payment system employing RFID technology for automatic toll fee deduction directly from a linked bank account or prepaid wallet."
    },
    "FD": {
        "full_form": "Fixed Deposit",
        "description": "A term deposit product offered by banks where money is deposited for a fixed tenure at a fixed interest rate."
    },
    "RD": {
        "full_form": "Recurring Deposit",
        "description": "A regular investment deposit product allowing individuals to save a fixed monthly sum and earn interest equivalent to fixed deposits."
    }
}

# Hinglish & Colloquial Query Patterns to Standard English
HINGLISH_TRANSLATIONS = [
    (r"\bmitakenly\b", "mistakenly"),
    (r"\baccidently\b", "accidentally"),
    (r"\bgalat\s+account\b", "wrong account"),
    (r"\bgalat\s+khate\b", "wrong account"),
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
    "debit card", "transaction", "fraud", "unauthorized", "unauthorised", "liability", "circular", "master direction",
    "policy", "penal", "cooling-off", "look-up", "foreclosure", "charges", "settlement", "remittance",
    "ombudsman", "housing", "mortgage", "limit", "rules", "rate", "documents", "aadhaar", "pan",
    "passport", "sachin", "tendulkar", "stolen", "lost", "compromised", "scam", "wrong", "mistake",
    "mistakenly", "mitakenly", "money", "transfer", "transferred", "credit", "debited", "reversal",
    "compensation", "turnaround", "tat", "delayed", "fail", "failed", "grievance", "complaint", "dispute"
]

class NLPEngine:
    def __init__(self):
        pass

    def extract_friendly_user_name(self, name: Optional[str] = None, email: Optional[str] = None) -> str:
        """Extracts clean, capitalized first name from user display name or email address."""
        if name and name.strip() and name.strip().lower() not in ["user", "guest user", "default user", "none", "customer"]:
            parts = name.strip().split()
            first = re.sub(r"[^a-zA-Z0-9_\-]", "", parts[0])
            if first and len(first) >= 2:
                return first.capitalize()

        if email and "@" in email:
            local = email.split("@")[0].strip()
            # Split on dots, underscores, dashes or numbers (e.g. shubham.kdjndjksv -> shubham)
            tokens = [t for t in re.split(r"[\._\-0-9]", local) if len(t) >= 2]
            if tokens:
                return tokens[0].capitalize()
            elif local:
                return local.capitalize()

        if name and name.strip() and name.strip().lower() not in ["none"]:
            return name.strip().capitalize()

        return "there"

    def detect_chitchat(self, text: str, user_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Detects if a user input is a conversational greeting, pleasantry, acknowledgment,
        identity question, or farewell, and formats personalized greetings addressing the user by name.
        """
        clean = text.strip()
        lower = clean.lower()
        name_str = f" {user_name}" if (user_name and user_name.lower() != "there") else ""

        # Check if the query contains any core banking / domain keywords
        has_domain_keyword = any(re.search(rf"\b{re.escape(k)}\b", lower) for k in DOMAIN_KEYWORDS)

        # 1. Identity & Capability Questions
        if re.search(r"\b(who are you|what is your name|who made you|what can you do|what are you|tum kaun ho|aap kaun ho|kya kar sakte ho|introduce yourself|help me)\b", lower):
            if not has_domain_keyword or lower in ["who are you", "what can you do", "help me", "introduce yourself"]:
                return {
                    "is_chitchat": True,
                    "response": (
                        f"Hello{name_str}! I am your **ChatGPT IDFC Banking Assistant**. I provide human-like, accurate answers grounded "
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
                    "response": f"I'm doing great{name_str}, thank you for asking! How can I assist you with your banking or regulatory questions today?"
                }

        # 3. Gratitude & Thanks
        if re.search(r"\b(thanks|thank you|thx|tysm|shukriya|dhanyawad|many thanks)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"You're very welcome{name_str}! Feel free to ask if you have any more questions about banking guidelines or transactions."
                }

        # 4. Acknowledgments & Approvals
        if re.search(r"\b(ok|okay|cool|got it|great|awesome|understood|perfect|nice|alright|fine|theek hai|accha|samajh gaya|superb|well done)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Glad that was helpful{name_str}! Let me know if there's anything else you'd like to explore."
                }

        # 5. Time-of-day specific Greetings (Good Morning, Afternoon, Evening, Night)
        if re.search(r"\bgood\s+morning\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Good morning{name_str}! How can I assist you today with RBI Master Directions, IDFC FIRST Bank policies, or regulatory compliance?"
                }

        if re.search(r"\bgood\s+afternoon\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Good afternoon{name_str}! How can I assist you with your banking, RBI, SEBI, or IRDAI regulatory questions today?"
                }

        if re.search(r"\bgood\s+evening\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Good evening{name_str}! How can I assist you with your banking and regulatory queries today?"
                }

        if re.search(r"\bgood\s+night\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Good night{name_str}! Wishing you a peaceful rest. If you have any banking or regulatory compliance questions tomorrow, I will be right here to assist you."
                }

        if re.search(r"\bgood\s+day\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Good day{name_str}! How can I assist you with banking guidelines or account services today?"
                }

        # 6. Farewells & Partings
        if re.search(r"\b(bye|goodbye|see you|see ya|cya|tata|alvida|chal milte hai|take care)\b", lower):
            if not has_domain_keyword:
                return {
                    "is_chitchat": True,
                    "response": f"Goodbye{name_str}! Have a wonderful day ahead, and feel free to reach out whenever you need banking assistance."
                }

        # 7. Pure Greetings & Slang (when no domain question is asked)
        is_greeting = bool(re.search(
            r"\b(h+e+l+l*o+|h+e+l+o+|h+e+y+|h+i+|h+e+y+a+|h+o+l+a+|greetings|namaste+|namaskar|pranam|kya\s+haal(\s+hai)?|kaise\s+ho|kaisa\s+hai|sab\s+theek|kem\s+cho|kemon\s+acho|yo+|wassup|what'?s\s+up|sup|bro+|bhai+|yaar|buddy|dude|suno|arre\s+bhai|oye|hlo+)\b",
            lower
        ))

        if is_greeting and not has_domain_keyword:
            # Differentiate Hinglish vs English greetings
            if re.search(r"\b(namaste+|namaskar|pranam|kya\s+haal|kaise\s+ho|kaisa\s+hai|sab\s+theek|bhai+|arre|suno)\b", lower):
                return {
                    "is_chitchat": True,
                    "response": f"Namaste{name_str}! Main aapki RBI Master Directions, banking rules aur IDFC FIRST Bank policies se related queries mein kaise help kar sakta hoon?"
                }
            return {
                "is_chitchat": True,
                "response": f"Hello{name_str}! How can I help you today with RBI Master Directions, IDFC FIRST Bank policies, or regulatory compliance?"
            }

        # 8. Greeting prefix attached to a real query (e.g. "Hi, what is NEFT limit?" or "Hello, kyc rules")
        greeting_prefix_match = re.match(
            r"^(h+e+l+l*o+|h+e+l+o+|h+e+y+|h+i+|namaste+|namaskar|good\s+(morning|afternoon|evening|day|night)|bro+|bhai+|yo+|hlo+)[\s,!.:;-]+(.*)$",
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

    def normalize_acronym_aliases(self, text: str) -> str:
        """Standardizes dotted, spaced, and alternate acronym spellings to canonical forms."""
        normalized = text
        aliases = [
            (r"\bN\.?E\.?F\.?T\.?\b", "NEFT"),
            (r"\bR\.?T\.?G\.?S\.?\b", "RTGS"),
            (r"\bI\.?M\.?P\.?S\.?\b", "IMPS"),
            (r"\bU\.?P\.?I\.?\b", "UPI"),
            (r"\bK\.?Y\.?C\.?\b", "KYC"),
            (r"\bV[\.\-\s]?C[\.\-\s]?I[\.\-\s]?P\.?\b", "V-CIP"),
            (r"\bO\.?V\.?D\.?\b", "OVD"),
            (r"\bK\.?F\.?S\.?\b", "KFS"),
            (r"\bF\.?A\.?S\.?T\.?A\.?G\.?\b|\bfast\s+tag\b", "FASTag"),
            (r"\bE\.?M\.?I\.?\b", "EMI"),
            (r"\bN\.?P\.?A\.?\b", "NPA"),
            (r"\bL\.?T\.?V\.?\b", "LTV"),
            (r"\bC\.?I\.?B\.?I\.?L\.?\b", "CIBIL"),
            (r"\bC\.?R\.?R\.?\b", "CRR"),
            (r"\bS\.?L\.?R\.?\b", "SLR"),
            (r"\bP\.?S\.?L\.?\b", "PSL")
        ]
        for pattern, replacement in aliases:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", normalized).strip()

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

    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyzes the semantic intent of a banking query to drive targeted fact synthesis:
        - FULL_FORM_ACRONYM: Acronym expansion and meaning
        - TEMPORAL_EFFECTIVE: Effective dates, inception dates, circular timing
        - OPERATING_HOURS_TIMELINES: Operating hours, batch schedules, turnaround times
        - NUMERICAL_LIMITS: Min/Max transaction amounts, LTV ratios, compensation caps
        - CHARGES_PENALTIES: Fees, waivers, penal interest rates, delay penalties
        - REQUIREMENTS_DOCUMENTS: OVD list, identity proof, Aadhaar/PAN, eligibility
        - PROCEDURAL_HOWTO: Step-by-step procedure, settlement flow, complaint escalation
        - RIGHTS_LIABILITY: Zero liability, limited customer liability, cooling-off rights
        - COMPARISON: Differences between payment modes or schemes
        - GENERAL_FACTUAL: Default open-ended regulatory inquiry
        """
        q = query.lower()

        # Check Catalog / Available Documents Intent
        if re.search(r"\b(what|which|list|show|tell\s+me\s+about)\s+(all\s+)?(official\s+)?(rbi\s+master\s+directions?|master\s+directions?|policies|bank\s+policies|documents?|circulars?|guidelines?|topics?|data)\s+(are\s+)?(available|present|in\s+(the\s+)?knowledge\s+base|in\s+(the\s+)?database|stored|indexed|covered)\b", q) or re.search(r"\b(what\s+do\s+you\s+know|what\s+can\s+i\s+ask|what\s+topics\s+are\s+available|available\s+in\s+the\s+knowledge\s+base|list\s+all\s+documents|what\s+policies\s+are\s+available)\b", q):
            return {"intent": "CATALOG_DOCUMENT_LIST"}

        if re.search(r"\b(full\s*form|stand\s*for|stands\s*for|expand|expansion|abbreviation|meaning\s+of\s+acronym|what\s+does\s+[a-z\-]+\s+stand\s+for)\b", q):
            return {"intent": "FULL_FORM_ACRONYM"}

        if re.search(r"\b(when\s+did|when\s+was|effective\s+date|start\s+date|launch\s+date|since\s+when|from\s+which\s+date|date\s+of\s+effect|came\s+into\s+action|came\s+into\s+effect|in\s+effect|what\s+date|which\s+year|since\s+which\s+year|historical\s+date)\b", q):
            return {"intent": "TEMPORAL_EFFECTIVE"}

        if re.search(r"\b(operating\s+hours|timings?|working\s+hours|settlement\s+batch|how\s+many\s+batches|batch\s+timings?|24x7|settlement\s+timeline|turnaround\s+time|credit\s+timeline|return\s+timeline|how\s+long\s+does\s+it\s+take|tat)\b", q):
            return {"intent": "OPERATING_HOURS_TIMELINES"}

        if re.search(r"\b(minimum\s+amount|maximum\s+amount|max\s+limit|min\s+limit|transaction\s+limit|ltv|loan\s+to\s+value|max\s+ltv|cap|compensation\s+amount|how\s+much\s+money|what\s+is\s+the\s+limit|ceiling|maximum\s+loan|threshold)\b", q):
            return {"intent": "NUMERICAL_LIMITS"}

        if re.search(r"\b(charges?|fees?|cost|free\s+or\s+paid|penal\s+interest|penalty|penalties|late\s+payment|penal\s+rate|fine|waiver|waived)\b", q):
            return {"intent": "CHARGES_PENALTIES"}

        if re.search(r"\b(documents?|docs?|ovd|officially\s+valid|aadhaar|pan|passport|voter|job\s+card|paperwork|eligibility|eligible|needed|required|prerequisites?|what\s+else\s+is\s+needed)\b", q):
            return {"intent": "REQUIREMENTS_DOCUMENTS"}

        if re.search(r"\b(zero\s+liability|customer\s+liability|limited\s+liability|cooling-off|look-up|unauthorized|fraud|shadow\s+reversal|borrower\s+consent)\b", q):
            return {"intent": "RIGHTS_LIABILITY"}

        if re.search(r"\b(difference\s+between|vs|versus|compare|distinction|diff)\b", q):
            return {"intent": "COMPARISON"}

        if re.search(r"\b(how\s+to|steps?\s+to|process|procedure|method|how\s+does.*work|how\s+can\s+i|how\s+the.*can\s+be|workflow|complaint\s+filing|how\s+to\s+file|mechanism|how\s+to\s+reload|how.*reloaded|how.*recharged?)\b", q):
            return {"intent": "PROCEDURAL_HOWTO"}

        # Check comparison intent
        if re.search(r"\b(COMPARE|DIFFERENCE BETWEEN|VS|VERSUS|COMPARISON)\b", query, re.IGNORECASE):
            return {"intent": "COMPARISON"}

        return {"intent": "GENERAL_FACTUAL"}

    def extract_temporal_and_regulator_scope(self, query: str) -> Dict[str, Any]:
        """
        Extracts explicit regulator mentions and historical temporal bounds (e.g. 'in 2021', 'as of 2018').
        """
        regulators = []
        query_upper = query.upper()

        if re.search(r"\b(SEBI|SECURITIES AND EXCHANGE BOARD|LODR|INSIDER TRADING)\b", query_upper):
            regulators.append("SEBI")
        if re.search(r"\b(IRDAI|INSURANCE REGULATORY|POLICYHOLDER|INSURER)\b", query_upper):
            regulators.append("IRDAI")
        if re.search(r"\b(RBI|RESERVE BANK|BANKING OMBUDSMAN|V-CIP|NEFT|RTGS|DIGITAL LENDING)\b", query_upper):
            regulators.append("RBI")
        if re.search(r"\b(INTERNAL|IDFC|IDFC FIRST|IDFC BANK|BANK POLICY|SOP)\b", query_upper):
            regulators.append("INTERNAL")
            regulators.append("IDFC_FIRST_BANK")
            regulators.append("BANK_POLICY")

        # Temporal detection
        as_of_date = None
        year_match = re.search(r"\b(?:IN|AS OF|BEFORE|DURING|UNDER THE)\s+(20\d\d)\b", query, re.IGNORECASE)
        if year_match:
            year = year_match.group(1)
            as_of_date = f"{year}-12-31"
        else:
            # Check for date formats like 2021-04-01 or 15/08/2022
            iso_match = re.search(r"\b(20\d\d-\d\d-\d\d)\b", query)
            if iso_match:
                as_of_date = iso_match.group(1)

        # Depth detection
        requested_depth = "concise"
        if re.search(r"\b(COMPARE|COMPARISON|VERSUS|VS|DIFFERENCE)\b", query, re.IGNORECASE):
            requested_depth = "comparison"
        elif re.search(r"\b(DETAILED|EXPLAIN IN DETAIL|COMPREHENSIVE|ALL REQUIREMENTS)\b", query, re.IGNORECASE):
            requested_depth = "detailed"

        return {
            "detected_regulators": regulators or ["ALL"],
            "as_of_date": as_of_date,
            "requested_depth": requested_depth
        }

    def normalize_jumbled_descriptive_query(self, query: str) -> Tuple[str, List[str]]:
        """
        Handles jumbled, conversational descriptions, and sentence fragments to extract
        the underlying canonical regulatory intent, sub-topics, and normalized search query.
        """
        lower = query.lower()
        subtopics = []

        # 1. KYC / V-CIP / OVD descriptive variations
        if "kyc" in lower or any(w in lower for w in ["know your customer", "v-cip", "vcip", "video kyc", "ovd"]):
            subtopics.append("Know Your Customer (KYC)")
            if any(w in lower for w in ["physical", "physically", "present", "presence", "in person", "branch"]):
                subtopics.append("Physical Verification & Officially Valid Documents (OVD)")
            if any(w in lower for w in ["video", "vcip", "v-cip", "authenticat", "digital", "online"]):
                subtopics.append("Video-based Customer Identification Process (V-CIP)")
            if any(w in lower for w in ["periodic", "update", "updation", "high risk", "medium risk", "low risk", "years"]):
                subtopics.append("Periodic KYC Updation")

        # 2. Digital Lending / KFS / Cooling-off variations
        if any(w in lower for w in ["lending", "loan", "cooling", "lookup", "kfs", "apr", "recovery agent"]):
            if any(w in lower for w in ["digital lending", "app", "online loan", "kfs", "cooling-off", "look-up"]):
                subtopics.append("RBI Digital Lending Directions 2022")

        # 3. Unauthorized transactions / Fraud liability variations
        if any(w in lower for w in ["fraud", "unauthorized", "unauthorised", "stolen", "lost card", "wrong debit", "scam"]):
            subtopics.append("Customer Protection & Zero Fraud Liability")

        # 4. NEFT / RTGS / IMPS settlement & limits variations
        if any(w in lower for w in ["neft", "rtgs", "fund transfer", "batch", "operating hours", "2 lakh", "minimum limit"]):
            if "rtgs" in lower:
                subtopics.append("Real Time Gross Settlement (RTGS)")
            if "neft" in lower:
                subtopics.append("National Electronic Funds Transfer (NEFT)")

        # 5. SEBI LODR / Materiality disclosure variations
        if any(w in lower for w in ["lodr", "material event", "disclosure timeline", "regulation 30", "related party"]):
            subtopics.append("SEBI LODR Regulation 30 Disclosures")

        # 6. IRDAI Cyber Security & Policyholder protection
        if any(w in lower for w in ["irdai", "free look", "ciso", "cyber incident", "localization"]):
            subtopics.append("IRDAI Regulatory Guidelines")

        return query, subtopics

    def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        user_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete query understanding pipeline:
        1. Check conversational intent (greetings, slang, gratitude) with user name personalization.
        2. Normalize Hinglish / colloquial phrasing & jumbled query structures.
        3. Coreference / pronoun resolution against conversation history.
        4. Entity extraction & canonical subtopic mapping.
        5. Query intent classification for precise answer synthesis.
        6. Extract temporal compliance dates and regulator scopes.
        """
        conversation_history = conversation_history or []
        original_query = query.strip()

        # Step 1: Check Chitchat Intent
        chitchat = self.detect_chitchat(original_query, user_name=user_name)
        if chitchat and chitchat.get("is_chitchat"):
            return {
                "original_query": original_query,
                "normalized_query": original_query,
                "resolved_entities": [],
                "extracted_entities": [],
                "clarification_needed": False,
                "is_chitchat": True,
                "chitchat_response": chitchat["response"],
                "query_intent": "CHITCHAT",
                "detected_regulators": ["ALL"],
                "as_of_date": None,
                "requested_depth": "concise"
            }

        target_query = chitchat["cleaned_query"] if (chitchat and "cleaned_query" in chitchat) else original_query

        # Step 2: Normalize Hinglish, Banking Acronym Aliases & Jumbled Patterns
        hinglish_normalized = self.normalize_hinglish(target_query)
        acronym_normalized = self.normalize_acronym_aliases(hinglish_normalized)
        _, jumbled_subtopics = self.normalize_jumbled_descriptive_query(acronym_normalized)

        # Step 3: Coreference resolution
        resolved_query, resolved_entities, clarification_needed = self.resolve_coreference(
            acronym_normalized, conversation_history
        )

        # Step 4: Extract entities and merge subtopics
        entities = self.extract_entities(resolved_query)
        all_resolved_names = list(set(
            resolved_entities +
            [e["canonical_value"] for e in entities] +
            [e["entity_value"] for e in entities] +
            jumbled_subtopics
        ))

        # Step 5: Semantic Intent Analysis
        intent_info = self.analyze_query_intent(resolved_query)

        # Step 6: Temporal & Regulator Scope Analysis
        scope_info = self.extract_temporal_and_regulator_scope(resolved_query)

        return {
            "original_query": original_query,
            "normalized_query": resolved_query,
            "resolved_entities": all_resolved_names,
            "extracted_entities": entities,
            "clarification_needed": clarification_needed,
            "is_chitchat": False,
            "chitchat_response": None,
            "query_intent": intent_info["intent"],
            "detected_regulators": scope_info["detected_regulators"],
            "as_of_date": scope_info["as_of_date"],
            "requested_depth": scope_info["requested_depth"]
        }

nlp_engine = NLPEngine()



import pytest
from backend.rag.nlp_engine import nlp_engine

def test_pronoun_resolution_neft(client, auth_headers_user1):
    # 1. First message: "What is NEFT?"
    res1 = client.post("/api/chat", json={"query": "What is NEFT?"}, headers=auth_headers_user1)
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]

    # 2. Second message: "What is its transaction limit?"
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is its transaction limit?"
    }, headers=auth_headers_user1)
    assert res2.status_code == 200
    data2 = res2.json()

    # Verify that 'its' was resolved to 'NEFT's' in normalized_query
    assert "NEFT" in data2["normalized_query"]
    assert data2["original_query"] == "What is its transaction limit?"
    assert "NEFT" in data2["resolved_entities"]
    assert data2["source_type"] in ["KNOWLEDGE_BASE", "DATABASE", "DATABASE_AND_KNOWLEDGE_BASE"]

def test_pronoun_resolution_rtgs_antecedent(client, auth_headers_user1):
    # Message: "What is RTGS?"
    res1 = client.post("/api/chat", json={"query": "What is RTGS?"}, headers=auth_headers_user1)
    conv_id = res1.json()["conversation_id"]

    # Follow-up: "What is its limit?"
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is its limit?"
    }, headers=auth_headers_user1)
    assert res2.status_code == 200
    data2 = res2.json()
    assert "RTGS" in data2["normalized_query"]
    assert "NEFT" not in data2["normalized_query"]

def test_ambiguous_multiple_antecedents_clarification_prompt(client, auth_headers_user1):
    # Turn 1 mentions BOTH NEFT and RTGS
    res1 = client.post("/api/chat", json={"query": "Tell me about NEFT and RTGS."}, headers=auth_headers_user1)
    conv_id = res1.json()["conversation_id"]

    # Turn 2 asks "What is its limit?" with ambiguous pronoun
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is its limit?"
    }, headers=auth_headers_user1)
    assert res2.status_code == 200
    data2 = res2.json()

    # Must ask for clarification rather than arbitrarily picking one
    assert data2["clarification_needed"] is True or "clarify" in data2["answer"].lower()
    assert "clarify" in data2["answer"].lower()

def test_pronoun_resolution_sachin_tendulkar():
    history = [
        {"role": "user", "original_content": "Who is Sachin Tendulkar?"},
        {"role": "assistant", "original_content": "Sachin Tendulkar is an Indian former international cricketer."}
    ]
    res = nlp_engine.process_query("What is his age?", conversation_history=history)
    assert "Sachin Tendulkar" in res["normalized_query"]
    assert res["clarification_needed"] is False

def test_hinglish_normalization_kyc(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "RBI ka KYC rule kya hai?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert any("KYC" in e for e in data["resolved_entities"])
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert len(data["citations"]) >= 1

def test_original_vs_normalized_query_persisted(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is KYC kya h"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    conv_id = res.json()["conversation_id"]

    conv_res = client.get(f"/api/conversations/{conv_id}", headers=auth_headers_user1)
    assert conv_res.status_code == 200
    messages = conv_res.json()["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert user_msg["original_content"] == "What is KYC kya h"
    assert user_msg["normalized_content"] is not None

def test_kyc_followup_what_else_is_needed_for_this(client, auth_headers_user1):
    # 1. Turn 1: "what is kyc"
    res1 = client.post("/api/chat", json={"query": "what is kyc"}, headers=auth_headers_user1)
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]
    data1 = res1.json()
    assert data1["source_type"] == "KNOWLEDGE_BASE"
    assert "KYC" in data1["resolved_entities"]

    # 2. Turn 2: "what else is needed for this"
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "what else is needed for this"
    }, headers=auth_headers_user1)
    assert res2.status_code == 200
    data2 = res2.json()

    # Coreference must resolve 'for this' to 'for KYC'
    assert "KYC" in data2["normalized_query"].upper()
    assert "KYC" in data2["resolved_entities"]
    assert data2["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    # Must NOT return a generic chitchat greeting
    assert "How can I help you today" not in data2["answer"]
    # Must provide verified KYC documents / OVD / CDD requirements
    assert any(term in data2["answer"].upper() for term in ["OVD", "AADHAAR", "PASSPORT", "DOCUMENTS", "DILIGENCE", "V-CIP", "CUSTOMER"])

def test_conversation_db_does_not_match_greeting_substring(client, auth_headers_user1):
    # 1. User says "Hi"
    res_hi = client.post("/api/chat", json={"query": "Hi"}, headers=auth_headers_user1)
    assert res_hi.status_code == 200
    assert any(term in res_hi.json()["answer"].lower() for term in ["help", "assist", "hello", "hi", "welcome"])

    # 2. User creates a new chat and asks a query containing 'hi' like "what else is needed for this"
    res_follow = client.post("/api/chat", json={"query": "what else is needed for KYC"}, headers=auth_headers_user1)
    assert res_follow.status_code == 200
    data = res_follow.json()
    # Must NOT falsely match "Hi" response from conversation memory
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "How can I help you today" not in data["answer"]

def test_universal_question_aware_synthesis_and_redis_context(client, auth_headers_user1):
    # Turn 1: "What is NEFT and what are its operating hours?"
    res1 = client.post("/api/chat", json={
        "query": "What is NEFT and what are its operating hours?"
    }, headers=auth_headers_user1)
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]
    data1 = res1.json()
    assert "NEFT" in data1["resolved_entities"]
    assert "24x7" in data1["answer"] or "batches" in data1["answer"]

    # Turn 2: "when did this came into action"
    res2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "when did this came into action"
    }, headers=auth_headers_user1)
    assert res2.status_code == 200
    data2 = res2.json()
    # Must synthesize exact effective date rather than repeating raw chunk
    assert "December 16, 2019" in data2["answer"] or "2019" in data2["answer"]
    assert "effect" in data2["answer"].lower()

    # Turn 3: "what is the full form of neft"
    res3 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "what is the full form of neft"
    }, headers=auth_headers_user1)
    assert res3.status_code == 200
    data3 = res3.json()
    # Must directly expand the acronym
    assert "National Electronic Funds Transfer" in data3["answer"]

    # Turn 4: "what are its charges"
    res4 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "what are its charges"
    }, headers=auth_headers_user1)
    assert res4.status_code == 200
    data4 = res4.json()
    assert any(term in data4["answer"].lower() for term in ["charges", "waived", "prohibited", "penal", "penalty"])

def test_redis_cache_operations():
    from backend.cache.redis_cache import redis_cache
    # Test setting and getting context
    redis_cache.cache_conversation_context(
        user_id="test_user_1",
        conv_id="conv_100",
        context_data={"topic": "NEFT", "intent": "TEMPORAL_EFFECTIVE"}
    )
    ctx = redis_cache.get_conversation_context(user_id="test_user_1", conv_id="conv_100")
    assert ctx is not None
    assert ctx["topic"] == "NEFT"
    assert ctx["intent"] == "TEMPORAL_EFFECTIVE"

    # Test topic facts caching
    redis_cache.cache_topic_facts("test_user_1", "conv_100", "NEFT", {"effective_date": "December 16, 2019"})
    facts = redis_cache.get_topic_facts("test_user_1", "conv_100", "NEFT")
    assert facts is not None
    assert facts["effective_date"] == "December 16, 2019"

def test_catalog_available_documents_intent(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What official RBI Master Directions and IDFC Bank policies are available in the knowledge base?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "Reserve Bank of India" in data["answer"]
    assert "IDFC FIRST Bank" in data["answer"]
    assert "KYC" in data["answer"]
    assert "NEFT" in data["answer"]
    assert "Digital Lending" in data["answer"]
    assert "FASTag" in data["answer"]

def test_fastag_reloading_procedural_intent(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "how the fastag can be reloaded"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "savings account" in data["answer"].lower()
    assert "auto-recharge" in data["answer"].lower()
    # Must NOT have raw 'Section 1: ...' unparsed prefix
    assert "Section 1: IDFC FIRST FASTag Issuance and Auto-Recharge" not in data["answer"]




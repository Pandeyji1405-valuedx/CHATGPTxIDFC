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


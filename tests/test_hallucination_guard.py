import pytest

def test_hallucination_rejection_weather_query(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is the weather forecast in Mumbai today?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower() or "verified information is unavailable" in data["answer"].lower()
    assert len(data["citations"]) == 0

def test_hallucination_rejection_sports_query(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "Who won yesterday's football match between Brazil and Argentina?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower()

def test_unapproved_fictitious_banking_penalty(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is the exact penalty for unapproved regulation XYZ-999-FAKE?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower()

def test_hallucination_rejection_crypto_binance_query(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What are the KYC rules for buying Bitcoin and cryptocurrency on Binance?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower()
    assert len(data["citations"]) == 0

def test_hallucination_rejection_external_bank_fixed_deposit(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is the interest rate on SBI bank fixed deposits?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower()

def test_chat_feedback_submission_and_audit(client, auth_headers_user1):
    chat_res = client.post("/api/chat", json={
        "query": "What is the compensation for delayed NEFT credit?"
    }, headers=auth_headers_user1)
    assert chat_res.status_code == 200
    msg_id = chat_res.json()["assistant_message_id"]

    fb_res = client.post("/api/chat/feedback", json={
        "message_id": msg_id,
        "rating": 5,
        "category": "ACCURACY",
        "feedback_text": "Repo rate + 2% verified accurately."
    }, headers=auth_headers_user1)
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "recorded"

def test_production_health_check_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database" in data
    assert "vector_store" in data

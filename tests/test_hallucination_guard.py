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

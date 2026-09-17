import pytest

def test_exact_circular_matching(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "Tell me about circular DOR.AML.REC.48/14.01.001/2023-24"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert len(data["citations"]) >= 1
    assert "KYC" in data["citations"][0]["document_title"]

def test_digital_lending_guidelines(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What are the cooling-off look-up period rules in RBI Digital Lending Directions 2022?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "cooling-off" in data["answer"].lower() or "look-up" in data["answer"].lower()
    assert "3 days" in data["answer"] or "Digital Lending" in data["citations"][0]["document_title"]

def test_housing_loan_ltv_limits(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is the maximum Loan to Value (LTV) ratio for housing loans up to 30 Lakhs?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "90%" in data["answer"] or "Housing Finance" in data["citations"][0]["document_title"]

def test_unauthorized_electronic_transaction_liability(client, auth_headers_user1):
    res = client.post("/api/chat", json={
        "query": "What is customer liability if an unauthorized electronic banking fraud is reported within 3 days?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert "Zero Liability" in data["answer"] or "zero" in data["answer"].lower()

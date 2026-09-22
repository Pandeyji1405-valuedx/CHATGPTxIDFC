import pytest

def test_home_loan_typo_and_layman_query(client, auth_headers_user1):
    """Verifies that 'whats the new updated guide line for home laon' answers correctly with citations."""
    res = client.post("/api/chat", json={
        "query": "whats the new updated guide line for home laon"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert data["confidence"] >= 0.40
    assert "couldn't find sufficient verified information" not in data["answer"].lower()
    assert any(term in data["answer"].lower() for term in ["ltv", "housing", "loan to value", "ratio", "30 lakh", "75 lakh", "80%"])

def test_foreclosure_floating_rate_layman_query(client, auth_headers_user1):
    """Verifies queries about loan prepayment and foreclosure penalties."""
    res = client.post("/api/chat", json={
        "query": "can bank charge penalty if i close my floating home loan early"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_atm_cash_failed_layman_query(client, auth_headers_user1):
    """Verifies query about ATM failed transactions and turnaround compensation."""
    res = client.post("/api/chat", json={
        "query": "atm machine did not give cash but money was deducted from account"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_wrong_account_transfer_layman_query(client, auth_headers_user1):
    """Verifies query about accidental wrong account transfer."""
    res = client.post("/api/chat", json={
        "query": "transferred money to wrong account mistakenly what to do"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_fraud_stolen_card_zero_liability(client, auth_headers_user1):
    """Verifies query about stolen debit card and zero fraud liability."""
    res = client.post("/api/chat", json={
        "query": "someone stole my debit card and did shopping, will bank pay back"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_video_kyc_from_home(client, auth_headers_user1):
    """Verifies query about doing video KYC from home."""
    res = client.post("/api/chat", json={
        "query": "how to do kyc from home using mobile video without visiting branch"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()
    assert "v-cip" in data["answer"].lower() or "video" in data["answer"].lower()

def test_recovery_agent_threats_digital_lending(client, auth_headers_user1):
    """Verifies query about recovery agent conduct and digital lending rules."""
    res = client.post("/api/chat", json={
        "query": "recovery agent is threatening me and calling my contacts for app loan"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_calamity_relief_moratorium(client, auth_headers_user1):
    """Verifies query about natural calamities and loan restructuring."""
    res = client.post("/api/chat", json={
        "query": "flood damaged my house and shop can bank give loan relief"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_fastag_duplicate_toll_chargeback(client, auth_headers_user1):
    """Verifies query about FASTag toll disputes."""
    res = client.post("/api/chat", json={
        "query": "fastag deducted money twice at toll gate how to get refund"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] in ["KNOWLEDGE_BASE", "DATABASE_AND_KNOWLEDGE_BASE"]
    assert len(data["citations"]) >= 1
    assert "couldn't find sufficient verified information" not in data["answer"].lower()

def test_unapproved_out_of_scope_query_rejected(client, auth_headers_user1):
    """Verifies that out-of-scope non-banking queries (like bitcoin/crypto/sports) are strictly refused."""
    res = client.post("/api/chat", json={
        "query": "what is the price of bitcoin in binance cryptocurrency exchange"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert data["confidence"] == 0.0
    assert "couldn't find sufficient verified information" in data["answer"].lower()

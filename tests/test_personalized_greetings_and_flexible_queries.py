import pytest
from backend.rag.nlp_engine import nlp_engine
from backend.rag.rag_engine import rag_engine

def test_extract_friendly_user_name():
    # Test email-based name extraction
    assert nlp_engine.extract_friendly_user_name("User", "shubham.kdjndjksv@ggmail.com") == "Shubham"
    assert nlp_engine.extract_friendly_user_name(None, "shubham.kdjndjksv@ggmail.com") == "Shubham"
    assert nlp_engine.extract_friendly_user_name("", "devesh.pandey1405@gmail.com") == "Devesh"
    assert nlp_engine.extract_friendly_user_name("devesh pandey1405", "devesh.pandey1405@gmail.com") == "Devesh"
    assert nlp_engine.extract_friendly_user_name("Shubham Sharma", "shubham@gmail.com") == "Shubham"
    assert nlp_engine.extract_friendly_user_name("Customer", "customer@idfcbank.com") == "Customer"

def test_personalized_greetings_with_username():
    # Hello / Hi
    res_hello = nlp_engine.detect_chitchat("hello", user_name="Shubham")
    assert res_hello is not None
    assert res_hello["is_chitchat"] is True
    assert "Hello Shubham!" in res_hello["response"]

    # Good Afternoon
    res_afternoon = nlp_engine.detect_chitchat("good afternoon", user_name="Shubham")
    assert res_afternoon is not None
    assert res_afternoon["is_chitchat"] is True
    assert "Good afternoon Shubham!" in res_afternoon["response"]

    # Good Morning
    res_morning = nlp_engine.detect_chitchat("good morning", user_name="Devesh")
    assert res_morning is not None
    assert res_morning["is_chitchat"] is True
    assert "Good morning Devesh!" in res_morning["response"]

    # Good Night
    res_night = nlp_engine.detect_chitchat("good night", user_name="Shubham")
    assert res_night is not None
    assert res_night["is_chitchat"] is True
    assert "Good night Shubham!" in res_night["response"]

    # Namaste
    res_namaste = nlp_engine.detect_chitchat("namaste", user_name="Shubham")
    assert res_namaste is not None
    assert res_namaste["is_chitchat"] is True
    assert "Namaste Shubham!" in res_namaste["response"]

def test_chat_endpoint_personalized_greeting(client, auth_headers_user1):
    # Test chat endpoint with user1 (name is User Alpha)
    res = client.post("/api/chat", headers=auth_headers_user1, json={"query": "hello"})
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "CONVERSATIONAL"
    assert "User" in data["answer"] or "Alpha" in data["answer"] or "Hello" in data["answer"]

def test_flexible_and_jumbled_kyc_queries(client, auth_headers_user1):
    # 1. Direct query
    res1 = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What is KYC?"
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert "Know Your Customer" in data1["answer"] or "KYC" in data1["answer"]
    assert len(data1["citations"]) > 0

    # 2. Keyword query
    res2 = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "KYC"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Know Your Customer" in data2["answer"] or "KYC" in data2["answer"]
    assert len(data2["citations"]) > 0

    # 3. Jumbled / Descriptive style query as given in user prompt:
    # "whats kyc or kyc, a term where person needs to be physically present of video authenticating etc"
    res3 = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "whats kyc or kyc, a term where person needs to be physically present of video authenticating etc"
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert "Know Your Customer" in data3["answer"] or "KYC" in data3["answer"]
    assert len(data3["citations"]) > 0
    # Verify core meaning consistency: mentions V-CIP / Video and physical / OVDs
    ans_lower = data3["answer"].lower()
    assert "video" in ans_lower or "v-cip" in ans_lower or "officially valid" in ans_lower or "ovd" in ans_lower

    # 4. Another descriptive variant
    res4 = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "kyc, person physically present or video authenticate"
    })
    assert res4.status_code == 200
    data4 = res4.json()
    assert "Know Your Customer" in data4["answer"] or "KYC" in data4["answer"]
    assert len(data4["citations"]) > 0

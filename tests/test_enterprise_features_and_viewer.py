import pytest
import uuid
import json
from backend.cache.redis_cache import redis_cache

def test_enterprise_sso_login_azure_ad(client):
    email = f"compliance_{uuid.uuid4().hex[:6]}@idfcbank.com"
    name = "IDFC Senior Compliance Officer"
    res = client.post("/api/auth/sso", json={
        "provider": "azure_ad",
        "email": email,
        "name": name,
        "tenant_domain": "idfcbank.com",
        "department": "Risk & Compliance"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["provider"] == "azure_ad"
    assert data["sso_federated"] is True
    assert data["user"]["email"] == email
    assert data["user"]["name"] == name

def test_enterprise_sso_login_saml_okta(client):
    email = f"saml_user_{uuid.uuid4().hex[:6]}@idfcbank.com"
    name = "IDFC SAML Officer"
    res = client.post("/api/auth/sso", json={
        "provider": "saml_okta",
        "email": email,
        "name": name,
        "tenant_domain": "idfcbank.com",
        "department": "Treasury & Capital Markets"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["provider"] == "saml_okta"
    assert data["sso_federated"] is True

def test_user_personal_memory_lifecycle(client, auth_headers_user1):
    # Seed a memory in redis/memory store for user1
    # Get user profile to determine user_id
    me_res = client.get("/api/auth/me", headers=auth_headers_user1)
    assert me_res.status_code == 200
    user_id = me_res.json()["id"]

    sample_memories = [
        {"key": "preferred_regulator", "category": "preference", "value": "RBI", "confidence": 1.0},
        {"key": "department", "category": "preference", "value": "Retail Lending", "confidence": 1.0}
    ]
    redis_cache.set(f"user_memory:{user_id}", json.dumps(sample_memories))

    # 1. Fetch user memories
    get_res = client.get("/api/user/memories", headers=auth_headers_user1)
    assert get_res.status_code == 200
    mem_data = get_res.json()
    assert mem_data["user_id"] == user_id
    assert mem_data["total_count"] >= 2
    keys = [m["key"] for m in mem_data["memories"]]
    assert "preferred_regulator" in keys
    assert "department" in keys

    # 2. Delete a specific memory
    del_res = client.delete("/api/user/memories/preferred_regulator", headers=auth_headers_user1)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify deleted
    get_res2 = client.get("/api/user/memories", headers=auth_headers_user1)
    keys2 = [m["key"] for m in get_res2.json()["memories"]]
    assert "preferred_regulator" not in keys2
    assert "department" in keys2

    # 3. Clear all memories
    clear_res = client.post("/api/user/memories/clear", headers=auth_headers_user1)
    assert clear_res.status_code == 200
    get_res3 = client.get("/api/user/memories", headers=auth_headers_user1)
    assert get_res3.json()["total_count"] == 0

def test_conversation_sharing_and_read_only_view(client, auth_headers_user1):
    # 1. Create a conversation and post a message
    create_res = client.post("/api/conversations", json={"title": "Compliance Review for Board Audit"}, headers=auth_headers_user1)
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    chat_res = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What are the KYC guidelines for individuals?"
    }, headers=auth_headers_user1)
    assert chat_res.status_code == 200

    # 2. Generate a shareable link
    share_res = client.post(f"/api/conversations/{conv_id}/share", json={"expires_in_hours": 48}, headers=auth_headers_user1)
    assert share_res.status_code == 200
    share_data = share_res.json()
    assert "share_token" in share_data
    assert "share_url" in share_data
    assert share_data["conversation_id"] == conv_id
    share_token = share_data["share_token"]

    # 3. View shared conversation as an unauthenticated external user
    view_res = client.get(f"/api/share/{share_token}")
    assert view_res.status_code == 200
    view_data = view_res.json()
    assert view_data["title"] == "Compliance Review for Board Audit"
    assert len(view_data["messages"]) >= 2 # user query + assistant answer
    assert view_data["is_expired"] is False

    # 4. Accessing invalid or expired token returns 404
    bad_res = client.get("/api/share/invalid_token_999xyz")
    assert bad_res.status_code == 404

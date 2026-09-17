import pytest

def test_cross_user_isolation(client, auth_headers_user1, auth_headers_user2):
    # 1. User 1 creates a conversation
    create_res = client.post("/api/conversations", json={"title": "Alpha Confidential Loan Query"}, headers=auth_headers_user1)
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # 2. User 1 sends a message in that conversation
    chat_res = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is the KYC requirement?"
    }, headers=auth_headers_user1)
    assert chat_res.status_code == 200

    # 3. User 2 attempts to view User 1's conversation -> MUST FAIL (404/403)
    user2_get_res = client.get(f"/api/conversations/{conv_id}", headers=auth_headers_user2)
    assert user2_get_res.status_code == 404

    # 4. User 2 attempts to rename User 1's conversation -> MUST FAIL (404/403)
    user2_put_res = client.put(f"/api/conversations/{conv_id}", json={"title": "Hacked Title"}, headers=auth_headers_user2)
    assert user2_put_res.status_code == 404

    # 5. User 2 attempts to delete User 1's conversation -> MUST FAIL (404/403)
    user2_del_res = client.delete(f"/api/conversations/{conv_id}", headers=auth_headers_user2)
    assert user2_del_res.status_code == 404

    # 6. User 2 searches conversations -> User 1's conversation MUST NOT appear
    search_res = client.get("/api/conversations/search?q=Confidential", headers=auth_headers_user2)
    assert search_res.status_code == 200
    assert len(search_res.json()) == 0

    # User 1 searches -> MUST appear
    search_u1 = client.get("/api/conversations/search?q=Confidential", headers=auth_headers_user1)
    assert search_u1.status_code == 200
    assert len(search_u1.json()) >= 1

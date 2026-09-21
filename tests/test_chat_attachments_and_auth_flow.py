import pytest
import io
import uuid

def test_login_nonexistent_user_returns_signup_prompt(client):
    res = client.post("/api/auth/login", json={
        "email": f"nonexistent_{uuid.uuid4().hex[:6]}@idfcbank.com",
        "password": "Password123"
    })
    assert res.status_code == 404
    data = res.json()
    assert "sign up" in data["detail"].lower()

def test_chat_attachment_upload_text_and_examine(client, auth_headers_user1):
    file_content = b"RBI Directive 2026: All banking portals must offer automated AI audit reports with 99.9% uptime."
    file_obj = io.BytesIO(file_content)
    
    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("rbi_directive_2026.txt", file_obj, "text/plain")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert "attachment" in upload_data
    att = upload_data["attachment"]
    assert att["original_name"] == "rbi_directive_2026.txt"
    assert att["file_type"] == "txt"
    assert "99.9%" in att["extracted_text"]

    # Now query the chat with the attachment
    chat_res = client.post(
        "/api/chat",
        json={
            "query": "What are the key requirements in this attached document?",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    assert "rbi_directive_2026.txt" in chat_data["answer"] or "Document Analysis" in chat_data["answer"]
    assert "99.9%" in chat_data["answer"] or "uptime" in chat_data["answer"].lower()

def test_chat_attachment_empty_query_defaults_to_analysis(client, auth_headers_user1):
    file_content = b"Financial Summary: IDFC FIRST Bank reported 24% YoY growth in retail deposits for Q4 FY26."
    file_obj = io.BytesIO(file_content)
    
    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("q4_financials.txt", file_obj, "text/plain")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]

    # Query with empty text
    chat_res = client.post(
        "/api/chat",
        json={
            "query": "",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    assert "q4_financials.txt" in chat_data["answer"]
    assert "24%" in chat_data["answer"]

def test_greeting_query_includes_user_name(client, auth_headers_user1):
    res = client.post(
        "/api/chat",
        json={"query": "hello, good morning!"},
        headers=auth_headers_user1
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "CONVERSATIONAL"
    assert "customer" in data["answer"].lower() or "shubham" in data["answer"].lower() or "devesh" in data["answer"].lower()

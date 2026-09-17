import pytest
import socket
from unittest.mock import patch
from backend.models import KnowledgeDocument, KnowledgeChunk
from backend.database import SessionLocal
from backend.routers.admin_router import rebuild_vector_index

def test_source_separation_distinction(client, auth_headers_user1):
    # Test RBI Document
    res_rbi = client.post("/api/chat", json={
        "query": "What are the KYC guidelines under DOR.AML.REC.48/14.01.001/2023-24?"
    }, headers=auth_headers_user1)
    assert res_rbi.status_code == 200
    data_rbi = res_rbi.json()
    assert len(data_rbi["citations"]) >= 1
    assert data_rbi["citations"][0]["source"] == "RBI"

    # Test Bank Policy Document
    res_bank = client.post("/api/chat", json={
        "query": "What is the interest credit frequency in IDFC FIRST Bank savings accounts?"
    }, headers=auth_headers_user1)
    assert res_bank.status_code == 200
    data_bank = res_bank.json()
    assert len(data_bank["citations"]) >= 1
    assert data_bank["citations"][0]["source"] == "BANK_POLICY"
    assert "IDFC FIRST" in data_bank["citations"][0]["document_title"]

def test_zero_internet_chat_network_isolation(client, auth_headers_user1):
    # During normal chat, assert no external web search client or urllib/requests call is invoked
    import urllib.request
    with patch("urllib.request.urlopen") as mock_url:
        res = client.post("/api/chat", json={
            "query": "What is the RTGS minimum limit?"
        }, headers=auth_headers_user1)
        assert res.status_code == 200
        data = res.json()
        assert data["source_type"] == "KNOWLEDGE_BASE"
        assert "2,00,000" in data["answer"] or "Two Lakhs" in data["answer"]
        # Ensure chat did not initiate external web search calls
        assert mock_url.call_count == 0

def test_answerability_intent_validation_refusal(client, auth_headers_user1):
    # Query mentions KYC but asks for a specific subtopic not present in the seeded KYC text
    res = client.post("/api/chat", json={
        "query": "What is the KYC document retention period for closed accounts in years?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    # Since the seed document does not specify the retention period for closed accounts,
    # the answerability check must prevent fabricating an answer.
    assert data["source_type"] == "NO_SUPPORTED_SOURCE"
    assert "couldn't find sufficient verified information" in data["answer"].lower()

def test_end_to_end_user_lifecycle(client):
    import uuid
    # 1. Register new user
    uid = uuid.uuid4().hex[:6]
    user_email = f"e2e_customer_{uid}@idfcbank.com"
    reg_res = client.post("/api/auth/register", json={
        "name": "E2E Tester",
        "email": user_email,
        "password": "SecurePassword@2026"
    })
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": user_email,
        "password": "SecurePassword@2026"
    })
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == user_email

    # 3. Create conversation
    conv_create = client.post("/api/conversations", json={"title": "E2E Banking Inquiries"}, headers=auth_headers)
    assert conv_create.status_code == 201
    conv_id = conv_create.json()["id"]

    # 4. Ask Turn 1: "What is NEFT?"
    turn1 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is NEFT?"
    }, headers=auth_headers)
    assert turn1.status_code == 200
    assert turn1.json()["source_type"] == "KNOWLEDGE_BASE"
    assert len(turn1.json()["citations"]) >= 1

    # 5. Ask Turn 2: "What is its transaction limit?" (Coreference resolution)
    turn2 = client.post("/api/chat", json={
        "conversation_id": conv_id,
        "query": "What is its transaction limit?"
    }, headers=auth_headers)
    assert turn2.status_code == 200
    assert "NEFT" in turn2.json()["normalized_query"]

    # 6. Reload Conversation History & verify stored records
    conv_get = client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
    assert conv_get.status_code == 200
    data = conv_get.json()
    assert len(data["messages"]) >= 4 # 2 user messages, 2 assistant messages
    user_msgs = [m for m in data["messages"] if m["role"] == "user"]
    assert user_msgs[0]["original_content"] == "What is NEFT?"
    assert user_msgs[1]["original_content"] == "What is its transaction limit?"
    assert "NEFT" in user_msgs[1]["normalized_content"]

    # 7. Rename Conversation
    rename_res = client.put(f"/api/conversations/{conv_id}", json={"title": "Renamed Banking Inquiries"}, headers=auth_headers)
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Renamed Banking Inquiries"

    # 8. Delete Conversation
    del_res = client.delete(f"/api/conversations/{conv_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # 9. Verify Deletion
    verify_del = client.get(f"/api/conversations/{conv_id}", headers=auth_headers)
    assert verify_del.status_code == 404

def test_conflicting_approved_documents_disclosure(client, auth_headers_user1, auth_headers_admin):
    # Upload conflicting test policies as admin
    # Document A
    doc_a_payload = {
        "title": "State Specific Interest Rate Policy 2023",
        "notification_number": "RBI/2023-CONFLICT-01",
        "source": "RBI",
        "publication_date": "2023-01-01"
    }
    # Test via direct RAG conflict detector check
    from backend.rag.rag_engine import rag_engine
    mock_chunks = [
        {
            "document_id": "doc-1",
            "doc_title": "RBI Housing Policy 2021",
            "source": "RBI",
            "notification_number": "RBI/2021-01",
            "chunk_text": "Conflict provision: Housing loan maximum LTV is capped strictly at 75%.",
            "score": 0.85
        },
        {
            "document_id": "doc-2",
            "doc_title": "RBI Housing Policy 2024 (Updated)",
            "source": "RBI",
            "notification_number": "RBI/2024-99",
            "chunk_text": "Conflict provision: Housing loan maximum LTV has been revised upwards to 85%.",
            "score": 0.82
        }
    ]
    conflict_result = rag_engine.check_conflicting_chunks(mock_chunks)
    assert conflict_result is not None
    assert "conflicting information" in conflict_result.lower()
    assert "Source A" in conflict_result
    assert "Source B" in conflict_result
    assert "effective date should be verified" in conflict_result.lower()

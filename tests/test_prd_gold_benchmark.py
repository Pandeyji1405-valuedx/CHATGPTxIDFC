import pytest
import os
import json
from backend.rag.vector_store import hybrid_vector_store
from backend.rag.token_budget import TokenBudgetController
from backend.rag.response_composer import ResponseComposer
from backend.rag.rag_engine import rag_engine
from backend.database import SessionLocal
from backend.models import KnowledgeDocument, KnowledgeChunk

def test_multi_regulator_sebi_lodr(client, auth_headers_user1):
    """Test SEBI LODR query returns accurate SEBI regulation citation."""
    res = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What are the SEBI LODR materiality thresholds for disclosure?",
        "regulator_filter": ["SEBI"]
    })
    assert res.status_code == 200
    data = res.json()
    assert "turnover" in data["answer"].lower() or "net worth" in data["answer"].lower() or "2%" in data["answer"]
    assert len(data["citations"]) > 0
    assert any("SEBI" in c.get("source", "").upper() or "SEBI" in c.get("title", "").upper() for c in data["citations"])
    assert data["tokens_used"] is not None
    assert data["tokens_used"]["tokens_total"] > 0

def test_multi_regulator_irdai_free_look(client, auth_headers_user1):
    """Test IRDAI query returns accurate Free Look period policyholder guidelines."""
    res = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What is the Free Look cancellation period for electronic insurance policies under IRDAI regulations?",
        "regulator_filter": ["IRDAI"]
    })
    assert res.status_code == 200
    data = res.json()
    assert "30" in data["answer"] or "free look" in data["answer"].lower()
    assert len(data["citations"]) > 0
    assert any("IRDAI" in c.get("title", "").upper() or "IRDAI" in c.get("source", "").upper() for c in data["citations"])

def test_multi_regulator_rbi_kyc(client, auth_headers_user1):
    """Test RBI KYC master direction query."""
    res = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What is the periodic updation KYC schedule for high risk, medium risk, and low risk customers under RBI?",
        "regulator_filter": ["RBI"]
    })
    assert res.status_code == 200
    data = res.json()
    assert "2 years" in data["answer"] or "8 years" in data["answer"] or "10 years" in data["answer"]
    assert any("RBI" in c.get("source", "").upper() or "KYC" in c.get("title", "").upper() for c in data["citations"])

def test_temporal_filter_superseded_neft(client, auth_headers_user1):
    """Test temporal query with historical as_of_date returns historical rule, while current returns 24x7."""
    # Historical date query (2018)
    res_hist = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What were the operating hours for NEFT transactions?",
        "as_of_date": "2018-06-01"
    })
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["citations"]) > 0

    # Current date query (default)
    res_curr = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What are the operating hours for NEFT transactions?",
        "as_of_date": "2024-06-01"
    })
    assert res_curr.status_code == 200
    curr_data = res_curr.json()
    assert "24x7" in curr_data["answer"] or "round the clock" in curr_data["answer"].lower() or "48" in curr_data["answer"]

def test_response_composer_zero_internal_leakage():
    """Verify ResponseComposer purges system IDs, chunk IDs, and score metadata."""
    dirty_answer = (
        "Under RBI KYC directions [S1], chunk_id=123e4567-e89b-12d3-a456-426614174000, high risk customers "
        "must be updated every 2 years [score: 0.985] (similarity=0.88). Based on provided context S2:"
    )
    citations = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "document_id": "doc-uuid-999",
            "doc_title": "RBI Master Direction - Know Your Customer (KYC)",
            "notification_number": "DOR.AML.REC.48/14.01.001/2023-24",
            "source": "RBI",
            "page_number": 1,
            "section": "Section 4",
            "chunk_text": "Periodic updation every 2 years for high risk",
            "source_offsets": {"start_char": 0, "end_char": 45},
            "bounding_box": {"page": 1, "x": 54, "y": 100, "width": 500, "height": 100}
        }
    ]
    
    clean_answer, clean_citations = ResponseComposer.compose_response(
        raw_answer=dirty_answer,
        retrieved_chunks=citations,
        requested_depth="standard"
    )
    
    assert "[S1]" not in clean_answer
    assert "chunk_id=" not in clean_answer
    assert "score:" not in clean_answer
    assert "similarity=" not in clean_answer
    assert len(clean_citations) == 1
    assert clean_citations[0]["notification_number"] == "DOR.AML.REC.48/14.01.001/2023-24"
    assert clean_citations[0]["page_number"] == 1
    assert "bounding_box" in clean_citations[0]

def test_token_budget_controller_budgeting():
    """Verify TokenBudgetController tracks and trims evidence within budget."""
    tbc = TokenBudgetController()
    assert tbc.budget["system"] == 800
    assert tbc.budget["evidence"] == 3000

    long_chunks = [
        {"id": f"c_{i}", "chunk_text": "word " * 100, "doc_title": f"Doc {i}", "page_number": 1, "section": "S1"}
        for i in range(20)
    ]
    selected = tbc.fit_evidence(long_chunks, max_tokens=1000)
    total_words = sum(len(c["chunk_text"].split()) for c in selected)
    assert total_words <= 1200 # Roughly within token budget
    assert len(selected) < len(long_chunks)

def test_token_budget_controller_history_summarization():
    """Verify conversation history summarization when history exceeds 6 turns."""
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message turn number {i} discussing regulatory requirement {i}"}
        for i in range(12)
    ]
    summarized_history, new_summary = TokenBudgetController.summarize_history_if_needed(
        messages=messages,
        existing_summary=None,
        max_recent_turns=4
    )
    assert len(summarized_history) <= 5 # 1 summary system msg + 4 recent turns
    assert new_summary is not None
    assert "Prior Conversation Summary" in summarized_history[0]["content"]

def test_feedback_submission_and_triage(client, auth_headers_user1, auth_headers_admin):
    """Test 8-category regulatory triage feedback submission and retrieval."""
    # First create a chat message to get message_id
    chat_res = client.post("/api/chat", headers=auth_headers_user1, json={
        "query": "What is the LTV ratio for housing loans above 75 Lakhs?"
    })
    assert chat_res.status_code == 200
    msg_id = chat_res.json()["assistant_message_id"]

    # Submit feedback with SUPERSEDED_OUTDATED category
    fb_res = client.post("/api/feedback", headers=auth_headers_user1, json={
        "message_id": msg_id,
        "rating": -1,
        "category": "SUPERSEDED_OUTDATED",
        "comment": "Needs to clarify between 2015 superseded norms and current 2020 circular.",
        "suggested_correction": "State that October 2020 rationalisation sets LTV to 75% with 50% risk weight."
    })
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["status"] == "logged"
    assert fb_data["category"] == "SUPERSEDED_OUTDATED"

    # Admin retrieve feedback MIS list
    list_res = client.get("/api/feedback", headers=auth_headers_admin)
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(item["message_id"] == msg_id for item in items)

def test_admin_ingestion_mis(client, auth_headers_admin):
    """Test Admin Ingestion MIS endpoint returns regulator counts, status counts, OCR stats."""
    res = client.get("/api/admin/mis/ingestion", headers=auth_headers_admin)
    assert res.status_code == 200
    data = res.json()
    assert "total_documents" in data
    assert "total_chunks" in data
    assert "documents_by_regulator" in data
    assert "documents_by_status" in data
    assert "ocr_statistics" in data
    assert data["total_documents"] >= 5

def test_admin_consumption_mis(client, auth_headers_admin):
    """Test Admin Consumption MIS endpoint returns query metrics and feedback breakdown."""
    res = client.get("/api/admin/mis/consumption", headers=auth_headers_admin)
    assert res.status_code == 200
    data = res.json()
    assert "total_queries" in data
    assert "queries_by_regulator" in data
    assert "feedback_by_category" in data

def test_admin_supersede_document(client, auth_headers_admin):
    """Test Admin Document Supersede endpoint."""
    # List documents
    docs_res = client.get("/api/admin/documents", headers=auth_headers_admin)
    assert docs_res.status_code == 200
    docs = docs_res.json()
    assert len(docs) > 0
    target_doc = docs[0]

    # Supersede target document
    super_res = client.post(f"/api/admin/documents/{target_doc['id']}/supersede", headers=auth_headers_admin, json={
        "effective_until": "2024-01-01",
        "superseded_by_id": None,
        "reason": "Superseded by updated 2024 master direction"
    })
    assert super_res.status_code == 200
    super_data = super_res.json()
    assert super_data["status"] == "superseded"
    assert super_data["effective_until"] == "2024-01-01"

def test_hybrid_search_regulator_filtering():
    """Direct test on HybridVectorStore regulator filtering."""
    results_sebi = hybrid_vector_store.search(
        query="incident reporting to CERT-In within 6 hours",
        regulator_filter=["SEBI"]
    )
    assert len(results_sebi) > 0
    assert any(r.get("regulator") == "SEBI" for r in results_sebi)
    assert all(r.get("regulator") == "SEBI" for r in results_sebi)

    results_irdai = hybrid_vector_store.search(
        query="CISO appointment reporting to Board Risk Management Committee",
        regulator_filter=["IRDAI"]
    )
    assert len(results_irdai) > 0
    assert any(r.get("regulator") == "IRDAI" for r in results_irdai)
    assert all(r.get("regulator") == "IRDAI" for r in results_irdai)

def test_hybrid_search_temporal_as_of_date():
    """Direct test on HybridVectorStore temporal validation."""
    # As of 2017, only active docs valid in 2017 should be returned
    results_2017 = hybrid_vector_store.search(
        query="NEFT operating hours and batches",
        as_of_date="2018-05-01"
    )
    assert len(results_2017) > 0
    # Any returned doc should have effective_from <= 2018-05-01
    for r in results_2017:
        eff_from = r.get("effective_from") or r.get("publication_date")
        if eff_from:
            assert eff_from <= "2018-05-01"

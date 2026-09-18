import pytest
from backend.ingestion.ocr_engine import ocr_engine

def test_ocr_character_ambiguity_detector():
    text = "Circular No: RBI/2024-25/0O18 with penalty amount ₹SO,OOO and interest B.5%"
    ambiguities = ocr_engine.detect_character_ambiguities(text)

    pairs = [a["character_pair"] for a in ambiguities]
    assert "0 ↔ O" in pairs
    assert "5 ↔ S" in pairs
    assert "8 ↔ B" in pairs

def test_ocr_ambiguity_in_chat_response(client, auth_headers_user1, auth_headers_admin):
    import io
    ocr_doc = io.BytesIO(b"Scanned Circular RBI/2024-25/0O18: The penalty for delayed reporting is Rs. 5O,OOO and interest B.5%.")
    client.post(
        "/api/admin/documents/upload",
        files={"file": ("ocr_circular.txt", ocr_doc, "text/plain")},
        data={"title": "Scanned Circular 0O18", "source": "RBI", "notification_number": "RBI/2024-25/0O18"},
        headers=auth_headers_admin
    )
    res = client.post("/api/chat", json={
        "query": "What is the penalty in scanned circular RBI/2024-25/0O18?"
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "KNOWLEDGE_BASE"
    assert len(data["ambiguity_flags"]) >= 1
    # Check that ambiguity flag is returned with context
    assert any(a["character_pair"] == "0 ↔ O" for a in data["ambiguity_flags"])

def test_ocr_no_false_positives_on_regular_prose():
    ordinary_text = "The customer must submit one document to the branch board for verification."
    ambiguities = ocr_engine.detect_character_ambiguities(ordinary_text)
    assert len(ambiguities) == 0, f"False positives detected on regular prose: {ambiguities}"

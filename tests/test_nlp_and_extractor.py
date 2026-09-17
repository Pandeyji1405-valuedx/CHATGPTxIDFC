import pytest
import io
from backend.rag.nlp_engine import nlp_engine
from backend.ingestion.extractor import document_extractor
from backend.rag.validator import answer_validator

def test_hinglish_banking_query_variations():
    queries = [
        ("neft kya hota hai", "NEFT"),
        ("neft ka limit kitna hai", "NEFT"),
        ("rtgs mein kitna amount bhej sakte hai", "RTGS"),
        ("mera neft transaction fail kyu hua", "NEFT"),
        ("NEFT ka max amount kya h", "NEFT"),
        ("tell me neft limit pls", "NEFT")
    ]
    for q, expected_ent in queries:
        res = nlp_engine.process_query(q)
        assert expected_ent in res["resolved_entities"] or expected_ent in res["normalized_query"].upper()

def test_document_extractor_text_and_csv():
    txt_content = b"RBI Circular on Liquidity Coverage Ratio. Minimum requirement is 100%."
    res_txt = document_extractor.extract_document(txt_content, "lcr_policy.txt")
    assert res_txt["page_count"] == 1
    assert "Liquidity Coverage Ratio" in res_txt["pages"][0]["text"]
    assert res_txt["is_ocr"] is False
    assert res_txt["checksum"] is not None

    csv_content = b"metric,target\nCRR,4.5%\nSLR,18.0%"
    res_csv = document_extractor.extract_document(csv_content, "ratios.csv")
    assert "CRR" in res_csv["pages"][0]["text"]
    assert res_csv["document_type"] == "csv"

def test_document_extractor_image():
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    res_img = document_extractor.extract_document(img_bytes, "scanned_memo.png")
    assert res_img["page_count"] == 1
    assert res_img["is_ocr"] is True
    assert res_img["document_type"] == "image"

def test_grounding_validator_catches_hallucinated_facts():
    context = "Under RBI guidelines, the maximum LTV is 90% for housing loans up to 30 Lakhs."
    
    # Valid answer
    valid_answer = "According to RBI guidelines, the maximum LTV is 90% for housing loans up to 30 Lakhs."
    is_valid, _, violations = answer_validator.validate_grounding(valid_answer, context, "KNOWLEDGE_BASE")
    assert is_valid is True
    assert len(violations) == 0

    # Fabricated percentage
    hallucinated_pct = "The maximum LTV is 99% for housing loans."
    is_valid_pct, _, violations_pct = answer_validator.validate_grounding(hallucinated_pct, context, "KNOWLEDGE_BASE")
    assert is_valid_pct is False
    assert any("Percentage" in v for v in violations_pct)

    # Fabricated circular
    hallucinated_circ = "Under circular RBI/2029-30/999, the LTV is 90%."
    is_valid_circ, _, violations_circ = answer_validator.validate_grounding(hallucinated_circ, context, "KNOWLEDGE_BASE")
    assert is_valid_circ is False
    assert any("circular" in v.lower() for v in violations_circ)

def test_admin_document_inspection_and_reindex(client, auth_headers_admin):
    # 1. List documents
    list_res = client.get("/api/admin/documents", headers=auth_headers_admin)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 1
    sample_doc_id = docs[0]["id"]

    # 2. Get document detail
    detail_res = client.get(f"/api/admin/documents/{sample_doc_id}", headers=auth_headers_admin)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert "document" in detail_data
    assert "chunks_preview" in detail_data

    # 3. Trigger re-index
    reindex_res = client.post("/api/admin/reindex", headers=auth_headers_admin)
    assert reindex_res.status_code == 200
    assert reindex_res.json()["total_chunks"] >= 1

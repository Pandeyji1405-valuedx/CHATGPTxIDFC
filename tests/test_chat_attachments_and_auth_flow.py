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

def test_chat_attachment_docx_and_null_byte_sanitization(client, auth_headers_user1):
    # Simulate docx binary with null bytes and content
    file_content = b"PK\x03\x04\x00\x00\x00Cloud Midterm Exam Notes: Distributed computing resilience and failover SLAs.\x00\x00"
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("cloud_midterm.docx", file_obj, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]
    assert att["filename"] == "cloud_midterm.docx"
    assert "\x00" not in att["extracted_text"]

    # Post chat query with this docx attachment
    chat_res = client.post(
        "/api/chat",
        json={
            "query": "Explain the failover SLAs mentioned in this doc",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    assert "\x00" not in chat_data["answer"]

def test_chat_attachment_with_rbi_guidelines_matching_query(client, auth_headers_user1):
    file_content = b"Loan Agreement Draft: Lender levies a penal interest of 36% per annum on missed payments with no Key Fact Statement (KFS) provided to the borrower."
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("sample_loan_agreement.pdf", file_obj, "application/pdf")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]

    # User asks "whether it matches the rbi guidelines"
    chat_res = client.post(
        "/api/chat",
        json={
            "query": "whether it matches the rbi guidelines",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    ans = chat_data["answer"]
    # Verify that the answer directly addresses the RBI compliance check and does NOT give the old placeholder
    assert "Ask specific questions" not in ans
    assert ("rbi" in ans.lower() or "guideline" in ans.lower() or "compliance" in ans.lower() or "kfs" in ans.lower() or "key fact statement" in ans.lower())

def test_chat_attachment_specific_fact_query_answers_directly(client, auth_headers_user1):
    file_content = b"Vendor Policy: Customer dispute resolution SLA is 3 business days for electronic fund transfers."
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("vendor_sla.pdf", file_obj, "application/pdf")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]

    chat_res = client.post(
        "/api/chat",
        json={
            "query": "What is the dispute resolution SLA stated in this document?",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    assert "3" in chat_data["answer"] or "SLA" in chat_data["answer"] or "business days" in chat_data["answer"]

def test_chat_attachment_table_formatting_and_custom_instruction(client, auth_headers_user1):
    file_content = b"Banking Loan Contract: Principal: Rs 10 Lakhs, Interest Rate: 11.5%, Processing Fee: Rs 5,000."
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("contract_terms.pdf", file_obj, "application/pdf")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]

    chat_res = client.post(
        "/api/chat",
        json={
            "query": "Format the financial figures from this contract into a markdown table with columns Parameter and Value",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    ans = chat_data["answer"]
    assert "10" in ans or "11.5" in ans or "5,000" in ans or "|" in ans

def test_chat_attachment_advisory_email_drafting_instruction(client, auth_headers_user1):
    file_content = b"Audit Report: Branch KYC records showed 15 accounts with expired OVD documents requiring immediate outreach."
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/chat/upload-attachment",
        files={"file": ("branch_audit.pdf", file_obj, "application/pdf")},
        headers=auth_headers_user1
    )
    assert upload_res.status_code == 200
    att = upload_res.json()["attachment"]

    chat_res = client.post(
        "/api/chat",
        json={
            "query": "Draft an urgent advisory email to the Branch Manager requesting KYC remediation for these 15 accounts.",
            "attachment": att
        },
        headers=auth_headers_user1
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["source_type"] == "ATTACHMENT_ANALYSIS"
    ans = chat_data["answer"]
    assert any(w in ans.lower() for w in ["branch manager", "dear", "subject", "remediation", "kyc", "15", "ovd", "accounts"])



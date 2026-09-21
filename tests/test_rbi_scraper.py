import os
import pytest
from backend.ingestion.rbi_scraper import rbi_scraper

MOCK_INDEX_HTML = """
<table class="tablebg">
  <tr><th>Circular Number</th><th>Date Of Issue</th><th>Department</th><th>Subject</th><th>Meant For</th></tr>
  <tr>
    <td><a class="link2" href="BS_CircularIndexDisplay.aspx?Id=99991">RBI/2026-2027/999<br>DOR.AML.REC.999/14.01.001/2026-27</a></td>
    <td>18.9.2026</td>
    <td>Department of Regulation</td>
    <td>Master KYC Directions Amendment 2026</td>
    <td>All Scheduled Commercial Banks</td>
  </tr>
</table>
"""

def test_parse_circular_table():
    circulars = rbi_scraper.parse_circular_table(MOCK_INDEX_HTML)
    assert len(circulars) == 1
    circ = circulars[0]
    assert circ["id"] == "99991"
    assert "RBI/2026-2027/999" in circ["circular_number"]
    assert "DOR.AML.REC.999" in circ["notification_number"]
    assert circ["date_of_issue"] == "2026-09-18"
    assert circ["department"] == "Department of Regulation"
    assert circ["subject"] == "Master KYC Directions Amendment 2026"
    assert circ["meant_for"] == "All Scheduled Commercial Banks"
    assert "BS_CircularIndexDisplay.aspx?Id=99991" in circ["detail_url"]

def test_generate_formatted_pdf_and_master(tmp_path):
    temp_pdf_dir = str(tmp_path / "pdfs")
    os.makedirs(temp_pdf_dir, exist_ok=True)
    rbi_scraper.output_dir = temp_pdf_dir

    mock_circular = {
        "id": "99991",
        "circular_number": "RBI/2026-2027/999",
        "notification_number": "DOR.AML.REC.999/14.01.001/2026-27",
        "date_of_issue": "2026-09-18",
        "department": "Department of Regulation",
        "subject": "Master KYC Directions Amendment 2026",
        "meant_for": "All Scheduled Commercial Banks",
        "full_text": "Paragraph 1: In exercise of powers under Banking Regulation Act, 1949.\n\nParagraph 2: Certified copy requirements are hereby updated.",
        "signatory": "Veena Srivastava"
    }

    pdf_path = rbi_scraper.save_and_deliver_as_pdf(mock_circular)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 500
    assert pdf_path.endswith(".pdf")

    master_pdf = os.path.join(temp_pdf_dir, "Master_Compendium.pdf")
    res_master = rbi_scraper.generate_master_compendium_pdf([mock_circular], master_pdf)
    assert os.path.exists(res_master)
    assert os.path.getsize(res_master) > 1000

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.services.language import detect_document_language
from app.services.pdf_parser import parse_pdf_document


@pytest.fixture
def fake_pdf_path():
    fd, path = tempfile.mkstemp(suffix=".pdf")
    sample_text = b"Notice Inviting Tender: Selection of Bus Operator for Procurement and Operation of Electric Buses across India under Gross Cost Contract."
    content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 180 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(" + sample_text + b") Tj\nET\nendstream\nendobj\n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\n%%EOF"
    )
    os.write(fd, content)
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except Exception:
        pass


def test_pdf_parser_success(fake_pdf_path):
    result = parse_pdf_document(fake_pdf_path)

    assert result["file_name"].endswith(".pdf")
    assert result["page_count"] >= 1
    assert len(result["pages"]) >= 1
    assert result["pages"][0]["page_number"] == 1
    assert len(result["document_hash"]) == 64
    assert result["is_english"] is True


def test_pdf_hash_idempotency(fake_pdf_path):
    result1 = parse_pdf_document(fake_pdf_path)
    result2 = parse_pdf_document(fake_pdf_path)
    assert result1["document_hash"] == result2["document_hash"]


def test_ocr_space_fallback_mocked(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "easyocr", None)
    fake_pdf = tmp_path / "scanned_sample.pdf"
    content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 30 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(Hi) Tj\nET\nendstream\nendobj\n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\n%%EOF"
    )
    fake_pdf.write_bytes(content)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ParsedResults": [{"ParsedText": "Mocked OCR Extracted English Text For Verification"}]
    }

    with patch("requests.post", return_value=mock_resp):
        res = parse_pdf_document(str(fake_pdf))
        assert "Mocked OCR Extracted" in res["full_text"]

import pytest
import os
import tempfile
from app.services.pdf_parser import parse_pdf_document
from app.services.language import detect_document_language

@pytest.fixture
def fake_pdf_path():
    fd, path = tempfile.mkstemp(suffix=".pdf")
    # minimal valid-ish PDF
    os.write(fd, b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(Hello World) Tj\nET\nendstream\nendobj\ntrailer\n<< /Size 5 /Root 1 0 R >>\n%%EOF")
    os.close(fd)
    yield path
    os.remove(path)


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




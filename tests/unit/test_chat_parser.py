import pytest
from pathlib import Path
from research_agent.chat.parser import extract_text_from_pdf

def test_extract_text_from_pdf_missing():
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf(Path("/nonexistent/file.pdf"))

def test_extract_text_from_invalid_pdf(tmp_path):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"not a real pdf")
    result = extract_text_from_pdf(pdf_path)
    assert result is None or "text" not in result

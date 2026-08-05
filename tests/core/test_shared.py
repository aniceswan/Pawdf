import pytest

from pawdf.core._shared.errors import InvalidPdfError
from pawdf.core._shared.pdf_io import open_pdf


def test_open_pdf_raises_invalid_pdf_error_on_corrupted_file(tmp_path):
    bad_pdf = tmp_path / "not_a_pdf.pdf"
    bad_pdf.write_bytes(b"this is definitely not a PDF")

    with pytest.raises(InvalidPdfError) as exc_info:
        with open_pdf(bad_pdf):
            pass

    assert "not a valid PDF" in str(exc_info.value) or "valid PDF" in str(exc_info.value)


def test_open_pdf_works_on_valid_pdf(sample_pdf):
    with open_pdf(sample_pdf) as pdf:
        assert len(pdf.pages) == 5

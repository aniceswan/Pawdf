"""Tests for PDF recovery.

The interesting assertions are the two this package exists to get right:
damage is detected at all, and the output is genuinely clean rather than
merely openable.
"""

import pytest

from pawdf.core._shared import EncryptedPdfError, InvalidPdfError
from pawdf.core.repair import repair_pdf


@pytest.fixture
def truncated_pdf(sample_pdf, tmp_path):
    """A PDF cut short, which destroys the cross-reference table while
    leaving most page content intact. This is what a failed download or an
    interrupted write actually looks like.
    """
    data = sample_pdf.read_bytes()
    broken = tmp_path / "truncated.pdf"
    broken.write_bytes(data[: int(len(data) * 0.82)])
    return broken


def test_a_healthy_file_is_reported_as_healthy(sample_pdf, tmp_path):
    result = repair_pdf(sample_pdf, tmp_path / "out.pdf")

    assert result.was_already_readable is True
    assert result.warnings == []


def test_damage_is_detected(truncated_pdf, tmp_path):
    """QPDF rebuilds a broken xref table silently on a normal open, so a plain
    "did it open" probe answers yes for a file that had to be rescued. If this
    ever reports True the detection has regressed to that useless check.
    """
    result = repair_pdf(truncated_pdf, tmp_path / "out.pdf")

    assert result.was_already_readable is False
    assert result.warnings, "a damaged file should say what was wrong with it"


def test_the_output_is_actually_clean(truncated_pdf, tmp_path):
    """Re-saving a recovered document carries the broken trailer straight
    through: the output opens, but only via recovery, which is not a repair.
    """
    import pikepdf

    result = repair_pdf(truncated_pdf, tmp_path / "out.pdf")

    assert result.is_now_clean is True
    with pikepdf.open(result.output_path, attempt_recovery=False) as pdf:
        assert len(pdf.pages) == result.pages_recovered
    with pikepdf.open(result.output_path) as pdf:
        assert pdf.get_warnings() == []


def test_recovered_pages_still_render(truncated_pdf, tmp_path):
    """Structurally valid is not the same as usable, so check a real renderer
    can draw what came back.
    """
    import pypdfium2 as pdfium

    result = repair_pdf(truncated_pdf, tmp_path / "out.pdf")

    doc = pdfium.PdfDocument(result.output_path)
    try:
        assert len(doc) == result.pages_recovered
        assert doc[0].render(scale=0.4).to_pil().size[0] > 0
    finally:
        doc.close()


def test_unrecoverable_input_raises(tmp_path):
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"this was never a PDF")

    with pytest.raises(InvalidPdfError):
        repair_pdf(junk, tmp_path / "out.pdf")


def test_encrypted_is_not_damaged(encrypted_pdf, tmp_path):
    """A locked file is not a broken one, and telling someone to repair it
    would send them down the wrong path.
    """
    with pytest.raises(EncryptedPdfError):
        repair_pdf(encrypted_pdf, tmp_path / "out.pdf")

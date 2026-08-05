"""Tests for OCR.

Tesseract is an external binary that most machines do not have, so the tests
split in two: everything that can be checked without it runs always, and the
end-to-end conversion is skipped when the engine is absent. The absent case is
itself worth testing, because "OCR is unavailable" has to be a clear message
rather than a crash.
"""

import pytest

from pawdf.core.ocr import MAX_DPI, MIN_DPI, ocr_pdf
from pawdf.core.ocr.tesseract import (
    ENV_OVERRIDE,
    TesseractNotFoundError,
    available_languages,
    find_tesseract,
    install_instructions,
)

needs_tesseract = pytest.mark.skipif(find_tesseract() is None, reason="Tesseract is not installed")


# ------------------------------------------------------------- locating --


def test_env_override_wins(tmp_path, monkeypatch):
    fake = tmp_path / "tesseract"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv(ENV_OVERRIDE, str(fake))

    assert find_tesseract() == fake


def test_env_override_is_ignored_when_the_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_OVERRIDE, str(tmp_path / "nope"))

    # Falls through to the normal search rather than trusting the variable.
    assert find_tesseract() != tmp_path / "nope"


def test_install_instructions_name_the_tool_and_a_command():
    text = install_instructions()

    assert "esseract" in text
    assert any(hint in text for hint in ("install", "brew", "winget", "dnf", "apt"))


def test_available_languages_is_empty_without_the_engine(monkeypatch):
    monkeypatch.setattr("pawdf.core.ocr.tesseract.find_tesseract", lambda: None)

    assert available_languages() == []


# ------------------------------------------------------------- guardrails --


def test_missing_tesseract_raises_with_instructions(sample_pdf, tmp_path, monkeypatch):
    """The error has to tell someone what to do, not just that it failed."""
    monkeypatch.setattr("pawdf.core.ocr.find_tesseract", lambda: None)

    with pytest.raises(TesseractNotFoundError) as caught:
        ocr_pdf(sample_pdf, tmp_path / "out.pdf")

    assert "esseract" in str(caught.value)


@pytest.mark.parametrize("dpi", [0, 72, MIN_DPI - 1, MAX_DPI + 1, 2400])
def test_dpi_is_validated(sample_pdf, tmp_path, dpi, monkeypatch):
    """Checked before the engine is looked for, so the message is about the
    argument rather than about a missing binary.
    """
    monkeypatch.setattr("pawdf.core.ocr.find_tesseract", lambda: None)

    with pytest.raises(ValueError):
        ocr_pdf(sample_pdf, tmp_path / "out.pdf", dpi=dpi)


def test_missing_input_raises(tmp_path, monkeypatch):
    fake = tmp_path / "tesseract"
    fake.write_text("")
    monkeypatch.setattr("pawdf.core.ocr.find_tesseract", lambda: fake)

    with pytest.raises(FileNotFoundError):
        ocr_pdf(tmp_path / "nope.pdf", tmp_path / "out.pdf")


# ---------------------------------------------------------- end to end --


@needs_tesseract
def test_a_scanned_page_becomes_searchable(tmp_path):
    """The whole point: text that was only pixels can be found afterwards."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    from pawdf.core.imagepdf import images_to_pdf

    # A "scan": text drawn as pixels, with no text layer at all.
    image = Image.new("RGB", (1240, 400), "white")
    ImageDraw.Draw(image).text((60, 150), "HELLO PAWDF", fill="black")
    png = tmp_path / "scan.png"
    image.save(png)
    scanned = images_to_pdf([png], tmp_path / "scan.pdf")

    def text_of(path):
        doc = pdfium.PdfDocument(path)
        try:
            textpage = doc[0].get_textpage()
            try:
                return textpage.get_text_range()
            finally:
                textpage.close()
        finally:
            doc.close()

    assert text_of(scanned).strip() == "", "the fixture should have no text layer"

    result = ocr_pdf(scanned, tmp_path / "out.pdf")

    assert result.pages_processed == 1
    assert "HELLO" in text_of(result.output_path).upper()


@needs_tesseract
def test_a_missing_language_pack_is_reported_immediately(sample_pdf, tmp_path):
    from pawdf.core._shared import ConversionError

    with pytest.raises(ConversionError, match="training data"):
        ocr_pdf(sample_pdf, tmp_path / "out.pdf", language="zzz")

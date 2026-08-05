import pytest

from pawdf.core import compress
from pawdf.core._shared.pdf_io import page_count
from pawdf.core.compress.ghostscript import find_ghostscript


def test_compress_rejects_unknown_preset(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        compress.compress_pdf(sample_pdf, tmp_path / "out.pdf", preset="bogus")


def test_fallback_compression_produces_valid_pdf(sample_pdf_with_image, tmp_path):
    result = compress.compress_pdf(sample_pdf_with_image, tmp_path / "out.pdf", force_fallback=True)

    assert result.method == "fallback"
    assert result.output_path.exists()
    assert page_count(result.output_path) == page_count(sample_pdf_with_image)
    assert result.compressed_size > 0


def test_fallback_compression_shrinks_image_heavy_pdf(sample_pdf_with_image, tmp_path):
    result = compress.compress_pdf(sample_pdf_with_image, tmp_path / "out.pdf", force_fallback=True)
    assert result.compressed_size < result.original_size


@pytest.mark.skipif(find_ghostscript() is None, reason="Ghostscript not installed")
def test_ghostscript_compression_produces_valid_pdf(sample_pdf_with_image, tmp_path):
    result = compress.compress_pdf(sample_pdf_with_image, tmp_path / "out.pdf")

    assert result.method == "ghostscript"
    assert result.output_path.exists()
    assert page_count(result.output_path) == page_count(sample_pdf_with_image)

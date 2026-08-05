import pytest

from pawdf.core import rasterize


def test_render_page_returns_rgba_bytes(sample_pdf):
    rendered = rasterize.render_page(sample_pdf, 0, dpi=72)
    assert rendered.width > 0
    assert rendered.height > 0
    assert len(rendered.rgba) == rendered.width * rendered.height * 4


def test_render_page_out_of_range_raises(sample_pdf):
    from pawdf.core._shared.errors import InvalidPageRangeError

    with pytest.raises(InvalidPageRangeError):
        rasterize.render_page(sample_pdf, 99)


def test_page_count_matches_pikepdf(sample_pdf):
    from pawdf.core._shared.pdf_io import page_count as pikepdf_page_count

    assert rasterize.page_count(sample_pdf) == pikepdf_page_count(sample_pdf)


def test_pdf_to_images_writes_one_file_per_page(sample_pdf, tmp_path):
    outputs = rasterize.pdf_to_images(sample_pdf, tmp_path / "out", dpi=72)
    assert len(outputs) == rasterize.page_count(sample_pdf)
    assert all(o.exists() for o in outputs)


def test_pdf_to_images_rejects_bad_format(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        rasterize.pdf_to_images(sample_pdf, tmp_path / "out", fmt="bmp")


def test_pdf_to_images_supports_webp(sample_pdf, tmp_path):
    outputs = rasterize.pdf_to_images(sample_pdf, tmp_path / "out", dpi=72, fmt="webp")
    assert all(o.suffix == ".webp" and o.exists() for o in outputs)


@pytest.mark.parametrize("bad_dpi", [0, -50, rasterize.MAX_DPI + 1])
def test_dpi_is_validated(sample_pdf, tmp_path, bad_dpi):
    # A negative scale makes PDFium fail obscurely and an enormous one tries to
    # allocate absurd amounts of memory, so both are rejected up front.
    with pytest.raises(ValueError):
        rasterize.render_page(sample_pdf, 0, dpi=bad_dpi)
    with pytest.raises(ValueError):
        rasterize.pdf_to_images(sample_pdf, tmp_path / "out", dpi=bad_dpi)


def test_render_page_on_encrypted_pdf_raises_encrypted_error(encrypted_pdf):
    from pawdf.core._shared.errors import EncryptedPdfError

    with pytest.raises(EncryptedPdfError):
        rasterize.render_page(encrypted_pdf, 0)


def test_pdf_to_images_on_encrypted_pdf_raises_encrypted_error(encrypted_pdf, tmp_path):
    from pawdf.core._shared.errors import EncryptedPdfError

    with pytest.raises(EncryptedPdfError):
        rasterize.pdf_to_images(encrypted_pdf, tmp_path / "out")


def test_page_count_on_encrypted_pdf_raises_encrypted_error(encrypted_pdf):
    from pawdf.core._shared.errors import EncryptedPdfError

    with pytest.raises(EncryptedPdfError):
        rasterize.page_count(encrypted_pdf)


def test_render_page_on_corrupt_pdf_raises_conversion_error(tmp_path):
    from pawdf.core._shared.errors import ConversionError

    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is definitely not a PDF")
    with pytest.raises(ConversionError):
        rasterize.render_page(bad, 0)

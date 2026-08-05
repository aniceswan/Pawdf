"""Tests for the in-project images -> PDF converter.

This replaced `img2pdf` (LGPL-3.0), so the tests carry more weight than usual:
they're what establishes that the replacement is actually lossless and that
the PDFs it writes are readable by a real renderer, not just by pikepdf.
"""

import pytest

from pawdf.core import imagepdf
from pawdf.core._shared import ConversionError, page_count


def _xobject_of(pdf, index=0):
    return list(pdf.pages[index].Resources.XObject.values())[0]


def test_creates_one_page_per_image(sample_images, tmp_path):
    out = imagepdf.images_to_pdf(sample_images, tmp_path / "out.pdf")
    assert out.exists()
    assert page_count(out) == len(sample_images)


def test_rejects_empty_list(tmp_path):
    with pytest.raises(ValueError):
        imagepdf.images_to_pdf([], tmp_path / "out.pdf")


def test_rejects_unknown_fit_mode(sample_images, tmp_path):
    with pytest.raises(ValueError):
        imagepdf.images_to_pdf(sample_images, tmp_path / "out.pdf", fit="a3")


def test_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        imagepdf.images_to_pdf([tmp_path / "nope.png"], tmp_path / "out.pdf")


def test_unreadable_image_raises_conversion_error(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image at all")
    with pytest.raises(ConversionError):
        imagepdf.images_to_pdf([bad], tmp_path / "out.pdf")


def test_baseline_jpeg_is_embedded_byte_for_byte(tmp_path):
    """The whole point of the passthrough path: a baseline JPEG is already
    DCT-compressed, and PDF's /DCTDecode is that same codec, so the original
    bytes go in untouched.
    """
    import pikepdf
    from PIL import Image

    src = tmp_path / "photo.jpg"
    Image.effect_noise((640, 480), 50).convert("RGB").save(src, quality=85)

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")

    with pikepdf.open(out) as pdf:
        xobject = _xobject_of(pdf)
        assert xobject.Filter == pikepdf.Name("/DCTDecode")
        assert xobject.read_raw_bytes() == src.read_bytes()


def test_greyscale_jpeg_keeps_its_colorspace(tmp_path):
    import pikepdf
    from PIL import Image

    src = tmp_path / "grey.jpg"
    Image.effect_noise((320, 240), 30).convert("L").save(src)

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")

    with pikepdf.open(out) as pdf:
        assert _xobject_of(pdf).ColorSpace == pikepdf.Name("/DeviceGray")


def test_progressive_jpeg_is_re_encoded_not_passed_through(tmp_path):
    """/DCTDecode only accepts baseline JPEG. A progressive file embedded
    verbatim renders as garbage, so it has to take the Flate path instead.
    """
    import pikepdf
    from PIL import Image

    src = tmp_path / "prog.jpg"
    Image.effect_noise((320, 240), 50).convert("RGB").save(src, progressive=True)

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")

    with pikepdf.open(out) as pdf:
        assert _xobject_of(pdf).Filter == pikepdf.Name("/FlateDecode")


@pytest.mark.parametrize(
    ("mode", "suffix"),
    [("RGBA", ".png"), ("P", ".png"), ("1", ".png"), ("LA", ".png"), ("CMYK", ".tiff")],
)
def test_awkward_colour_modes_still_produce_a_readable_page(tmp_path, mode, suffix):
    """Everything that isn't plain RGB or greyscale is normalized rather than
    rejected, since a scanner or an old clip-art file can hand you any of these.
    """
    from PIL import Image

    src = tmp_path / f"{mode}{suffix}"
    Image.new(mode, (120, 90)).save(src)

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")
    assert page_count(out) == 1


def test_transparency_is_composited_onto_white(tmp_path):
    """A PDF page has no "nothing" to show through to, so alpha has to be
    resolved at build time rather than dropped.
    """
    import pypdfium2 as pdfium
    from PIL import Image

    src = tmp_path / "half.png"
    Image.new("RGBA", (60, 60), (0, 0, 0, 0)).save(src)

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")

    doc = pdfium.PdfDocument(out)
    try:
        pixel = doc[0].render(scale=1).to_pil().convert("RGB").getpixel((30, 30))
    finally:
        doc.close()
    assert pixel == (255, 255, 255)


def test_page_size_follows_image_dpi(tmp_path):
    """A 600px image tagged 300 dpi is two inches wide, so the page should be
    144 points, not 600.
    """
    import pikepdf
    from PIL import Image

    src = tmp_path / "dense.jpg"
    Image.effect_noise((600, 600), 20).convert("RGB").save(src, dpi=(300, 300))

    out = imagepdf.images_to_pdf([src], tmp_path / "out.pdf")

    with pikepdf.open(out) as pdf:
        _, _, width, height = (float(v) for v in pdf.pages[0].MediaBox)
    assert width == pytest.approx(144.0, abs=0.5)
    assert height == pytest.approx(144.0, abs=0.5)


def test_missing_dpi_falls_back_to_one_point_per_pixel(sample_images, tmp_path):
    import pikepdf

    out = imagepdf.images_to_pdf([sample_images[0]], tmp_path / "out.pdf")

    with pikepdf.open(out) as pdf:
        _, _, width, height = (float(v) for v in pdf.pages[0].MediaBox)
    assert (width, height) == (64.0, 48.0)


@pytest.mark.parametrize(
    ("fit", "expected"),
    [("a4", (595.276, 841.890)), ("letter", (612.0, 792.0))],
)
def test_fixed_page_sizes(sample_images, tmp_path, fit, expected):
    import pikepdf

    out = imagepdf.images_to_pdf([sample_images[0]], tmp_path / "out.pdf", fit=fit)

    with pikepdf.open(out) as pdf:
        _, _, width, height = (float(v) for v in pdf.pages[0].MediaBox)
    assert (width, height) == pytest.approx(expected, abs=0.01)


def test_output_is_readable_by_an_actual_renderer(sample_images, tmp_path):
    """pikepdf parsing the file proves the structure; only a renderer proves
    the content stream and image dictionaries are actually valid.
    """
    import pypdfium2 as pdfium

    out = imagepdf.images_to_pdf(sample_images, tmp_path / "out.pdf")

    doc = pdfium.PdfDocument(out)
    try:
        assert len(doc) == len(sample_images)
        for i in range(len(doc)):
            assert doc[i].render(scale=0.5).to_pil().size[0] > 0
    finally:
        doc.close()

"""Tests for the overlay tools.

Assertions go through extracted text wherever possible: it proves the mark
actually landed on the page, which measuring how dark the render got does not.
"""

import pytest

from pawdf.core._shared import page_count
from pawdf.core.stamp import POSITIONS, add_page_numbers, add_watermark, stamp_image


def _text_of(path, index=0):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    try:
        page = doc[index]
        textpage = page.get_textpage()
        try:
            return textpage.get_text_range()
        finally:
            textpage.close()
    finally:
        doc.close()


@pytest.fixture
def signature_png(tmp_path):
    from PIL import Image

    path = tmp_path / "signature.png"
    Image.new("RGB", (300, 120), (20, 20, 140)).save(path)
    return path


# ------------------------------------------------------------- watermark --


def test_watermark_text_lands_on_every_page(sample_pdf, tmp_path):
    out = add_watermark(sample_pdf, tmp_path / "out.pdf", text="CONFIDENTIAL")

    assert page_count(out) == page_count(sample_pdf)
    for index in range(page_count(out)):
        assert "CONFIDENTIAL" in _text_of(out, index)


def test_watermark_respects_a_page_range(sample_pdf, tmp_path):
    out = add_watermark(sample_pdf, tmp_path / "out.pdf", text="DRAFT", pages="2-3")

    assert "DRAFT" not in _text_of(out, 0)
    assert "DRAFT" in _text_of(out, 1)
    assert "DRAFT" in _text_of(out, 2)
    assert "DRAFT" not in _text_of(out, 3)


def test_watermark_leaves_the_original_text_alone(sample_pdf, tmp_path):
    """A watermark is drawn over the page, not instead of it."""
    out = add_watermark(sample_pdf, tmp_path / "out.pdf", text="COPY")

    text = _text_of(out, 0)
    assert "COPY" in text
    assert "Page 1" in text


@pytest.mark.parametrize("position", POSITIONS)
def test_every_position_produces_a_readable_page(sample_pdf, tmp_path, position):
    out = add_watermark(
        sample_pdf, tmp_path / f"{position}.pdf", text="MARK", position=position, rotation=0
    )
    assert "MARK" in _text_of(out, 0)


def test_watermark_rejects_bad_input(sample_pdf, tmp_path):
    for kwargs in (
        {"text": ""},
        {"text": "x", "opacity": 0},
        {"text": "x", "opacity": 1.5},
        {"text": "x", "position": "nowhere"},
        {"text": "x", "colour": "zzz"},
    ):
        with pytest.raises(ValueError):
            add_watermark(sample_pdf, tmp_path / "out.pdf", **kwargs)


# ----------------------------------------------------------- page numbers --


def test_page_numbers_count_up(sample_pdf, tmp_path):
    out = add_page_numbers(sample_pdf, tmp_path / "out.pdf")

    for index in range(page_count(out)):
        assert str(index + 1) in _text_of(out, index)


def test_template_can_include_the_total(sample_pdf, tmp_path):
    out = add_page_numbers(sample_pdf, tmp_path / "out.pdf", template="Page {n} of {total}")

    assert "Page 1 of 5" in _text_of(out, 0)
    assert "Page 5 of 5" in _text_of(out, 4)


def test_start_at_shifts_the_numbering(sample_pdf, tmp_path):
    """What a document with front matter needs."""
    out = add_page_numbers(sample_pdf, tmp_path / "out.pdf", template="Page {n}", start_at=7)

    assert "Page 7" in _text_of(out, 0)
    assert "Page 11" in _text_of(out, 4)


def test_skip_first_leaves_the_cover_alone(sample_pdf, tmp_path):
    out = add_page_numbers(sample_pdf, tmp_path / "out.pdf", template="[{n}]", skip_first=True)

    assert "[1]" not in _text_of(out, 0)
    assert "[2]" in _text_of(out, 1)


def test_template_must_contain_the_number(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        add_page_numbers(sample_pdf, tmp_path / "out.pdf", template="page")


# ------------------------------------------------------------------ image --


def test_image_is_stamped_on_every_page(sample_pdf, signature_png, tmp_path):
    import pikepdf

    out = stamp_image(sample_pdf, tmp_path / "out.pdf", image_path=signature_png)

    assert page_count(out) == page_count(sample_pdf)
    with pikepdf.open(out) as pdf:
        for page in pdf.pages:
            # get_images() rather than .images: the overlay arrives as a form
            # XObject, and the picture is nested inside it.
            assert page.get_images(), "no image reached the page"


def _overlay_content(page) -> str:
    """The drawing commands of the stamp laid over `page`.

    The overlay is added as a form XObject, so the page's own content stream
    only says "draw this form"; the geometry is one level down.
    """
    import pikepdf

    for xobject in page.Resources.XObject.values():
        if xobject.get("/Subtype") == pikepdf.Name("/Form"):
            return xobject.read_bytes().decode("latin-1")
    raise AssertionError("no overlay form found on the page")


def test_image_keeps_its_aspect_ratio(sample_pdf, signature_png, tmp_path):
    """A squashed signature looks forged, so the height follows the width."""
    import pikepdf

    out = stamp_image(sample_pdf, tmp_path / "out.pdf", image_path=signature_png, width_pt=150)

    with pikepdf.open(out) as pdf:
        content = _overlay_content(pdf.pages[0])

    # The image is 300x120, so 150 wide has to be drawn 60 high.
    assert "150" in content, content
    assert "60" in content, content


def test_image_rejects_bad_input(sample_pdf, signature_png, tmp_path):
    with pytest.raises(ValueError):
        stamp_image(sample_pdf, tmp_path / "o.pdf", image_path=signature_png, width_pt=0)
    with pytest.raises(ValueError):
        stamp_image(sample_pdf, tmp_path / "o.pdf", image_path=signature_png, opacity=0)
    with pytest.raises(FileNotFoundError):
        stamp_image(sample_pdf, tmp_path / "o.pdf", image_path=tmp_path / "nope.png")


# -------------------------------------------------------- rotated pages --


def test_a_rotated_page_gets_an_upright_stamp(sample_pdf, tmp_path):
    """A page carrying /Rotate 90 is drawn turned, so an overlay built at the
    unrotated size would come out sideways and clipped.
    """
    from pawdf.core.rotate import rotate_pdf

    turned = rotate_pdf(sample_pdf, tmp_path / "turned.pdf", degrees=90)
    out = add_watermark(turned, tmp_path / "out.pdf", text="SIDEWAYS", rotation=0)

    assert "SIDEWAYS" in _text_of(out, 0)

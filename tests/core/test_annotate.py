import pytest

from pawdf.core._shared import page_count
from pawdf.core.annotate import (
    Ellipse,
    Highlight,
    Line,
    Rectangle,
    TextNote,
    add_note,
    annotate_pdf,
)


def _text_of(path, index=0):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    try:
        textpage = doc[index].get_textpage()
        try:
            return textpage.get_text_range()
        finally:
            textpage.close()
    finally:
        doc.close()


def test_a_note_lands_on_the_page(sample_pdf, tmp_path):
    out = add_note(sample_pdf, tmp_path / "out.pdf", text="Reviewed 4 Aug")

    assert "Reviewed 4 Aug" in _text_of(out)
    assert page_count(out) == page_count(sample_pdf)


def test_marks_go_to_their_own_pages(sample_pdf, tmp_path):
    out = annotate_pdf(
        sample_pdf,
        tmp_path / "out.pdf",
        [TextNote(text="first", x=60, y=600, page=0), TextNote(text="third", x=60, y=600, page=2)],
    )

    assert "first" in _text_of(out, 0)
    assert "third" not in _text_of(out, 0)
    assert "third" in _text_of(out, 2)


def test_the_original_content_survives(sample_pdf, tmp_path):
    """Annotations are a layer over the page, not a replacement for it."""
    out = add_note(sample_pdf, tmp_path / "out.pdf", text="note")

    text = _text_of(out)
    assert "note" in text
    assert "Page 1" in text


@pytest.mark.parametrize(
    "mark",
    [
        Rectangle(x=60, y=500, width=200, height=80),
        Rectangle(x=60, y=500, width=200, height=80, filled=True, opacity=0.3),
        Ellipse(x=60, y=400, width=180, height=90),
        Line(x1=60, y1=300, x2=300, y2=340),
        Highlight(x=60, y=200, width=240),
    ],
)
def test_every_shape_produces_a_readable_pdf(sample_pdf, tmp_path, mark):
    import pypdfium2 as pdfium

    out = annotate_pdf(sample_pdf, tmp_path / "out.pdf", [mark])

    doc = pdfium.PdfDocument(out)
    try:
        assert doc[0].render(scale=0.4).to_pil().size[0] > 0
    finally:
        doc.close()


def test_highlight_leaves_the_text_readable(sample_pdf, tmp_path):
    """Translucent by design: a highlight marks text, it does not cover it."""
    out = annotate_pdf(
        sample_pdf, tmp_path / "out.pdf", [Highlight(x=60, y=710, width=300, height=20)]
    )

    assert "Page 1" in _text_of(out)


def test_an_empty_mark_list_is_rejected(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        annotate_pdf(sample_pdf, tmp_path / "out.pdf", [])


def test_a_page_outside_the_document_is_rejected(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        annotate_pdf(sample_pdf, tmp_path / "out.pdf", [TextNote(text="x", x=0, y=0, page=99)])


def test_a_bad_colour_is_rejected(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        add_note(sample_pdf, tmp_path / "out.pdf", text="x", colour="not-a-colour")


def test_empty_note_text_is_rejected(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        add_note(sample_pdf, tmp_path / "out.pdf", text="")

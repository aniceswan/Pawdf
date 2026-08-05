"""Tests for PDF -> Markdown.

Split between the two halves the package is built around: the renderer is
driven with a hand-built IR and needs no PDF at all, while the extractor is
checked against a PDF with real visual hierarchy.
"""

import pytest

from pawdf.core._shared import ConversionError, EncryptedPdfError
from pawdf.core.pdf_to_markdown import pdf_to_markdown
from pawdf.core.pdf_to_markdown.model import DocumentIR, ImageIR, PageIR, ParagraphIR, TextRunIR
from pawdf.core.pdf_to_markdown.render_markdown import render_markdown


def _doc(*blocks):
    return DocumentIR(pages=[PageIR(blocks=list(blocks))])


def _para(text, **kwargs):
    return ParagraphIR(runs=[TextRunIR(text=text)], **kwargs)


# ------------------------------------------------------------- renderer --


def test_headings_become_hashes(tmp_path):
    out = render_markdown(
        _doc(_para("Title", heading_level=1), _para("Section", heading_level=3)),
        tmp_path / "out.md",
    )
    text = out.read_text()

    assert "# Title" in text
    assert "### Section" in text


def test_heading_level_is_clamped(tmp_path):
    """Markdown only defines six levels."""
    out = render_markdown(_doc(_para("Deep", heading_level=9)), tmp_path / "out.md")

    assert out.read_text().startswith("###### Deep")


def test_emphasis(tmp_path):
    out = render_markdown(
        _doc(
            ParagraphIR(
                runs=[
                    TextRunIR(text="plain "),
                    TextRunIR(text="bold", bold=True),
                    TextRunIR(text=" and "),
                    TextRunIR(text="italic", italic=True),
                    TextRunIR(text=" and "),
                    TextRunIR(text="both", bold=True, italic=True),
                    TextRunIR(text=" and "),
                    TextRunIR(text="code", monospace=True),
                ]
            )
        ),
        tmp_path / "out.md",
    )

    assert "plain **bold** and _italic_ and ***both*** and `code`" in out.read_text()


def test_emphasis_markers_sit_outside_surrounding_spaces(tmp_path):
    """`** bold **` renders as literal asterisks in most parsers."""
    out = render_markdown(
        _doc(ParagraphIR(runs=[TextRunIR(text=" spaced ", bold=True)])),
        tmp_path / "out.md",
    )

    assert "**spaced**" in out.read_text()


def test_headings_carry_no_emphasis_markers(tmp_path):
    """`## **Title**` shows literal asterisks in several viewers."""
    out = render_markdown(
        _doc(ParagraphIR(runs=[TextRunIR(text="Bold title", bold=True)], heading_level=2)),
        tmp_path / "out.md",
    )

    assert "## Bold title" in out.read_text()
    assert "**" not in out.read_text()


def test_special_characters_are_escaped(tmp_path):
    out = render_markdown(_doc(_para("A [link] and *stars* and _score_")), tmp_path / "out.md")

    text = out.read_text()
    assert r"\[link\]" in text
    assert r"\*stars\*" in text


def test_ordered_lists_always_use_one(tmp_path):
    """Markdown renumbers, and hard-coded numbers break when an item moves."""
    out = render_markdown(
        _doc(_para("first", list_marker="4."), _para("second", list_marker="5.")),
        tmp_path / "out.md",
    )

    assert out.read_text().count("1. ") == 2


def test_list_items_are_not_separated_by_blank_lines(tmp_path):
    """A blank line between items renders them as separate loose lists."""
    out = render_markdown(
        _doc(_para("a", list_marker="-"), _para("b", list_marker="-")),
        tmp_path / "out.md",
    )

    assert "- a\n- b" in out.read_text()


def test_images_are_written_and_linked(tmp_path):
    from PIL import Image

    buffer = tmp_path / "seed.png"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(buffer)

    out = render_markdown(
        _doc(_para("before"), ImageIR(data=buffer.read_bytes(), suffix=".png")),
        tmp_path / "out.md",
    )

    assert "![](out_images/image-001.png)" in out.read_text()
    assert (tmp_path / "out_images" / "image-001.png").is_file()


def test_page_separators_are_off_by_default(tmp_path):
    document = DocumentIR(pages=[PageIR(blocks=[_para("one")]), PageIR(blocks=[_para("two")])])

    plain = render_markdown(document, tmp_path / "a.md")
    assert "---" not in plain.read_text()

    ruled = render_markdown(document, tmp_path / "b.md", page_separators=True)
    assert "---" in ruled.read_text()


# ------------------------------------------------------------ extractor --


def test_converts_a_real_pdf(structured_pdf, tmp_path):
    out = pdf_to_markdown(structured_pdf, tmp_path / "out.md")
    text = out.read_text()

    assert "Quarterly Report" in text
    assert "Introduction" in text


def test_larger_fonts_become_headings(structured_pdf, tmp_path):
    out = pdf_to_markdown(structured_pdf, tmp_path / "out.md")
    lines = [ln for ln in out.read_text().splitlines() if ln.strip()]

    title = next(ln for ln in lines if "Quarterly Report" in ln)
    section = next(ln for ln in lines if "Introduction" in ln)

    assert title.startswith("#")
    assert section.startswith("#")
    # The 26pt title should outrank the 16pt section heading, i.e. fewer hashes.
    assert len(title) - len(title.lstrip("#")) < len(section) - len(section.lstrip("#"))


def test_body_text_is_not_promoted(structured_pdf, tmp_path):
    out = pdf_to_markdown(structured_pdf, tmp_path / "out.md")

    body = next(ln for ln in out.read_text().splitlines() if "wraps across" in ln)
    assert not body.startswith("#")


def test_wrapped_lines_merge_into_one_paragraph(structured_pdf, tmp_path):
    out = pdf_to_markdown(structured_pdf, tmp_path / "out.md")

    wrapped = [ln for ln in out.read_text().splitlines() if "wraps across" in ln]
    assert len(wrapped) == 1
    assert "instead of many." in wrapped[0]


def test_emphasis_survives_the_round_trip(structured_pdf, tmp_path):
    out = pdf_to_markdown(structured_pdf, tmp_path / "out.md")
    text = out.read_text()

    assert "_This line is italic._" in text
    assert "**This line is bold.**" in text


def test_page_range_limits_the_output(structured_pdf, tmp_path):
    everything = pdf_to_markdown(structured_pdf, tmp_path / "all.md").read_text()
    first = pdf_to_markdown(
        structured_pdf, tmp_path / "first.md", start_page=0, end_page=1
    ).read_text()

    assert "second page" in everything
    assert "second page" not in first


def test_encrypted_input_raises(encrypted_pdf, tmp_path):
    with pytest.raises(EncryptedPdfError):
        pdf_to_markdown(encrypted_pdf, tmp_path / "out.md")


def test_corrupt_input_raises(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    with pytest.raises(ConversionError):
        pdf_to_markdown(bad, tmp_path / "out.md")

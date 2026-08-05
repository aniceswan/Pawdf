import pytest

from pawdf.core._shared import InvalidPageRangeError, page_count
from pawdf.core.crop import MIN_SIDE_PT, Margins, crop_pdf


def _boxes(path):
    import pikepdf

    with pikepdf.open(path) as pdf:
        return [
            tuple(round(float(v), 2) for v in (page.get("/CropBox") or page.get("/MediaBox")))
            for page in pdf.pages
        ]


def test_uniform_margins_trim_every_edge(sample_pdf, tmp_path):
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(36))

    # The fixture is US Letter: 612 x 792 points.
    assert _boxes(out)[0] == (36.0, 36.0, 576.0, 756.0)


def test_margins_can_differ_per_edge(sample_pdf, tmp_path):
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins(left=20, top=50))

    assert _boxes(out)[0] == (20.0, 0.0, 612.0, 742.0)


def test_an_explicit_box_is_used_as_given(sample_pdf, tmp_path):
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", box=(50, 60, 400, 700))

    assert _boxes(out)[0] == (50.0, 60.0, 400.0, 700.0)


def test_a_box_larger_than_the_page_is_clamped(sample_pdf, tmp_path):
    """Asking for more page than exists should give you the page, not a box
    describing empty space beyond it.
    """
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", box=(-100, -100, 9999, 9999))

    assert _boxes(out)[0] == (0.0, 0.0, 612.0, 792.0)


def test_an_absurd_margin_cannot_collapse_the_page(sample_pdf, tmp_path):
    """A margin bigger than the page would otherwise produce a zero-area or
    inverted rectangle, which no viewer can render.
    """
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(9999))

    left, bottom, right, top = _boxes(out)[0]
    assert right - left == pytest.approx(MIN_SIDE_PT)
    assert top - bottom == pytest.approx(MIN_SIDE_PT)


def test_a_page_range_leaves_the_rest_alone(sample_pdf, tmp_path):
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(40), pages="1,3")

    boxes = _boxes(out)
    assert boxes[0] == (40.0, 40.0, 572.0, 752.0)
    assert boxes[1] == (0.0, 0.0, 612.0, 792.0)
    assert boxes[2] == (40.0, 40.0, 572.0, 752.0)


def test_cropping_twice_stacks(sample_pdf, tmp_path):
    """Margins apply to the current CropBox, not to the original MediaBox."""
    once = crop_pdf(sample_pdf, tmp_path / "a.pdf", margins=Margins.uniform(20))
    twice = crop_pdf(once, tmp_path / "b.pdf", margins=Margins.uniform(20))

    assert _boxes(twice)[0] == (40.0, 40.0, 572.0, 752.0)


def test_exactly_one_of_margins_or_box_is_required(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        crop_pdf(sample_pdf, tmp_path / "out.pdf")
    with pytest.raises(ValueError):
        crop_pdf(
            sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(10), box=(0, 0, 100, 100)
        )


def test_out_of_range_pages_raise(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(10), pages="9-12")


def test_page_count_is_unchanged(sample_pdf, tmp_path):
    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(30))

    assert page_count(out) == page_count(sample_pdf)


def test_cropped_pages_still_render(sample_pdf, tmp_path):
    """The CropBox is what a renderer draws, so a bad one shows up here and
    nowhere else.
    """
    import pypdfium2 as pdfium

    out = crop_pdf(sample_pdf, tmp_path / "out.pdf", margins=Margins.uniform(72))

    doc = pdfium.PdfDocument(out)
    try:
        width, height = doc[0].render(scale=1).to_pil().size
        # 612 x 792 less an inch on each side, at 1:1 scale.
        assert width == pytest.approx(468, abs=2)
        assert height == pytest.approx(648, abs=2)
    finally:
        doc.close()

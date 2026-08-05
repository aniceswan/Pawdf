import pytest

from pawdf.core._shared import InvalidPageRangeError, page_count
from pawdf.core.rotate import rotate_pdf


def _rotations(path):
    import pikepdf

    with pikepdf.open(path) as pdf:
        return [int(page.get("/Rotate", 0)) for page in pdf.pages]


def test_rotates_every_page(sample_pdf, tmp_path):
    out = rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=90)

    assert _rotations(out) == [90] * page_count(sample_pdf)


def test_rotation_is_relative_by_default(sample_pdf, tmp_path):
    """Someone straightening a scan expects a second quarter turn to land at
    180, not to re-apply 90.
    """
    once = rotate_pdf(sample_pdf, tmp_path / "a.pdf", degrees=90)
    twice = rotate_pdf(once, tmp_path / "b.pdf", degrees=90)

    assert _rotations(twice) == [180] * page_count(sample_pdf)


def test_absolute_sets_rather_than_adds(sample_pdf, tmp_path):
    """How you normalise a document whose pages disagree with each other."""
    once = rotate_pdf(sample_pdf, tmp_path / "a.pdf", degrees=180)
    fixed = rotate_pdf(once, tmp_path / "b.pdf", degrees=90, absolute=True)

    assert _rotations(fixed) == [90] * page_count(sample_pdf)


def test_a_page_range_leaves_the_rest_alone(sample_pdf, tmp_path):
    out = rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=180, pages="2-3")

    assert _rotations(out) == [0, 180, 180, 0, 0]


@pytest.mark.parametrize("degrees", [45, 1, -30, 100])
def test_only_quarter_turns_are_accepted(sample_pdf, tmp_path, degrees):
    with pytest.raises(ValueError):
        rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=degrees)


@pytest.mark.parametrize("degrees", [0, 360, -360])
def test_a_no_op_rotation_is_rejected(sample_pdf, tmp_path, degrees):
    """Silently writing an unchanged copy would look like it worked."""
    with pytest.raises(ValueError):
        rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=degrees)


def test_negative_quarter_turns_normalise(sample_pdf, tmp_path):
    out = rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=-90)

    assert _rotations(out) == [270] * page_count(sample_pdf)


def test_out_of_range_pages_raise(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=90, pages="1-99")


def test_page_count_is_unchanged(sample_pdf, tmp_path):
    out = rotate_pdf(sample_pdf, tmp_path / "out.pdf", degrees=270)

    assert page_count(out) == page_count(sample_pdf)

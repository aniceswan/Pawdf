import pytest

from pawdf.core import organize
from pawdf.core._shared.errors import InvalidPageRangeError
from pawdf.core._shared.pdf_io import page_count


def test_rotate_pages_out_of_range_raises(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        organize.rotate_pages(sample_pdf, {99: 90}, tmp_path / "out.pdf")


def test_rotate_pages_rejects_non_multiple_of_90(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        organize.rotate_pages(sample_pdf, {0: 45}, tmp_path / "out.pdf")


def test_rotate_pages_preserves_page_count(sample_pdf, tmp_path):
    out = organize.rotate_pages(sample_pdf, {0: 90, 2: 180}, tmp_path / "out.pdf")
    assert page_count(out) == page_count(sample_pdf)


def test_delete_pages_removes_requested_pages(sample_pdf, tmp_path):
    out = organize.delete_pages(sample_pdf, [0, 1], tmp_path / "out.pdf")
    assert page_count(out) == page_count(sample_pdf) - 2


def test_delete_all_pages_raises(sample_pdf, tmp_path):
    total = page_count(sample_pdf)
    with pytest.raises(InvalidPageRangeError):
        organize.delete_pages(sample_pdf, list(range(total)), tmp_path / "out.pdf")


def test_reorder_pages_supports_subset_and_duplicates(sample_pdf, tmp_path):
    out = organize.reorder_pages(sample_pdf, [2, 0, 0], tmp_path / "out.pdf")
    assert page_count(out) == 3


def test_reorder_pages_rejects_empty(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        organize.reorder_pages(sample_pdf, [], tmp_path / "out.pdf")


def test_reorder_pages_rejects_out_of_range(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        organize.reorder_pages(sample_pdf, [0, 99], tmp_path / "out.pdf")


def test_apply_page_edits_reorders_rotates_and_drops(sample_pdf, tmp_path):
    out = organize.apply_page_edits(sample_pdf, [(2, 90), (0, 0)], tmp_path / "out.pdf")
    assert page_count(out) == 2


def test_apply_page_edits_rejects_empty(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        organize.apply_page_edits(sample_pdf, [], tmp_path / "out.pdf")


def test_apply_page_edits_rejects_bad_rotation(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        organize.apply_page_edits(sample_pdf, [(0, 45)], tmp_path / "out.pdf")

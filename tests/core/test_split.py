import pytest

from pawdf.core import split
from pawdf.core._shared.errors import InvalidPageRangeError
from pawdf.core._shared.pdf_io import page_count


def test_split_by_ranges_writes_expected_page_counts(sample_pdf, tmp_path):
    out_dir = tmp_path / "out"
    outputs = split.split_by_ranges(sample_pdf, ["1-2", "3", "4-5"], out_dir)

    assert [o.name for o in outputs] == ["sample_part1.pdf", "sample_part2.pdf", "sample_part3.pdf"]
    assert page_count(outputs[0]) == 2
    assert page_count(outputs[1]) == 1
    assert page_count(outputs[2]) == 2


def test_split_by_ranges_round_trip_preserves_total_pages(sample_pdf, tmp_path):
    outputs = split.split_by_ranges(sample_pdf, ["1-2", "3-5"], tmp_path / "out")
    assert sum(page_count(o) for o in outputs) == page_count(sample_pdf)


def test_split_every_n_pages(sample_pdf, tmp_path):
    outputs = split.split_every_n_pages(sample_pdf, 2, tmp_path / "out")
    assert [page_count(o) for o in outputs] == [2, 2, 1]


def test_split_rejects_out_of_range(sample_pdf, tmp_path):
    with pytest.raises(InvalidPageRangeError):
        split.split_by_ranges(sample_pdf, ["1-99"], tmp_path / "out")


def test_split_rejects_invalid_n():
    with pytest.raises(ValueError):
        split.split_every_n_pages("unused.pdf", 0, "unused_out")

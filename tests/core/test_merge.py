import pytest

from pawdf.core import merge
from pawdf.core._shared.pdf_io import page_count


def test_merge_concatenates_in_order(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 2, label_prefix="A")
    b = make_pdf("b.pdf", 3, label_prefix="B")

    out = merge.merge_pdfs([a, b], tmp_path / "merged.pdf")

    assert page_count(out) == 5


def test_merge_rejects_empty_list(tmp_path):
    with pytest.raises(ValueError):
        merge.merge_pdfs([], tmp_path / "merged.pdf")


def test_merge_then_split_round_trip(make_pdf, tmp_path):
    a = make_pdf("a.pdf", 2)
    b = make_pdf("b.pdf", 3)

    merged = merge.merge_pdfs([a, b], tmp_path / "merged.pdf")
    assert page_count(merged) == page_count(a) + page_count(b)

"""Split one PDF into several output PDFs by page range.

Standalone feature package: depends only on `pawdf.core._shared` and pikepdf.
See README.md in this directory.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ensure_parent_dir, open_pdf, parse_page_ranges

__all__ = ["split_by_ranges", "split_every_n_pages"]


def split_by_ranges(
    input_path: str | Path,
    ranges: list[str],
    out_dir: str | Path,
    *,
    stem: str | None = None,
) -> list[Path]:
    """Split `input_path` into one output PDF per entry in `ranges`.

    Each entry is a page-range spec like "1-3" or "5,7-9", 1-indexed and
    inclusive. Returns the written paths, in the same order as `ranges`.
    """
    import pikepdf

    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or input_path.stem

    outputs: list[Path] = []
    with open_pdf(input_path) as src:
        total_pages = len(src.pages)
        for i, range_spec in enumerate(ranges, start=1):
            page_indices = parse_page_ranges(range_spec, total_pages)
            out_path = ensure_parent_dir(out_dir / f"{stem}_part{i}.pdf")
            with pikepdf.new() as out_pdf:
                for idx in page_indices:
                    out_pdf.pages.append(src.pages[idx])
                out_pdf.save(out_path)
            outputs.append(out_path)

    return outputs


def split_every_n_pages(
    input_path: str | Path,
    n: int,
    out_dir: str | Path,
    *,
    stem: str | None = None,
) -> list[Path]:
    """Split `input_path` into consecutive chunks of `n` pages each."""
    if n < 1:
        raise ValueError("n must be >= 1")

    with open_pdf(input_path) as src:
        total_pages = len(src.pages)

    ranges = []
    start = 1
    while start <= total_pages:
        end = min(start + n - 1, total_pages)
        ranges.append(f"{start}-{end}")
        start = end + 1

    return split_by_ranges(input_path, ranges, out_dir, stem=stem)

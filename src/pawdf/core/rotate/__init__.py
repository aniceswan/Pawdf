"""Turn every page of a PDF, or a chosen range of them.

Separate from `organize` on purpose. Arrange is a per-page editor: you look at
thumbnails and pick individual pages. This is the bulk case, which is most of
them in practice - a document scanned sideways needs all of it turned, and
doing that through a page grid is a chore.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ensure_parent_dir, open_pdf, parse_page_ranges

__all__ = ["QUARTER_TURNS", "rotate_pdf"]

#: The only rotations a PDF can express. Anything else is not a page rotation,
#: it is a transform of the page content, which is a different operation.
QUARTER_TURNS = (90, 180, 270)


def rotate_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    degrees: int,
    pages: str | None = None,
    absolute: bool = False,
) -> Path:
    """Rotate pages of `input_path` by `degrees` clockwise.

    `pages` is a 1-indexed range spec like "1-3,7", or None for every page.

    `absolute=False` (the default) adds to whatever rotation a page already
    carries, which is what someone straightening a scan expects. `absolute=True`
    sets the rotation outright, which is how you normalise a document whose
    pages disagree with each other.
    """
    normalised = degrees % 360
    if normalised == 0:
        raise ValueError("degrees must be 90, 180 or 270")
    if normalised not in QUARTER_TURNS:
        raise ValueError(f"Rotation must be a multiple of 90, got {degrees}")

    out_path = ensure_parent_dir(out_path)
    with open_pdf(input_path) as pdf:
        total = len(pdf.pages)
        targets = range(total) if pages is None else parse_page_ranges(pages, total)

        for index in targets:
            pdf.pages[index].rotate(normalised, relative=not absolute)

        pdf.save(out_path)

    return out_path

"""Trim the visible area of PDF pages.

Cropping a PDF does not delete anything: it narrows the CropBox, which is the
rectangle a viewer draws. The content outside it is still in the file and can
be recovered by widening the box again. That makes this safe to undo and
useless for hiding sensitive material - redaction is a different, much more
careful operation, and deliberately not what this is.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pawdf.core._shared import ensure_parent_dir, open_pdf, parse_page_ranges

__all__ = ["Margins", "crop_pdf"]

#: A page must keep at least this much of each dimension, in points. Below
#: roughly a quarter-inch a "page" is a sliver no viewer will render usefully.
MIN_SIDE_PT = 18.0


@dataclass(frozen=True)
class Margins:
    """How much to trim from each edge, in points (72 to the inch)."""

    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @classmethod
    def uniform(cls, amount: float) -> Margins:
        return cls(amount, amount, amount, amount)


def _current_box(page) -> tuple[float, float, float, float]:  # noqa: ANN001 - pikepdf Page
    """The page's CropBox, falling back to MediaBox when it has none.

    Most pages carry no CropBox at all, and the spec says it then defaults to
    the MediaBox. Reading it directly would raise on exactly the common case.
    """
    box = page.get("/CropBox") or page.get("/MediaBox")
    return tuple(float(v) for v in box)  # type: ignore[return-value]


def crop_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    margins: Margins | None = None,
    box: tuple[float, float, float, float] | None = None,
    pages: str | None = None,
) -> Path:
    """Crop `input_path`, either by trimming `margins` or to an explicit `box`.

    `box` is (left, bottom, right, top) in PDF points, measured from the
    bottom-left of the page. `pages` is a 1-indexed range spec, or None for all.

    Requests are clamped to the page's existing box, so a margin larger than
    the page cannot produce a zero-area or inverted rectangle - the result is
    a small page rather than a broken one.
    """
    if (margins is None) == (box is None):
        raise ValueError("pass exactly one of margins or box")

    out_path = ensure_parent_dir(out_path)
    with open_pdf(input_path) as pdf:
        total = len(pdf.pages)
        targets = range(total) if pages is None else parse_page_ranges(pages, total)

        for index in targets:
            page = pdf.pages[index]
            left, bottom, right, top = _current_box(page)

            if margins is not None:
                new = (
                    left + margins.left,
                    bottom + margins.bottom,
                    right - margins.right,
                    top - margins.top,
                )
            else:
                assert box is not None
                new = (
                    max(box[0], left),
                    max(box[1], bottom),
                    min(box[2], right),
                    min(box[3], top),
                )

            new_left, new_bottom, new_right, new_top = new
            # Never let the box collapse or invert; keep a sliver anchored to
            # the original edge instead.
            if new_right - new_left < MIN_SIDE_PT:
                new_right = min(right, new_left + MIN_SIDE_PT)
                new_left = max(left, new_right - MIN_SIDE_PT)
            if new_top - new_bottom < MIN_SIDE_PT:
                new_top = min(top, new_bottom + MIN_SIDE_PT)
                new_bottom = max(bottom, new_top - MIN_SIDE_PT)

            page.CropBox = [
                round(new_left, 4),
                round(new_bottom, 4),
                round(new_right, 4),
                round(new_top, 4),
            ]

        pdf.save(out_path)

    return out_path

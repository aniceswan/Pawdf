"""Parsing for the 1-indexed page-range syntax the UI exposes ("1-3,5,8-9")."""

from __future__ import annotations

from pawdf.core._shared.errors import InvalidPageRangeError


def parse_page_ranges(spec: str, page_count: int) -> list[int]:
    """Parse a 1-indexed, comma-separated page-range spec into a sorted list of
    unique 0-indexed page numbers.

    Both ends of a range are inclusive, so "1-3" yields [0, 1, 2].
    """
    if not spec.strip():
        raise InvalidPageRangeError("Page range cannot be empty.")

    pages: set[int] = set()
    for raw_chunk in spec.split(","):
        chunk = raw_chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, _, end_s = chunk.partition("-")
            try:
                start, end = int(start_s), int(end_s)
            except ValueError as exc:
                raise InvalidPageRangeError(f"Invalid range segment: '{chunk}'") from exc
            if start < 1 or end < start:
                raise InvalidPageRangeError(f"Invalid range segment: '{chunk}'")
        else:
            try:
                start = end = int(chunk)
            except ValueError as exc:
                raise InvalidPageRangeError(f"Invalid page number: '{chunk}'") from exc
            if start < 1:
                raise InvalidPageRangeError(f"Invalid page number: '{chunk}'")

        if end > page_count:
            raise InvalidPageRangeError(
                f"Range '{chunk}' exceeds document page count ({page_count})."
            )
        pages.update(range(start - 1, end))

    if not pages:
        raise InvalidPageRangeError("Page range cannot be empty.")

    return sorted(pages)

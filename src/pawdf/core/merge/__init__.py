"""Concatenate several PDFs into one, in the given order.

Standalone feature package: depends only on `pawdf.core._shared` and pikepdf.
See README.md in this directory.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ensure_parent_dir, open_pdf

__all__ = ["merge_pdfs"]


def merge_pdfs(paths: list[str | Path], out_path: str | Path) -> Path:
    """Concatenate the PDFs in `paths` (in order) into a single PDF."""
    import pikepdf

    if not paths:
        raise ValueError("paths must contain at least one PDF")

    out_path = ensure_parent_dir(out_path)
    with pikepdf.new() as out_pdf:
        for path in paths:
            with open_pdf(path) as src:
                out_pdf.pages.extend(src.pages)
        out_pdf.save(out_path)

    return out_path

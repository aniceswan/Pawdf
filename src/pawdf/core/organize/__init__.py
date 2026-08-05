"""Rotate, reorder, and delete pages within a PDF.

Standalone feature package: depends only on `pawdf.core._shared` and pikepdf.
See README.md in this directory.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import InvalidPageRangeError, ensure_parent_dir, open_pdf

__all__ = ["apply_page_edits", "delete_pages", "reorder_pages", "rotate_pages"]


def _check_rotation(degrees: int) -> None:
    if degrees % 90 != 0:
        raise ValueError(f"Rotation must be a multiple of 90, got {degrees}")


def rotate_pages(
    input_path: str | Path,
    rotations: dict[int, int],
    out_path: str | Path,
) -> Path:
    """Rotate specific pages, adding to their existing rotation.

    `rotations` maps 0-indexed page number -> degrees (a multiple of 90,
    positive for clockwise). Pages not listed are left untouched.
    """
    out_path = ensure_parent_dir(out_path)
    with open_pdf(input_path) as pdf:
        page_count = len(pdf.pages)
        for index, degrees in rotations.items():
            if not (0 <= index < page_count):
                raise InvalidPageRangeError(f"Page index {index} out of range")
            _check_rotation(degrees)
            pdf.pages[index].rotate(degrees, relative=True)
        pdf.save(out_path)
    return out_path


def delete_pages(
    input_path: str | Path,
    indices: list[int],
    out_path: str | Path,
) -> Path:
    """Write a copy of the PDF with the given 0-indexed pages removed."""
    import pikepdf

    out_path = ensure_parent_dir(out_path)
    to_delete = set(indices)
    with open_pdf(input_path) as pdf:
        page_count = len(pdf.pages)
        for index in to_delete:
            if not (0 <= index < page_count):
                raise InvalidPageRangeError(f"Page index {index} out of range")
        if len(to_delete) == page_count:
            raise InvalidPageRangeError("Cannot delete every page in a PDF")

        with pikepdf.new() as out_pdf:
            for i in range(page_count):
                if i not in to_delete:
                    out_pdf.pages.append(pdf.pages[i])
            out_pdf.save(out_path)
    return out_path


def reorder_pages(
    input_path: str | Path,
    new_order: list[int],
    out_path: str | Path,
) -> Path:
    """Write a copy of the PDF with pages arranged per `new_order`.

    `new_order` lists 0-indexed original page numbers in the desired output
    order. Omitting an index drops that page; repeating one duplicates it.
    """
    import pikepdf

    if not new_order:
        raise InvalidPageRangeError("new_order cannot be empty")

    out_path = ensure_parent_dir(out_path)
    with open_pdf(input_path) as pdf:
        page_count = len(pdf.pages)
        for index in new_order:
            if not (0 <= index < page_count):
                raise InvalidPageRangeError(f"Page index {index} out of range")

        with pikepdf.new() as out_pdf:
            for index in new_order:
                out_pdf.pages.append(pdf.pages[index])
            out_pdf.save(out_path)
    return out_path


def apply_page_edits(
    input_path: str | Path,
    edits: list[tuple[int, int]],
    out_path: str | Path,
) -> Path:
    """Reorder, rotate, and drop pages in a single pass.

    `edits` is a list of (original_page_index, additional_rotation_degrees) in
    the desired output order, which is exactly what the UI's page grid produces
    after a session of dragging, rotating, and deleting. Combining the three
    operations avoids writing an intermediate file per step.
    """
    import pikepdf

    if not edits:
        raise InvalidPageRangeError("edits cannot be empty")

    out_path = ensure_parent_dir(out_path)
    with open_pdf(input_path) as pdf:
        page_count = len(pdf.pages)
        for index, degrees in edits:
            if not (0 <= index < page_count):
                raise InvalidPageRangeError(f"Page index {index} out of range")
            _check_rotation(degrees)

        with pikepdf.new() as out_pdf:
            for index, degrees in edits:
                out_pdf.pages.append(pdf.pages[index])
                if degrees:
                    out_pdf.pages[-1].rotate(degrees, relative=True)
            out_pdf.save(out_path)
    return out_path

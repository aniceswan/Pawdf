"""Render PDF pages to raster images: file export, and in-memory page
bitmaps for UI thumbnails.

Rendering runs on pypdfium2 (PDFium, the engine Chromium uses) rather than
PyMuPDF: PyMuPDF is AGPL/commercial, which would relicense anything that
imports it, while pypdfium2 is BSD-3-Clause / Apache-2.0. Output is
equivalent for this purpose - same pixel dimensions at a given DPI.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pawdf.core._shared import (
    ConversionError,
    EncryptedPdfError,
    InvalidPageRangeError,
    ensure_exists,
    ensure_parent_dir,
)
from pawdf.core._shared import page_count as _page_count

if TYPE_CHECKING:
    import pypdfium2

__all__ = [
    "DEFAULT_EXPORT_DPI",
    "DEFAULT_THUMBNAIL_DPI",
    "RenderedPage",
    "SUPPORTED_FORMATS",
    "page_count",
    "pdf_to_images",
    "render_page",
]

DEFAULT_EXPORT_DPI = 200
DEFAULT_THUMBNAIL_DPI = 72
MAX_DPI = 1200

SUPPORTED_FORMATS = ("png", "jpg", "jpeg", "webp")

# PDF user space is 1/72 inch, so this turns a DPI into PDFium's scale factor.
_POINTS_PER_INCH = 72.0

# PDFium is not thread-safe: concurrent calls into the library corrupt its
# internal state and abort the process, which is a segfault rather than an
# exception you could catch. Callers that render several pages at once (a UI
# filling a thumbnail grid, for instance) would hit this immediately, so the
# guarantee is provided here rather than left as a footnote for every caller
# to rediscover. Rendering is CPU-bound in native code anyway, so serializing
# costs far less than it looks.
_PDFIUM_LOCK = threading.Lock()


@dataclass
class RenderedPage:
    """One rasterized page as raw RGBA bytes, ready for a UI to blit."""

    rgba: bytes
    width: int
    height: int


def _check_dpi(dpi: int) -> int:
    """Reject a DPI that would produce a nonsensical or ruinously large render.

    A negative scale makes PDFium fail in confusing ways, and an absurdly high
    one will happily try to allocate tens of gigabytes, so both are caught here
    rather than deep inside the renderer.
    """
    if dpi <= 0:
        raise ValueError(f"DPI must be positive, got {dpi}")
    if dpi > MAX_DPI:
        raise ValueError(f"DPI must be at most {MAX_DPI}, got {dpi}")
    return dpi


def _open_pdfium(path: Path) -> pypdfium2.PdfDocument:
    """Open a PDF with pypdfium2, mapping its single error type onto the same
    distinctions the rest of core/ makes.

    PDFium reports every failure as PdfiumError with the reason in the message,
    so password protection is told apart from corruption by matching on that
    text rather than an exception subclass.
    """
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise EncryptedPdfError(str(path)) from exc
        raise ConversionError(f"Could not open '{path}': {exc}") from exc


def render_page(
    path: str | Path, page_index: int, dpi: int = DEFAULT_THUMBNAIL_DPI
) -> RenderedPage:
    """Rasterize one page to raw RGBA bytes at the given DPI.

    Used for UI thumbnails and as the building block of `pdf_to_images`.
    """
    _check_dpi(dpi)
    p = ensure_exists(path)

    with _PDFIUM_LOCK:
        doc = _open_pdfium(p)
        try:
            if not (0 <= page_index < len(doc)):
                raise InvalidPageRangeError(f"Page index {page_index} out of range")

            bitmap = doc[page_index].render(scale=dpi / _POINTS_PER_INCH)
            image = bitmap.to_pil().convert("RGBA")
            return RenderedPage(rgba=image.tobytes(), width=image.width, height=image.height)
        finally:
            doc.close()


def page_count(path: str | Path) -> int:
    """Number of pages in `path`.

    Delegates to the shared pikepdf helper rather than opening the file again
    with PDFium: counting pages needs no rendering, and this keeps
    encrypted/corrupt errors identical to every other core/ operation.
    """
    return _page_count(path)


def pdf_to_images(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    dpi: int = DEFAULT_EXPORT_DPI,
    fmt: str = "png",
    stem: str | None = None,
) -> list[Path]:
    """Render every page of `input_path` to an image file in `out_dir`."""
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}")
    _check_dpi(dpi)

    p = ensure_exists(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or p.stem

    outputs: list[Path] = []
    with _PDFIUM_LOCK:
        doc = _open_pdfium(p)
        try:
            for i in range(len(doc)):
                image = doc[i].render(scale=dpi / _POINTS_PER_INCH).to_pil()
                # PDFium composites onto opaque white, so this is already RGB;
                # the convert only matters for the rare document that comes
                # back with an alpha channel, which JPEG cannot store.
                if fmt in ("jpg", "jpeg") and image.mode != "RGB":
                    image = image.convert("RGB")
                out_path = ensure_parent_dir(out_dir / f"{stem}_page{i + 1}.{fmt}")
                image.save(out_path)
                outputs.append(out_path)
        finally:
            doc.close()

    return outputs

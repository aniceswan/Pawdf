"""Draw a layer of notes and marks onto a PDF.

This is the additive half of "edit a PDF": text boxes, boxes, ellipses, lines
and highlights placed at coordinates you choose. It is the half that is
actually tractable.

The other half - editing text that is already in the document - is not here
and is not planned. A PDF stores positioned glyphs against subsetted embedded
fonts, so changing one word means re-encoding the font, reflowing the line and
hoping the rest of the page still fits. Tools that advertise "edit PDF" mostly
do what this does: add a layer on top.

Coordinates are PDF points from the bottom-left of the page, which is the
coordinate system the file itself uses.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from pawdf.core._shared import ConversionError, ensure_exists, ensure_parent_dir, open_pdf

__all__ = [
    "Ellipse",
    "Highlight",
    "Line",
    "Mark",
    "Rectangle",
    "TextNote",
    "annotate_pdf",
    "add_note",
]

_DEFAULT_INK = "#c9343b"


@dataclass
class TextNote:
    """A line of text at a point on the page."""

    text: str
    x: float
    y: float
    size: float = 12.0
    colour: str = _DEFAULT_INK
    page: int = 0


@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    height: float
    colour: str = _DEFAULT_INK
    line_width: float = 1.5
    #: Fill as well as outline. Combined with a low opacity this is a box
    #: highlight rather than a solid block over the text.
    filled: bool = False
    opacity: float = 1.0
    page: int = 0


@dataclass
class Ellipse:
    x: float
    y: float
    width: float
    height: float
    colour: str = _DEFAULT_INK
    line_width: float = 1.5
    filled: bool = False
    opacity: float = 1.0
    page: int = 0


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    colour: str = _DEFAULT_INK
    line_width: float = 1.5
    page: int = 0


@dataclass
class Highlight:
    """A translucent band over a strip of text.

    Separate from a filled Rectangle because the defaults are what make it a
    highlight rather than a redaction: yellow, and see-through.
    """

    x: float
    y: float
    width: float
    height: float = 14.0
    colour: str = "#ffe14d"
    opacity: float = 0.4
    page: int = 0


Mark = TextNote | Rectangle | Ellipse | Line | Highlight


def _rgb(colour: str) -> tuple[float, float, float]:
    value = colour.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Colour must be six hex digits, got '{colour}'")
    try:
        return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"Colour must be six hex digits, got '{colour}'") from exc


def _draw(canvas, mark: Mark) -> None:  # noqa: ANN001 - reportlab Canvas
    canvas.saveState()
    try:
        if isinstance(mark, TextNote):
            canvas.setFillColorRGB(*_rgb(mark.colour))
            canvas.setFont("Helvetica", mark.size)
            canvas.drawString(mark.x, mark.y, mark.text)
            return

        if isinstance(mark, Highlight):
            canvas.setFillColorRGB(*_rgb(mark.colour))
            canvas.setFillAlpha(mark.opacity)
            canvas.rect(mark.x, mark.y, mark.width, mark.height, stroke=0, fill=1)
            return

        colour = _rgb(mark.colour)
        canvas.setStrokeColorRGB(*colour)
        canvas.setFillColorRGB(*colour)

        if isinstance(mark, Line):
            canvas.setLineWidth(mark.line_width)
            canvas.line(mark.x1, mark.y1, mark.x2, mark.y2)
            return

        canvas.setLineWidth(mark.line_width)
        canvas.setFillAlpha(mark.opacity)
        canvas.setStrokeAlpha(mark.opacity)
        fill = 1 if mark.filled else 0

        if isinstance(mark, Rectangle):
            canvas.rect(mark.x, mark.y, mark.width, mark.height, stroke=1, fill=fill)
        elif isinstance(mark, Ellipse):
            canvas.ellipse(
                mark.x, mark.y, mark.x + mark.width, mark.y + mark.height, stroke=1, fill=fill
            )
    finally:
        canvas.restoreState()


def annotate_pdf(
    input_path: str | Path,
    out_path: str | Path,
    marks: list[Mark],
) -> Path:
    """Draw `marks` onto `input_path`.

    Each mark carries its own `page`, so one call annotates the whole document.
    """
    import pikepdf
    from reportlab.pdfgen.canvas import Canvas

    ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    if not marks:
        raise ValueError("marks must not be empty")

    by_page: dict[int, list[Mark]] = {}
    for mark in marks:
        by_page.setdefault(mark.page, []).append(mark)

    try:
        with open_pdf(input_path) as pdf:
            total = len(pdf.pages)
            for index in sorted(by_page):
                if not 0 <= index < total:
                    raise ValueError(f"Page index {index} is outside the document")

                page = pdf.pages[index]
                box = page.get("/CropBox") or page.get("/MediaBox")
                left, bottom, right, top = (float(v) for v in box)
                width, height = right - left, top - bottom

                buffer = io.BytesIO()
                canvas = Canvas(buffer, pagesize=(width, height))
                for mark in by_page[index]:
                    _draw(canvas, mark)
                canvas.showPage()
                canvas.save()

                overlay = pikepdf.open(io.BytesIO(buffer.getvalue()))
                try:
                    page.add_overlay(overlay.pages[0])
                finally:
                    overlay.close()

            pdf.save(out_path)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Could not annotate the PDF: {exc}") from exc

    return out_path


def add_note(
    input_path: str | Path,
    out_path: str | Path,
    *,
    text: str,
    page: int = 0,
    x: float = 72.0,
    y: float = 720.0,
    size: float = 12.0,
    colour: str = _DEFAULT_INK,
) -> Path:
    """Put a single line of text on a page.

    The common case, and the one a UI can offer without a canvas editor.
    """
    if not text:
        raise ValueError("text must not be empty")
    return annotate_pdf(
        input_path,
        out_path,
        [TextNote(text=text, x=x, y=y, size=size, colour=colour, page=page)],
    )

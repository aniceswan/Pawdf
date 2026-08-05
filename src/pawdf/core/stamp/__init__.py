"""Draw something on top of every page: a watermark, page numbers, a signature.

Three tools, one package, because they are the same operation with different
content. Each one builds a single-page PDF the size of the target page,
draws into it with reportlab, and lays it over the original with pikepdf.
Splitting them into three packages would mean three copies of that machinery,
and the copies would drift.

Everything here composites *over* the page. Nothing is removed, and the
original content is still underneath - a watermark is a mark, not a redaction.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pawdf.core._shared import (
    ConversionError,
    ensure_exists,
    ensure_parent_dir,
    open_pdf,
    parse_page_ranges,
)

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

__all__ = [
    "POSITIONS",
    "add_page_numbers",
    "add_watermark",
    "stamp_image",
]

#: Where a stamp sits on the page. The nine-point grid everyone expects, and
#: the only vocabulary the callers need to learn.
POSITIONS = (
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)

#: Distance from the page edge for anything not in the middle, in points.
EDGE_INSET_PT = 36.0


def _anchor(
    position: str, page_w: float, page_h: float, item_w: float, item_h: float
) -> tuple[float, float]:
    """Bottom-left corner for an item of the given size at `position`."""
    if position not in POSITIONS:
        raise ValueError(f"Unknown position '{position}', expected one of {POSITIONS}")

    vertical, _, horizontal = position.partition("-")

    if horizontal == "left":
        x = EDGE_INSET_PT
    elif horizontal == "right":
        x = page_w - item_w - EDGE_INSET_PT
    else:
        x = (page_w - item_w) / 2

    if vertical == "top":
        y = page_h - item_h - EDGE_INSET_PT
    elif vertical == "bottom":
        y = EDGE_INSET_PT
    else:
        y = (page_h - item_h) / 2

    return x, y


def _hex_to_rgb(colour: str) -> tuple[float, float, float]:
    """'#8899aa' or '8899aa' to reportlab's 0..1 triple."""
    value = colour.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Colour must be six hex digits, got '{colour}'")
    try:
        return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"Colour must be six hex digits, got '{colour}'") from exc


def _overlay_page(width: float, height: float, draw: Callable[[Canvas], None]) -> bytes:
    """A one-page PDF of the given size with `draw` applied to its canvas."""
    from reportlab.pdfgen.canvas import Canvas

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(width, height))
    draw(canvas)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _effective_size(page) -> tuple[float, float]:  # noqa: ANN001 - pikepdf Page
    """The page's visible size, accounting for its rotation.

    A page carrying /Rotate 90 is drawn turned, so an overlay built at the
    unrotated dimensions would come out sideways and cropped.
    """
    box = page.get("/CropBox") or page.get("/MediaBox")
    left, bottom, right, top = (float(v) for v in box)
    width, height = right - left, top - bottom

    rotation = int(page.get("/Rotate", 0)) % 360
    if rotation in (90, 270):
        width, height = height, width
    return width, height


def _stamp(
    input_path: str | Path,
    out_path: str | Path,
    draw_for: Callable[[int, float, float], Callable[[Canvas], None] | None],
    *,
    pages: str | None = None,
    under: bool = False,
) -> Path:
    """Apply a per-page overlay to `input_path`.

    `draw_for(page_index, width, height)` returns the drawing function for that
    page, or None to leave the page alone - which is how "skip the first page"
    and page ranges are expressed without special cases in here.
    """
    import pikepdf

    ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    try:
        with open_pdf(input_path) as pdf:
            total = len(pdf.pages)
            targets = set(range(total) if pages is None else parse_page_ranges(pages, total))

            for index, page in enumerate(pdf.pages):
                if index not in targets:
                    continue

                width, height = _effective_size(page)
                draw = draw_for(index, width, height)
                if draw is None:
                    continue

                overlay = pikepdf.open(io.BytesIO(_overlay_page(width, height, draw)))
                try:
                    if under:
                        page.add_underlay(overlay.pages[0])
                    else:
                        page.add_overlay(overlay.pages[0])
                finally:
                    overlay.close()

            pdf.save(out_path)
    except (ValueError, ConversionError):
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Could not stamp the PDF: {exc}") from exc

    return out_path


# --------------------------------------------------------------- watermark --


def add_watermark(
    input_path: str | Path,
    out_path: str | Path,
    *,
    text: str,
    position: str = "center",
    opacity: float = 0.18,
    rotation: float = 45.0,
    font_size: float = 52.0,
    colour: str = "#808080",
    pages: str | None = None,
) -> Path:
    """Draw `text` across every page (or `pages`).

    Defaults are tuned for the usual case: large, grey, diagonal, and faint
    enough to read the document through.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if not text:
        raise ValueError("text must not be empty")
    if not 0.0 < opacity <= 1.0:
        raise ValueError(f"opacity must be between 0 and 1, got {opacity}")

    red, green, blue = _hex_to_rgb(colour)
    font = "Helvetica-Bold"

    def draw_for(_index: int, width: float, height: float):
        text_width = stringWidth(text, font, font_size)

        def draw(canvas: Canvas) -> None:
            canvas.saveState()
            canvas.setFillColorRGB(red, green, blue)
            canvas.setFillAlpha(opacity)
            canvas.setFont(font, font_size)

            if rotation:
                # Rotate about the anchor point, so a diagonal watermark stays
                # where the position asked for rather than swinging off-page.
                x, y = _anchor(position, width, height, 0, font_size)
                canvas.translate(x + text_width / 2, y)
                canvas.rotate(rotation)
                canvas.drawCentredString(0, 0, text)
            else:
                x, y = _anchor(position, width, height, text_width, font_size)
                canvas.drawString(x, y, text)

            canvas.restoreState()

        return draw

    return _stamp(input_path, out_path, draw_for, pages=pages)


# ------------------------------------------------------------ page numbers --


def add_page_numbers(
    input_path: str | Path,
    out_path: str | Path,
    *,
    position: str = "bottom-center",
    start_at: int = 1,
    template: str = "{n}",
    font_size: float = 10.0,
    colour: str = "#404040",
    skip_first: bool = False,
    pages: str | None = None,
) -> Path:
    """Number the pages.

    `template` may use `{n}` for the page's number and `{total}` for the count,
    so "Page {n} of {total}" works. `start_at` shifts the numbering, which is
    what a document with front matter needs.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if "{n}" not in template:
        raise ValueError("template must contain {n}")

    red, green, blue = _hex_to_rgb(colour)
    font = "Helvetica"

    with open_pdf(input_path) as pdf:
        total = len(pdf.pages)

    def draw_for(index: int, width: float, height: float):
        if skip_first and index == 0:
            return None

        label = template.format(n=index + start_at, total=total + start_at - 1)
        text_width = stringWidth(label, font, font_size)
        x, y = _anchor(position, width, height, text_width, font_size)

        def draw(canvas: Canvas) -> None:
            canvas.saveState()
            canvas.setFillColorRGB(red, green, blue)
            canvas.setFont(font, font_size)
            canvas.drawString(x, y, label)
            canvas.restoreState()

        return draw

    return _stamp(input_path, out_path, draw_for, pages=pages)


# ------------------------------------------------------------------ image --


def stamp_image(
    input_path: str | Path,
    out_path: str | Path,
    *,
    image_path: str | Path,
    position: str = "bottom-right",
    width_pt: float = 140.0,
    opacity: float = 1.0,
    pages: str | None = None,
) -> Path:
    """Place an image on the page: a signature, a logo, an approval stamp.

    `width_pt` sets the drawn width; the height follows the image's own aspect
    ratio, because a stamped signature that has been squashed looks forged.
    """
    from reportlab.lib.utils import ImageReader

    if width_pt <= 0:
        raise ValueError(f"width_pt must be positive, got {width_pt}")
    if not 0.0 < opacity <= 1.0:
        raise ValueError(f"opacity must be between 0 and 1, got {opacity}")

    image_file = ensure_exists(image_path)
    try:
        reader = ImageReader(str(image_file))
        native_w, native_h = reader.getSize()
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Could not read image '{image_file}': {exc}") from exc

    draw_h = width_pt * (native_h / native_w)

    def draw_for(_index: int, width: float, height: float):
        x, y = _anchor(position, width, height, width_pt, draw_h)

        def draw(canvas: Canvas) -> None:
            canvas.saveState()
            canvas.setFillAlpha(opacity)
            # mask="auto" honours the image's own transparency, which is what
            # makes a signature sit on the page instead of in a white box.
            canvas.drawImage(
                reader, x, y, width=width_pt, height=draw_h, mask="auto", preserveAspectRatio=True
            )
            canvas.restoreState()

        return draw

    return _stamp(input_path, out_path, draw_for, pages=pages)

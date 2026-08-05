"""PDF -> DocumentIR, using pypdfium2 for text and image extraction.

A PDF stores positioned glyphs, not structure, so everything here is inferred
from geometry and font metrics:

- Lines come from PDFium's own reading-order text stream.
- Paragraphs are lines merged across small vertical gaps; a gap noticeably
  larger than the line height starts a new one.
- Headings are lines whose font is meaningfully larger than the *document's*
  median body size, so a document that uses one size throughout produces no
  headings rather than false ones.
- List items are recognised from a leading bullet or "1." at the start of a
  line, which is all a PDF preserves of a list.

Best-effort by construction. See docs/conversion_fidelity.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from pawdf.core._shared import ConversionError, EncryptedPdfError, ensure_exists
from pawdf.core.pdf_to_markdown.model import (
    DocumentIR,
    ImageIR,
    PageIR,
    ParagraphIR,
    TextRunIR,
)

# How much bigger than the body text a line must be before it counts as a
# heading. Above 1.0 with room to spare, so ordinary size jitter does not
# promote body text.
_HEADING_RATIOS = ((1.9, 1), (1.55, 2), (1.28, 3), (1.12, 4))

# Vertical gap between two lines, as a fraction of the taller one's height,
# above which they are separate paragraphs rather than a wrapped continuation.
_PARAGRAPH_GAP_RATIO = 0.65

# Images smaller than this on a side are bullets, rules or artefacts.
_MIN_IMAGE_SIDE_PT = 24.0

# A leading bullet or number, which is all a PDF keeps of a list.
_LIST_MARKER = re.compile(r"^\s*([•●▪‣\-\*·]|\d{1,3}[.)])\s+")


@dataclass
class _Line:
    runs: list[TextRunIR]
    size: float
    top: float
    bottom: float

    @property
    def height(self) -> float:
        return max(self.top - self.bottom, 1.0)

    def text(self) -> str:
        return "".join(run.text for run in self.runs)


def _style_from_font_name(font_name: str) -> tuple[bool, bool, bool]:
    """Infer (bold, italic, monospace) from a PDF font name.

    The font descriptor's flags are unreliable: PDFium reports
    Helvetica-Oblique with no italic bit set, so the name is what actually
    carries the style in practice.
    """
    name = font_name.lower()
    bold = "bold" in name or "black" in name or "heavy" in name or "semibold" in name
    italic = "italic" in name or "oblique" in name
    mono = "mono" in name or "courier" in name or "consol" in name
    return bold, italic, mono


def _runs_from_chars(chars: list[tuple[str, str]]) -> list[TextRunIR]:
    """Merge consecutive characters that share a style into runs."""
    runs: list[TextRunIR] = []
    for char, font_name in chars:
        bold, italic, mono = _style_from_font_name(font_name)
        if runs and (runs[-1].bold, runs[-1].italic, runs[-1].monospace) == (bold, italic, mono):
            runs[-1].text += char
            continue
        runs.append(TextRunIR(text=char, bold=bold, italic=italic, monospace=mono))
    return runs


def _extract_lines(page) -> list[_Line]:  # noqa: ANN001 - pypdfium2 PdfPage
    import pypdfium2.raw as raw

    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()
        lines: list[_Line] = []
        pending: list[tuple[str, str]] = []
        sizes: list[float] = []
        bounds: list[tuple[float, float, float, float]] = []

        def flush() -> None:
            if not pending:
                return
            lines.append(
                _Line(
                    runs=_runs_from_chars(pending),
                    size=median(sizes),
                    bottom=min(b[1] for b in bounds),
                    top=max(b[3] for b in bounds),
                )
            )
            pending.clear()
            sizes.clear()
            bounds.clear()

        for i in range(count):
            char = chr(raw.FPDFText_GetUnicode(textpage.raw, i))
            if char in "\r\n":
                flush()
                continue

            flags = raw.ctypes.c_int()
            buf = raw.ctypes.create_string_buffer(256)
            written = raw.FPDFText_GetFontInfo(textpage.raw, i, buf, 256, raw.ctypes.byref(flags))
            font_name = buf.value[: max(written - 1, 0)].decode("utf-8", errors="replace")

            pending.append((char, font_name))
            sizes.append(raw.FPDFText_GetFontSize(textpage.raw, i))
            try:
                bounds.append(textpage.get_charbox(i))
            except Exception:  # noqa: BLE001 - a glyph with no box shouldn't kill the page
                bounds.append((0.0, 0.0, 0.0, 0.0))

        flush()
        return [line for line in lines if line.text().strip()]
    finally:
        textpage.close()


def _extract_images(page) -> list[ImageIR]:  # noqa: ANN001 - pypdfium2 PdfPage
    import io

    import pypdfium2 as pdfium

    found: list[ImageIR] = []
    for obj in page.get_objects():
        if not isinstance(obj, pdfium.PdfImage):
            continue
        try:
            left, bottom, right, top = obj.get_bounds()
            if (right - left) < _MIN_IMAGE_SIDE_PT or (top - bottom) < _MIN_IMAGE_SIDE_PT:
                continue

            buffer = io.BytesIO()
            obj.extract(buffer)
            data = buffer.getvalue()
            if not data:
                continue

            # extract() re-encodes to whatever suits the source; sniff the
            # magic bytes rather than guessing from the filename we don't have.
            suffix = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png"
            found.append(ImageIR(data=data, suffix=suffix))
        except Exception:  # noqa: BLE001 - skip anything PDFium can't hand over
            continue
    return found


def _heading_level(size: float, body_size: float) -> int:
    if body_size <= 0:
        return 0
    ratio = size / body_size
    for threshold, level in _HEADING_RATIOS:
        if ratio >= threshold:
            return level
    return 0


def _group_into_paragraphs(lines: list[_Line], body_size: float) -> list[ParagraphIR]:
    paragraphs: list[ParagraphIR] = []
    current: ParagraphIR | None = None
    previous: _Line | None = None

    for line in lines:
        level = _heading_level(line.size, body_size)
        raw_text = line.text()
        # Only body text can start a list. A numbered heading ("1. Introduction")
        # matches the same pattern, and stripping its number would throw away
        # the section number the author wrote.
        marker_match = None if level else _LIST_MARKER.match(raw_text)
        marker = marker_match.group(1) if marker_match else ""

        starts_new = (
            current is None
            or previous is None
            or bool(marker)
            or previous.bottom - line.top > previous.height * _PARAGRAPH_GAP_RATIO
            or level != current.heading_level
            or abs(line.size - previous.size) > 0.5
        )

        if starts_new:
            runs = list(line.runs)
            if marker:
                runs = _strip_marker(runs, marker_match.end())
            current = ParagraphIR(runs=runs, heading_level=level, list_marker=marker)
            paragraphs.append(current)
        else:
            # A wrapped line: the break was the column width, not the author's.
            current.runs.append(TextRunIR(text=" "))
            current.runs.extend(line.runs)

        previous = line

    return paragraphs


def _strip_marker(runs: list[TextRunIR], upto: int) -> list[TextRunIR]:
    """Drop the first `upto` characters, which are the list marker itself.

    Markdown supplies its own marker, so leaving the original in produces
    "- - item".
    """
    remaining = upto
    out: list[TextRunIR] = []
    for run in runs:
        if remaining <= 0:
            out.append(run)
            continue
        if len(run.text) <= remaining:
            remaining -= len(run.text)
            continue
        out.append(
            TextRunIR(
                text=run.text[remaining:],
                bold=run.bold,
                italic=run.italic,
                monospace=run.monospace,
            )
        )
        remaining = 0
    return out


def extract_document(
    path: str | Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> DocumentIR:
    """Read `path` into a DocumentIR.

    `start_page`/`end_page` are 0-indexed and inclusive-exclusive.
    """
    import pypdfium2 as pdfium

    p = ensure_exists(path)
    try:
        doc = pdfium.PdfDocument(p)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise EncryptedPdfError(str(p)) from exc
        raise ConversionError(f"Could not open '{p}': {exc}") from exc

    try:
        first = max(start_page or 0, 0)
        last = len(doc) if end_page is None else min(end_page, len(doc))

        # First pass over the whole selection, so heading detection compares
        # against the document's typical size rather than one page's. A title
        # page would otherwise be measured against itself and yield nothing.
        per_page: list[tuple[list[_Line], list[ImageIR]]] = []
        for index in range(first, last):
            page = doc[index]
            try:
                per_page.append((_extract_lines(page), _extract_images(page)))
            finally:
                page.close()

        sizes = [line.size for lines, _ in per_page for line in lines]
        body_size = median(sizes) if sizes else 0.0

        document = DocumentIR()
        for lines, images in per_page:
            page_ir = PageIR()
            page_ir.blocks.extend(_group_into_paragraphs(lines, body_size))
            # Images go after the page's text: placing them correctly would
            # need the layout analysis this converter deliberately avoids.
            page_ir.blocks.extend(images)
            document.pages.append(page_ir)

        return document
    finally:
        doc.close()

"""PDF -> DocumentIR, using pypdfium2 (PDFium) for text and image extraction.

A PDF stores positioned glyphs, not paragraphs, so everything structural here
is inferred from geometry and font metrics:

- Lines come from PDFium's own reading-order text stream, which separates
  them with newline characters.
- Paragraphs are lines merged across small vertical gaps; a gap noticeably
  larger than the local line height starts a new one.
- Headings are lines whose font is meaningfully larger than the document's
  median body size, so a document that uses one size throughout produces no
  headings at all rather than false ones.

All of this is best-effort by construction. See docs/conversion_fidelity.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

from pawdf.core._shared import ConversionError, EncryptedPdfError, ensure_exists
from pawdf.core.pdf_to_docx.model import DocumentIR, ImageIR, PageIR, ParagraphIR, TextRunIR

# A line must be this much bigger than the document's median text size before
# it's treated as a heading. Set above 1.0 with room to spare so ordinary
# size jitter (superscripts, a slightly larger first line) doesn't promote
# body text into headings.
_HEADING_RATIO_H3 = 1.15
_HEADING_RATIO_H2 = 1.4
_HEADING_RATIO_H1 = 1.8

# Vertical gap between two lines, as a fraction of the taller line's height,
# above which they're considered separate paragraphs rather than a wrapped
# continuation of one.
_PARAGRAPH_GAP_RATIO = 0.65

# How close a line's horizontal centre must be to the page's, as a fraction
# of page width, to be called centred.
_CENTER_TOLERANCE_RATIO = 0.06

# Images smaller than this on a side (in points) are almost always bullets,
# rules, or background artefacts rather than real figures.
_MIN_IMAGE_SIDE_PT = 12.0


@dataclass
class _Line:
    """One visual line of text, before paragraph grouping."""

    runs: list[TextRunIR]
    size: float
    left: float
    right: float
    top: float
    bottom: float

    @property
    def height(self) -> float:
        return max(self.top - self.bottom, 1.0)

    def text(self) -> str:
        return "".join(run.text for run in self.runs)


def _style_from_font_name(font_name: str) -> tuple[bool, bool]:
    """Infer (bold, italic) from a PDF font name.

    The font descriptor's own flags are unreliable for this: PDFium reports
    Helvetica-Oblique with only the nonsymbolic bit set, no italic bit, so
    the name is what actually carries the style in practice.
    """
    name = font_name.lower()
    bold = "bold" in name or "black" in name or "heavy" in name
    italic = "italic" in name or "oblique" in name
    return bold, italic


def _runs_from_chars(chars: list[tuple[str, float, str]]) -> list[TextRunIR]:
    """Merge consecutive characters that share a style into runs."""
    runs: list[TextRunIR] = []
    for char, size, font_name in chars:
        bold, italic = _style_from_font_name(font_name)
        rounded = round(size, 1)
        if runs and runs[-1].bold == bold and runs[-1].italic == italic:
            if abs(runs[-1].font_size_pt - rounded) < 0.05:
                runs[-1].text += char
                continue
        runs.append(TextRunIR(text=char, bold=bold, italic=italic, font_size_pt=rounded))
    return runs


def _extract_lines(page) -> list[_Line]:  # noqa: ANN001 - pypdfium2 PdfPage
    """Pull every text line off one page, in PDFium's reading order."""
    import pypdfium2.raw as raw

    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()
        lines: list[_Line] = []
        pending: list[tuple[str, float, str]] = []
        bounds: list[tuple[float, float, float, float]] = []

        def flush() -> None:
            if not pending:
                return
            runs = _runs_from_chars(pending)
            sizes = [size for _, size, _ in pending]
            # pypdfium2's get_charbox returns (left, bottom, right, top),
            # reordering PDFium's own (left, right, bottom, top) signature.
            lines.append(
                _Line(
                    runs=runs,
                    size=median(sizes),
                    left=min(b[0] for b in bounds),
                    bottom=min(b[1] for b in bounds),
                    right=max(b[2] for b in bounds),
                    top=max(b[3] for b in bounds),
                )
            )
            pending.clear()
            bounds.clear()

        for i in range(count):
            char = chr(raw.FPDFText_GetUnicode(textpage.raw, i))
            if char in "\r\n":
                flush()
                continue

            size = raw.FPDFText_GetFontSize(textpage.raw, i)
            flags = raw.ctypes.c_int()
            buf = raw.ctypes.create_string_buffer(256)
            written = raw.FPDFText_GetFontInfo(textpage.raw, i, buf, 256, raw.ctypes.byref(flags))
            font_name = buf.value[: max(written - 1, 0)].decode("utf-8", errors="replace")

            pending.append((char, size, font_name))
            try:
                bounds.append(textpage.get_charbox(i))
            except Exception:  # noqa: BLE001 - a glyph with no box shouldn't kill the page
                bounds.append((0.0, 0.0, 0.0, 0.0))

        flush()
        return [line for line in lines if line.text().strip()]
    finally:
        textpage.close()


def _extract_images(page) -> list[tuple[float, ImageIR]]:  # noqa: ANN001 - pypdfium2 PdfPage
    """Return (vertical position, image) pairs for embedded raster images."""
    import pypdfium2 as pdfium

    found: list[tuple[float, ImageIR]] = []
    for obj in page.get_objects():
        if not isinstance(obj, pdfium.PdfImage):
            continue
        try:
            left, bottom, right, top = obj.get_bounds()
            width_pt, height_pt = right - left, top - bottom
            if width_pt < _MIN_IMAGE_SIDE_PT or height_pt < _MIN_IMAGE_SIDE_PT:
                continue

            # extract() re-encodes to a format python-docx can embed, and
            # handles the image's own filter/colourspace details for us.
            import io

            buffer = io.BytesIO()
            obj.extract(buffer)
            data = buffer.getvalue()
            if not data:
                continue
            found.append((top, ImageIR(data=data, width_pt=width_pt, height_pt=height_pt)))
        except Exception:  # noqa: BLE001 - skip anything PDFium can't hand over
            continue
    return found


def _heading_level(size: float, body_size: float) -> int:
    if body_size <= 0:
        return 0
    ratio = size / body_size
    if ratio >= _HEADING_RATIO_H1:
        return 1
    if ratio >= _HEADING_RATIO_H2:
        return 2
    if ratio >= _HEADING_RATIO_H3:
        return 3
    return 0


def _alignment(line: _Line, page_width: float) -> str:
    if page_width <= 0:
        return "left"
    line_center = (line.left + line.right) / 2
    if abs(line_center - page_width / 2) <= page_width * _CENTER_TOLERANCE_RATIO:
        # Only call it centred if it doesn't also start at the left margin,
        # since a full-width line of body text is centred by coincidence.
        if line.left > page_width * 0.15:
            return "center"
    return "left"


def _group_into_paragraphs(
    lines: list[_Line], body_size: float, page_width: float
) -> list[ParagraphIR]:
    paragraphs: list[ParagraphIR] = []
    current: ParagraphIR | None = None
    previous: _Line | None = None

    for line in lines:
        level = _heading_level(line.size, body_size)

        if current is None or previous is None:
            starts_new = True
        else:
            gap = previous.bottom - line.top
            starts_new = (
                gap > previous.height * _PARAGRAPH_GAP_RATIO
                or level != current.heading_level
                or abs(line.size - previous.size) > 0.5
            )

        if starts_new:
            current = ParagraphIR(
                runs=list(line.runs),
                heading_level=level,
                alignment=_alignment(line, page_width),
            )
            paragraphs.append(current)
        else:
            assert current is not None
            # Wrapped lines are joined with a space: the line break was a
            # layout artefact of the PDF's column width, not real content.
            current.runs.append(TextRunIR(text=" ", font_size_pt=line.size))
            current.runs.extend(line.runs)

        previous = line

    return paragraphs


def extract_document(
    path: str | Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> DocumentIR:
    """Read `path` into a DocumentIR.

    `start_page`/`end_page` are 0-indexed and inclusive-exclusive, or None
    for the whole document.
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

        # First pass: every line in the selected range, so heading detection
        # can compare against the whole document's typical size rather than a
        # single page's (a title page would otherwise skew its own page).
        per_page: list[tuple[list[_Line], list[tuple[float, ImageIR]], float]] = []
        for index in range(first, last):
            page = doc[index]
            try:
                width, _height = page.get_size()
                per_page.append((_extract_lines(page), _extract_images(page), width))
            finally:
                page.close()

        all_sizes = [line.size for lines, _, _ in per_page for line in lines]
        body_size = median(all_sizes) if all_sizes else 0.0

        document = DocumentIR()
        for lines, images, width in per_page:
            page_ir = PageIR()
            paragraphs = _group_into_paragraphs(lines, body_size, width)
            page_ir.blocks.extend(paragraphs)
            # Images go after the page's text: reconstructing true interleaved
            # position would need the same layout analysis this converter
            # deliberately doesn't attempt.
            page_ir.blocks.extend(image for _, image in sorted(images, key=lambda t: -t[0]))
            document.pages.append(page_ir)

        return document
    finally:
        doc.close()

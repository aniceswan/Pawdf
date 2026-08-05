"""DocumentIR -> PDF via reportlab Platypus.

reportlab (not weasyprint) specifically because it's pure-Python-plus-C-
extension with no system Cairo/Pango dependency, which matters for reliable
PyInstaller packaging across three OSes.
"""

from __future__ import annotations

import html
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pawdf.core.docx_to_pdf.model import (
    BlockIR,
    DocumentIR,
    ImageIR,
    ListItemIR,
    PageBreakIR,
    ParagraphIR,
    RunIR,
    TableIR,
)
from pawdf.core.docx_to_pdf.styles import style_for

MAX_IMAGE_WIDTH_PT = 400
LIST_INDENT_PT = 18
FALLBACK_IMAGE_DPI = 96


def render_to_pdf(doc_ir: DocumentIR, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    doc = SimpleDocTemplate(str(out_path), pagesize=letter)
    doc.build(_render_blocks(doc_ir.blocks))
    return out_path


def _render_blocks(blocks: list[BlockIR]) -> list:
    story = []
    list_counters: dict[int, int] = {}

    for block in blocks:
        if isinstance(block, ListItemIR):
            story.append(_render_list_item(block, list_counters))
            continue

        list_counters.clear()  # a non-list block breaks numbered-list continuity
        if isinstance(block, ParagraphIR):
            story.append(_render_paragraph(block))
        elif isinstance(block, TableIR):
            story.append(_render_table(block))
        elif isinstance(block, ImageIR):
            story.append(_render_image(block))
        elif isinstance(block, PageBreakIR):
            story.append(PageBreak())

    return story


def _run_markup(run: RunIR) -> str:
    text = html.escape(run.text)
    if run.color_hex:
        text = f'<font color="#{run.color_hex}">{text}</font>'
    if run.font_size_pt:
        text = f'<font size="{run.font_size_pt}">{text}</font>'
    if run.underline:
        text = f"<u>{text}</u>"
    if run.italic:
        text = f"<i>{text}</i>"
    if run.bold:
        text = f"<b>{text}</b>"
    return text


def _render_paragraph(paragraph: ParagraphIR) -> Paragraph | Spacer:
    style = style_for(paragraph.style, paragraph.alignment)
    if not paragraph.runs:
        return Spacer(1, style.fontSize * 0.8)
    text = "".join(_run_markup(r) for r in paragraph.runs)
    return Paragraph(text, style)


def _render_list_item(item: ListItemIR, counters: dict[int, int]) -> Paragraph:
    base_style = style_for(item.paragraph.style, item.paragraph.alignment)
    style = ParagraphStyle(
        f"list_level_{item.level}",
        parent=base_style,
        leftIndent=LIST_INDENT_PT * (item.level + 1),
    )

    if item.ordered:
        counters[item.level] = counters.get(item.level, 0) + 1
        prefix = f"{counters[item.level]}. "
    else:
        prefix = "• "

    text = prefix + "".join(_run_markup(r) for r in item.paragraph.runs)
    return Paragraph(text, style)


def _render_table(table: TableIR) -> Table:
    empty_cell_style = style_for("Normal")
    data = []
    for row in table.rows:
        row_cells = []
        for cell_blocks in row:
            flowables = _render_blocks(cell_blocks) or [Paragraph("", empty_cell_style)]
            row_cells.append(flowables)
        data.append(row_cells)

    rl_table = Table(data)
    rl_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return rl_table


def _render_image(image: ImageIR) -> Image:
    from PIL import Image as PILImage

    width, height = image.width_pt, image.height_pt
    if width is None or height is None:
        px_width, px_height = PILImage.open(io.BytesIO(image.data)).size
        width = width or px_width * 72 / FALLBACK_IMAGE_DPI
        height = height or px_height * 72 / FALLBACK_IMAGE_DPI

    if width > MAX_IMAGE_WIDTH_PT:
        scale = MAX_IMAGE_WIDTH_PT / width
        width, height = width * scale, height * scale

    return Image(io.BytesIO(image.data), width=width, height=height)

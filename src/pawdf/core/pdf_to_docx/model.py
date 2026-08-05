"""Intermediate representation for PDF -> Word conversion.

Deliberately has no pypdfium2 or python-docx imports: extract.py builds this
from a PDF, render_docx.py consumes it to produce a .docx. Keeping the IR
dependency-free lets each side be tested on its own.

This is a separate IR from docx_to_pdf/model.py rather than a shared one.
The two directions genuinely carry different information: going Word -> PDF
starts from explicit structure (styles, list numbering, table grids), while
going PDF -> Word starts from positioned glyphs and has to *infer* structure,
so this side needs font sizes and geometry that the other side never has.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextRunIR:
    """A stretch of text sharing one font and style."""

    text: str
    bold: bool = False
    italic: bool = False
    font_size_pt: float = 0.0


@dataclass
class ParagraphIR:
    runs: list[TextRunIR] = field(default_factory=list)
    # 0 means body text; 1..3 map to Word's Heading 1..3.
    heading_level: int = 0
    alignment: str = "left"  # "left" | "center" | "right"

    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass
class ImageIR:
    data: bytes
    # Rendered size on the PDF page, in points. Used to size the picture in
    # the .docx so it doesn't come out at the raster's native pixel size.
    width_pt: float
    height_pt: float


@dataclass
class PageIR:
    blocks: list[BlockIR] = field(default_factory=list)


BlockIR = ParagraphIR | ImageIR


@dataclass
class DocumentIR:
    pages: list[PageIR] = field(default_factory=list)

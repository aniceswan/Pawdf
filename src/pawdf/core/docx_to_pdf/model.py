"""Intermediate representation for Word -> PDF conversion.

Deliberately has no python-docx or reportlab imports: parser.py builds this
from a .docx, render_reportlab.py consumes it to produce a PDF. Keeping the
IR dependency-free lets each side be tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunIR:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size_pt: float | None = None
    color_hex: str | None = None  # e.g. "FF0000", no leading '#'


@dataclass
class ParagraphIR:
    runs: list[RunIR] = field(default_factory=list)
    style: str = "Normal"  # e.g. "Normal", "Heading1".."Heading9", "Title"
    alignment: str = "left"  # "left" | "center" | "right" | "justify"


@dataclass
class ListItemIR:
    paragraph: ParagraphIR
    level: int = 0
    ordered: bool = False


@dataclass
class ImageIR:
    data: bytes
    width_pt: float | None = None
    height_pt: float | None = None


@dataclass
class PageBreakIR:
    pass


@dataclass
class TableIR:
    # rows -> cells -> list of blocks (a cell can contain multiple paragraphs)
    rows: list[list[list[BlockIR]]] = field(default_factory=list)


BlockIR = ParagraphIR | ListItemIR | TableIR | ImageIR | PageBreakIR


@dataclass
class DocumentIR:
    blocks: list[BlockIR] = field(default_factory=list)

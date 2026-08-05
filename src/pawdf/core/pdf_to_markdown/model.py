"""Intermediate representation for PDF -> Markdown.

No pypdfium2 and no rendering imports: `extract.py` builds this from a PDF and
`render_markdown.py` turns it into text, so each half is testable on its own.
You can hand-build a DocumentIR and check the Markdown without a PDF, or
extract one and assert on its shape without writing a file.

This is a separate IR from `pdf_to_docx/model.py` rather than a shared one,
because features in this project do not import each other - lifting either
package out has to work without dragging the other along. They also want
different things: Word cares about alignment and run colours, Markdown has no
way to express either.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextRunIR:
    """A stretch of text sharing one style."""

    text: str
    bold: bool = False
    italic: bool = False
    monospace: bool = False


@dataclass
class ParagraphIR:
    runs: list[TextRunIR] = field(default_factory=list)
    #: 0 is body text; 1..6 map to Markdown's `#` levels.
    heading_level: int = 0
    #: True when the line began with a bullet or a number, so the renderer can
    #: emit a list item instead of a paragraph.
    list_marker: str = ""

    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass
class ImageIR:
    data: bytes
    #: Extension including the dot, decided by the extractor from the bytes.
    suffix: str = ".png"


BlockIR = ParagraphIR | ImageIR


@dataclass
class PageIR:
    blocks: list[BlockIR] = field(default_factory=list)


@dataclass
class DocumentIR:
    pages: list[PageIR] = field(default_factory=list)

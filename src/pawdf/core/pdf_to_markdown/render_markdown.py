"""DocumentIR -> Markdown text, plus any extracted images written alongside.

Consumes only the IR, so it can be tested by handing it a DocumentIR built in
code with no PDF involved.
"""

from __future__ import annotations

import re
from pathlib import Path

from pawdf.core.pdf_to_markdown.model import DocumentIR, ImageIR, ParagraphIR, TextRunIR

__all__ = ["render_markdown"]

#: Markdown only defines six heading levels.
MAX_HEADING = 6

# Characters that would otherwise be read as formatting. Deliberately narrow:
# escaping every possible special character makes ordinary prose unreadable in
# the source, and these are the ones that actually bite mid-sentence.
_ESCAPE = re.compile(r"([\\`*_{}\[\]])")


def _escape(text: str) -> str:
    return _ESCAPE.sub(r"\\\1", text)


def _emphasise(run: TextRunIR) -> str:
    """One run as Markdown, with its emphasis applied."""
    text = run.text
    if not text.strip():
        # Whitespace between runs carries no emphasis, and wrapping it in
        # markers produces `** **`, which renders literally.
        return text

    # Leading and trailing spaces have to sit outside the markers or the
    # emphasis simply does not apply.
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    core = text.strip()

    core = f"`{core}`" if run.monospace else _escape(core)
    if run.bold and run.italic:
        core = f"***{core}***"
    elif run.bold:
        core = f"**{core}**"
    elif run.italic:
        core = f"_{core}_"

    return f"{leading}{core}{trailing}"


def _paragraph_text(paragraph: ParagraphIR) -> str:
    return "".join(_emphasise(run) for run in paragraph.runs).strip()


def _render_paragraph(paragraph: ParagraphIR) -> str:
    text = _paragraph_text(paragraph)
    if not text:
        return ""

    if paragraph.heading_level > 0:
        level = min(paragraph.heading_level, MAX_HEADING)
        # Headings must not carry emphasis markers: `## **Title**` renders as
        # a heading containing literal asterisks in several viewers.
        plain = "".join(run.text for run in paragraph.runs).strip()
        return f"{'#' * level} {_escape(plain)}"

    if paragraph.list_marker:
        ordered = paragraph.list_marker[0].isdigit()
        # Always "1." for ordered lists: Markdown renumbers automatically, and
        # hard-coding the original numbers goes wrong the moment an item moves.
        return f"{'1.' if ordered else '-'} {text}"

    return text


def render_markdown(
    document: DocumentIR,
    out_path: str | Path,
    *,
    image_dir_name: str | None = None,
    page_separators: bool = False,
) -> Path:
    """Write `document` as Markdown at `out_path`.

    Images are written to a sibling folder (named after the file by default)
    and linked relatively, so moving the pair keeps the links working.

    `page_separators` inserts a `---` rule between pages. Off by default: page
    boundaries are a fact about the PDF, not about the text, and most people
    converting to Markdown want continuous prose.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    folder_name = image_dir_name or f"{out_path.stem}_images"
    image_dir = out_path.parent / folder_name

    chunks: list[str] = []
    image_count = 0

    for page_index, page in enumerate(document.pages):
        if page_separators and page_index > 0:
            chunks.append("---")

        for block in page.blocks:
            if isinstance(block, ParagraphIR):
                rendered = _render_paragraph(block)
                if rendered:
                    chunks.append(rendered)
            elif isinstance(block, ImageIR):
                image_count += 1
                image_dir.mkdir(parents=True, exist_ok=True)
                name = f"image-{image_count:03d}{block.suffix}"
                (image_dir / name).write_bytes(block.data)
                chunks.append(f"![]({folder_name}/{name})")

    # One blank line between blocks, which is what every Markdown parser needs
    # to see a paragraph break. Consecutive list items are joined tightly so
    # they render as one list rather than a loose one.
    body = _join(chunks)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def _join(chunks: list[str]) -> str:
    if not chunks:
        return ""

    out: list[str] = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            both_items = _is_list_item(chunks[i - 1]) and _is_list_item(chunk)
            out.append("\n" if both_items else "\n\n")
        out.append(chunk)
    return "".join(out).strip() + "\n"


def _is_list_item(chunk: str) -> bool:
    return chunk.startswith(("- ", "1. "))

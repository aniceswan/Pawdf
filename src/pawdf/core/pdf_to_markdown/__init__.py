"""PDF -> Markdown via a custom PDF -> IR -> text pipeline.

Markdown is what people paste into notes, wikis, static sites and language
models, and nothing else in this class exports it cleanly. The extraction
work was already done for PDF -> Word, so this direction is mostly a second
renderer over the same idea.

A PDF has no headings, lists or emphasis to read back: it has positioned
glyphs. So structure is reconstructed by inference (see extract.py), which is
best-effort by nature. docs/conversion_fidelity.md documents what survives.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ConversionError, PawdfError, ensure_parent_dir

__all__ = ["pdf_to_markdown"]


def pdf_to_markdown(
    input_path: str | Path,
    out_path: str | Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
    page_separators: bool = False,
) -> Path:
    """Convert a PDF to a Markdown file.

    `start_page`/`end_page` are 0-indexed and inclusive-exclusive. Extracted
    images land in a sibling folder and are linked relatively.
    """
    # Imported here, not at module level: pypdfium2 is only needed when this
    # conversion actually runs, and the GUI imports core modules at startup.
    from pawdf.core.pdf_to_markdown.extract import extract_document
    from pawdf.core.pdf_to_markdown.render_markdown import render_markdown

    out_path = ensure_parent_dir(out_path)

    try:
        document = extract_document(input_path, start_page=start_page, end_page=end_page)
        render_markdown(document, out_path, page_separators=page_separators)
    except PawdfError:
        # EncryptedPdfError and friends already say something useful; only
        # unexpected failures need wrapping.
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for the GUI
        raise ConversionError(f"Could not convert PDF to Markdown: {exc}") from exc

    if not out_path.exists():
        raise ConversionError("Conversion did not produce an output file.")

    return out_path

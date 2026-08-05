"""PDF -> Word (.docx) via a custom PDF -> IR -> python-docx pipeline.

Built in-project rather than wrapping pdf2docx, which hard-requires PyMuPDF
(AGPL/commercial) and would force the whole project copyleft. Everything
here runs on pypdfium2 (BSD-3-Clause/Apache-2.0) and python-docx (MIT).

A PDF has no paragraphs, headings, or styles to read back: it has positioned
glyphs. So this reconstructs structure by inference (see extract.py), which
is best-effort by nature. docs/conversion_fidelity.md documents what survives
the round trip and what doesn't.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ConversionError, PawdfError, ensure_parent_dir


def pdf_to_docx(
    input_path: str | Path,
    out_path: str | Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> Path:
    """Convert a PDF to an editable .docx. `start_page`/`end_page` are
    0-indexed and inclusive-exclusive, or None for the whole document.
    """
    # Imported here, not at module level: python-docx (~45ms) and pypdfium2
    # are only needed when this conversion actually runs, and core modules
    # are imported eagerly by the GUI bridge at startup.
    from pawdf.core.pdf_to_docx.extract import extract_document
    from pawdf.core.pdf_to_docx.render_docx import render_to_docx

    out_path = ensure_parent_dir(out_path)

    try:
        document_ir = extract_document(input_path, start_page=start_page, end_page=end_page)
        render_to_docx(document_ir, out_path)
    except PawdfError:
        # EncryptedPdfError and friends already say something useful; only
        # unexpected failures need wrapping.
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for the GUI
        raise ConversionError(f"Could not convert PDF to Word: {exc}") from exc

    if not out_path.exists():
        raise ConversionError("Conversion did not produce an output file.")

    return out_path

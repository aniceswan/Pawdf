"""Word (.docx) -> PDF via a custom docx model -> IR -> reportlab pipeline.

Best-effort fidelity by design, so the app has no dependency on Word or
LibreOffice being installed. See docs/conversion_fidelity.md for what's
supported and what isn't.
"""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared import ConversionError, ensure_exists, ensure_parent_dir


def docx_to_pdf(input_path: str | Path, out_path: str | Path) -> Path:
    # parser.py and render_reportlab.py import python-docx (~45ms) and
    # reportlab (~112ms) at their own module level (both are used
    # pervasively enough within those files that deferring function-by-
    # function wasn't worth the churn); deferring the submodule imports
    # themselves to here instead means the app only pays that cost when
    # Word->PDF is actually used, not at startup.
    from pawdf.core.docx_to_pdf.parser import parse_docx
    from pawdf.core.docx_to_pdf.render_reportlab import render_to_pdf

    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    try:
        document_ir = parse_docx(str(p))
        render_to_pdf(document_ir, out_path)
    except Exception as exc:  # noqa: BLE001 - normalized for the GUI
        raise ConversionError(f"Could not convert Word document to PDF: {exc}") from exc

    return out_path

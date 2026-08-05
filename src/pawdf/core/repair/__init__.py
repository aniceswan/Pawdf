"""Recover what can be read from a damaged PDF.

QPDF, which pikepdf wraps, rebuilds a file's cross-reference table by scanning
for object definitions when the table itself is missing or wrong. That covers
the common damage: a truncated download, a file written by something that
crashed mid-save, a corrupted index over intact page content.

What it cannot do is invent bytes that are not there. A file whose page
streams are genuinely gone comes back with fewer pages, so this reports how
many survived instead of claiming success and leaving the caller to find out
later.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pawdf.core._shared import (
    EncryptedPdfError,
    InvalidPdfError,
    ensure_exists,
    ensure_parent_dir,
)

__all__ = ["RepairResult", "repair_pdf"]


@dataclass
class RepairResult:
    output_path: Path
    pages_recovered: int
    #: True when the input opened with no recovery at all, i.e. it wasn't broken.
    was_already_readable: bool
    #: True when the *output* opens with no recovery. False means the damage
    #: outlived the attempt and the file is readable but still not clean.
    is_now_clean: bool
    #: What QPDF had to reconstruct while reading, verbatim.
    warnings: list[str] = field(default_factory=list)
    original_size: int = 0
    repaired_size: int = 0


def _opens_without_recovery(path: Path) -> bool:
    """Whether `path` parses on its own terms.

    The distinction this whole module turns on: QPDF silently rebuilds a
    broken cross-reference table on a normal open, so "did it open" answers
    yes for a file that had to be rescued. Turning recovery off is what makes
    the question mean anything.
    """
    import pikepdf

    try:
        with pikepdf.open(path, attempt_recovery=False):
            return True
    except pikepdf.PasswordError:
        raise
    except pikepdf.PdfError:
        return False


def repair_pdf(input_path: str | Path, out_path: str | Path) -> RepairResult:
    """Rebuild `input_path` into a structurally clean PDF.

    Raises InvalidPdfError when nothing readable could be recovered, rather
    than writing an empty file and calling it a success.
    """
    import pikepdf

    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    try:
        already_readable = _opens_without_recovery(p)
    except pikepdf.PasswordError as exc:
        # Encrypted is not damaged. Unlock it first.
        raise EncryptedPdfError(str(p)) from exc

    try:
        with pikepdf.open(p) as src:
            pages = len(src.pages)
            if pages == 0:
                raise InvalidPdfError(str(p), detail="no readable pages were found")

            # Collected before saving: these describe what QPDF reconstructed
            # while reading, which is the only account of the damage there is.
            warnings = list(src.get_warnings())

            # Copy the recovered pages into a document built from nothing.
            # Re-saving the damaged Pdf in place carries its broken trailer
            # straight through -- the output still needs recovery to open,
            # which is not a repair. A fresh document has a correct
            # cross-reference table by construction.
            rebuilt = pikepdf.new()
            try:
                rebuilt.pages.extend(src.pages)
                try:
                    rebuilt.open_metadata().load_from_docinfo(src.docinfo)
                except Exception:  # noqa: BLE001 - metadata is not worth failing over
                    pass
                rebuilt.save(out_path)
            finally:
                rebuilt.close()
    except pikepdf.PasswordError as exc:
        raise EncryptedPdfError(str(p)) from exc
    except pikepdf.PdfError as exc:
        raise InvalidPdfError(str(p), detail=f"could not be recovered: {exc}") from exc

    return RepairResult(
        output_path=out_path,
        pages_recovered=pages,
        was_already_readable=already_readable,
        # Checked rather than assumed: if the output still needs recovery, the
        # caller should be told the repair did not fully take.
        is_now_clean=_opens_without_recovery(out_path),
        warnings=warnings,
        original_size=p.stat().st_size,
        repaired_size=out_path.stat().st_size,
    )

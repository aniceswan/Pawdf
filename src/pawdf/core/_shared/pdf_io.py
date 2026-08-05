"""Consistent PDF opening for every feature that reads a PDF with pikepdf.

pikepdf is imported lazily (inside the functions, not at module level): it's
an ~85ms import and this module is pulled in by nearly every feature, so
importing it eagerly meant paying that cost at app startup whether or not the
user ever touched a PDF.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from pawdf.core._shared.errors import EncryptedPdfError, InvalidPdfError
from pawdf.core._shared.paths import ensure_exists

if TYPE_CHECKING:
    import pikepdf


@contextmanager
def open_pdf(path: str | Path) -> Iterator[pikepdf.Pdf]:
    """Open a PDF with pikepdf, normalizing its exceptions into core/ ones.

    Raises EncryptedPdfError for password-protected files and InvalidPdfError
    for anything else pikepdf can't parse.
    """
    import pikepdf

    p = ensure_exists(path)
    try:
        with pikepdf.open(p) as pdf:
            yield pdf
    except pikepdf.PasswordError as exc:
        raise EncryptedPdfError(str(p)) from exc
    except pikepdf.PdfError as exc:
        raise InvalidPdfError(str(p), detail=str(exc)) from exc


def page_count(path: str | Path) -> int:
    """Number of pages in `path`."""
    with open_pdf(path) as pdf:
        return len(pdf.pages)

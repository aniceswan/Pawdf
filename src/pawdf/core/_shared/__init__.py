"""The only module every core/ feature is allowed to share.

Kept deliberately tiny (errors, path helpers, page-range parsing, and a
pikepdf open/close wrapper) so that lifting a single feature package out of
this repo means copying that feature plus this one directory, and nothing
else. See _shared/README.md.
"""

from pawdf.core._shared.errors import (
    ConversionError,
    EncryptedPdfError,
    GhostscriptNotFoundError,
    InvalidPageRangeError,
    InvalidPdfError,
    PawdfError,
    ResourceLimitError,
)
from pawdf.core._shared.paths import ensure_exists, ensure_parent_dir
from pawdf.core._shared.pdf_io import open_pdf, page_count
from pawdf.core._shared.ranges import parse_page_ranges

__all__ = [
    "ConversionError",
    "EncryptedPdfError",
    "GhostscriptNotFoundError",
    "InvalidPageRangeError",
    "InvalidPdfError",
    "PawdfError",
    "ResourceLimitError",
    "ensure_exists",
    "ensure_parent_dir",
    "open_pdf",
    "page_count",
    "parse_page_ranges",
]

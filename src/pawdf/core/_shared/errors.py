"""Exceptions raised by every core/ feature.

Feature packages raise these instead of bare exceptions so a caller can tell
"the user picked a locked file" apart from "this library blew up" without
parsing strings. The GUI turns them straight into user-facing messages.
"""

from __future__ import annotations


class PawdfError(Exception):
    """Base class for all expected, user-facing errors raised from core/."""


class ResourceLimitError(PawdfError):
    """Raised before an unsafe or unreasonable input reaches a parser."""


class EncryptedPdfError(PawdfError):
    """Raised when an operation needs to read a password-protected PDF."""

    def __init__(self, path: str):
        super().__init__(f"'{path}' is password-protected and cannot be processed.")
        self.path = path


class InvalidPdfError(PawdfError):
    """Raised when a file can't be read as a PDF at all: corrupted, truncated,
    or simply not a PDF despite the extension.
    """

    def __init__(self, path: str, detail: str = ""):
        message = f"'{path}' doesn't look like a valid PDF file (it may be corrupted)."
        if detail:
            message += f" Details: {detail}"
        super().__init__(message)
        self.path = path


class InvalidPageRangeError(PawdfError):
    """Raised when a requested page range is malformed or out of bounds."""


class GhostscriptNotFoundError(PawdfError):
    """Raised when Ghostscript is required but unavailable and no fallback applies."""


class ConversionError(PawdfError):
    """Raised when a format conversion (images, docx, ...) fails."""

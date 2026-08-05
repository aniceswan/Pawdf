"""Locating Tesseract, and saying what to install when it isn't there.

Deliberately the same shape as `core/compress/ghostscript.py`. Tesseract is
Apache-2.0, so unlike Ghostscript there is no licence reason to keep it at
arm's length - the reason here is size. The engine plus one language's
training data is a few hundred megabytes, and bundling that into every build
so that the minority who scan documents are served would be a poor trade.

So it is invoked as a subprocess when present, and the tool explains how to
install it when absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from pawdf.core._shared import PawdfError

__all__ = [
    "ENV_OVERRIDE",
    "TesseractNotFoundError",
    "available_languages",
    "find_tesseract",
    "install_instructions",
]

ENV_OVERRIDE = "PAWDF_TESSERACT_PATH"

_WINDOWS_FALLBACK_GLOBS = (
    "C:/Program Files/Tesseract-OCR/tesseract.exe",
    "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe",
)

_MACOS_FALLBACKS = (
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
)

_LINUX_PACKAGE_MANAGERS = {
    "dnf": "sudo dnf install tesseract tesseract-langpack-eng",
    "apt": "sudo apt install tesseract-ocr",
    "pacman": "sudo pacman -S tesseract tesseract-data-eng",
    "zypper": "sudo zypper install tesseract-ocr",
    "apk": "sudo apk add tesseract-ocr",
}


class TesseractNotFoundError(PawdfError):
    """Raised when OCR is asked for and Tesseract is not installed."""

    def __init__(self) -> None:
        super().__init__(install_instructions())


def find_tesseract() -> Path | None:
    """Return a path to a usable Tesseract binary, or None.

    Priority: the `PAWDF_TESSERACT_PATH` env var, the system PATH, then the
    default install locations for the platform.
    """
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        path = Path(override)
        if path.is_file():
            return path

    found = shutil.which("tesseract")
    if found:
        return Path(found)

    candidates: tuple[str, ...] = ()
    if sys.platform == "win32":
        candidates = _WINDOWS_FALLBACK_GLOBS
    elif sys.platform == "darwin":
        candidates = _MACOS_FALLBACKS

    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path

    return None


def install_instructions() -> str:
    """What to run to get Tesseract, for the platform this is running on."""
    if sys.platform == "win32":
        return (
            "OCR needs Tesseract, which isn't installed.\n\n"
            "    winget install UB-Mannheim.TesseractOCR\n\n"
            "or download the installer from "
            "https://github.com/UB-Mannheim/tesseract/wiki, then restart Pawdf."
        )
    if sys.platform == "darwin":
        return (
            "OCR needs Tesseract, which isn't installed.\n\n"
            "    brew install tesseract\n\n"
            "then restart Pawdf."
        )

    for manager, command in _LINUX_PACKAGE_MANAGERS.items():
        if shutil.which(manager):
            return (
                "OCR needs Tesseract, which isn't installed.\n\n"
                f"    {command}\n\n"
                "then restart Pawdf."
            )
    return (
        "OCR needs Tesseract, which isn't installed. Install the 'tesseract' "
        "package with your distribution's package manager, along with the "
        "language data you need, then restart Pawdf."
    )


def available_languages() -> list[str]:
    """Language codes Tesseract has training data for.

    Empty when Tesseract is missing, so a UI can offer the list without
    having to check twice.
    """
    binary = find_tesseract()
    if binary is None:
        return []

    try:
        result = subprocess.run(
            [str(binary), "--list-langs"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    # The first line is a header ("List of available languages (5):"), the
    # rest are codes.
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [line for line in lines[1:] if " " not in line]

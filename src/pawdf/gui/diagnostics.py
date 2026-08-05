"""Local logging and privacy-preserving diagnostic bundles for Pawdf."""

from __future__ import annotations

import json
import locale
import logging
import os
import platform
import sys
import tempfile
import traceback as traceback_module
import zipfile
from datetime import UTC, datetime
from importlib import metadata
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from platformdirs import user_log_dir

from pawdf import __version__
from pawdf.core._shared.limits import current_limits

__all__ = [
    "clear_logs",
    "configure_logging",
    "create_diagnostic_bundle",
    "diagnostic_info",
    "install_exception_hook",
    "log_directory",
]


_LOG_NAME = "pawdf.log"
_CONFIGURED = False
_ORIGINAL_EXCEPTHOOK = sys.excepthook
_DEPENDENCIES = (
    "pikepdf",
    "pypdfium2",
    "python-docx",
    "reportlab",
    "Pillow",
    "platformdirs",
    "openpyxl",
    "python-pptx",
    "PySide6",
)


def log_directory() -> Path:
    path = Path(user_log_dir("Pawdf", "pawdf"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_path() -> Path:
    return log_directory() / _LOG_NAME


def configure_logging() -> Path:
    """Configure a small rotating local log and return its path."""

    global _CONFIGURED
    path = _log_path()
    if _CONFIGURED:
        return path

    root = logging.getLogger("pawdf")
    root.setLevel(logging.INFO)
    root.propagate = False
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        root.addHandler(handler)

    _CONFIGURED = True
    root.info("Pawdf %s started on %s", __version__, platform.platform())
    return path


def install_exception_hook() -> None:
    """Log uncaught exceptions before delegating to Python's normal hook."""

    def hook(exc_type: type[BaseException], exc: BaseException, traceback: Any) -> None:
        stack = "".join(traceback_module.format_tb(traceback))
        logging.getLogger("pawdf.crash").critical(
            "Uncaught exception type=%s\n%s",
            exc_type.__name__,
            stack,
        )
        _ORIGINAL_EXCEPTHOOK(exc_type, exc, traceback)

    sys.excepthook = hook


def _versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in _DEPENDENCIES:
        try:
            versions[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[distribution] = "not installed"
    return versions


def diagnostic_info() -> dict[str, Any]:
    """Return system metadata that does not include document names or paths."""

    language, encoding = locale.getlocale()
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "pawdfVersion": __version__,
        "pythonVersion": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "locale": language or "unknown",
        "preferredEncoding": encoding or locale.getpreferredencoding(False),
        "frozen": bool(getattr(sys, "frozen", False)),
        "dependencies": _versions(),
        "resourceLimits": current_limits().as_dict(),
        "environmentOverrides": sorted(key for key in os.environ if key.startswith("PAWDF_")),
    }


def _sanitize(text: str) -> str:
    replacements = {
        str(Path.home()): "<HOME>",
        tempfile.gettempdir(): "<TEMP>",
    }
    for source, replacement in replacements.items():
        if source:
            text = text.replace(source, replacement)
    return text


def _iter_logs() -> list[Path]:
    root = log_directory()
    return sorted(path for path in root.glob(f"{_LOG_NAME}*") if path.is_file())


def create_diagnostic_bundle(output_dir: str | Path) -> Path:
    """Create a ZIP containing metadata and sanitized Pawdf logs only."""

    configure_logging()
    destination_dir = Path(output_dir).expanduser()
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    final = destination_dir / f"pawdf-diagnostics-{stamp}.zip"
    counter = 2
    while final.exists():
        final = destination_dir / f"pawdf-diagnostics-{stamp}-{counter}.zip"
        counter += 1

    temporary = final.with_suffix(".zip.part")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                "diagnostics.json",
                json.dumps(diagnostic_info(), indent=2, sort_keys=True) + "\n",
            )
            archive.writestr(
                "README.txt",
                "This bundle contains Pawdf version/system metadata and sanitized "
                "application logs. It never includes the documents you opened. "
                "Review the files before sharing them.\n",
            )
            for path in _iter_logs():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                archive.writestr(f"logs/{path.name}", _sanitize(content))
        temporary.replace(final)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    logging.getLogger("pawdf.diagnostics").info("Diagnostic bundle created: %s", final.name)
    return final


def clear_logs() -> None:
    """Remove local log files; active handlers reopen the main log as needed."""

    logger = logging.getLogger("pawdf")
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        finally:
            logger.removeHandler(handler)

    for path in _iter_logs():
        path.unlink(missing_ok=True)

    global _CONFIGURED
    _CONFIGURED = False
    configure_logging()

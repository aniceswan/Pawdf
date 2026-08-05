"""Entry point: ``python -m pawdf`` and the ``pawdf`` console script."""

from __future__ import annotations

import importlib
import json
import sys
from importlib import resources

from pawdf import __version__

_MISSING_GUI = """\
Pawdf's desktop UI needs PySide6, which isn't installed.

Qt is not a base dependency on purpose: `pip install pawdf` gives you every
PDF operation in pawdf.core with no GUI dependency in the tree. The window is
opt-in.

    pip install "pawdf[gui]"
"""


def _missing_pyside6(exc: ImportError) -> bool:
    """True only when PySide6 itself could not be found at all.

    A plain `"PySide6" in str(exc)` substring match also catches messages
    like `ImportError: dlopen(.../PySide6/Qt/lib/libQt6QuickWidgets...):
    Library not loaded` - PySide6 *is* installed there, one of its own
    shared libraries just failed to load, which is a packaging defect, not
    a missing dependency. Printing the friendly "not installed" message for
    that case hides the real error instead of surfacing it. A packaged build
    shipped exactly that mix-up once: a pruned Qt library made every
    PySide6 import fail, and every user-facing message said "not installed"
    instead of naming the missing shared library.

    `ModuleNotFoundError.name` is Python's own precise answer to "which
    module could not be found", which is what this needs to check instead.
    """
    return isinstance(exc, ModuleNotFoundError) and (
        exc.name == "PySide6" or (exc.name or "").startswith("PySide6.")
    )


def self_test_info() -> dict[str, object]:
    from pawdf.core import registry

    failures: dict[str, str] = {}
    imported: list[str] = []
    for feature in registry.FEATURES:
        try:
            importlib.import_module(feature.import_path)
        except Exception as exc:  # noqa: BLE001 - diagnostic boundary
            failures[feature.id] = f"{type(exc).__name__}: {exc}"
        else:
            imported.append(feature.id)

    assets = {
        "webIndex": resources.files("pawdf.gui").joinpath("web/index.html").is_file(),
        "webApp": resources.files("pawdf.gui").joinpath("web/app.js").is_file(),
    }
    optional_runtime: dict[str, bool] = {}
    try:
        from pawdf.core.ocr.tesseract import find_tesseract
    except Exception:  # noqa: BLE001 - optional diagnostic
        optional_runtime["tesseract"] = False
    else:
        optional_runtime["tesseract"] = find_tesseract() is not None

    try:
        from pawdf.core.compress.ghostscript import find_ghostscript
    except Exception:  # noqa: BLE001 - optional diagnostic
        optional_runtime["ghostscript"] = False
    else:
        optional_runtime["ghostscript"] = find_ghostscript() is not None

    status = (
        "PASS"
        if (not failures and len(imported) == len(registry.FEATURES) and all(assets.values()))
        else "FAIL"
    )
    return {
        "status": status,
        "pawdfVersion": __version__,
        "featureCount": len(registry.FEATURES),
        "importedFeatures": sorted(imported),
        "failures": failures,
        "assets": assets,
        "optionalRuntime": optional_runtime,
    }


def main() -> int:
    arguments = sys.argv[1:]
    if "--version" in arguments or "-V" in arguments:
        print(__version__)
        return 0
    if "--diagnostics-json" in arguments:
        try:
            from pawdf.gui.diagnostics import diagnostic_info
        except ImportError as exc:  # pragma: no cover - install dependent
            if not _missing_pyside6(exc):
                raise
            print(json.dumps({"pawdfVersion": __version__, "gui": "not installed"}))
        else:
            print(json.dumps(diagnostic_info(), sort_keys=True))
        return 0
    if "--self-test-json" in arguments:
        payload = self_test_info()
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload["status"] == "PASS" else 2

    try:
        from pawdf.gui.app import run_app
    except ImportError as exc:  # pragma: no cover - depends on installation
        if not _missing_pyside6(exc):
            raise
        print(_MISSING_GUI, file=sys.stderr)
        return 1
    return run_app(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

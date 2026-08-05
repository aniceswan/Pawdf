#!/usr/bin/env python3
# Verify Linux shared libraries required by PySide6's xcb platform plugin and
# Qt WebEngine. Run after installing PySide6 and before launching QApplication.

from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

DIRECT_LIBRARIES = (
    "libxcb-cursor.so.0",
    "libxcb-icccm.so.4",
    "libxcb-image.so.0",
    "libxcb-keysyms.so.1",
    "libxcb-randr.so.0",
    "libxcb-render-util.so.0",
    "libxcb-util.so.1",
    "libxcb-xkb.so.1",
    "libxkbcommon-x11.so.0",
)


def load_direct_libraries() -> list[str]:
    failures: list[str] = []
    for name in DIRECT_LIBRARIES:
        try:
            ctypes.CDLL(name)
        except OSError as exc:
            failures.append(f"{name}: {exc}")
        else:
            print(f"LOAD OK: {name}")
    return failures


def shared_objects() -> list[Path]:
    import PySide6.QtWebEngineCore as webengine_core
    from PySide6.QtCore import QLibraryInfo

    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    libraries = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath))

    candidates = [
        plugins / "platforms" / "libqxcb.so",
        Path(webengine_core.__file__).resolve(),
        libraries / "libQt6WebEngineCore.so.6",
    ]
    return [path for path in candidates if path.is_file()]


def inspect_ldd(path: Path) -> list[str]:
    completed = subprocess.run(
        ["ldd", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    print(f"\nLDD: {path}")
    print(output.rstrip())

    failures = [line.strip() for line in output.splitlines() if "not found" in line]
    if completed.returncode:
        failures.append(f"ldd exited {completed.returncode} for {path}")
    return failures


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("Linux Qt runtime check: skipped on non-Linux platform")
        return 0

    failures = load_direct_libraries()
    objects = shared_objects()
    if not objects:
        failures.append("No Qt xcb/WebEngine shared objects were found.")

    for path in objects:
        failures.extend(inspect_ldd(path))

    if failures:
        print("\nLINUX QT RUNTIME: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nLINUX QT RUNTIME: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

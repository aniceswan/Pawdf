# Pawdf override for PyInstaller 6.21 + PySide6 6.11.1 on macOS.
#
# PySide6 6.11.1's QtWebEngineCore.framework/Versions directory contains
# both the actual version ("A") and a "Resources" directory. PyInstaller
# 6.21 sorts every entry and chooses the last one, so it treats "Resources"
# as the framework version and omits QtWebEngineProcess.app.
#
# This hook mirrors PyInstaller's official QtWebEngineCore hook, but selects
# the framework version by locating the directory that contains the actual
# QtWebEngineCore Mach-O binary. Collection still happens during Analysis,
# before COLLECT/BUNDLE processing and code signing.

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller import compat
from PyInstaller.utils import hooks
from PyInstaller.utils.hooks.qt import (
    add_qt6_dependencies,
    pyside6_library_info,
)


def _select_binary_framework_version(framework: Path) -> str:
    versions_root = framework / "Versions"
    candidates = sorted(
        child.name
        for child in versions_root.iterdir()
        if (child.name != "Current" and child.is_dir() and (child / "QtWebEngineCore").is_file())
    )
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected one binary-bearing QtWebEngineCore framework version; "
            f"found {candidates!r} below {versions_root}"
        )
    return candidates[0]


def _collect_macos_webengine_files() -> tuple[list, list]:
    binaries: list = []
    datas: list = []

    rel_data_path = pyside6_library_info.qt_rel_dir
    framework = Path(pyside6_library_info.location["LibrariesPath"]) / "QtWebEngineCore.framework"
    if not framework.is_dir():
        raise RuntimeError(f"QtWebEngineCore.framework is missing: {framework}")

    package_location = Path(pyside6_library_info.package_location).resolve()
    if package_location in framework.resolve().parents:
        destination_framework = os.path.join(
            rel_data_path,
            "lib",
            "QtWebEngineCore.framework",
        )
    else:
        destination_framework = "QtWebEngineCore.framework"

    version = _select_binary_framework_version(framework)

    source_helpers = framework / "Versions" / version / "Helpers"
    if not source_helpers.exists():
        source_helpers = framework / "Helpers"
    if not source_helpers.is_dir():
        raise RuntimeError(f"QtWebEngine framework Helpers directory is missing: {source_helpers}")

    destination_helpers = os.path.join(
        destination_framework,
        "Versions",
        version,
        "Helpers",
    )
    helper_files = hooks.collect_system_data_files(
        str(source_helpers),
        destination_helpers,
    )

    helper_executable = "QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
    for source_name, destination_name in helper_files:
        normalized = source_name.replace("\\", "/")
        if normalized.endswith(helper_executable):
            binaries.append((source_name, destination_name))
        else:
            datas.append((source_name, destination_name))

    source_resources = framework / "Versions" / version / "Resources"
    if not source_resources.exists():
        source_resources = framework / "Resources"
    if not source_resources.is_dir():
        raise RuntimeError(
            f"QtWebEngine framework Resources directory is missing: {source_resources}"
        )

    destination_resources = os.path.join(
        destination_framework,
        "Versions",
        version,
        "Resources",
    )
    datas += hooks.collect_system_data_files(
        str(source_resources),
        destination_resources,
    )
    return binaries, datas


hiddenimports: list[str] = []
binaries: list = []
datas: list = []

if pyside6_library_info.version is not None:
    if pyside6_library_info.version < [6, 2, 2]:
        raise SystemExit("PyInstaller QtWebEngine support requires Qt 6.2.2 or later.")

    hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

    if compat.is_darwin:
        webengine_binaries, webengine_datas = _collect_macos_webengine_files()
    else:
        webengine_binaries, webengine_datas = pyside6_library_info.collect_qtwebengine_files()

    binaries += webengine_binaries
    datas += webengine_datas
    hiddenimports += ["PySide6.QtPrintSupport"]

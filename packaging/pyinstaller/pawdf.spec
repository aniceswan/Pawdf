# -*- mode: python ; coding: utf-8 -*-
"""Size-optimized complete end-user runtime for Pawdf.

Developer dependencies remain complete in ``.[dev]``. This spec removes only
Qt product families, QML packages, translations, locales, and development
metadata that the shipped Widgets + WebEngine application does not use.
"""

import sys
from pathlib import Path

repo_root = Path(SPECPATH).resolve().parent.parent  # noqa: F821
src_dir = repo_root / "src"
icons_dir = repo_root / "packaging" / "icons"
gui_dir = src_dir / "pawdf" / "gui"

datas = [
    (str(gui_dir / "web"), "pawdf/gui/web"),
    (str(gui_dir / "resources"), "pawdf/gui/resources"),
    (str(repo_root / "LICENSE"), "."),
    (str(repo_root / "THIRD-PARTY-NOTICES.md"), "."),
]

hiddenimports = [
    "pawdf.core.split",
    "pawdf.core.merge",
    "pawdf.core.organize",
    "pawdf.core.rotate",
    "pawdf.core.crop",
    "pawdf.core.repair",
    "pawdf.core.ocr",
    "pawdf.core.protect",
    "pawdf.core.stamp",
    "pawdf.core.forms",
    "pawdf.core.annotate",
    "pawdf.core.compress",
    "pawdf.core.rasterize",
    "pawdf.core.imagepdf",
    "pawdf.core.pdf_to_docx",
    "pawdf.core.pdf_to_markdown",
    "pawdf.core.docx_to_pdf",
    "pawdf.core.xlsx_to_pdf",
    "pawdf.core.pptx_to_pdf",
    "pikepdf",
    "pypdfium2",
]

unused_qt_modules = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickTest",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWebView",
]

a = Analysis(  # noqa: F821
    [str(src_dir / "pawdf" / "__main__.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(repo_root / "packaging" / "pyinstaller" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=unused_qt_modules + ["tkinter", "pytest", "ruff", "coverage", "PyInstaller"],
    noarchive=False,
)


_UNUSED_QT_FAMILIES = (
    "qt3d",
    "qtcharts",
    "qtdatavisualization",
    "qtgraphs",
    "qtmultimedia",
    "qtbluetooth",
    "qtdesigner",
    "qtlocation",
    "qtpdf",
    "qtremoteobjects",
    "qtscxml",
    "qtsensors",
    "qtserialport",
    "qtspatialaudio",
    "qtsql",
    "qtstatemachine",
    "qttexttospeech",
    "qtvirtualkeyboard",
    "qtwebview",
    "qtquick3d",
    "qtquickcontrols2",
    "qtquickdialogs2",
    "qtquickeffects",
    "qtquicklayouts",
    "qtquickparticles",
    "qtquickshapes",
    "qtquicktemplates2",
    "qtquicktest",
    "qtquicktimeline",
    "qtquickvectorimage",
    "qtlabs",
    "qtpositioningquick",
    "qtwebchannelquick",
    "qtwebenginequick",
)

_UNUSED_PLUGIN_PATHS = (
    "/plugins/designer/",
    "/plugins/qmltooling/",
    "/plugins/virtualkeyboard/",
    "/plugins/multimedia/",
    "/plugins/canbus/",
    "/plugins/geoservices/",
    "/plugins/sqldrivers/",
)

_UNUSED_DEVELOPMENT_PATHS = (
    "/tests/",
    "/test/",
    "/examples/",
    "/include/",
    "/mkspecs/",
    "/typesystems/",
    "/glue/",
    "/support/",
)

# Bundling libstdc++ on Linux is actively harmful, not merely unnecessary: the
# bundled copy shadows the system's own at runtime, so any *system* library
# the process later dlopen's (a Mesa GL driver, a VA-API decoder, a Vulkan
# ICD reached through the software-rendering fallback) can fail to resolve a
# GLIBCXX symbol newer than whatever glibc the CI runner happened to ship.
# Confirmed against the published v0.2.0 Linux AppImage: it bundled GLIBCXX up
# to 3.4.30 (Ubuntu 22.04's runtime), while the system's own libSPIRV-Tools.so
# (pulled in through llvmpipe/lavapipe software rendering) needed 3.4.32,
# aborting the process before a window ever appeared. Excluding it here lets
# the dynamic linker fall through to the host's own libstdc++, which every
# real Linux desktop already has and which is strictly newer-or-equal to what
# any reasonably current build toolchain requires - GLIBCXX symbol versioning
# is purely additive, so this cannot make an *older* host worse than bundling
# already made it.
_LINUX_SYSTEM_PROVIDED_LIBRARIES = ("libstdc++.so",)


def _normalized_destination(entry):  # noqa: ANN001
    return entry[0].replace("\\", "/").lower()


def _canonical_qt_path(destination):  # noqa: ANN001
    """Normalize versioned Qt6 library names for family matching."""

    return destination.replace("qt6", "qt")


def _is_unused_runtime_path(destination):  # noqa: ANN001
    if sys.platform.startswith("linux"):
        basename = destination.rsplit("/", 1)[-1]
        if any(basename.startswith(name) for name in _LINUX_SYSTEM_PROVIDED_LIBRARIES):
            return True

    canonical = _canonical_qt_path(destination)
    padded = f"/{canonical}/"

    # Qt WebEngine links to QtQml/QtQuick shared libraries internally, so
    # those libraries remain. Pawdf never loads QML application modules or
    # their plugin binaries, therefore the qml directory itself is removable.
    if "/qml/" in padded:
        return True

    # QtQuickWidgets was previously in _UNUSED_QT_FAMILIES on the assumption
    # that "Pawdf never uses QML/Quick" extends to it too. It doesn't:
    # PySide6's QtWebEngineWidgets import chain loads libQt6QuickWidgets at
    # runtime even though application code never touches the module directly.
    # Pruning it produced a build that passed every text-pattern-matching
    # test in this repo but crashed the packaged Linux binary on first launch
    # with `ImportError: libQt6QuickWidgets.so.6: cannot open shared object
    # file`, caught only by actually launching the built binary in CI
    # (scripts/smoke_packaged.py / scripts/verify_installed.py), not by any
    # test that reads this file as text. Do not remove this family again
    # without a build that is actually launched, not just linted.

    if any(family in canonical for family in _UNUSED_QT_FAMILIES):
        return True

    if any(plugin in padded for plugin in _UNUSED_PLUGIN_PATHS):
        return True

    if any(segment in padded for segment in _UNUSED_DEVELOPMENT_PATHS):
        return True

    return False


def _prune_datas(entries):  # noqa: ANN001
    kept = []
    for entry in entries:
        destination = _normalized_destination(entry)
        padded = f"/{destination}/"

        if _is_unused_runtime_path(destination):
            continue

        if "qtwebengine_locales/" in destination and not destination.endswith("en-us.pak"):
            continue

        if "qtwebengine_devtools_resources" in destination:
            continue

        if "/translations/" in padded and destination.endswith(".qm"):
            continue

        kept.append(entry)
    return kept


def _prune_binaries(entries):  # noqa: ANN001
    return [
        entry for entry in entries if not _is_unused_runtime_path(_normalized_destination(entry))
    ]


a.datas = _prune_datas(a.datas)
a.binaries = _prune_binaries(a.binaries)

strip_linux = sys.platform.startswith("linux")

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pawdf",
    debug=False,
    bootloader_ignore_signals=False,
    strip=strip_linux,
    upx=False,
    console=False,
    icon=str(icons_dir / "icon.ico"),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=strip_linux,
    upx=False,
    name="pawdf",
)

if sys.platform == "darwin":
    icns = icons_dir / "icon.icns"
    app = BUNDLE(  # noqa: F821
        coll,
        name="pawdf.app",
        icon=str(icns) if icns.is_file() else str(icons_dir / "icon.png"),
        bundle_identifier="org.pawdf.app",
        info_plist={
            "CFBundleName": "Pawdf",
            "CFBundleDisplayName": "Pawdf",
            "CFBundleVersion": "0.2.1",
            "CFBundleShortVersionString": "0.2.1",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Pawdf contributors",
        },
    )

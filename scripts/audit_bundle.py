#!/usr/bin/env python3
"""Audit Pawdf runtime contents and enforce release-size regressions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FORBIDDEN_FAMILIES = (
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
# QtQuickWidgets is deliberately absent from FORBIDDEN_FAMILIES, matching
# packaging/pyinstaller/pawdf.spec's _UNUSED_QT_FAMILIES: PySide6's
# QtWebEngineWidgets import chain loads libQt6QuickWidgets at runtime, so
# pruning it (as this list once did) crashes the packaged app on launch.
# Keep the two lists in sync - see the comment in pawdf.spec for the
# incident this duplication caused.
FORBIDDEN_SEGMENTS = {"qml", "tests", "test", "pytest", "ruff", "pyinstaller", "__pycache__"}
REQUIRED_BASENAMES = {"index.html", "LICENSE", "THIRD-PARTY-NOTICES.md"}


def canonical_qt_path(value: str) -> str:
    """Normalize Qt6 filenames so family deny-lists match them."""

    return value.replace("qt6", "qt")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--installed-budget-mb", type=float, default=700)
    parser.add_argument("--artifact-budget-mb", type=float, default=250)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.bundle_root.resolve()
    if not root.exists():
        raise RuntimeError(f"Bundle root does not exist: {root}")
    # PyInstaller's COLLECT step aliases several large Qt libraries with a
    # convenience symlink at the top of _internal/ pointing at their real
    # location under _internal/PySide6/Qt/lib/. `Path.is_file()` follows
    # symlinks, so without excluding them here every aliased library (the
    # 195 MiB QtWebEngineCore among them) would be summed twice: once at its
    # real path and once through the symlink pointing at the same bytes.
    # That inflated a real ~458 MiB Linux bundle into a reported ~765 MiB.
    files = sorted(
        (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix().lower(),
    )
    total = sum(path.stat().st_size for path in files)
    forbidden: list[str] = []
    forbidden_bytes = 0
    names = {path.name for path in files}

    for path in files:
        relative = path.relative_to(root).as_posix()
        lowered = relative.lower()
        canonical = canonical_qt_path(lowered)
        segments = {part.lower() for part in path.relative_to(root).parts}
        if segments & FORBIDDEN_SEGMENTS:
            forbidden.append(relative)
            forbidden_bytes += path.stat().st_size
        elif any(family in canonical for family in FORBIDDEN_FAMILIES):
            forbidden.append(relative)
            forbidden_bytes += path.stat().st_size
        elif "qtwebengine_devtools_resources" in lowered:
            forbidden.append(relative)
            forbidden_bytes += path.stat().st_size

    missing = sorted(REQUIRED_BASENAMES - names)
    if not any(path.name.lower() in {"pawdf", "pawdf.exe"} for path in files):
        missing.append("main Pawdf executable")
    if not any("qtwebengineprocess" in path.name.lower() for path in files):
        missing.append("QtWebEngineProcess")

    artifact_size = None
    if args.artifact:
        artifact = args.artifact.resolve()
        if not artifact.is_file():
            raise RuntimeError(f"Release artifact does not exist: {artifact}")
        artifact_size = artifact.stat().st_size

    largest = [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size}
        for path in sorted(files, key=lambda item: item.stat().st_size, reverse=True)[:50]
    ]
    payload = {
        "platform": args.platform,
        "architecture": args.arch,
        "bundleRoot": str(root),
        "installedBytes": total,
        "installedMiB": round(total / (1024 * 1024), 3),
        "installedBudgetMiB": args.installed_budget_mb,
        "artifact": str(args.artifact.resolve()) if args.artifact else None,
        "artifactBytes": artifact_size,
        "artifactMiB": (
            round(artifact_size / (1024 * 1024), 3) if artifact_size is not None else None
        ),
        "artifactBudgetMiB": args.artifact_budget_mb,
        "fileCount": len(files),
        "largestFiles": largest,
        "forbiddenFiles": forbidden,
        "forbiddenBytes": forbidden_bytes,
        "forbiddenMiB": round(forbidden_bytes / (1024 * 1024), 3),
        "missingRequiredFiles": missing,
    }
    report = (
        args.report.resolve()
        if args.report
        else Path("dist") / f"release-size-{args.platform.lower()}-{args.arch}.json"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    errors: list[str] = []
    if forbidden:
        errors.append(f"{len(forbidden)} forbidden runtime files remain")
    if missing:
        errors.append("missing required runtime files: " + ", ".join(missing))
    if total > args.installed_budget_mb * 1024 * 1024:
        errors.append(
            f"installed size {payload['installedMiB']} MiB exceeds {args.installed_budget_mb} MiB"
        )
    if artifact_size is not None and artifact_size > args.artifact_budget_mb * 1024 * 1024:
        errors.append(
            f"artifact size {payload['artifactMiB']} MiB exceeds {args.artifact_budget_mb} MiB"
        )
    print(report)
    print(f"Bundle size: {payload['installedMiB']} MiB across {payload['fileCount']} files")
    if forbidden:
        print(f"Forbidden runtime paths: {len(forbidden)} files, {payload['forbiddenMiB']} MiB")
        for relative in forbidden[:100]:
            print(f"  FORBIDDEN {relative}")
    if errors:
        print("Largest installed files:")
        for item in largest[:25]:
            size_mib = item["bytes"] / (1024 * 1024)
            print(f"  {size_mib:9.3f} MiB  {item['path']}")
        raise RuntimeError("; ".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

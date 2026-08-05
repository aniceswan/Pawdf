#!/usr/bin/env python3
"""Collect redistributable license material beside a Pawdf binary bundle."""

from __future__ import annotations

import argparse
import re
import shutil
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DISTRIBUTIONS = (
    "pikepdf",
    "pypdfium2",
    "python-docx",
    "reportlab",
    "Pillow",
    "platformdirs",
    "openpyxl",
    "python-pptx",
    "lxml",
    "PySide6",
    "PySide6-Addons",
    "PySide6-Essentials",
    "shiboken6",
)
LICENSE_PREFIXES = ("license", "licence", "copying", "notice", "authors")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "package"


def _looks_like_license(relative: Path) -> bool:
    name = relative.name.lower()
    return name.startswith(LICENSE_PREFIXES) or any(
        part.lower() in {"licenses", "license"} for part in relative.parts
    )


def _copy_distribution_licenses(distribution_name: str, destination: Path) -> int:
    try:
        dist = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError:
        return 0

    package_dir = destination / _safe_name(dist.metadata.get("Name", distribution_name))
    copied = 0
    for relative in dist.files or ():
        relative_path = Path(str(relative))
        if not _looks_like_license(relative_path):
            continue
        source = Path(dist.locate_file(relative))
        if not source.is_file():
            continue

        package_dir.mkdir(parents=True, exist_ok=True)
        target = package_dir / _safe_name(relative_path.name)
        counter = 2
        while target.exists() and target.read_bytes() != source.read_bytes():
            target = package_dir / f"{target.stem}-{counter}{target.suffix}"
            counter += 1
        if not target.exists():
            shutil.copy2(source, target)
        copied += 1

    if copied == 0:
        package_dir.mkdir(parents=True, exist_ok=True)
        metadata_text = dist.read_text("METADATA") or ""
        (package_dir / "PACKAGE-METADATA.txt").write_text(metadata_text, encoding="utf-8")
        copied = 1
    return copied


def collect_licenses(bundle: str | Path) -> Path:
    bundle_path = Path(bundle)
    legal = bundle_path / "legal"
    third_party = legal / "third-party"
    third_party.mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "LICENSE", legal / "LICENSE")
    shutil.copy2(REPO_ROOT / "THIRD-PARTY-NOTICES.md", legal / "THIRD-PARTY-NOTICES.md")

    counts = {name: _copy_distribution_licenses(name, third_party) for name in DISTRIBUTIONS}
    summary = [
        "Pawdf legal and third-party license material",
        "",
        "Main notices:",
        "  LICENSE",
        "  THIRD-PARTY-NOTICES.md",
        "",
        "Collected installed distributions:",
    ]
    summary.extend(f"  {name}: {counts[name]} file(s)" for name in DISTRIBUTIONS)
    (legal / "README.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return legal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(collect_licenses(args.bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build Pawdf and place legal notices beside the distributable bundle."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from collect_licenses import collect_licenses

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "packaging" / "pyinstaller" / "pawdf.spec"
DIST_DIR = REPO_ROOT / "dist"


def _bundle_roots() -> list[Path]:
    candidates = [
        DIST_DIR / "pawdf",
        DIST_DIR / "pawdf.app" / "Contents" / "Resources",
    ]
    return [candidate for candidate in candidates if candidate.is_dir()]


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC_PATH),
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(REPO_ROOT / "build"),
            "--noconfirm",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode:
        return result.returncode

    roots = _bundle_roots()
    if not roots:
        print("PyInstaller succeeded but no Pawdf bundle directory was found.", file=sys.stderr)
        return 1

    for root in roots:
        legal = collect_licenses(root)
        required = [
            legal / "LICENSE",
            legal / "THIRD-PARTY-NOTICES.md",
            legal / "README.txt",
        ]
        if not all(path.is_file() for path in required):
            print(f"Legal material is incomplete under {legal}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

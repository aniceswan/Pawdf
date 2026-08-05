#!/usr/bin/env python3
# Verify committed Pawdf icons against a fresh semantic regeneration.
#
# PNG and ICO encoders can produce different byte streams across Pillow/zlib
# builds even when every decoded pixel is identical. This checker compares the
# actual rendered images, not container compression bytes.

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent

ICON_PATHS = (
    "src/pawdf/gui/resources/icons/app_icon.png",
    "src/pawdf/gui/web/img/logo.png",
    "packaging/icons/icon.png",
    "packaging/icons/icon.ico",
    "packaging/icons/hicolor/16x16/apps/pawdf.png",
    "packaging/icons/hicolor/22x22/apps/pawdf.png",
    "packaging/icons/hicolor/24x24/apps/pawdf.png",
    "packaging/icons/hicolor/32x32/apps/pawdf.png",
    "packaging/icons/hicolor/48x48/apps/pawdf.png",
    "packaging/icons/hicolor/64x64/apps/pawdf.png",
    "packaging/icons/hicolor/128x128/apps/pawdf.png",
    "packaging/icons/hicolor/256x256/apps/pawdf.png",
    "packaging/icons/hicolor/512x512/apps/pawdf.png",
)


def _rgba_signature(path: Path) -> tuple[tuple[int, int], bytes]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        return rgba.size, rgba.tobytes()


def _ico_signature(path: Path) -> tuple[tuple[tuple[int, int], bytes], ...]:
    with Image.open(path) as image:
        sizes = sorted(image.ico.sizes())
        return tuple((size, image.ico.getimage(size).convert("RGBA").tobytes()) for size in sizes)


def _signature(path: Path):
    if path.suffix.lower() == ".ico":
        return _ico_signature(path)
    return _rgba_signature(path)


def main() -> int:
    missing_committed = [
        relative for relative in ICON_PATHS if not (REPO_ROOT / relative).is_file()
    ]
    if missing_committed:
        print("Missing committed icons:", file=sys.stderr)
        for relative in missing_committed:
            print(f"  - {relative}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="pawdf-icons-") as raw_temp:
        generated_root = Path(raw_temp)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "generate_icons.py"),
                "--output-root",
                str(generated_root),
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        if completed.returncode:
            return completed.returncode

        mismatches: list[str] = []
        for relative in ICON_PATHS:
            committed = REPO_ROOT / relative
            generated = generated_root / relative

            if not generated.is_file():
                mismatches.append(f"{relative}: generator produced no file")
                continue

            try:
                same = _signature(committed) == _signature(generated)
            except Exception as exc:
                mismatches.append(f"{relative}: comparison failed: {exc}")
                continue

            if not same:
                mismatches.append(f"{relative}: decoded image differs")

        if mismatches:
            print(
                "Committed icons differ semantically from scripts/generate_icons.py output.",
                file=sys.stderr,
            )
            for mismatch in mismatches:
                print(f"  - {mismatch}", file=sys.stderr)
            return 1

    print(f"Verified {len(ICON_PATHS)} generated icon files by decoded pixels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

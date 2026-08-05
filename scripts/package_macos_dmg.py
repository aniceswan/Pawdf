#!/usr/bin/env python3
"""Create the architecture-specific Pawdf macOS DMG."""

from __future__ import annotations

import argparse
import platform
import subprocess
import tempfile
import time
from pathlib import Path

# hdiutil intermittently fails with "Resource busy" when disk arbitration (or
# another process briefly holding the source folder) races the create call.
# Observed directly in a real hosted macOS release build with no code change
# between a passing and a failing run. A short retry absorbs that instead of
# failing an otherwise-successful release for reasons unrelated to Pawdf.
HDIUTIL_CREATE_ATTEMPTS = 3
HDIUTIL_RETRY_DELAY_SECONDS = 5


def architecture() -> str:
    value = platform.machine().lower()
    if value in {"arm64", "aarch64"}:
        return "arm64"
    if value in {"x86_64", "amd64"}:
        return "x86_64"
    raise RuntimeError(f"Unsupported macOS architecture: {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dist = args.dist.resolve()
    app = dist / "pawdf.app"
    if not app.is_dir():
        raise RuntimeError(f"macOS application bundle is missing: {app}")
    output = args.output.resolve() if args.output else dist / f"Pawdf-macOS-{architecture()}.dmg"
    output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="pawdf-dmg-") as raw_temp:
        staging = Path(raw_temp) / "Pawdf"
        staging.mkdir()
        subprocess.run(["ditto", str(app), str(staging / "Pawdf.app")], check=True)
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)

        command = [
            "hdiutil",
            "create",
            "-volname",
            "Pawdf",
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(output),
        ]
        last_error: subprocess.CalledProcessError | None = None
        for attempt in range(1, HDIUTIL_CREATE_ATTEMPTS + 1):
            try:
                subprocess.run(command, check=True)
                last_error = None
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
                if attempt < HDIUTIL_CREATE_ATTEMPTS:
                    print(
                        f"hdiutil create failed (attempt {attempt}/"
                        f"{HDIUTIL_CREATE_ATTEMPTS}), retrying: {exc}"
                    )
                    time.sleep(HDIUTIL_RETRY_DELAY_SECONDS)
        if last_error is not None:
            raise last_error
    if not output.is_file():
        raise RuntimeError(f"DMG was not produced: {output}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

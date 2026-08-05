#!/usr/bin/env python3
"""Package dist/pawdf as a self-contained AppImage release asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import urllib.request
from pathlib import Path

from pawdf import __version__

REPOSITORIES = ("AppImage/appimagetool", "AppImage/AppImageKit")


def machine() -> str:
    value = platform.machine().lower()
    if value in {"x86_64", "amd64"}:
        return "x86_64"
    if value in {"aarch64", "arm64"}:
        return "aarch64"
    raise RuntimeError(f"Unsupported AppImage architecture: {value}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_payload(repository: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/tags/continuous",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Pawdf-release-builder"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_appimagetool(destination: Path, architecture: str) -> Path:
    expected_name = f"appimagetool-{architecture}.AppImage"
    asset = None
    for repository in REPOSITORIES:
        try:
            payload = release_payload(repository)
        except Exception:
            continue
        asset = next(
            (item for item in payload.get("assets", []) if item.get("name") == expected_name),
            None,
        )
        if asset is not None:
            break
    if asset is None:
        raise RuntimeError(f"Could not find {expected_name} in official AppImage releases.")

    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "Pawdf-release-builder"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        destination.write_bytes(response.read())

    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].lower()
        actual = sha256(destination)
        if actual != expected:
            raise RuntimeError(f"appimagetool SHA-256 mismatch: expected {expected}, got {actual}")
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR)
    return destination


def build_appdir(dist: Path, appdir: Path) -> None:
    bundle = dist / "pawdf"
    binary = bundle / "pawdf"
    if not binary.is_file():
        raise RuntimeError(f"PyInstaller bundle is missing: {binary}")
    if appdir.exists():
        shutil.rmtree(appdir)

    runtime = appdir / "usr" / "lib" / "pawdf"
    runtime.parent.mkdir(parents=True)
    shutil.copytree(bundle, runtime, symlinks=True)

    app_run = appdir / "AppRun"
    app_run.write_text(
        "#!/usr/bin/env bash\n"
        "set -e\n"
        'HERE="$(cd "$(dirname "$0")" && pwd)"\n'
        'exec "$HERE/usr/lib/pawdf/pawdf" "$@"\n',
        encoding="utf-8",
    )
    app_run.chmod(0o755)

    desktop = appdir / "pawdf.desktop"
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=Pawdf\nComment=Offline PDF tools\n"
        "Exec=pawdf %F\nIcon=pawdf\nTerminal=false\nCategories=Office;Utility;\n"
        "StartupWMClass=pawdf\nMimeType=application/pdf;\n",
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parent.parent
    icon_source = repo_root / "packaging" / "icons" / "icon.png"
    icon_destination = appdir / "pawdf.png"
    shutil.copy2(icon_source, icon_destination)

    applications = appdir / "usr" / "share" / "applications"
    icons = appdir / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    applications.mkdir(parents=True)
    icons.mkdir(parents=True)
    shutil.copy2(desktop, applications / "pawdf.desktop")
    shutil.copy2(icon_destination, icons / "pawdf.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    architecture = machine()
    dist = args.dist.resolve()
    appdir = dist / "Pawdf.AppDir"
    output = args.output.resolve() if args.output else dist / f"Pawdf-Linux-{architecture}.AppImage"
    build_appdir(dist, appdir)

    cache = Path("build").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    tool = download_appimagetool(cache / f"appimagetool-{architecture}.AppImage", architecture)

    environment = os.environ.copy()
    environment.update(
        {
            "ARCH": architecture,
            "VERSION": __version__,
            "APPIMAGE_EXTRACT_AND_RUN": "1",
        }
    )
    completed = subprocess.run(
        [
            str(tool),
            str(appdir),
            str(output),
        ],
        env=environment,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"appimagetool exited with {completed.returncode}")
    if not output.is_file():
        raise RuntimeError(f"AppImage was not produced: {output}")
    output.chmod(output.stat().st_mode | 0o111)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

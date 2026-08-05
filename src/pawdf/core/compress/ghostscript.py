"""Locate Ghostscript and securely install the pinned Windows release."""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from pawdf.core._shared import PawdfError

__all__ = [
    "ENV_OVERRIDE",
    "GhostscriptSetupError",
    "find_ghostscript",
    "instructions_linux",
    "instructions_macos",
    "run_setup",
    "vendor_install_dir",
]

ENV_OVERRIDE = "PAWDF_GS_PATH"
APP_NAME = "pawdf"

GS_RELEASE_TAG = "gs10071"
GS_VERSION = "10.07.1"
WINDOWS_INSTALLER_URL = (
    "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/"
    f"{GS_RELEASE_TAG}/{GS_RELEASE_TAG}w64.exe"
)
WINDOWS_INSTALLER_SHA256 = "3a4c28d0aac47aa7cccd35a5932c55110376e9dbd966898dde388b7faba444a4"
DOWNLOAD_TIMEOUT_SECONDS = 90

_WINDOWS_SYSTEM_NAMES = ("gswin64c", "gswin32c")
_WINDOWS_FALLBACK_GLOBS = (
    "C:/Program Files/gs/gs*/bin/gswin64c.exe",
    "C:/Program Files (x86)/gs/gs*/bin/gswin32c.exe",
)
_LINUX_PACKAGE_MANAGERS = {
    "dnf": "sudo dnf install ghostscript",
    "apt": "sudo apt install ghostscript",
    "pacman": "sudo pacman -S ghostscript",
    "zypper": "sudo zypper install ghostscript",
    "apk": "sudo apk add ghostscript",
    "xbps-install": "sudo xbps-install ghostscript",
}


class GhostscriptSetupError(PawdfError):
    """Raised when an attempt to install Ghostscript fails."""


def _vendor_dir() -> Path:
    from platformdirs import user_data_dir

    return Path(user_data_dir(APP_NAME)) / "vendor" / "ghostscript"


def _vendored_binary() -> Path | None:
    vendor_dir = _vendor_dir()
    if not vendor_dir.is_dir():
        return None

    if sys.platform == "win32":
        candidates = list(vendor_dir.glob("**/gswin64c.exe")) + list(
            vendor_dir.glob("**/gswin32c.exe")
        )
    else:
        candidates = list(vendor_dir.glob("**/bin/gs")) + list(vendor_dir.glob("**/gs"))

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _system_binary() -> Path | None:
    names = _WINDOWS_SYSTEM_NAMES if sys.platform == "win32" else ("gs",)
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def _known_fallback_paths() -> Path | None:
    if sys.platform != "win32":
        return None
    for pattern in _WINDOWS_FALLBACK_GLOBS:
        drive, _, rest = pattern.partition(":/")
        matches = sorted(Path(f"{drive}:/").glob(rest))
        if matches:
            return matches[-1]
    return None


def find_ghostscript() -> Path | None:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        path = Path(override)
        if path.is_file():
            return path

    for finder in (_vendored_binary, _system_binary, _known_fallback_paths):
        found = finder()
        if found is not None:
            return found
    return None


def vendor_install_dir() -> Path:
    directory = _vendor_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def instructions_linux() -> str:
    for manager, command in _LINUX_PACKAGE_MANAGERS.items():
        if shutil.which(manager):
            return (
                "Artifex does not publish a portable Linux Ghostscript binary. "
                f"Install it with your package manager:\n\n    {command}\n\n"
                "then restart Pawdf."
            )
    return "Install Ghostscript with your distribution package manager, then restart Pawdf."


def instructions_macos() -> str:
    return (
        "Install Ghostscript with Homebrew:\n\n    brew install ghostscript\n\n"
        "or with MacPorts, then restart Pawdf."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_installer(path: Path) -> None:
    actual = _sha256(path)
    if not hmac.compare_digest(actual.lower(), WINDOWS_INSTALLER_SHA256.lower()):
        path.unlink(missing_ok=True)
        raise GhostscriptSetupError(
            "Ghostscript download failed SHA-256 verification. "
            f"Expected {WINDOWS_INSTALLER_SHA256}, received {actual}. "
            "The installer was deleted and was not executed."
        )


def _download_installer(destination: Path) -> None:
    request = urllib.request.Request(
        WINDOWS_INSTALLER_URL,
        headers={"User-Agent": f"Pawdf/{GS_VERSION}"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - pinned HTTPS URL and verified hash
            request,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            final_url = response.geturl()
            if not final_url.lower().startswith("https://"):
                raise GhostscriptSetupError(
                    f"Ghostscript download redirected to a non-HTTPS URL: {final_url}"
                )
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError) as exc:
        destination.unlink(missing_ok=True)
        raise GhostscriptSetupError(f"Could not download Ghostscript: {exc}") from exc

    _verify_installer(destination)


def setup_windows() -> Path:
    """Download, verify, then silently run the pinned official installer."""
    dest = vendor_install_dir()
    with tempfile.TemporaryDirectory(prefix="pawdf-ghostscript-") as tmp:
        installer_path = Path(tmp) / "gs-installer.exe"
        _download_installer(installer_path)
        try:
            subprocess.run(
                [str(installer_path), "/VERYSILENT", f"/DIR={dest}"],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise GhostscriptSetupError(f"Ghostscript installer failed: {exc}") from exc

    binary = next(dest.glob("**/gswin64c.exe"), None) or next(dest.glob("**/gswin32c.exe"), None)
    if binary is None:
        raise GhostscriptSetupError(
            f"Installed but could not find a Ghostscript console binary under {dest}"
        )
    return binary


def run_setup() -> Path | str:
    existing = find_ghostscript()
    if existing is not None:
        return existing
    if sys.platform == "win32":
        return setup_windows()
    if sys.platform == "darwin":
        return instructions_macos()
    if sys.platform.startswith("linux"):
        return instructions_linux()
    raise GhostscriptSetupError(f"Unsupported platform: {sys.platform}")

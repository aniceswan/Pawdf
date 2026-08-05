#!/usr/bin/env python3
"""Cross-platform metadata and feature smoke for packaged Pawdf."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pawdf import __version__

#: How long the packaged GUI has to stay alive to count as a real launch,
#: not just a fast crash during Qt/QtWebEngine startup. --version and
#: --diagnostics-json only exercise the CLI path and exit before QApplication
#: is ever constructed, so they cannot catch a packaging defect that only
#: breaks the actual window (a stale bundled shared library, a missing Qt
#: plugin, a WebEngine renderer that cannot start). This check launches the
#: real binary with no arguments and confirms it is still running afterward.
GUI_LIVENESS_SECONDS = 6


def find_executable(dist: Path) -> Path:
    if sys.platform == "darwin":
        candidates = (
            dist / "pawdf.app" / "Contents" / "MacOS" / "pawdf",
            dist / "pawdf" / "pawdf",
        )
    elif sys.platform == "win32":
        candidates = (dist / "pawdf" / "pawdf.exe",)
    else:
        candidates = (dist / "pawdf" / "pawdf",)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"No packaged Pawdf executable found below {dist}")


def capture(binary: Path, argument: str) -> str:
    environment = os.environ.copy()
    if binary.suffix.lower() == ".appimage":
        environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    completed = subprocess.run(
        [str(binary), argument],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=90,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode:
        raise RuntimeError(
            f"{binary.name} {argument} exited {completed.returncode}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    if not stdout:
        raise RuntimeError(f"{binary.name} {argument} returned no stdout.\nstderr:\n{stderr}")
    return stdout


def gui_liveness(binary: Path, seconds: int = GUI_LIVENESS_SECONDS) -> dict[str, object]:
    """Launch the real window and confirm it survives past Qt/WebEngine startup.

    Every other check here runs a CLI flag and exits before QApplication is
    ever constructed, so none of them can catch a defect that only breaks the
    actual GUI process (see the module docstring on GUI_LIVENESS_SECONDS).
    """
    environment = os.environ.copy()
    if binary.suffix.lower() == ".appimage":
        environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"

    popen_kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(
        [str(binary)],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        **popen_kwargs,
    )
    started = time.monotonic()
    time.sleep(seconds)
    early_exit = process.poll()
    if early_exit is not None:
        output = process.stdout.read() if process.stdout else ""
        raise RuntimeError(
            f"{binary.name} exited after {time.monotonic() - started:.1f}s "
            f"(code {early_exit}) instead of staying open as a running "
            f"window:\n{output[-4000:]}"
        )

    try:
        if sys.platform == "win32":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        output, _ = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate(timeout=5)

    return {"aliveSeconds": seconds, "output": (output or "")[-2000:]}


def smoke(binary: Path) -> dict[str, object]:
    version = capture(binary, "--version")
    if version != __version__:
        raise RuntimeError(f"Version mismatch: executable={version!r}, package={__version__!r}")
    diagnostics = json.loads(capture(binary, "--diagnostics-json"))
    if diagnostics.get("pawdfVersion") != __version__:
        raise RuntimeError("Packaged diagnostics did not report the expected Pawdf version.")
    self_test = json.loads(capture(binary, "--self-test-json"))
    if self_test.get("status") != "PASS" or self_test.get("featureCount") != 22:
        raise RuntimeError(f"Packaged self-test failed: {self_test}")
    liveness = gui_liveness(binary)
    return {
        "binary": str(binary),
        "version": version,
        "diagnostics": diagnostics,
        "selfTest": self_test,
        "guiLiveness": liveness,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args()
    binary = args.executable.resolve() if args.executable else find_executable(args.dist.resolve())
    print(json.dumps(smoke(binary), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

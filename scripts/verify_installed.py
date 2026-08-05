#!/usr/bin/env python3
"""Verify an installed Pawdf executable, including all feature imports."""

from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import time
from pathlib import Path


def environment_for(binary: Path) -> dict[str, str]:
    environment = os.environ.copy()
    if binary.suffix.lower() == ".appimage":
        environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    return environment


def capture(binary: Path, argument: str) -> str:
    completed = subprocess.run(
        [str(binary), argument],
        env=environment_for(binary),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=90,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode:
        raise RuntimeError(
            f"{binary} {argument} exited {completed.returncode}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return stdout


def liveness(binary: Path, seconds: int) -> dict:
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [str(binary)],
        env=environment_for(binary),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        **kwargs,
    )
    time.sleep(seconds)
    early_code = process.poll()
    if early_code is not None:
        output = process.stdout.read() if process.stdout else ""
        raise RuntimeError(f"Installed GUI exited early with code {early_code}\n{output}")
    if os.name == "nt":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        output, _ = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate(timeout=5)
    return {"seconds": seconds, "output": (output or "")[-4000:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--liveness-seconds", type=int, default=7)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        raise RuntimeError(f"Installed binary does not exist: {binary}")
    version = capture(binary, "--version")
    diagnostics = json.loads(capture(binary, "--diagnostics-json"))
    self_test = json.loads(capture(binary, "--self-test-json"))
    if self_test.get("status") != "PASS" or self_test.get("featureCount") != 22:
        raise RuntimeError(f"Installed self-test failed: {self_test}")
    payload = {
        "status": "PASS",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "binary": str(binary),
        "version": version,
        "diagnostics": diagnostics,
        "selfTest": self_test,
        "liveness": liveness(binary, args.liveness_seconds),
    }
    output = json.dumps(payload, indent=2) + "\n"
    if args.report:
        args.report.resolve().write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

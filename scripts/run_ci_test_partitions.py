#!/usr/bin/env python3
"""Run Pawdf CI tests without letting Qt WebEngine poison the whole suite."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def child_environment(*, gui: bool) -> dict[str, str]:
    env = os.environ.copy()
    local_src = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = local_src if not existing else local_src + os.pathsep + existing
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    if gui:
        env["PYTEST_QT_API"] = "pyside6"
        env.setdefault("QT_OPENGL", "software")
        env.setdefault("QT_QUICK_BACKEND", "software")
        env.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
        env.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            (
                "--no-sandbox --disable-gpu --disable-gpu-compositing "
                "--disable-features=Vulkan --disable-dev-shm-usage"
            ),
        )
    return env


def start_process(
    command: list[str],
    *,
    env: dict[str, str],
) -> subprocess.Popen:
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    print("$ " + " ".join(command), flush=True)
    return subprocess.Popen(command, cwd=ROOT, env=env, **kwargs)


def terminate_tree(process: subprocess.Popen, *, force: bool) -> None:
    if os.name == "nt":
        command = ["taskkill", "/PID", str(process.pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(
            process.pid,
            signal.SIGKILL if force else signal.SIGTERM,
        )
    except ProcessLookupError:
        pass


def run_with_timeout(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: int,
    clean_process_group: bool,
) -> None:
    process = start_process(command, env=env)
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        print(
            f"\nTIMEOUT after {timeout}s: {' '.join(command)}",
            file=sys.stderr,
            flush=True,
        )
        terminate_tree(process, force=True)
        process.wait(timeout=15)
        raise RuntimeError("Test subprocess timed out.") from exc
    finally:
        if clean_process_group and os.name != "nt":
            terminate_tree(process, force=False)

    if returncode:
        raise RuntimeError(f"Test subprocess exited {returncode}: {' '.join(command)}")


def non_gui_paths() -> list[str]:
    paths = [str(TESTS / "core")]
    paths.extend(str(path) for path in sorted(TESTS.glob("test_*.py")))
    return paths


def run_non_gui(timeout: int) -> None:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *non_gui_paths(),
        "-q",
        "--maxfail=1",
    ]
    run_with_timeout(
        command,
        env=child_environment(gui=False),
        timeout=timeout,
        clean_process_group=False,
    )
    print("NON-GUI TEST PARTITION: PASS")


def collect_gui_nodes(match: str | None) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "pytestqt.plugin",
        str(TESTS / "gui"),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=child_environment(gui=True),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("GUI test collection failed:\n" + completed.stdout + completed.stderr)

    nodes = [
        line.strip()
        for line in completed.stdout.splitlines()
        if "::" in line and line.strip().startswith("tests/")
    ]
    if match:
        nodes = [node for node in nodes if match in node]
    if not nodes:
        raise RuntimeError(
            "GUI collection produced no matching test node IDs.\n" + completed.stdout
        )
    return nodes


def run_gui(timeout: int, match: str | None) -> None:
    nodes = collect_gui_nodes(match)
    print(f"Collected {len(nodes)} isolated GUI test node(s).", flush=True)

    for index, node in enumerate(nodes, start=1):
        print(f"\n[{index}/{len(nodes)}] {node}", flush=True)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_single_qt_test.py"),
            node,
        ]
        run_with_timeout(
            command,
            env=child_environment(gui=True),
            timeout=timeout,
            clean_process_group=True,
        )

    print(f"GUI TEST PARTITION: PASS ({len(nodes)} isolated nodes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("non-gui", "gui"))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--match")
    args = parser.parse_args()

    if args.timeout < 10:
        parser.error("--timeout must be at least 10 seconds")

    if args.mode == "non-gui":
        run_non_gui(args.timeout)
    else:
        run_gui(args.timeout, args.match)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

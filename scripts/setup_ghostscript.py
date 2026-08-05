#!/usr/bin/env python3
"""CLI entry point for Ghostscript setup.

A thin wrapper around `pawdf.core.compress.ghostscript` so the same tested
logic backs both this script and the app's Settings panel.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pawdf.core.compress.ghostscript import run_setup  # noqa: E402


def main() -> int:
    result = run_setup()
    if isinstance(result, str):
        # Nothing could be installed automatically; `result` explains what the
        # user needs to run. Non-zero, because setup did not complete.
        print(result)
        return 1
    print(f"Ghostscript is available at {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

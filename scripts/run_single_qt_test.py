#!/usr/bin/env python3
"""Run exactly one Qt test and exit on its call-phase result.

Qt WebEngine can hang or crash during fixture/interpreter teardown even after
the test body has passed. Each invocation runs one collected node in its own
process group, so after setup and the test call finish there is no useful
state left to preserve. Genuine setup/call failures still return non-zero.
"""

from __future__ import annotations

import argparse
import os
import sys

import pytest


class CallPhaseExit:
    @pytest.hookimpl(trylast=True)
    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "setup":
            if report.failed:
                self._finish(1)
            if report.skipped:
                self._finish(0)
            return

        if report.when != "call":
            return

        if report.passed or report.skipped:
            self._finish(0)
        self._finish(1)

    @staticmethod
    def _finish(exit_code: int) -> None:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("node_id")
    args = parser.parse_args()

    # CallPhaseExit normally terminates the worker. Returning from pytest.main
    # means collection failed or no setup/call report was produced.
    exit_code = int(
        pytest.main(
            [
                "-q",
                "-p",
                "pytestqt.plugin",
                args.node_id,
                "--maxfail=1",
            ],
            plugins=[CallPhaseExit()],
        )
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()

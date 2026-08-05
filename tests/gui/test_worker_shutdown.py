"""Lifecycle tests for conversions running during window shutdown."""

from __future__ import annotations

import time

from pawdf.gui.workers import JobRunner


def test_wait_all_never_cancels_a_worker_mid_write(qtbot, tmp_path):
    output = tmp_path / "finished.txt"
    runner = JobRunner()

    def write_slowly():
        time.sleep(0.12)
        output.write_text("complete", encoding="utf-8")

    runner.start(write_slowly)

    assert runner.wait_all(5) is False
    assert not output.exists()

    assert runner.wait_all(-1) is True
    assert output.read_text(encoding="utf-8") == "complete"
    assert len(runner) == 0


def test_worker_thread_can_exit_while_gui_thread_is_waiting(qtbot):
    runner = JobRunner()
    runner.start(lambda: time.sleep(0.02))

    assert runner.wait_all(-1) is True
    assert runner.active == 0


def test_job_runner_reports_start_and_finish(qtbot):
    counts: list[int] = []
    runner = JobRunner(on_change=counts.append)
    runner.start(lambda: time.sleep(0.03))

    qtbot.waitUntil(lambda: counts and counts[-1] == 0, timeout=2000)
    assert any(count >= 1 for count in counts)
    assert counts[-1] == 0

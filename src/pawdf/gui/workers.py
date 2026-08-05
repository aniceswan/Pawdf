"""Run core functions off the Qt main thread without unsafe teardown."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

__all__ = ["Job", "JobRunner", "Worker"]


class Worker(QObject):
    """Call one function, report its result, and exit its own thread."""

    finished = Signal(object)
    failed = Signal(Exception)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced through a signal
            self.failed.emit(exc)
        else:
            self.finished.emit(result)
        finally:
            # Quit from inside the worker thread. A GUI-thread wait during
            # close can otherwise prevent a queued finished -> quit slot from
            # running, leaving the thread alive while the window is destroyed.
            QThread.currentThread().quit()


class Job:
    __slots__ = ("thread", "worker")

    def __init__(self, thread: QThread, worker: Worker):
        self.thread = thread
        self.worker = worker


class JobRunner:
    """Own background jobs until their threads have actually stopped."""

    def __init__(self, on_change: Callable[[int], None] | None = None) -> None:
        self._jobs: set[Job] = set()
        self._on_change = on_change

    def __len__(self) -> int:
        return self.total

    @property
    def active(self) -> int:
        active = 0
        for job in list(self._jobs):
            try:
                active += int(job.thread.isRunning())
            except RuntimeError:
                self._jobs.discard(job)
        return active

    @property
    def total(self) -> int:
        for job in list(self._jobs):
            try:
                job.thread.isRunning()
            except RuntimeError:
                self._jobs.discard(job)
        return len(self._jobs)

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change(self.total)

    def _discard(self, job: Job) -> None:
        self._jobs.discard(job)
        self._notify()

    def start(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_finished: Callable[[Any], None] | None = None,
        on_failed: Callable[[Exception], None] | None = None,
        **kwargs: Any,
    ) -> Job:
        thread = QThread()
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)
        job = Job(thread, worker)
        self._jobs.add(job)

        thread.started.connect(worker.run)
        if on_finished is not None:
            worker.finished.connect(on_finished)
        if on_failed is not None:
            worker.failed.connect(on_failed)

        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._discard(job))

        thread.start()
        self._notify()
        return job

    def wait_all(self, msecs: int = -1) -> bool:
        """Wait for work without requesting cancellation.

        ``msecs < 0`` waits without a deadline. A finite timeout returns False
        if any job is still running; it never calls ``quit()`` on a worker that
        may be halfway through writing an output file.
        """

        completed = True
        for job in list(self._jobs):
            thread = job.thread
            try:
                if thread.isRunning():
                    stopped = thread.wait() if msecs < 0 else thread.wait(msecs)
                    completed = completed and stopped
                if not thread.isRunning():
                    self._jobs.discard(job)
            except RuntimeError:
                self._jobs.discard(job)

        self._notify()
        return completed and self.active == 0

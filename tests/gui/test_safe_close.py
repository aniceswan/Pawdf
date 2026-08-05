from __future__ import annotations

import time

from PySide6.QtWidgets import QMessageBox

from pawdf.gui.shell import MainWindow


def test_window_defers_close_until_active_write_finishes(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.bridge._jobs.start(lambda: time.sleep(0.08))
    qtbot.waitUntil(lambda: window.bridge.active_jobs == 1, timeout=1000)

    window.close()
    assert window.isVisible()

    qtbot.waitUntil(lambda: not window.isVisible(), timeout=3000)
    assert window.bridge.active_jobs == 0

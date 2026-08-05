"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pawdf.gui.diagnostics import configure_logging, install_exception_hook
from pawdf.gui.resources import APP_ICON_PATH
from pawdf.gui.shell import MainWindow

__all__ = ["run_app"]

APP_USER_MODEL_ID = "org.pawdf.Pawdf"


def _claim_windows_taskbar_identity() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def run_app(argv: list[str] | None = None) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    configure_logging()
    install_exception_hook()
    _claim_windows_taskbar_identity()

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Pawdf")
    app.setApplicationDisplayName("Pawdf")
    app.setOrganizationName("pawdf")
    app.setDesktopFileName("pawdf")
    if APP_ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    window.show()
    exit_code = app.exec()
    logging.getLogger("pawdf").info("Pawdf stopped exit_code=%s", exit_code)
    return exit_code

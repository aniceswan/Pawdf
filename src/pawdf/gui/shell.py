"""The native Pawdf window and the plumbing around the local HTML UI."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QIcon, QKeyEvent, QShowEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QMessageBox, QWidget

from pawdf.gui.bridge import Bridge
from pawdf.gui.dnd import FileDropFilter
from pawdf.gui.resources import APP_ICON_PATH, INDEX_HTML

__all__ = ["MainWindow"]

WINDOW_TITLE = "Pawdf"
DEFAULT_SIZE = (1240, 820)
MINIMUM_SIZE = (860, 600)

_DISABLED_WEB_SETTINGS = (
    QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
    QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(*MINIMUM_SIZE)
        self._settings = QSettings("pawdf", "Pawdf")
        self._drop_target: QWidget | None = None
        self._close_pending = False
        if APP_ICON_PATH.is_file():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        settings = self.view.settings()
        for attribute in _DISABLED_WEB_SETTINGS:
            settings.setAttribute(attribute, False)

        self.bridge = Bridge(self)
        self.bridge.allJobsFinished.connect(self._finish_deferred_close)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.view.load(QUrl.fromLocalFile(str(INDEX_HTML)))

        self.drop_filter = FileDropFilter(
            on_files=self.bridge.handle_dropped_files,
            on_drag_state=self.bridge.handle_drag_state,
            parent=self,
        )
        self._restore_geometry()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if getattr(self, "_drop_target", None) is None:
            self.install_drop_filter()

    def install_drop_filter(self) -> bool:
        target = self.view.focusProxy()
        if target is None:
            return False

        target.setAcceptDrops(True)
        target.installEventFilter(self.drop_filter)
        self._drop_target = target
        return True

    def _restore_geometry(self) -> None:
        saved = self._settings.value("geometry")
        if saved is not None and self.restoreGeometry(saved):
            if self._settings.value("maximized", False, type=bool):
                self.showMaximized()
            return
        self.resize(*DEFAULT_SIZE)

    def _save_geometry(self) -> None:
        self._settings.setValue("maximized", self.isMaximized())
        if not self.isMaximized() and not self.isFullScreen():
            self._settings.setValue("geometry", self.saveGeometry())

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(event)

    def _finish_deferred_close(self) -> None:
        if not self._close_pending:
            return
        self._close_pending = False
        QTimer.singleShot(0, self.close)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_geometry()
        active = self.bridge.active_jobs
        if active:
            event.ignore()
            if not self._close_pending:
                self._close_pending = True
                QMessageBox.information(
                    self,
                    "Finishing work",
                    (
                        f"Pawdf is finishing {active} active "
                        f"{'job' if active == 1 else 'jobs'} safely. "
                        "The window will close automatically when every output "
                        "has finished writing."
                    ),
                )
            return
        super().closeEvent(event)

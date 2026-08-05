"""Native drag-and-drop, because the web layer genuinely cannot do this.

A dropped `File` object in the browser exposes `name`, `size`, `type` and
`lastModified` - and no path. `File.path` is a property Electron adds by
patching Blink; standard Chromium, which is what QtWebEngine embeds,
deliberately withholds filesystem paths from page content. So JavaScript can
see *that* a PDF was dropped and never *where* it is.

Qt, one layer below, gets the real `file://` URLs. This module catches the
drag at that level and hands the paths to the page, which keeps the whole
"JS never touches the filesystem" boundary intact: the page still receives
only paths that the user explicitly dropped or picked.

The page must still `preventDefault()` its own dragover/drop events. Without
that, Chromium treats a dropped PDF as a navigation and replaces the entire
UI with the document.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent

__all__ = ["FileDropFilter"]

_DRAG_EVENTS = (
    QEvent.Type.DragEnter,
    QEvent.Type.DragMove,
    QEvent.Type.DragLeave,
    QEvent.Type.Drop,
)


class FileDropFilter(QObject):
    """Event filter that turns file drags into path callbacks.

    Installed on the web view's focus proxy, not on the view and not on the
    QApplication. The widget that actually receives drag events is a private
    render-widget child which QWebEngineView creates lazily, so filtering the
    view itself catches nothing - and filtering the whole application means
    inspecting every event the app ever delivers, which is needless work on a
    very hot path.
    """

    def __init__(
        self,
        on_files: Callable[[list[str]], None],
        on_drag_state: Callable[[bool], None] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._on_files = on_files
        self._on_drag_state = on_drag_state or (lambda _active: None)
        self._dragging = False

    @staticmethod
    def _local_paths(mime) -> list[str]:  # noqa: ANN001 - QMimeData
        if not mime.hasUrls():
            return []
        paths = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local and Path(local).is_file():
                paths.append(local)
        return paths

    def _set_dragging(self, active: bool) -> None:
        if active != self._dragging:
            self._dragging = active
            self._on_drag_state(active)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Returning False rather than delegating to QObject.eventFilter is
        # deliberate: this filter is installed on a widget that sees a very
        # high volume of events, and crossing back into C++ for every one of
        # them is both wasteful and, in practice, unstable during teardown.
        event_type = event.type()
        if event_type not in _DRAG_EVENTS:
            return False

        if event_type == QEvent.Type.DragLeave:
            assert isinstance(event, QDragLeaveEvent)
            self._set_dragging(False)
            return False

        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            assert isinstance(event, QDragEnterEvent | QDragMoveEvent)
            if self._local_paths(event.mimeData()):
                self._set_dragging(True)
                event.acceptProposedAction()
                return True
            return False

        assert isinstance(event, QDropEvent)
        paths = self._local_paths(event.mimeData())
        self._set_dragging(False)
        if not paths:
            return False

        event.acceptProposedAction()
        self._on_files(paths)
        # Swallow the event so Chromium never sees it and never tries to
        # navigate the view to the dropped file.
        return True


def filter_by_extension(paths: Iterable[str], extensions: Iterable[str]) -> list[str]:
    """Keep only the paths whose suffix is in `extensions` (case-insensitive)."""
    wanted = {e.lower() for e in extensions}
    return [p for p in paths if Path(p).suffix.lower() in wanted]

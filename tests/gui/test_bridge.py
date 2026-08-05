"""Tests for the Python half of the UI.

The page itself isn't driven here, but everything it depends on is: the slots
it calls, the signals it listens for, and the drag-and-drop path that
JavaScript cannot implement on its own.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture
def bridge(qtbot, tmp_path, monkeypatch):
    """A bridge whose results land in tmp_path rather than in the real
    Downloads folder, which the tests would otherwise fill with artefacts.
    """
    from pawdf.gui.bridge import OUTPUT_DIR_ENV, Bridge

    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path / "out"))
    instance = Bridge(None)
    yield instance
    instance.shutdown()


# --------------------------------------------------------------- metadata --


def test_features_are_served_from_the_registry(bridge):
    from pawdf.core import registry

    served = json.loads(bridge.features())

    assert [c["id"] for c in served["categories"]] == [c.id for c in registry.CATEGORIES]
    assert [f["id"] for f in served["features"]] == [f.id for f in registry.FEATURES]

    # The page needs these to build both rings and to validate dropped files.
    for entry in served["features"]:
        assert entry["title"] and entry["tagline"]
        assert isinstance(entry["accepts"], list)
        assert entry["category"] in {c["id"] for c in served["categories"]}


def test_served_features_carry_a_resolved_hue(bridge):
    """Tools inherit their category's colour unless they override it. The page
    should never have to know that rule, so the bridge resolves it.
    """
    served = json.loads(bridge.features())
    by_category = {c["id"]: c["hue"] for c in served["categories"]}

    for entry in served["features"]:
        assert isinstance(entry["hue"], int)
        assert entry["hue"] == by_category[entry["category"]]


def test_app_info_reports_the_version(bridge):
    from pawdf import __version__

    assert json.loads(bridge.appInfo())["version"] == __version__


# ------------------------------------------------------------ page counts --


def test_page_count(bridge, sample_pdf: Path):
    assert bridge.pageCount(str(sample_pdf)) == 5


def test_page_count_returns_zero_rather_than_raising(bridge, tmp_path: Path):
    """A slot that raises gives JavaScript no reply at all, so unreadable
    input has to come back as a value the page can act on.
    """
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    assert bridge.pageCount(str(bad)) == 0
    assert bridge.pageCount(str(tmp_path / "missing.pdf")) == 0


def test_page_count_on_encrypted_pdf_returns_zero(bridge, encrypted_pdf: Path):
    assert bridge.pageCount(str(encrypted_pdf)) == 0


# ------------------------------------------------------------ thumbnails --


def test_thumbnail_reply_carries_its_page_index(bridge, qtbot, sample_pdf: Path):
    """Replies are matched to slots by index, not by arrival order - the page
    grid would otherwise mislabel pages if a reply ever overtook another.
    """
    with qtbot.waitSignal(bridge.thumbnailReady, timeout=15_000) as blocker:
        bridge.requestThumbnail(str(sample_pdf), 3)

    payload = json.loads(blocker.args[0])
    assert payload["index"] == 3
    assert payload["dataUrl"].startswith("data:image/png;base64,")
    assert payload["error"] == ""


def test_failed_thumbnail_still_replies(bridge, qtbot, sample_pdf: Path):
    """Every request must answer, or the grid waits forever for a page that
    raised instead of returning.
    """
    with qtbot.waitSignal(bridge.thumbnailReady, timeout=15_000) as blocker:
        bridge.requestThumbnail(str(sample_pdf), 99)

    payload = json.loads(blocker.args[0])
    assert payload["index"] == 99
    assert payload["dataUrl"] == ""
    assert payload["error"]


def test_every_page_of_a_document_is_answered(bridge, qtbot, sample_pdf: Path):
    received: list[int] = []
    bridge.thumbnailReady.connect(lambda raw: received.append(json.loads(raw)["index"]))

    for index in range(5):
        bridge.requestThumbnail(str(sample_pdf), index)

    qtbot.waitUntil(lambda: len(received) == 5, timeout=30_000)
    assert sorted(received) == [0, 1, 2, 3, 4]


# ------------------------------------------------------------ operations --


def test_split_runs_in_the_background_and_writes_to_the_output_folder(
    bridge, qtbot, sample_pdf: Path, tmp_path: Path
):
    with qtbot.waitSignal(bridge.splitFinished, timeout=30_000) as blocker:
        bridge.runSplit(str(sample_pdf), json.dumps(["1-2", "3-5"]))

    payload = json.loads(blocker.args[0])
    assert payload["count"] == 2
    assert all(Path(p).is_file() for p in payload["outputs"])
    # No dialog was involved: the destination came from the bridge itself.
    assert Path(payload["where"]).parent == (tmp_path / "out")


def test_failure_arrives_on_the_failed_signal(bridge, qtbot, tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    with qtbot.waitSignal(bridge.splitFailed, timeout=30_000) as blocker:
        bridge.runSplit(str(bad), json.dumps(["1"]))

    assert "valid PDF" in blocker.args[0]


def test_compress_reports_both_sizes(bridge, qtbot, sample_pdf_with_image: Path):
    with qtbot.waitSignal(bridge.compressFinished, timeout=60_000) as blocker:
        bridge.runCompress(str(sample_pdf_with_image), "ebook")

    payload = json.loads(blocker.args[0])
    assert payload["method"] in ("ghostscript", "fallback")
    assert payload["originalSize"] > 0
    assert payload["compressedSize"] > 0


def test_ghostscript_status_is_json(bridge):
    status = json.loads(bridge.ghostscriptStatus())
    assert isinstance(status["found"], bool)


# ------------------------------------------------------- job bookkeeping --


def test_finished_jobs_are_released(qtbot, sample_pdf: Path):
    """The runner has to hold a reference to each thread or Qt collects it
    mid-run - and has to let go afterwards, or every operation ever run stays
    in memory for the life of the process.
    """
    from pawdf.gui.workers import JobRunner

    runner = JobRunner()
    results: list[int] = []
    runner.start(lambda: 42, on_finished=results.append)

    qtbot.waitUntil(lambda: results == [42], timeout=10_000)
    qtbot.waitUntil(lambda: len(runner) == 0, timeout=10_000)


def test_a_failing_job_is_also_released(qtbot):
    from pawdf.gui.workers import JobRunner

    def boom():
        raise RuntimeError("nope")

    runner = JobRunner()
    failures: list[Exception] = []
    runner.start(boom, on_failed=failures.append)

    qtbot.waitUntil(lambda: len(failures) == 1, timeout=10_000)
    qtbot.waitUntil(lambda: len(runner) == 0, timeout=10_000)


# ---------------------------------------------------------- drag and drop --


def _drop_event(paths: list[Path]):
    """Build a synthetic drop event.

    The QMimeData is returned alongside the event and must be kept alive by the
    caller: QDropEvent stores a borrowed pointer to it, so letting the Python
    wrapper be collected leaves the event holding freed memory and segfaults
    the moment anything reads `event.mimeData()`.
    """
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    return event, mime


def test_drop_filter_extracts_real_paths(qtbot, sample_pdf: Path):
    """This is the whole reason dnd.py exists: a dropped File in the page has
    no path, so Qt has to supply it.
    """
    from pawdf.gui.dnd import FileDropFilter

    received: list[list[str]] = []
    drop_filter = FileDropFilter(on_files=received.append)

    event, _mime = _drop_event([sample_pdf])
    handled = drop_filter.eventFilter(None, event)

    assert handled is True  # swallowed, so Chromium can't navigate to the file
    assert received == [[str(sample_pdf)]]


def test_drop_filter_ignores_a_drop_with_no_files(qtbot, tmp_path: Path):
    from pawdf.gui.dnd import FileDropFilter

    received: list[list[str]] = []
    drop_filter = FileDropFilter(on_files=received.append)

    # A directory is not a file, so there's nothing to hand over.
    event, _mime = _drop_event([tmp_path])
    handled = drop_filter.eventFilter(None, event)

    assert handled is False
    assert received == []


def test_drop_filter_reports_drag_state_once_per_change(qtbot, sample_pdf: Path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent

    from pawdf.gui.dnd import FileDropFilter

    states: list[bool] = []
    drop_filter = FileDropFilter(on_files=lambda _: None, on_drag_state=states.append)

    mime = QMimeData()  # must outlive `enter`, same borrowed-pointer caveat
    mime.setUrls([QUrl.fromLocalFile(str(sample_pdf))])
    enter = QDragEnterEvent(
        QPointF(1, 1).toPoint(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    drop_filter.eventFilter(None, enter)
    drop_filter.eventFilter(None, enter)  # still dragging: must not re-notify

    assert states == [True]

    drop_event, _keep = _drop_event([sample_pdf])
    drop_filter.eventFilter(None, drop_event)
    assert states == [True, False]


def test_extension_filter():
    from pawdf.gui.dnd import filter_by_extension

    paths = ["/a/one.pdf", "/a/two.PDF", "/a/three.docx", "/a/four.png"]
    assert filter_by_extension(paths, [".pdf"]) == ["/a/one.pdf", "/a/two.PDF"]


def test_add_files_dialog_offers_every_extension_any_tool_accepts():
    """The user picks the file before the tool, so the Add-files dialog has to
    show everything the app can open.

    A feature added with a new extension and no matching glob here would be
    unreachable through the dialog -- the tool would light up for a dropped
    file but the file picker would hide it.
    """
    from pawdf.core import registry
    from pawdf.gui.bridge import FILE_FILTERS

    combined = FILE_FILTERS["any"].lower()
    for feature in registry.FEATURES:
        for extension in feature.accepts:
            assert f"*{extension}" in combined, (
                f"'{feature.id}' accepts {extension} but the Add-files filter does not offer it"
            )


# ------------------------------------------------------- output naming --


def test_results_go_to_the_output_folder_without_a_dialog(
    bridge, qtbot, sample_pdf: Path, tmp_path
):
    """There is no save dialog anywhere in the app, so the bridge has to pick
    a destination itself.
    """
    with qtbot.waitSignal(bridge.compressFinished, timeout=60_000) as blocker:
        bridge.runCompress(str(sample_pdf), "ebook")

    written = Path(json.loads(blocker.args[0])["output"])
    assert written.parent == (tmp_path / "out")
    assert written.name.startswith(sample_pdf.stem)
    assert written.is_file()


def test_an_existing_name_is_never_overwritten(bridge, qtbot, sample_pdf: Path, tmp_path: Path):
    """Not asking where to save is only acceptable if nothing can be lost to
    it, so a colliding name gets a numbered variant instead.
    """
    first = None
    for _ in range(2):
        with qtbot.waitSignal(bridge.compressFinished, timeout=60_000) as blocker:
            bridge.runCompress(str(sample_pdf), "ebook")
        written = Path(json.loads(blocker.args[0])["output"])
        if first is None:
            first = written
        else:
            assert written != first
            assert first.is_file(), "the first result was overwritten"
            assert "(2)" in written.name


def test_output_dir_defaults_to_downloads(monkeypatch):
    from pawdf.gui.bridge import OUTPUT_DIR_ENV, Bridge

    monkeypatch.delenv(OUTPUT_DIR_ENV, raising=False)
    assert Bridge.download_dir().name.lower() in {"downloads", "download"} or (
        Bridge.download_dir() == Path.home()
    )

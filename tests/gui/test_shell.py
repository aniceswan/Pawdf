"""Smoke tests for the window itself: it builds, the page loads, and the UI
the page builds from the registry actually appears.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture
def window(qtbot):
    from pawdf.gui.shell import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    return win


def test_window_builds_with_a_registered_bridge(window):
    assert window.windowTitle() == "Pawdf"
    assert window.channel.registeredObjects()["bridge"] is window.bridge


def test_page_loads(window, qtbot):
    with qtbot.waitSignal(window.view.loadFinished, timeout=30_000) as blocker:
        pass
    assert blocker.args == [True]


def _probe(window, qtbot, expression: str, timeout: int = 30_000):
    """Evaluate `expression` and wait until it returns something non-empty.

    Waiting for a *populated* answer rather than for any answer at all: the
    page replies as soon as it can, which is before app.js has finished
    building the ring, so polling on "did anything come back" passes or fails
    depending on how long the rest of the page took to load that run.
    """
    import json

    result: list = []

    def ready() -> bool:
        window.view.page().runJavaScript(expression, result.append)
        if not result or not result[-1]:
            return False
        return bool(json.loads(result[-1]))

    qtbot.waitUntil(ready, timeout=timeout)
    return json.loads(result[-1])


def test_top_level_ring_shows_categories(window, qtbot):
    """The first ring is categories, not tools. Eight tools fit in a circle;
    twenty do not, so the ring groups them and expands one group at a time.
    """
    from pawdf.core import registry

    with qtbot.waitSignal(window.view.loadFinished, timeout=30_000):
        pass

    shown = _probe(
        window,
        qtbot,
        "JSON.stringify(Array.from(document.querySelectorAll('.node'))"
        ".map(n => n.dataset.category))",
    )
    assert shown == [c.id for c in registry.CATEGORIES]


def test_opening_a_category_shows_its_tools(window, qtbot):
    from pawdf.core import registry

    with qtbot.waitSignal(window.view.loadFinished, timeout=30_000):
        pass

    # Wait for the first ring before driving it.
    _probe(
        window,
        qtbot,
        "JSON.stringify(Array.from(document.querySelectorAll('.node'))"
        ".map(n => n.dataset.category))",
    )

    first = registry.CATEGORIES[0].id
    shown = _probe(
        window,
        qtbot,
        f"openCategory('{first}');"
        "JSON.stringify(Array.from(document.querySelectorAll('.node'))"
        ".map(n => n.dataset.feature))",
    )
    assert shown == [f.id for f in registry.in_category(first)]


def test_every_feature_has_a_panel_in_the_markup(window, qtbot):
    """The ring is generated, but each tool's form is hand-written. A feature
    added to the registry with no panel would show a node that opens nothing.
    """
    from pawdf.core import registry
    from pawdf.gui.resources import INDEX_HTML

    markup = INDEX_HTML.read_text(encoding="utf-8")
    for feature in registry.FEATURES:
        assert f'data-panel="{feature.id}"' in markup, (
            f"core/registry.py declares '{feature.id}' but index.html has no panel for it"
        )


# ---------------------------------------------------- window restoration --


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Keep QSettings out of the developer's real config file."""
    from PySide6.QtCore import QSettings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "config")
    )
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "pawdf", "Pawdf")
    settings.clear()
    settings.sync()
    return settings


def test_window_opens_when_it_was_last_closed_maximized(qtbot, isolated_settings):
    """Regression: restoring a maximized window shows it, and showEvent runs
    against whatever the constructor has built so far.

    Restoring geometry partway through __init__ meant showEvent fired before
    the drag-and-drop attributes existed, and the app died on startup with an
    AttributeError for every user who had ever maximized it.
    """
    from PySide6.QtCore import QSettings

    from pawdf.gui.shell import MainWindow

    saved = QSettings("pawdf", "Pawdf")
    saved.setValue("maximized", True)
    saved.sync()

    try:
        window = MainWindow()
    except AttributeError as exc:  # pragma: no cover - the bug this guards
        pytest.fail(f"MainWindow could not be constructed: {exc}")

    qtbot.addWidget(window)
    assert window.bridge is not None
    window.close()


def test_geometry_survives_a_restart(qtbot, isolated_settings):
    from pawdf.gui.shell import MainWindow

    # The old 1101x733 fixture exceeded the hosted macOS work area and tested
    # Qt's screen clamping rather than Pawdf's persistence behavior.
    target_size = (900, 620)

    first = MainWindow()
    qtbot.addWidget(first)
    first.resize(*target_size)
    assert (first.width(), first.height()) == target_size
    first.close()  # closeEvent is what persists the geometry
    isolated_settings.sync()

    second = MainWindow()
    qtbot.addWidget(second)
    assert (second.width(), second.height()) == target_size
    second.close()

"""Runtime WebEngine checks for reliability UI behavior."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture
def loaded_window(qtbot):
    from pawdf.gui.shell import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.view.loadFinished, timeout=30_000) as blocker:
        pass
    assert blocker.args == [True]

    # loadFinished only means the local HTML loaded. Registry metadata arrives
    # asynchronously through QWebChannel, so wait for boot() to finish before
    # a test calls openCategory() or openTool().
    _probe(
        window,
        qtbot,
        "features.has('forms') && categories.has('annotate') ? JSON.stringify(true) : ''",
    )
    return window


def _probe(window, qtbot, expression: str, timeout: int = 30_000):
    results: list = []

    def ready() -> bool:
        window.view.page().runJavaScript(expression, results.append)
        return bool(results and results[-1])

    qtbot.waitUntil(ready, timeout=timeout)
    return json.loads(results[-1])


def _run_once(window, qtbot, script: str) -> None:
    results: list = []
    window.view.page().runJavaScript(script, results.append)
    qtbot.waitUntil(lambda: bool(results), timeout=30_000)


def test_category_labels_use_american_english(loaded_window, qtbot):
    labels = _probe(
        loaded_window,
        qtbot,
        "JSON.stringify(Object.fromEntries("
        "Array.from(document.querySelectorAll('.node[data-category]'))"
        ".map(node => [node.dataset.category, node.querySelector('.node-label').textContent])))",
    )

    assert labels["organise"] == "Organize"
    assert labels["optimise"] == "Optimize"


def test_form_panel_renders_radio_and_choice_controls(loaded_window, qtbot, tmp_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    form_pdf = tmp_path / "ui-form.pdf"
    output = canvas.Canvas(str(form_pdf), pagesize=letter)
    form = output.acroForm
    form.radio(name="plan", value="basic", x=72, y=610, selected=True)
    form.radio(name="plan", value="pro", x=110, y=610, selected=False)
    form.choice(
        name="country",
        value="ID",
        options=["ID", "US"],
        x=72,
        y=560,
        width=100,
        height=24,
    )
    output.showPage()
    output.save()

    path = json.dumps(str(form_pdf))
    _run_once(
        loaded_window,
        qtbot,
        "session.files = [" + path + "];"
        "renderFiles(); renderRing(); openCategory('annotate'); openTool('forms'); true;",
    )

    controls = _probe(
        loaded_window,
        qtbot,
        "(() => {"
        "const selects = Array.from(document.querySelectorAll('#form-fields select'));"
        "if (selects.length < 2) return '';"
        "return JSON.stringify(Object.fromEntries(selects.map(select => ["
        "select.dataset.field, Array.from(select.options).map(option => option.value)"
        "])));"
        "})()",
    )

    assert {value.removeprefix("/") for value in controls["plan"]} >= {
        "basic",
        "pro",
    }
    assert set(controls["country"]) >= {"ID", "US"}


def test_split_segments_follow_runtime_cut_points(loaded_window, qtbot):
    segments = _probe(
        loaded_window,
        qtbot,
        "(() => {"
        "splitUx.count = 8;"
        "splitUx.cuts = new Set([5, 2, 99, 0]);"
        "return JSON.stringify(splitSegments());"
        "})()",
    )

    assert segments == [
        {"start": 1, "end": 2},
        {"start": 3, "end": 5},
        {"start": 6, "end": 8},
    ]


def test_arrange_pointer_drop_reorders_runtime_pages(
    loaded_window,
    qtbot,
):
    order = _probe(
        loaded_window,
        qtbot,
        "(() => {"
        "organize.pages = [0, 1, 2].map(index => ({"
        "originalIndex: index, rotation: 0, selected: false"
        "}));"
        "const fakeItem = {"
        "hasPointerCapture: () => false,"
        "releasePointerCapture: () => {},"
        "classList: { remove: () => {} }"
        "};"
        "arrangePointer = {"
        "pointerId: 17, from: 0, dragging: true,"
        "target: { index: 2, after: true }, item: fakeItem"
        "};"
        "finishArrangePointer({ pointerId: 17 });"
        "return JSON.stringify(organize.pages.map(page => page.originalIndex));"
        "})()",
    )

    assert order == [1, 2, 0]

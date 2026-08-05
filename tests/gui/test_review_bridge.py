"""Regression tests for result reporting, output reservations, and wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")


@pytest.fixture
def bridge(qtbot, tmp_path, monkeypatch):
    from pawdf.gui.bridge import OUTPUT_DIR_ENV, Bridge

    monkeypatch.setenv(OUTPUT_DIR_ENV, str(tmp_path / "out"))
    instance = Bridge(None)
    yield instance
    instance.shutdown()


def test_shape_failure_keeps_success_and_output_path(
    bridge,
    qtbot,
    tmp_path,
):
    output = tmp_path / "created.pdf"
    output.write_bytes(b"already written")
    failures: list[str] = []
    bridge.mergeFailed.connect(failures.append)

    def broken_shape(_result):
        raise KeyError("future payload field")

    with qtbot.waitSignal(bridge.mergeFinished, timeout=10_000) as blocker:
        bridge._dispatch(
            bridge.mergeFinished,
            bridge.mergeFailed,
            lambda: output,
            shape=broken_shape,
        )

    payload = json.loads(blocker.args[0])
    assert payload["output"] == str(output)
    assert payload["detailsUnavailable"] is True
    assert failures == []


def test_output_names_are_reserved_before_a_worker_writes(
    bridge,
    tmp_path,
):
    first = bridge._out_file("same.pdf", ".pdf", tag="_result")
    second = bridge._out_file("same.pdf", ".pdf", tag="_result")

    try:
        assert first != second
        assert first.parent == tmp_path / "out"
        assert "(2)" in second.name
        assert not first.exists()
        assert not second.exists()
    finally:
        bridge._release_outputs({first, second})


def test_every_registry_feature_has_bridge_and_javascript_wiring():
    from pawdf.core import registry
    from pawdf.gui.bridge import FEATURE_CHANNELS, Bridge

    assert set(FEATURE_CHANNELS) == {feature.id for feature in registry.FEATURES}

    root = Path(__file__).resolve().parents[2]
    javascript = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "src/pawdf/gui/web/app.js",
            "src/pawdf/gui/web/enhancements.js",
        )
    )

    for feature_id, (slot, finished, failed) in FEATURE_CHANNELS.items():
        assert callable(getattr(Bridge, slot)), feature_id
        assert hasattr(Bridge, finished), feature_id
        assert hasattr(Bridge, failed), feature_id
        assert f"bridge.{slot}" in javascript, feature_id
        assert f"bridge.{finished}" in javascript, feature_id
        assert f"bridge.{failed}" in javascript, feature_id

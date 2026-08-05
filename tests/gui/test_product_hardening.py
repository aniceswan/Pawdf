from __future__ import annotations

import json


def test_diagnostic_slots_return_json_and_existing_paths(tmp_path, qtbot):
    from pawdf.gui.bridge import Bridge

    existing = tmp_path / "exists.pdf"
    existing.write_bytes(b"%PDF-1.4\n")
    bridge = Bridge()
    restored = json.loads(
        bridge.existingFiles(json.dumps([str(existing), str(tmp_path / "gone.pdf")]))
    )
    assert restored == [str(existing)]
    info = json.loads(bridge.diagnosticInfo())
    assert info["pawdfVersion"]

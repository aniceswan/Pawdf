from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

from pawdf.gui import diagnostics


def _reset_logging(monkeypatch, tmp_path):
    logger = logging.getLogger("pawdf")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    monkeypatch.setattr(diagnostics, "user_log_dir", lambda *args, **kwargs: str(tmp_path / "logs"))
    monkeypatch.setattr(diagnostics, "_CONFIGURED", False)


def test_diagnostic_bundle_has_metadata_and_no_documents(tmp_path, monkeypatch):
    _reset_logging(monkeypatch, tmp_path)
    log = diagnostics.configure_logging()
    logging.getLogger("pawdf.test").info("home=%s", Path.home())
    for handler in logging.getLogger("pawdf").handlers:
        handler.flush()

    document = tmp_path / "private-document.pdf"
    document.write_bytes(b"secret document bytes")

    bundle = diagnostics.create_diagnostic_bundle(tmp_path / "out")
    assert bundle.is_file()
    assert log.is_file()

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "diagnostics.json" in names
        assert "README.txt" in names
        assert not any("private-document" in name for name in names)
        metadata = json.loads(archive.read("diagnostics.json"))
        assert metadata["pawdfVersion"]
        assert metadata["resourceLimits"]["max_input_bytes"] > 0
        logs = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
            if name.startswith("logs/")
        )
        assert str(Path.home()) not in logs
        assert "<HOME>" in logs
        assert b"secret document bytes" not in bundle.read_bytes()


def test_clear_logs_recreates_an_empty_current_log(tmp_path, monkeypatch):
    _reset_logging(monkeypatch, tmp_path)
    diagnostics.configure_logging()
    logging.getLogger("pawdf.test").info("old event")
    diagnostics.clear_logs()
    assert (tmp_path / "logs" / "pawdf.log").is_file()


def test_diagnostic_info_does_not_expose_environment_values(monkeypatch):
    monkeypatch.setenv("PAWDF_MAX_INPUT_MIB", "1234")
    monkeypatch.setenv("PAWDF_SECRET_EXAMPLE", "do-not-copy")
    info = diagnostics.diagnostic_info()
    encoded = json.dumps(info)
    assert "PAWDF_MAX_INPUT_MIB" in info["environmentOverrides"]
    assert "PAWDF_SECRET_EXAMPLE" in info["environmentOverrides"]
    assert "do-not-copy" not in encoded

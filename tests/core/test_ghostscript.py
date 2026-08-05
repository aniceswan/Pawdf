from pawdf.core.compress import ghostscript as locator


def test_env_override_wins_when_file_exists(tmp_path, monkeypatch):
    fake_gs = tmp_path / "fake-gs"
    fake_gs.write_text("#!/bin/sh\n")
    monkeypatch.setenv(locator.ENV_OVERRIDE, str(fake_gs))

    assert locator.find_ghostscript() == fake_gs


def test_env_override_ignored_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv(locator.ENV_OVERRIDE, str(tmp_path / "does-not-exist"))
    monkeypatch.setattr(locator, "_vendored_binary", lambda: None)
    monkeypatch.setattr(locator, "_system_binary", lambda: None)
    monkeypatch.setattr(locator, "_known_fallback_paths", lambda: None)

    assert locator.find_ghostscript() is None


def test_falls_back_to_system_path_when_no_override(monkeypatch, tmp_path):
    monkeypatch.delenv(locator.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(locator, "_vendored_binary", lambda: None)
    fake_system_gs = tmp_path / "system-gs"
    monkeypatch.setattr(locator, "_system_binary", lambda: fake_system_gs)

    assert locator.find_ghostscript() == fake_system_gs


def test_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.delenv(locator.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(locator, "_vendored_binary", lambda: None)
    monkeypatch.setattr(locator, "_system_binary", lambda: None)
    monkeypatch.setattr(locator, "_known_fallback_paths", lambda: None)

    assert locator.find_ghostscript() is None

from __future__ import annotations

from pathlib import Path

import pawdf.__main__ as entrypoint
from pawdf import __version__


def test_version_cli_avoids_importing_the_gui(monkeypatch, capsys):
    monkeypatch.setattr(entrypoint.sys, "argv", ["pawdf", "--version"])
    assert entrypoint.main() == 0
    assert capsys.readouterr().out.strip() == __version__


def test_session_recovery_and_diagnostics_controls_are_wired():
    app = Path("src/pawdf/gui/web/app.js").read_text(encoding="utf-8")
    html = Path("src/pawdf/gui/web/index.html").read_text(encoding="utf-8")
    assert 'const SESSION_KEY = "pawdf-session-v1"' in app
    assert "bridge.existingFiles" in app
    assert "persistSession();" in app
    assert 'id="diagnostics-export"' in html
    assert 'id="session-forget"' in html
    assert "bridge.exportDiagnostics" in app
    assert "bridge.jobCountChanged.connect" in app


def test_accessibility_hardening_is_present():
    css = Path("src/pawdf/gui/web/enhancements.css").read_text(encoding="utf-8")
    app = Path("src/pawdf/gui/web/app.js").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert 'btn.setAttribute("aria-busy"' in app


def test_production_docs_and_private_corpus_policy_exist():
    assert Path("docs/production_readiness.md").is_file()
    assert Path("docs/qa/windows.md").is_file()
    assert Path("docs/qa/macos.md").is_file()
    assert Path("docs/qa/linux.md").is_file()
    policy = Path("tests/fixtures/corpus/README.md").read_text(encoding="utf-8")
    assert "Never commit" in policy
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "tests/fixtures/corpus/*" in gitignore

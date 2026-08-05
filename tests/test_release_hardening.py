"""Release, metadata and supply-chain contracts."""

from __future__ import annotations

from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def test_versions_are_synchronized():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]

    about = (ROOT / "src/pawdf/__about__.py").read_text(encoding="utf-8")
    spec = (ROOT / "packaging/pyinstaller/pawdf.spec").read_text(encoding="utf-8")
    installer = (ROOT / "packaging/windows/installer.iss").read_text(encoding="utf-8")

    assert f'__version__ = "{project_version}"' in about
    assert spec.count(f'"CFBundleVersion": "{project_version}"') == 1
    assert spec.count(f'"CFBundleShortVersionString": "{project_version}"') == 1
    assert f'#define AppVersion "{project_version}"' in installer


def test_display_spelling_and_documented_inventory_are_current():
    from pawdf.core import registry

    titles = {category.id: category.title for category in registry.CATEGORIES}
    assert titles["organise"] == "Organize"
    assert titles["optimise"] == "Optimize"
    assert len(registry.FEATURES) == 22

    package_count = len({feature.import_path.rsplit(".", 1)[-1] for feature in registry.FEATURES})
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "**22 tools**" in readme
    assert f"**{package_count} independent feature packages**" in readme
    assert "335 tests" not in readme


def test_ghostscript_installer_is_hash_pinned_before_execution():
    source = (ROOT / "src/pawdf/core/compress/ghostscript.py").read_text(encoding="utf-8")

    assert "WINDOWS_INSTALLER_SHA256" in source
    assert "_verify_installer(destination)" in source
    assert source.index("_verify_installer(destination)") < source.index("subprocess.run(")


def test_binary_bundle_collects_legal_material():
    build = (ROOT / "scripts/build_pyinstaller.py").read_text(encoding="utf-8")
    collector = (ROOT / "scripts/collect_licenses.py").read_text(encoding="utf-8")
    spec = (ROOT / "packaging/pyinstaller/pawdf.spec").read_text(encoding="utf-8")

    assert "collect_licenses(root)" in build
    assert "THIRD-PARTY-NOTICES.md" in collector
    assert '"PySide6"' in collector
    assert 'repo_root / "LICENSE"' in spec
    assert 'repo_root / "THIRD-PARTY-NOTICES.md"' in spec


def test_ci_and_release_workflows_cover_hardening():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "tests/test_release_hardening.py" in ci
    assert "dist/pawdf/legal/LICENSE" in ci
    assert "pawdf.app" in release
    assert "if-no-files-found: error" in release


def test_no_accidental_local_backup_directory_is_tracked():
    assert not (ROOT / ".pawdf_ux_backups").exists()


def test_changelog_names_the_reliability_fixes():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for phrase in (
        "OCR preserves failed pages",
        "form appearances before flattening",
        "Ghostscript installer SHA-256",
        "PowerPoint fidelity warnings",
    ):
        assert phrase in changelog

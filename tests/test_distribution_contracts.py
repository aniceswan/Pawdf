"""Release-based installation and runtime-size contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_user_installers_do_not_build_source():
    shell = read("install.sh").lower()
    powershell = read("install.ps1").lower()
    for forbidden in ("git clone", "python -m venv", "pip install", "build_pyinstaller.py"):
        assert forbidden not in shell
        assert forbidden not in powershell
    assert "sha256sums.txt" in shell
    assert "sha256sums.txt" in powershell
    assert "releases/latest/download" in shell
    assert "releases/latest/download" in powershell


def test_release_environment_is_separate_from_development():
    pyproject = read("pyproject.toml")
    release = read(".github/workflows/release.yml")
    assert "release = [" in pyproject
    assert '-e ".[release]"' in release
    assert '-e ".[dev]"' not in release

    launcher = read("scripts/test_all_os.sh")
    assert "Install source QA environment" in launcher
    assert "pawdf-release-venv" in launcher
    assert "RELEASE_PYTHON" in launcher


def test_release_matrix_covers_four_shipping_targets():
    """linux-aarch64 is deliberately absent from the *release* matrix.

    Six real hosted release attempts fixed several genuine Pawdf bugs
    (QtQuickWidgets over-pruning, a stale audit deny-list, missing
    libevent/libopus) and then hit a real upstream gap: PySide6 6.11.1's
    Qt WebEngine wants libwebp.so.6, an ABI Ubuntu 22.04's main archive no
    longer ships for aarch64. That is not something a workflow edit fixes,
    so the four targets that do build and launch correctly ship, and
    aarch64 is tracked separately rather than blocking them indefinitely.
    """
    release = read(".github/workflows/release.yml")
    for token in (
        "ubuntu-22.04",
        "windows-2025",
        "macos-15",
        "macos-15-intel",
        "Pawdf-Linux-x86_64.AppImage",
        "Pawdf-Windows-x86_64-Setup.exe",
        "Pawdf-macOS-arm64.dmg",
        "Pawdf-macOS-x86_64.dmg",
    ):
        assert token in release
    assert "ubuntu-22.04-arm" not in release
    assert "Pawdf-Linux-aarch64.AppImage" not in release


def test_all_os_qa_snapshot_still_tracks_five_targets():
    """The hosted QA snapshot tool (not the release gate) keeps testing
    aarch64 too, so a future fix is visible in QA output rather than
    needing to be rediscovered.
    """
    launcher = read("scripts/test_all_os.sh")
    for token in (
        "ubuntu-22.04",
        "ubuntu-22.04-arm",
        "windows-2025",
        "macos-15",
        "macos-15-intel",
        "Pawdf-Linux-x86_64.AppImage",
        "Pawdf-Linux-aarch64.AppImage",
        "Pawdf-Windows-x86_64-Setup.exe",
        "Pawdf-macOS-arm64.dmg",
        "Pawdf-macOS-x86_64.dmg",
    ):
        assert token in launcher


def test_pruning_preserves_complete_feature_contract():
    spec = read("packaging/pyinstaller/pawdf.spec")
    main = read("src/pawdf/__main__.py")
    smoke = read("scripts/smoke_packaged.py")
    audit = read("scripts/audit_bundle.py")
    assert spec.count('if "/qml/" in padded:') == 1
    assert "_canonical_qt_path" in spec
    assert 'replace("qt6", "qt")' in spec
    assert "_is_unused_runtime_path" in spec
    assert "_prune_binaries" in spec
    assert "_is_unused_runtime_path(_normalized_destination(entry))" in spec
    assert 'strip_linux = sys.platform.startswith("linux")' in spec
    assert "--self-test-json" in main
    assert "featureCount" in main
    assert "--self-test-json" in smoke
    assert "FORBIDDEN_FAMILIES" in audit
    assert "canonical_qt_path" in audit
    assert "QtWebEngineProcess" in audit

    launcher = read("scripts/test_all_os.sh")
    assert 'head_sha="$HEAD_SHA"' in launcher
    assert ".github/workflows/pawdf-all-os-qa.yml" in launcher
    assert "gh run list" not in launcher


def test_release_metadata_and_installer_contracts():
    source = read("src/pawdf/release_manifest.py")
    workflow = read(".github/workflows/release.yml")
    installer = read("packaging/windows/installer.iss")
    assert '"release-manifest.json"' in source
    assert '".appimage"' in source
    assert "release-assets/release-manifest.json" in workflow
    assert "release-size-*.json" in workflow
    assert "installed-smoke-*.json" in workflow
    assert "PrivilegesRequired=lowest" in installer
    assert "DefaultDirName={localappdata}\\Programs\\{#AppName}" in installer
    # lzma2/max, not lzma2/ultra64: the ultra preset ran a real hosted
    # Windows runner out of memory compiling a ~460 MiB payload. See the
    # comment above Compression= in installer.iss.
    assert "Compression=lzma2/max" in installer
    assert "Compression=lzma2/ultra64" not in installer


def test_documentation_presents_binary_install_before_source_install():
    readme = read("README.md")
    distribution = read("docs/distribution.md")
    assert readme.index("curl -fsSL") < readme.index("Build from source")
    assert "No Git, Python, pip" in distribution
    assert "optional external runtime" in distribution

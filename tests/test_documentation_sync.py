"""Contracts for synchronized public Pawdf documentation."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def test_public_documentation_sync_markers_are_present():
    expected = {
        "README.md": "PAWDF_DOC_SYNC_2026_08",
        "CHANGELOG.md": "PAWDF_DOC_SYNC_2026_08",
        "docs/production_readiness.md": "PAWDF_DOC_SYNC_2026_08",
        "docs/qa/README.md": "PAWDF_DOC_SYNC_2026_08",
        "docs/qa/linux.md": "PAWDF_DOC_SYNC_2026_08",
        "docs/qa/windows.md": "PAWDF_DOC_SYNC_2026_08",
        "docs/qa/macos.md": "PAWDF_DOC_SYNC_2026_08",
    }
    for relative, marker in expected.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert marker in content


def test_readme_describes_current_visual_contracts():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert "PAWDF_DOC_SYNC_2026_08:current-ui" in readme
    assert "three miniature document-shaped paw pads" in normalized
    assert "reset to the same upright transform" in normalized
    assert "larger editorial hero" in normalized
    assert "bash scripts/test_all_os.sh" in normalized


def test_main_screenshot_is_current_desktop_size():
    screenshot = ROOT / "docs/screenshots/main_window.png"
    assert screenshot.is_file()
    with Image.open(screenshot) as image:
        assert image.format == "PNG"
        assert image.width >= 1200
        assert image.height >= 700


def test_all_os_launcher_contains_each_runner():
    launcher = (ROOT / "scripts/test_all_os.sh").read_text(encoding="utf-8")
    for runner in (
        "ubuntu-22.04",
        "ubuntu-22.04-arm",
        "windows-2025",
        "macos-15",
        "macos-15-intel",
    ):
        assert runner in launcher


def test_hosted_qa_is_not_described_as_physical_verification():
    combined = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "README.md",
            "docs/production_readiness.md",
            "docs/qa/README.md",
        )
    )
    normalized = " ".join(combined.replace("**", "").split())

    assert "not a substitute" in normalized
    assert "remain unverified" in normalized

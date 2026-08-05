# Brand and ring regressions that are easy to reintroduce visually.

from __future__ import annotations

import runpy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_logo_has_exactly_three_scaled_document_pads():
    generator = REPO_ROOT / "scripts" / "generate_icons.py"
    namespace = runpy.run_path(str(generator), run_name="pawdf_icon_contract")

    assert len(namespace["TOE_LAYOUT"]) == 3

    source = generator.read_text(encoding="utf-8")
    assert "def _document_pad(" in source
    assert "for dx, cy_ratio, width_ratio, height_ratio, angle in TOE_LAYOUT" in source
    assert "_toe(" not in source


def test_open_tool_forces_orbit_layers_to_the_same_zero_transform():
    css = (REPO_ROOT / "src" / "pawdf" / "gui" / "web" / "styles.css").read_text(encoding="utf-8")

    marker = "body.tool-open #ring-nodes,\nbody.tool-open .upright {"
    start = css.index(marker)
    block = css[start : css.index("}", start) + 1]

    assert "animation: none !important;" in block
    assert "transform: none !important;" in block


def test_generated_logo_files_exist_at_release_sizes():
    expected = [
        REPO_ROOT / "src/pawdf/gui/resources/icons/app_icon.png",
        REPO_ROOT / "src/pawdf/gui/web/img/logo.png",
        REPO_ROOT / "packaging/icons/icon.png",
        REPO_ROOT / "packaging/icons/icon.ico",
    ]
    expected.extend(
        REPO_ROOT / "packaging" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "pawdf.png"
        for size in (16, 22, 24, 32, 48, 64, 128, 256, 512)
    )

    assert all(path.is_file() and path.stat().st_size > 0 for path in expected)

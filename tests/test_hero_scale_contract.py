# Contract tests for the intentionally expansive landing hero.

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = REPO_ROOT / "src" / "pawdf" / "gui" / "web" / "styles.css"


def hero_block() -> str:
    css = CSS_PATH.read_text(encoding="utf-8")
    marker = "PAWDF_EXPANSIVE_HERO_V1"
    start = css.index(marker)
    return css[start:]


def test_expansive_hero_marker_exists_once():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert css.count("PAWDF_EXPANSIVE_HERO_V1") == 1


def test_expansive_hero_uses_larger_width_and_typography():
    block = hero_block()
    assert "flex-basis: clamp(460px, 42vw, 720px);" in block
    assert "font-size: clamp(48px, 5.25vw, 84px);" in block
    assert "max-width: 38ch;" in block
    assert "min-height: 54px;" in block


def test_expansive_hero_keeps_medium_and_small_breakpoints():
    block = hero_block()
    assert "@media (max-width: 1180px)" in block
    assert "@media (max-width: 820px)" in block
    assert "@media (max-width: 560px)" in block


def test_tool_open_collapse_rule_is_still_present():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert "body.tool-open #hero" in css
    assert "flex-basis: 0;" in css

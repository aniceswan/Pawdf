from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "pawdf" / "gui" / "web"


def test_enhancement_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="enhancements.css" />' in index
    assert '<script src="enhancements.js"></script>' in index


def test_arrange_uses_pointer_drag_not_native_html_drag():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")
    assert "item.draggable = false" in script
    assert 'addEventListener("pointerdown"' in script
    assert 'addEventListener("pointermove"' in script
    assert 'document.body.classList.add("arrange-dragging")' in script


def test_split_is_cut_point_based():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")
    assert 'className = "split-cutter"' in script
    assert "function splitSegments()" in script
    assert "Press scissors between pages" in script
    assert "bridge.runSplit(input, JSON.stringify(ranges))" in script


def test_every_operation_can_render_save_and_continue_results():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")
    assert "function showOperationResults" in script
    assert 'save.textContent = "Save"' in script
    assert 'next.textContent = "Continue"' in script
    assert "bridge.saveOutput" in script
    assert "bridge.saveOutputs" in script


def test_bridge_has_native_save_slots():
    bridge = (ROOT / "src" / "pawdf" / "gui" / "bridge.py").read_text(encoding="utf-8")
    assert "def saveOutput" in bridge
    assert "def saveOutputs" in bridge
    assert "shutil.copy2" in bridge


def test_ring_orbits_while_tiles_stay_upright():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")
    stylesheet = (WEB / "enhancements.css").read_text(encoding="utf-8")

    assert "PAWDF_STABLE_ORBIT_V2" in script
    assert "function pawdfOrbitFrame" in script
    assert "container.style.transform = `rotate(${angle}deg)`" in script
    assert "upright.style.transform = `rotate(${-angle}deg)`" in script
    assert "transform: none !important" not in stylesheet


def test_final_hardening_is_installed():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")
    stylesheet = (WEB / "enhancements.css").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "PAWDF_UX_HARDENING_V3" in script
    assert "function renderSplitDocument" in script
    assert "pagesOf(path, renderSplitDocument)" in script
    assert "function closeContinueMenus" in script
    assert "function autoScrollArrange" in script
    assert "continue-menu[hidden]" in stylesheet
    assert ".pawdf_ux_backups/" in gitignore


def test_split_preview_uses_one_stable_listener():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")

    assert "pagesOf(path, (doc) =>" not in script
    assert script.count("pagesOf(path, renderSplitDocument)") == 1


def test_continue_menu_has_accessible_state():
    script = (WEB / "enhancements.js").read_text(encoding="utf-8")

    assert 'next.setAttribute("aria-haspopup", "menu")' in script
    assert 'next.setAttribute("aria-expanded", "false")' in script
    assert 'menu.setAttribute("role", "menu")' in script


def test_form_ui_supports_radio_and_choice_fields():
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'field.kind === "radio"' in script
    assert 'field.kind === "choice"' in script
    assert 'document.createElement("select")' in script
    assert "option.value = raw" in script


def test_powerpoint_partial_fidelity_is_user_visible():
    script = (WEB / "app.js").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "pawdf" / "gui" / "bridge.py").read_text(encoding="utf-8")

    assert "d.shapesSkipped" in script
    assert "Review the output" in script
    assert "pptx_to_pdf_detailed" in bridge

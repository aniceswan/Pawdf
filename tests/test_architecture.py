"""Executable enforcement of the two structural promises this project makes.

1. `core/` never imports a GUI toolkit, so every PDF operation is testable and
   reusable without Qt.
2. No feature package imports another feature package, so any one of them can
   be copied out of this repo together with `_shared/` and nothing else.

Both are easy to break by accident with a convenient-looking import, and a
README saying "don't" doesn't stop anyone. These tests do.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "src" / "pawdf" / "core"

GUI_TOOLKITS = ("PySide6", "PyQt5", "PyQt6", "tkinter", "wx", "gi", "kivy", "webview")

FEATURE_DIRS = sorted(
    p.name for p in CORE_DIR.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
)


def _core_python_files() -> list[Path]:
    return sorted(p for p in CORE_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_modules(path: Path) -> set[str]:
    """Every module name imported by `path`, including inside functions.

    Walks the AST rather than grepping so that a name appearing in a docstring
    or a comment can't trip the check, and so lazily-imported modules inside
    function bodies are caught the same as top-level ones.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def test_feature_directories_are_discovered():
    """Guards every parametrised test below.

    Those tests are driven by `FEATURE_DIRS`, so if the layout changed and the
    list came back empty they would all pass while checking nothing. This is
    not a hard-coded inventory of packages -- that would need editing every
    time a tool is added, and `test_every_feature_points_at_a_real_package`
    already keeps the directories and the registry honest with each other.
    """
    assert FEATURE_DIRS, "no feature packages found under core/"
    assert (CORE_DIR / "_shared").is_dir(), "the shared base is missing"


@pytest.mark.parametrize("path", _core_python_files(), ids=lambda p: p.name)
def test_core_never_imports_a_gui_toolkit(path: Path):
    offenders = {
        module for module in _imported_modules(path) if module.split(".")[0] in GUI_TOOLKITS
    }
    assert not offenders, (
        f"{path.relative_to(REPO_ROOT)} imports {sorted(offenders)}. "
        "core/ must stay usable without a GUI toolkit installed."
    )


@pytest.mark.parametrize("feature", FEATURE_DIRS)
def test_features_do_not_import_each_other(feature: str):
    feature_dir = CORE_DIR / feature
    siblings = {f"pawdf.core.{name}" for name in FEATURE_DIRS} - {f"pawdf.core.{feature}"}

    for path in sorted(feature_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for module in _imported_modules(path):
            assert module not in siblings and not any(
                module.startswith(f"{sibling}.") for sibling in siblings
            ), (
                f"{path.relative_to(REPO_ROOT)} imports {module}. "
                "Features must depend only on pawdf.core._shared so each one "
                "can be lifted out of this repo on its own."
            )


@pytest.mark.parametrize("feature", FEATURE_DIRS)
def test_every_feature_documents_how_to_lift_it_out(feature: str):
    readme = CORE_DIR / feature / "README.md"
    assert readme.is_file(), f"core/{feature}/ needs a README.md"

    text = readme.read_text(encoding="utf-8")
    assert "Lifting this out" in text, f"core/{feature}/README.md must explain reuse"
    assert "pip packages" in text, f"core/{feature}/README.md must list its dependencies"


def test_shared_stays_small():
    """`_shared` is the one thing every feature carries, so it has to stay
    something you'd actually want to copy.
    """
    total = sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in (CORE_DIR / "_shared").glob("*.py")
    )
    assert total < 550, (
        f"core/_shared/ has grown to {total} lines; the shared security and "
        "I/O base must stay below its reviewed 550-line budget"
    )


def _package_of(feature) -> str:
    """The directory under core/ that backs a feature."""
    return feature.import_path.rsplit(".", 1)[-1]


def test_every_feature_points_at_a_real_package():
    """Features and packages are no longer one-to-one: `core/stamp/` backs
    watermark, page numbers and signatures, because all three are the same
    overlay with different content, and splitting them would mean copying
    that overlay three times.

    What still has to hold is that nothing is phantom and nothing is orphaned.
    """
    from pawdf.core import registry

    referenced = {_package_of(f) for f in registry.FEATURES}

    assert referenced <= set(FEATURE_DIRS), (
        f"registry points at packages that don't exist: {sorted(referenced - set(FEATURE_DIRS))}"
    )
    assert set(FEATURE_DIRS) <= referenced, (
        f"packages no feature exposes: {sorted(set(FEATURE_DIRS) - referenced)}"
    )


def test_feature_ids_are_unique():
    from pawdf.core import registry

    ids = [f.id for f in registry.FEATURES]
    assert len(ids) == len(set(ids)), "duplicate feature id in the registry"


def test_every_feature_belongs_to_a_declared_category():
    """The UI's first ring is categories, so a typo here would leave a tool
    unreachable rather than merely mislabelled.
    """
    from pawdf.core import registry

    known = {c.id for c in registry.CATEGORIES}
    for feature in registry.FEATURES:
        assert feature.category in known, (
            f"'{feature.id}' is in category '{feature.category}', which is not declared"
        )


def test_no_category_is_empty():
    """An empty category is a ring node that opens onto nothing."""
    from pawdf.core import registry

    for category in registry.CATEGORIES:
        assert registry.in_category(category.id), (
            f"category '{category.id}' has no tools; remove it or fill it"
        )


def test_registry_import_paths_resolve():
    from pawdf.core import registry

    for feature in registry.FEATURES:
        assert registry.load(feature.id) is not None


def test_registry_import_is_free_of_pdf_libraries():
    """Importing the registry must not drag in a PDF library.

    This is what lets the UI describe all eight tools at startup while paying
    for none of them, so it's worth a test rather than a comment.
    """
    import subprocess
    import sys

    code = (
        "import sys; import pawdf.core.registry as r; "
        "assert r.FEATURES; "
        "heavy = {'pikepdf', 'pypdfium2', 'reportlab', 'docx', 'PIL'} & set(sys.modules); "
        "print(sorted(heavy))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]", f"registry import pulled in {result.stdout.strip()}"


def test_every_feature_package_has_an_extras_entry_in_pyproject():
    """`pip install pawdf[split]` should install exactly what split needs.

    Keyed by *package*, not by tool: one package can expose several tools, and
    they share a dependency set by definition.
    """
    from pawdf.core import registry

    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)

    extras = pyproject["project"]["optional-dependencies"]
    for feature in registry.FEATURES:
        package = _package_of(feature)
        assert package in extras, f"pyproject.toml needs an extras group for '{package}'"

        declared = {
            requirement.split(">")[0].split("=")[0].split("[")[0].strip().lower()
            for requirement in extras[package]
        }
        expected = {name.lower() for name in feature.requires}
        assert expected == declared, (
            f"extras group '{package}' drifted: "
            f"missing {sorted(expected - declared)}, "
            f"unnecessary {sorted(declared - expected)}"
        )


def test_no_lgpl_dependency_reaches_core():
    """`core/` is restricted to licenses that place no conditions on how a
    downstream product is *distributed*, so anyone can lift a feature into a
    closed-source product with attribution alone.

    img2pdf (LGPL-3.0) used to be imported here for images -> PDF; it was
    replaced by `core/imagepdf/`. This test is what stops it coming back.
    """
    banned = {"img2pdf", "fitz", "pymupdf", "pdf2docx"}

    for path in _core_python_files():
        offenders = {m for m in _imported_modules(path) if m.split(".")[0].lower() in banned}
        assert not offenders, (
            f"{path.relative_to(REPO_ROOT)} imports {sorted(offenders)}, which is "
            "copyleft or drags in something that is. See CONTRIBUTING.md."
        )


def test_qt_is_an_optional_extra_not_a_base_dependency():
    """`pip install pawdf` must not pull in Qt.

    The README promises that installing Pawdf gives you every PDF operation
    with no LGPL anywhere in the tree, and that the desktop window is opt-in.
    That promise is only true while PySide6 stays out of `[project]
    dependencies` - moving it back would silently break it for every consumer
    without breaking a single import.
    """
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)

    base = {
        requirement.split(">")[0].split("=")[0].split("[")[0].strip().lower()
        for requirement in pyproject["project"]["dependencies"]
    }
    copyleft_by_linking = {"pyside6", "pyqt5", "pyqt6", "img2pdf", "pymupdf"}

    assert not (base & copyleft_by_linking), (
        f"{sorted(base & copyleft_by_linking)} is an LGPL/GPL dependency and must "
        "live in an optional extra (see the 'gui' group), not in base dependencies."
    )
    assert "pyside6" in {
        r.split(">")[0].split("=")[0].strip().lower()
        for r in pyproject["project"]["optional-dependencies"]["gui"]
    }

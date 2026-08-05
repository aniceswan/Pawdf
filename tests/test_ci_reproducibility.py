# Regression contracts for CI reproducibility fixes.

from pathlib import Path

from pawdf.release_manifest import generate_release_metadata

ROOT = Path(__file__).resolve().parent.parent


def test_release_metadata_is_importable_from_installed_package():
    assert callable(generate_release_metadata)


def test_release_manifest_script_is_only_a_package_wrapper():
    script = (ROOT / "scripts/release_manifest.py").read_text(encoding="utf-8")
    assert "from pawdf.release_manifest import" in script


def test_icon_generator_supports_isolated_output_root():
    generator = (ROOT / "scripts/generate_icons.py").read_text(encoding="utf-8")
    assert "--output-root" in generator
    assert "output_root" in generator


def test_icon_ci_uses_semantic_checker_and_a_pillow_pin():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements/icon-generation.txt").read_text(encoding="utf-8")

    assert "python scripts/check_generated_icons.py" in workflow
    assert "requirements/icon-generation.txt" in workflow
    icon_job = workflow[workflow.index("icons-are-reproducible:") :]
    assert "git diff --quiet" not in icon_job
    assert requirements.startswith("# Exact visual-generator dependency.")
    assert "Pillow==" in requirements


def test_ci_reproducibility_marker_exists():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "PAWDF_CI_REPRODUCIBILITY_V1" in workflow

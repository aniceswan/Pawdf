from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pawdf.release_manifest import generate_release_metadata


def test_release_metadata_hashes_every_artifact_deterministically(tmp_path):
    root = tmp_path / "dist"
    (root / "bundle").mkdir(parents=True)
    first = root / "pawdf-linux.tar.gz"
    second = root / "bundle" / "pawdf"
    first.write_bytes(b"archive")
    second.write_bytes(b"binary")

    checksums, sbom = generate_release_metadata(root)
    first_run = checksums.read_text(encoding="utf-8")
    generate_release_metadata(root)
    assert checksums.read_text(encoding="utf-8") == first_run

    assert f"{hashlib.sha256(b'archive').hexdigest()}  pawdf-linux.tar.gz" in first_run
    assert "bundle/pawdf" not in first_run
    assert "SHA256SUMS.txt" not in first_run
    assert "SBOM.cdx.json" not in first_run

    payload = json.loads(sbom.read_text(encoding="utf-8"))
    assert payload["bomFormat"] == "CycloneDX"
    assert payload["metadata"]["component"]["name"] == "Pawdf"
    file_names = {
        component["name"] for component in payload["components"] if component["type"] == "file"
    }
    assert {"pawdf-linux.tar.gz", "bundle/pawdf"} <= file_names


def test_release_workflow_publishes_checksums_and_sbom():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "python scripts/release_manifest.py" in workflow
    assert "dist/SHA256SUMS.txt" in workflow
    assert "dist/SBOM.cdx.json" in workflow


def test_packaged_executables_have_version_smoke_tests():
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    smoke = Path("scripts/smoke_packaged.py").read_text(encoding="utf-8")

    assert "python scripts/smoke_packaged.py --dist dist" in ci
    assert "python scripts/smoke_packaged.py --dist dist" in release

    # See test_ci_runtime_contracts.test_windows_smoke_uses_subprocess_capture
    # for why this is scoped to capture() rather than the whole file:
    # gui_liveness() legitimately needs Popen(stdout=PIPE, ...) to stream a
    # long-running process, which subprocess.run's capture_output cannot do.
    capture_fn = smoke[smoke.index("def capture(") : smoke.index("def gui_liveness(")]
    assert "capture_output=True" in capture_fn
    assert "stdout=subprocess.PIPE" not in capture_fn
    assert "stderr=subprocess.PIPE" not in capture_fn
    assert "pawdf.exe --version" not in ci


def test_release_metadata_writes_installer_manifest(tmp_path):
    root = tmp_path / "dist"
    root.mkdir()
    appimage = root / "Pawdf-Linux-x86_64.AppImage"
    appimage.write_bytes(b"appimage")

    generate_release_metadata(root)

    manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["application"] == "Pawdf"
    assert manifest["assets"][0]["name"] == appimage.name
    assert manifest["assets"][0]["target"] == {
        "system": "linux",
        "architecture": "x86_64",
    }

"""Generate deterministic checksums, release manifest, and CycloneDX SBOM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path

from pawdf import __version__

__all__ = ["generate_release_metadata", "main"]
_EXCLUDED = {"SHA256SUMS.txt", "SBOM.cdx.json", "release-manifest.json"}
_DISTRIBUTIONS = (
    "pawdf",
    "pikepdf",
    "pypdfium2",
    "python-docx",
    "reportlab",
    "Pillow",
    "platformdirs",
    "openpyxl",
    "python-pptx",
    "PySide6",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.name not in _EXCLUDED and not path.name.endswith(".part")
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def release_artifacts(root: Path, all_files: list[Path]) -> list[Path]:
    suffixes = (".tar.gz", ".zip", ".exe", ".msi", ".dmg", ".pkg", ".appimage")
    artifacts = [
        path for path in all_files if path.parent == root and path.name.lower().endswith(suffixes)
    ]
    return artifacts or [path for path in all_files if path.parent == root]


def target(name: str) -> dict[str, str] | None:
    patterns = (
        (r"^Pawdf-Linux-(x86_64|aarch64)\.AppImage$", "linux"),
        (r"^Pawdf-macOS-(arm64|x86_64)\.dmg$", "macos"),
        (r"^Pawdf-Windows-(x86_64)-Setup\.exe$", "windows"),
    )
    for pattern, system in patterns:
        match = re.match(pattern, name)
        if match:
            return {"system": system, "architecture": match.group(1)}
    return None


def license_name(distribution: metadata.Distribution) -> str:
    expression = distribution.metadata.get("License-Expression")
    if expression:
        return expression
    license_text = distribution.metadata.get("License")
    if license_text and license_text.strip():
        return license_text.strip().splitlines()[0][:200]
    classifiers = distribution.metadata.get_all("Classifier") or []
    matches = [
        value.removeprefix("License :: ").strip()
        for value in classifiers
        if value.startswith("License :: ")
    ]
    return " OR ".join(matches) if matches else "NOASSERTION"


def components() -> list[dict]:
    result: list[dict] = []
    for name in _DISTRIBUTIONS:
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        normalized = distribution.metadata.get("Name") or name
        result.append(
            {
                "type": "library" if normalized.lower() != "pawdf" else "application",
                "name": normalized,
                "version": distribution.version,
                "licenses": [{"license": {"name": license_name(distribution)}}],
                "purl": f"pkg:pypi/{normalized}@{distribution.version}",
            }
        )
    return sorted(result, key=lambda item: item["name"].lower())


def generate_release_metadata(root: str | Path = "dist") -> tuple[Path, Path]:
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    all_files = files(directory)
    artifacts = release_artifacts(directory, all_files)

    checksums = directory / "SHA256SUMS.txt"
    lines = [f"{sha256(path)}  {path.relative_to(directory).as_posix()}" for path in artifacts]
    checksums.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    manifest = {
        "schemaVersion": 1,
        "application": "Pawdf",
        "version": __version__,
        "repository": "aniceswan/Pawdf",
        "assets": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "target": target(path.name),
            }
            for path in artifacts
        ],
    }
    (directory / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    file_components = [
        {
            "type": "file",
            "name": path.relative_to(directory).as_posix(),
            "hashes": [{"alg": "SHA-256", "content": sha256(path)}],
        }
        for path in all_files
    ]
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "Pawdf", "version": __version__}},
        "components": components() + file_components,
    }
    sbom_path = directory / "SBOM.cdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return checksums, sbom_path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="dist")
    args = parser.parse_args(list(argv) if argv is not None else None)
    checksums, sbom = generate_release_metadata(args.root)
    print(checksums)
    print(Path(args.root) / "release-manifest.json")
    print(sbom)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

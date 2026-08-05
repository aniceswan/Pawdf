"""Validate a private real-world document corpus without uploading anything."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pawdf.core._shared.limits import validate_input_file

SUPPORTED = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def _inspect(path: Path) -> dict:
    entry = {
        "relativePath": path.name,
        "suffix": path.suffix.lower(),
        "bytes": path.stat().st_size,
        "status": "ok",
    }
    try:
        validate_input_file(path)
        if path.suffix.lower() == ".pdf":
            import pikepdf

            try:
                with pikepdf.open(path) as pdf:
                    entry["pages"] = len(pdf.pages)
                    entry["encrypted"] = bool(pdf.is_encrypted)
            except pikepdf.PasswordError:
                entry["encrypted"] = True
                entry["pages"] = None
    except Exception as exc:  # noqa: BLE001 - report every corpus failure
        entry["status"] = "failed"
        entry["errorType"] = type(exc).__name__
        entry["error"] = str(exc)
    return entry


def verify_corpus(root: str | Path) -> dict:
    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    files = sorted(
        path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED
    )
    entries = []
    for path in files:
        entry = _inspect(path)
        entry["relativePath"] = path.relative_to(directory).as_posix()
        entries.append(entry)

    failures = sum(entry["status"] != "ok" for entry in entries)
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "root": str(directory),
        "files": len(entries),
        "failures": failures,
        "entries": entries,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a local document corpus and write a JSON report."
    )
    parser.add_argument("corpus")
    parser.add_argument("--output", default="corpus-report.json")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="return exit code 0 even when one or more files fail",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = verify_corpus(args.corpus)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    if report["failures"] and not args.allow_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

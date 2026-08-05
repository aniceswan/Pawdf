"""Small repeatable Pawdf performance benchmark.

This is intentionally not a hard CI timing gate: hosted runners vary too much.
It produces JSON that can be compared between releases on the same machine.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import pikepdf

from pawdf import __version__
from pawdf.core.merge import merge_pdfs
from pawdf.core.rotate import rotate_pdf
from pawdf.core.split import split_by_ranges


def _time(fn: Callable[[], object], repeats: int) -> dict[str, float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - started)
    return {
        "minSeconds": min(samples),
        "medianSeconds": statistics.median(samples),
        "maxSeconds": max(samples),
    }


def _fixture(path: Path, pages: int) -> Path:
    with pikepdf.new() as pdf:
        for _ in range(pages):
            pdf.add_blank_page(page_size=(612, 792))
        pdf.save(path)
    return path


def run_benchmarks(pages: int = 200, repeats: int = 3) -> dict:
    with tempfile.TemporaryDirectory(prefix="pawdf-benchmark-") as raw:
        root = Path(raw)
        source = _fixture(root / "source.pdf", pages)

        split_dir = root / "split"
        split_dir.mkdir()
        split_result = _time(
            lambda: split_by_ranges(
                source,
                [f"1-{pages // 2}", f"{pages // 2 + 1}-{pages}"],
                split_dir,
            ),
            repeats,
        )

        first = root / "first.pdf"
        second = root / "second.pdf"
        split_by_ranges(source, [f"1-{pages // 2}"], root / "first-parts")
        generated_first = next((root / "first-parts").glob("*.pdf"))
        generated_first.replace(first)
        split_by_ranges(source, [f"{pages // 2 + 1}-{pages}"], root / "second-parts")
        generated_second = next((root / "second-parts").glob("*.pdf"))
        generated_second.replace(second)

        merge_result = _time(
            lambda: merge_pdfs([first, second], root / "merged.pdf"),
            repeats,
        )
        rotate_result = _time(
            lambda: rotate_pdf(source, root / "rotated.pdf", degrees=90),
            repeats,
        )

        return {
            "pawdfVersion": __version__,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "pages": pages,
            "repeats": repeats,
            "benchmarks": {
                "splitTwoHalves": split_result,
                "mergeTwoHalves": merge_result,
                "rotateAllPages": rotate_result,
            },
        }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", default="benchmark-result.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.pages < 2 or args.repeats < 1:
        parser.error("--pages must be at least 2 and --repeats at least 1")
    result = run_benchmarks(args.pages, args.repeats)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Make a scanned PDF searchable without dropping pages on partial failure.

Each page is rendered and sent to Tesseract independently. A page that cannot
be rendered or recognised is copied from the original PDF unchanged, so the
output always preserves the source page count and order.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pawdf.core._shared import (
    ConversionError,
    EncryptedPdfError,
    ensure_exists,
    ensure_parent_dir,
)
from pawdf.core.ocr.tesseract import TesseractNotFoundError, find_tesseract

__all__ = ["DEFAULT_DPI", "OcrResult", "ocr_pdf"]

DEFAULT_DPI = 300
MIN_DPI = 150
MAX_DPI = 600
PAGE_TIMEOUT_SECONDS = 180


@dataclass
class OcrResult:
    output_path: Path
    pages_processed: int
    failed_pages: list[int]
    language: str


def _render_page(document, index: int, dpi: int, into: Path) -> Path:  # noqa: ANN001
    """Rasterise one page to a PNG that Tesseract can read."""
    page = document[index]
    try:
        image = page.render(scale=dpi / 72.0).to_pil()
    finally:
        page.close()

    path = into / f"page-{index:05d}.png"
    image.save(path)
    return path


def _assemble_output(source: Path, produced: dict[int, Path], total: int, out_path: Path) -> None:
    """Merge OCR pages and unchanged fallback pages in original order."""
    import pikepdf

    merged = pikepdf.new()
    try:
        with pikepdf.open(source) as original:
            for index in range(total):
                page_pdf = produced.get(index)
                if page_pdf is None:
                    merged.pages.append(original.pages[index])
                    continue

                with pikepdf.open(page_pdf) as part:
                    if not part.pages:
                        merged.pages.append(original.pages[index])
                    else:
                        merged.pages.append(part.pages[0])
        merged.save(out_path)
    finally:
        merged.close()


def _is_missing_language(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "failed loading language" in lowered
        or "please make sure" in lowered
        or "error opening data file" in lowered
    )


def ocr_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    language: str = "eng",
    dpi: int = DEFAULT_DPI,
) -> OcrResult:
    """Write a searchable copy while preserving every source page."""
    import pypdfium2 as pdfium

    if not MIN_DPI <= dpi <= MAX_DPI:
        raise ValueError(f"dpi must be between {MIN_DPI} and {MAX_DPI}, got {dpi}")

    binary = find_tesseract()
    if binary is None:
        raise TesseractNotFoundError()

    source = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    try:
        document = pdfium.PdfDocument(source)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise EncryptedPdfError(str(source)) from exc
        raise ConversionError(f"Could not open '{source}': {exc}") from exc

    failed: list[int] = []
    try:
        total = len(document)
        if total == 0:
            raise ConversionError("That PDF has no pages.")

        with tempfile.TemporaryDirectory(prefix="pawdf-ocr-") as tmp:
            workdir = Path(tmp)
            produced: dict[int, Path] = {}

            for index in range(total):
                try:
                    image = _render_page(document, index, dpi, workdir)
                except Exception:  # noqa: BLE001 - this page falls back unchanged
                    failed.append(index + 1)
                    continue

                stem = workdir / f"ocr-{index:05d}"
                try:
                    result = subprocess.run(
                        [str(binary), str(image), str(stem), "-l", language, "pdf"],
                        capture_output=True,
                        text=True,
                        timeout=PAGE_TIMEOUT_SECONDS,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    failed.append(index + 1)
                    continue
                except OSError as exc:
                    raise ConversionError(f"Could not run Tesseract: {exc}") from exc

                page_pdf = stem.with_suffix(".pdf")
                if result.returncode != 0 or not page_pdf.is_file():
                    detail = (result.stderr or result.stdout).strip()
                    if _is_missing_language(detail):
                        raise ConversionError(
                            f"Tesseract has no training data for '{language}'. "
                            "Install that language pack and try again."
                        )
                    failed.append(index + 1)
                    continue

                produced[index] = page_pdf

            _assemble_output(source, produced, total, out_path)
    except (ConversionError, EncryptedPdfError, ValueError):
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"OCR failed: {exc}") from exc
    finally:
        document.close()

    return OcrResult(
        output_path=out_path,
        pages_processed=total - len(failed),
        failed_pages=failed,
        language=language,
    )

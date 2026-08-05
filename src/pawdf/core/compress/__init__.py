"""Shrink a PDF: Ghostscript when it's available, a pure-Python pass otherwise.

The fallback matters more than it looks. It means Compress has no setup step
and no failure mode on a machine with nothing installed, which is the whole
point of an offline tool. See README.md for what each path actually does.

Standalone feature package.
"""

from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pawdf.core._shared import ConversionError, ensure_exists, ensure_parent_dir, open_pdf
from pawdf.core.compress.ghostscript import find_ghostscript

if TYPE_CHECKING:
    from pikepdf import Pdf

__all__ = ["DEFAULT_PRESET", "GS_PRESETS", "CompressResult", "compress_pdf"]

GS_PRESETS = ("screen", "ebook", "printer", "prepress")
DEFAULT_PRESET = "ebook"

GS_TIMEOUT_SECONDS = 300

# Fallback tuning. These cap resolution and quality rather than trying to
# reproduce Ghostscript's per-preset DPI targets, which aren't publicly
# specified in a form worth reverse-engineering.
FALLBACK_MAX_DIMENSION = 1600
FALLBACK_JPEG_QUALITY = 60


@dataclass
class CompressResult:
    output_path: Path
    method: str  # "ghostscript" or "fallback"
    original_size: int
    compressed_size: int

    @property
    def ratio(self) -> float:
        """Fraction of the original size saved, 0.0 if the input was empty."""
        if self.original_size <= 0:
            return 0.0
        return 1.0 - (self.compressed_size / self.original_size)


def compress_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    preset: str = DEFAULT_PRESET,
    force_fallback: bool = False,
) -> CompressResult:
    """Compress `input_path`, preferring Ghostscript.

    Falls back to a pure-Python pass when Ghostscript isn't installed, or when
    `force_fallback` is set. The returned `CompressResult` says which ran.
    """
    if preset not in GS_PRESETS:
        raise ValueError(f"Unknown preset '{preset}', expected one of {GS_PRESETS}")

    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    # Check the file opens (and isn't encrypted) with the same error types the
    # rest of the app uses, before handing off to either path.
    with open_pdf(p):
        pass

    original_size = p.stat().st_size
    gs_path = None if force_fallback else find_ghostscript()

    if gs_path is not None:
        _run_ghostscript(gs_path, p, out_path, preset)
        method = "ghostscript"
    else:
        _compress_with_fallback(p, out_path)
        method = "fallback"

    return CompressResult(out_path, method, original_size, out_path.stat().st_size)


def _run_ghostscript(gs_path: Path, input_path: Path, out_path: Path, preset: str) -> None:
    args = [
        str(gs_path),
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{preset}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        f"-sOutputFile={out_path}",
        str(input_path),
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=GS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError("Ghostscript timed out while compressing the PDF.") from exc
    except OSError as exc:
        raise ConversionError(f"Could not run Ghostscript at '{gs_path}': {exc}") from exc

    if result.returncode != 0 or not out_path.exists():
        detail = result.stderr.strip() or result.stdout.strip()
        raise ConversionError(f"Ghostscript failed: {detail}")


def _compress_with_fallback(input_path: Path, out_path: Path) -> None:
    from pikepdf import Pdf

    try:
        with Pdf.open(input_path) as pdf:
            _recompress_images_in_place(pdf)
            pdf.save(out_path, compress_streams=True, object_stream_mode=1)
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Fallback compression failed: {exc}") from exc


def _recompress_images_in_place(pdf: Pdf) -> None:
    """Downsample and re-encode embedded rasters, which is where the bytes are.

    Anything with a colorspace or filter Pillow can't round-trip is skipped
    rather than risking a corrupted image: a slightly larger output is a much
    better failure than an unreadable one.
    """
    from pikepdf import Name, PdfImage
    from PIL import Image

    for page in pdf.pages:
        for raw_image in page.get_images().values():
            try:
                pil_image = PdfImage(raw_image).as_pil_image()
            except Exception:  # noqa: BLE001 - unsupported colorspace/filter
                continue

            width, height = pil_image.size
            if max(width, height) > FALLBACK_MAX_DIMENSION:
                scale = FALLBACK_MAX_DIMENSION / max(width, height)
                pil_image = pil_image.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.LANCZOS,
                )
            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")

            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=FALLBACK_JPEG_QUALITY)

            raw_image.write(buf.getvalue(), filter=Name("/DCTDecode"))
            raw_image.Width = pil_image.width
            raw_image.Height = pil_image.height
            raw_image.BitsPerComponent = 8
            raw_image.ColorSpace = (
                Name("/DeviceGray") if pil_image.mode == "L" else Name("/DeviceRGB")
            )
            # These describe the image that was just replaced, not the new one.
            for stale_key in ("/SMask", "/Decode", "/Indexed"):
                if stale_key in raw_image:
                    del raw_image[stale_key]

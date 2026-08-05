"""Build a PDF from a sequence of images, without re-encoding when possible.

Written for this project on top of pikepdf rather than using `img2pdf`, which
does the same job well but is LGPL-3.0. Everything here is MPL-2.0/HPND at
worst, which keeps `core/` free of any library whose license attaches
conditions to how a downstream product is *distributed*. See README.md.

The interesting part is the passthrough path: a baseline JPEG is already
DCT-compressed, and PDF's `/DCTDecode` filter is that same codec, so the
original bytes can be embedded verbatim. No decode, no re-encode, no quality
loss, and the PDF is barely larger than the inputs.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pawdf.core._shared import ConversionError, ensure_exists, ensure_parent_dir

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

__all__ = ["PAGE_FIT_MODES", "images_to_pdf"]

# Page sizing strategies.
#   "image"  -> every page is exactly the size of its image
#   "a4"     -> every page is A4 portrait, image centred and scaled to fit
#   "letter" -> same, US Letter
PAGE_FIT_MODES = ("image", "a4", "letter")

_PAGE_SIZES_PT = {
    "a4": (595.276, 841.890),
    "letter": (612.0, 792.0),
}

_DEFAULT_DPI = 72.0
_POINTS_PER_INCH = 72.0

# EXIF tag 0x0112. Values 2..8 mean the pixels need flipping/rotating before
# they read the right way up.
_EXIF_ORIENTATION_TAG = 0x0112


@dataclass(frozen=True)
class _Embeddable:
    """An image reduced to exactly what a PDF image XObject needs."""

    data: bytes  # already encoded with `filter`
    filter_name: str  # "/DCTDecode" or "/FlateDecode"
    width: int
    height: int
    colorspace: str  # "/DeviceRGB" or "/DeviceGray"
    dpi: tuple[float, float]


def _dpi_of(image: PILImage) -> tuple[float, float]:
    """Pixel density from the file's own metadata, defaulting to 72.

    A bogus or zero DPI would make the page size infinite, so anything
    non-positive falls back to the default.
    """
    raw = image.info.get("dpi")
    if not raw:
        return (_DEFAULT_DPI, _DEFAULT_DPI)
    try:
        x_dpi, y_dpi = float(raw[0]), float(raw[1])
    except (TypeError, ValueError, IndexError):
        return (_DEFAULT_DPI, _DEFAULT_DPI)
    if x_dpi <= 0 or y_dpi <= 0:
        return (_DEFAULT_DPI, _DEFAULT_DPI)
    return (x_dpi, y_dpi)


def _needs_exif_rotation(image: PILImage) -> bool:
    """True if EXIF says the stored pixels aren't in display orientation.

    This matters for the passthrough decision: a photo straight off a phone is
    usually stored sideways with an EXIF tag telling viewers to rotate it. PDF
    has no equivalent tag, so such a file has to be decoded, rotated, and
    re-encoded rather than passed through.
    """
    exif = getattr(image, "getexif", lambda: None)()
    if not exif:
        return False
    return exif.get(_EXIF_ORIENTATION_TAG, 1) not in (0, 1)


def _try_jpeg_passthrough(path: Path, image: PILImage) -> _Embeddable | None:
    """Return the original JPEG bytes ready to embed, or None if this file
    can't be passed through untouched.

    Rejected cases, each for a concrete reason:
      - not a JPEG: nothing to pass through
      - progressive JPEG: `/DCTDecode` only accepts baseline, so a progressive
        file embedded verbatim renders as garbage in most PDF viewers
      - CMYK / anything not RGB or greyscale: needs an /Decode array and
        Adobe-inversion handling that isn't worth the complexity here
      - EXIF orientation: see _needs_exif_rotation
    """
    if image.format != "JPEG":
        return None
    if image.info.get("progressive") or image.info.get("progression"):
        return None
    if image.mode not in ("RGB", "L"):
        return None
    if _needs_exif_rotation(image):
        return None

    return _Embeddable(
        data=path.read_bytes(),
        filter_name="/DCTDecode",
        width=image.width,
        height=image.height,
        colorspace="/DeviceRGB" if image.mode == "RGB" else "/DeviceGray",
        dpi=_dpi_of(image),
    )


def _flate_encode(image: PILImage) -> _Embeddable:
    """Decode to raw samples and zlib them: lossless, works for any format.

    Used for PNG, WebP, TIFF, and for the JPEGs passthrough turned down.
    """
    from PIL import ImageOps

    dpi = _dpi_of(image)
    prepared = ImageOps.exif_transpose(image) or image

    if prepared.mode == "L":
        colorspace = "/DeviceGray"
    elif prepared.mode == "RGB":
        colorspace = "/DeviceRGB"
    else:
        # Palette, RGBA, CMYK, 1-bit, and friends all normalize to RGB.
        # Transparency is composited onto white, since a PDF page has no
        # meaningful "nothing" to show through to.
        if prepared.mode in ("RGBA", "LA", "PA"):
            from PIL import Image as _Image

            background = _Image.new("RGB", prepared.size, (255, 255, 255))
            background.paste(prepared, mask=prepared.convert("RGBA").split()[-1])
            prepared = background
        else:
            prepared = prepared.convert("RGB")
        colorspace = "/DeviceRGB"

    return _Embeddable(
        data=zlib.compress(prepared.tobytes(), level=6),
        filter_name="/FlateDecode",
        width=prepared.width,
        height=prepared.height,
        colorspace=colorspace,
        dpi=dpi,
    )


def _load(path: Path) -> _Embeddable:
    from PIL import Image

    try:
        with Image.open(path) as image:
            image.load()
            passthrough = _try_jpeg_passthrough(path, image)
            if passthrough is not None:
                return passthrough
            return _flate_encode(image)
    except ConversionError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Could not read image '{path}': {exc}") from exc


def _page_and_placement(
    item: _Embeddable, fit: str
) -> tuple[float, float, float, float, float, float]:
    """Return (page_w, page_h, draw_w, draw_h, offset_x, offset_y), in points."""
    x_dpi, y_dpi = item.dpi
    natural_w = item.width * _POINTS_PER_INCH / x_dpi
    natural_h = item.height * _POINTS_PER_INCH / y_dpi

    if fit == "image":
        return natural_w, natural_h, natural_w, natural_h, 0.0, 0.0

    page_w, page_h = _PAGE_SIZES_PT[fit]
    scale = min(page_w / natural_w, page_h / natural_h)
    draw_w, draw_h = natural_w * scale, natural_h * scale
    return page_w, page_h, draw_w, draw_h, (page_w - draw_w) / 2, (page_h - draw_h) / 2


def images_to_pdf(
    image_paths: list[str | Path],
    out_path: str | Path,
    *,
    fit: str = "image",
) -> Path:
    """Combine images (in order) into a single PDF, one image per page.

    `fit` is one of PAGE_FIT_MODES: "image" sizes each page to its image,
    "a4"/"letter" use a fixed page with the image centred and scaled to fit.

    Baseline RGB/greyscale JPEGs are embedded byte-for-byte with no
    re-encoding. Everything else is decoded and stored with lossless Flate
    compression, so no input is ever degraded.
    """
    import pikepdf

    if fit not in PAGE_FIT_MODES:
        raise ValueError(f"Unknown fit mode '{fit}', expected one of {PAGE_FIT_MODES}")
    if not image_paths:
        raise ValueError("image_paths must contain at least one image")

    out_path = ensure_parent_dir(out_path)
    resolved = [ensure_exists(p) for p in image_paths]

    pdf = pikepdf.new()
    try:
        for path in resolved:
            item = _load(path)
            page_w, page_h, draw_w, draw_h, off_x, off_y = _page_and_placement(item, fit)

            xobject = pikepdf.Stream(pdf, b"")
            xobject.write(item.data, filter=pikepdf.Name(item.filter_name))
            xobject.Type = pikepdf.Name("/XObject")
            xobject.Subtype = pikepdf.Name("/Image")
            xobject.Width = item.width
            xobject.Height = item.height
            xobject.ColorSpace = pikepdf.Name(item.colorspace)
            xobject.BitsPerComponent = 8

            # The image XObject is drawn into a 1x1 unit square, so the CTM
            # carries the real size: scale to the drawn size, translate to the
            # centring offset.
            content = (
                f"q\n{draw_w:.4f} 0 0 {draw_h:.4f} {off_x:.4f} {off_y:.4f} cm\n/Im0 Do\nQ\n"
            ).encode("ascii")

            page = pikepdf.Dictionary(
                Type=pikepdf.Name("/Page"),
                MediaBox=[0, 0, round(page_w, 4), round(page_h, 4)],
                Resources=pikepdf.Dictionary(
                    XObject=pikepdf.Dictionary(Im0=pdf.make_indirect(xobject))
                ),
                Contents=pdf.make_indirect(pikepdf.Stream(pdf, content)),
            )
            pdf.pages.append(pikepdf.Page(pdf.make_indirect(page)))

        pdf.save(out_path)
    except (ConversionError, ValueError):
        raise
    except Exception as exc:  # noqa: BLE001 - normalized for callers
        raise ConversionError(f"Could not build a PDF from those images: {exc}") from exc
    finally:
        pdf.close()

    return out_path

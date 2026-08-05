#!/usr/bin/env python3
"""Draw the Pawdf mark and write every icon file the app and installers need.

The icons are generated rather than committed as opaque binaries so the brand
is reproducible: change a number here, re-run, and every size updates
together. Run it after editing anything below.

    python scripts/generate_icons.py

Writes:
    src/pawdf/gui/resources/icons/app_icon.png   window + taskbar
    src/pawdf/gui/web/img/logo.png               the UI's own header mark
    packaging/icons/icon.png                     generic / README
    packaging/icons/icon.ico                     Windows .exe and installer
    packaging/icons/hicolor/<size>/apps/pawdf.png Linux icon theme, 9 sizes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Drawn at this size then downsampled, which is cheaper than antialiasing each
# shape by hand and gives noticeably cleaner curves at 32px.
SUPERSAMPLE = 8
BASE = 512

# A paw whose main pad is a document with a folded corner: the mark says
# "paw" at a glance and "PDF tool" on a second look.
#
# Red, because that is what "PDF" has meant on every desktop for twenty years
# and the mark should be legible as a document tool before it is legible as a
# cat. The paw is knocked out in near-white rather than drawn in dark ink --
# on a saturated red, dark-on-red goes muddy at small sizes while white holds
# its edges.
BG_TOP = (240, 90, 94)
BG_MID = (214, 55, 62)
BG_BOTTOM = (169, 30, 44)
FG = (255, 248, 247)

OUTPUT_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# Sizes the freedesktop icon theme spec expects for an application icon.
HICOLOR_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# Exactly three upper pads. Each is rendered by the same document-pad
# primitive as the main pad, only scaled down and gently splayed.
# (x offset, y centre, width, height, rotation)
TOE_LAYOUT = (
    (-0.220, 0.335, 0.145, 0.170, 18),
    (0.000, 0.270, 0.155, 0.180, 0),
    (0.220, 0.335, 0.145, 0.170, -18),
)


def _rounded_mask(size: int, radius_ratio: float):
    from PIL import Image, ImageDraw

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255)
    return mask


def _vertical_gradient(size: int, stops):
    """A multi-stop vertical gradient, one pixel wide, stretched to `size`."""
    from PIL import Image

    gradient = Image.new("RGB", (1, size))
    segments = len(stops) - 1
    for y in range(size):
        pos = (y / max(size - 1, 1)) * segments
        i = min(int(pos), segments - 1)
        f = pos - i
        a, b = stops[i], stops[i + 1]
        gradient.putpixel((0, y), tuple(round(a[c] + (b[c] - a[c]) * f) for c in range(3)))
    return gradient.resize((size, size), Image.NEAREST)


def _document_pad(width: float, height: float, angle: float = 0):
    """A document-shaped paw pad that can be scaled and rotated.

    The main pad and all three upper pads use this exact primitive. That keeps
    the upper shapes from looking like unrelated oval claws.
    """
    import math

    from PIL import Image, ImageDraw

    margin = int(max(width, height) * 0.42) + 4
    canvas_width = max(8, math.ceil(width) + margin * 2)
    canvas_height = max(8, math.ceil(height) + margin * 2)
    canvas = Image.new("L", (canvas_width, canvas_height), 0)
    draw = ImageDraw.Draw(canvas)

    left = (canvas_width - width) / 2
    top = (canvas_height - height) / 2
    right = left + width
    bottom = top + height
    radius = max(1, int(min(width, height) * 0.17))
    fold = width * 0.34

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=radius,
        fill=255,
    )
    draw.polygon(
        [
            (right - fold, top - 2),
            (right + 2, top - 2),
            (right + 2, top + fold),
        ],
        fill=0,
    )

    if angle:
        canvas = canvas.rotate(
            angle,
            resample=Image.BICUBIC,
            expand=False,
        )
    return canvas


def _paste_document_pad(
    mask,
    centre_x: float,
    centre_y: float,
    width: float,
    height: float,
    angle: float = 0,
) -> None:
    """Place one document pad by its visual centre."""
    pad = _document_pad(width, height, angle)
    x = round(centre_x - pad.width / 2)
    y = round(centre_y - pad.height / 2)
    mask.paste(255, (x, y), pad)


def _paw_mask(size: int):
    """The paw as an alpha mask, so the gradient shows through it untouched."""
    from PIL import Image

    mask = Image.new("L", (size, size), 0)
    cx = size / 2

    # --- main document pad ----------------------------------------------
    pad_width = size * 0.395
    pad_height = size * 0.330
    pad_top = size * 0.487
    _paste_document_pad(
        mask,
        cx,
        pad_top + pad_height / 2,
        pad_width,
        pad_height,
    )

    # --- three miniature document pads ---------------------------------
    # These are literally scaled instances of the main-pad primitive.
    for dx, cy_ratio, width_ratio, height_ratio, angle in TOE_LAYOUT:
        _paste_document_pad(
            mask,
            cx + dx * size,
            cy_ratio * size,
            width_ratio * size,
            height_ratio * size,
            angle,
        )

    return mask


def build_master():
    """The mark at high resolution, RGBA with rounded corners."""
    from PIL import Image, ImageDraw, ImageFilter

    big = BASE * SUPERSAMPLE
    canvas = _vertical_gradient(big, (BG_TOP, BG_MID, BG_BOTTOM)).convert("RGBA")

    # A gentle light from the top-left. Blurred hard, because an unblurred
    # shape reads as a stripe painted across the tile rather than as light.
    sheen = Image.new("L", (big, big), 0)
    ImageDraw.Draw(sheen).ellipse((-big * 0.5, -big * 0.7, big * 0.85, big * 0.5), fill=30)
    sheen = sheen.filter(ImageFilter.GaussianBlur(big * 0.09))
    canvas = Image.composite(Image.new("RGBA", (big, big), (255, 214, 210, 255)), canvas, sheen)

    paw = Image.new("RGBA", (big, big), (*FG, 255))
    canvas = Image.composite(paw, canvas, _paw_mask(big))

    canvas.putalpha(_rounded_mask(big, 0.235))
    return canvas.resize((BASE, BASE), Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT,
        help="Write the repository-relative icon tree below this directory.",
    )
    args = parser.parse_args(argv)
    output_root = args.output_root.resolve()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required: pip install Pillow", file=sys.stderr)
        return 1

    master = build_master()

    targets = [
        output_root / "src" / "pawdf" / "gui" / "resources" / "icons" / "app_icon.png",
        output_root / "src" / "pawdf" / "gui" / "web" / "img" / "logo.png",
        output_root / "packaging" / "icons" / "icon.png",
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        master.save(target)
        print(f"wrote {target.relative_to(output_root)} ({BASE}x{BASE})")

    # The freedesktop icon theme, at every size a desktop actually asks for.
    # Shipping only 256x256 means the panel, the dock, and the alt-tab switcher
    # each downscale it themselves, which looks soft - and some shells simply
    # skip a theme that has no size close to what they want.
    hicolor = output_root / "packaging" / "icons" / "hicolor"
    for size in HICOLOR_SIZES:
        target = hicolor / f"{size}x{size}" / "apps" / "pawdf.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        master.resize((size, size), Image.LANCZOS).save(target)
    print(f"wrote {len(HICOLOR_SIZES)} hicolor sizes: {', '.join(map(str, HICOLOR_SIZES))}")

    ico_path = output_root / "packaging" / "icons" / "icon.ico"
    master.save(ico_path, format="ICO", sizes=[(s, s) for s in OUTPUT_SIZES])
    print(f"wrote {ico_path.relative_to(output_root)} ({len(OUTPUT_SIZES)} sizes)")

    # .icns needs macOS tooling (iconutil) or an extra dependency, so the ICO
    # is what PyInstaller falls back to on macOS. Noted rather than silently
    # skipped.
    print("note: packaging/icons/icon.icns is not generated here; see packaging/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

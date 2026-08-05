# `stamp` - watermarks, page numbers, signatures

```python
from pawdf.core.stamp import add_watermark, add_page_numbers, stamp_image

add_watermark("in.pdf", "out.pdf", text="CONFIDENTIAL")
add_watermark(
    "in.pdf",
    "out.pdf",
    text="DRAFT",
    position="top-right",
    rotation=0,
    opacity=0.3,
    colour="#c0392b",
)

add_page_numbers("in.pdf", "out.pdf", template="Page {n} of {total}", skip_first=True)
add_page_numbers("in.pdf", "out.pdf", position="bottom-right", start_at=5)

stamp_image("in.pdf", "out.pdf", image_path="signature.png", position="bottom-right", width_pt=140)
```

## Three tools, one package

They are the same operation with different content: build a single-page PDF
the size of the target page, draw into it with reportlab, lay it over the
original with pikepdf. Three separate packages would mean three copies of that
machinery, and the copies would drift apart.

This is why the registry allows several tools per package.

## What they share

**Position** is the nine-point grid: `top-left` through `bottom-right`, plus
`center`. Anything not in the middle sits 36 points (half an inch) from the
edge.

**Page rotation is accounted for.** A page carrying `/Rotate 90` is drawn
turned, so the overlay is built at the *visible* dimensions. Without that a
stamp on a rotated page comes out sideways and clipped.

**Page ranges** use the same `"1-3,7"` syntax as everything else, and
`skip_first` is expressed as "return no drawing for page 0" rather than as a
special case in the loop.

## This is not redaction

Everything here composites *over* the page. The original content is still
underneath and comes back the moment the overlay is removed. A watermark
marks a document; it does not hide anything in it.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0`, `reportlab>=4.2`, `Pillow>=10.4` |
| Licenses pulled in | pikepdf: MPL-2.0 · reportlab: BSD-3-Clause · Pillow: HPND |

Pillow arrives through reportlab's `ImageReader`, and is only needed by
`stamp_image`.

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ValueError` for an unknown position, an out-of-range opacity, a malformed
colour, an empty watermark, or a `template` with no `{n}`.
`ConversionError` if the image cannot be read or the overlay cannot be applied.

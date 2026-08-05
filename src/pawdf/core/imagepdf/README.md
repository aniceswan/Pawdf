# `imagepdf` - images to PDF

```python
from pawdf.core.imagepdf import images_to_pdf

images_to_pdf(["a.jpg", "b.png"], "out.pdf")  # page = image size
images_to_pdf(["a.jpg"], "out.pdf", fit="a4")  # centred on A4
```

One image per page, in list order. `fit` is `"image"` (default), `"a4"`, or
`"letter"`.

## Lossless by construction

| Input | How it's stored | Re-encoded? |
|---|---|---|
| Baseline JPEG, RGB or greyscale, no EXIF rotation | original bytes as `/DCTDecode` | **no** - byte-for-byte |
| Progressive JPEG | decoded, `/FlateDecode` | pixels preserved |
| CMYK JPEG | converted to RGB, `/FlateDecode` | pixels preserved |
| PNG / WebP / TIFF / BMP | decoded, `/FlateDecode` | pixels preserved |
| RGBA / LA (transparency) | composited on white, `/FlateDecode` | pixels preserved |

Nothing is ever lossily re-compressed. The passthrough case matters because
PDF's `/DCTDecode` filter *is* JPEG: a baseline JPEG can be dropped into the
file untouched, so a PDF of photos ends up barely larger than the photos.

Progressive JPEGs are excluded deliberately - `/DCTDecode` only accepts
baseline, and a progressive file embedded verbatim renders as garbage in most
viewers. EXIF-rotated images are excluded because PDF has no orientation tag,
so the rotation has to be baked into the pixels.

Page size comes from each image's own DPI metadata (a 600px image tagged
300 dpi becomes a 2-inch page), defaulting to 72 dpi when absent.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0`, `Pillow>=10.4` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) · Pillow: HPND |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

**Why not `img2pdf`:** it's an excellent library that does this job, but it's
LGPL-3.0. Everything in `core/` is deliberately restricted to licenses that
place no conditions on how a downstream product is distributed, so this was
written in-project instead. Output is equivalent - measured on a test photo,
this produces a marginally smaller file than `img2pdf` for the same input.

## Errors

`ValueError` for an empty list or unknown `fit`. `ConversionError` if an
image can't be read or the PDF can't be assembled. `FileNotFoundError` for a
missing input.

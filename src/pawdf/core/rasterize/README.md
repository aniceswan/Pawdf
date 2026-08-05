# `rasterize` - PDF pages to images

```python
from pawdf.core.rasterize import pdf_to_images, render_page, page_count

pdf_to_images("in.pdf", "out/", dpi=300, fmt="png")  # -> [Path, ...]

page = render_page("in.pdf", 0, dpi=72)  # in-memory, for thumbnails
page.rgba, page.width, page.height  # raw RGBA bytes + size
```

`render_page` returns raw RGBA rather than an encoded file, so a UI can hand
the buffer straight to an image widget without a disk round trip.

Formats: `png`, `jpg`/`jpeg`, `webp`. DPI is validated (must be 1-1200) -
a negative scale makes PDFium fail obscurely and a huge one will try to
allocate absurd amounts of memory, so both are rejected up front.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pypdfium2>=4.30`, `Pillow>=10.4`, `pikepdf>=9.0` |
| Licenses pulled in | pypdfium2: BSD-3-Clause/Apache-2.0 (bundles Google's PDFium, BSD-3-Clause) · Pillow: HPND · pikepdf: MPL-2.0 |

`pikepdf` is only used for `page_count`, via `_shared`. Drop that one function
and the dependency goes with it.

**Why not PyMuPDF:** it is the more common choice and has a nicer API, but
Artifex dual-licenses it AGPL-3.0 or commercial, so importing it would force
copyleft onto anything built on top. pypdfium2 wraps the same renderer
Chromium ships under a permissive license.

## Errors

`EncryptedPdfError` for password-protected input, `ConversionError` for
corrupted input, `InvalidPageRangeError` for a bad page index, `ValueError`
for an unsupported format or out-of-bounds DPI.

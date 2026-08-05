# `rotate` - turn whole documents

```python
from pawdf.core.rotate import rotate_pdf

rotate_pdf("in.pdf", "out.pdf", degrees=90)  # every page
rotate_pdf("in.pdf", "out.pdf", degrees=180, pages="2-4,9")  # some pages
rotate_pdf("in.pdf", "out.pdf", degrees=90, absolute=True)  # set, don't add
```

Only 90, 180 and 270 are accepted. Those are the only rotations a PDF page can
express; anything else would be a transform of the page *content*, which is a
different operation entirely.

**Relative by default.** `degrees` is added to whatever rotation a page already
carries, which is what someone straightening a scan expects. `absolute=True`
sets it outright, which is how you normalise a document whose pages disagree
with each other.

## Why this is separate from `organize`

`organize` is a per-page editor: you look at thumbnails and act on individual
pages. This is the bulk case, and it is most of them - a document scanned
sideways needs all of it turned, and doing that through a page grid is a chore.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ValueError` for a rotation that is not a quarter turn,
`InvalidPageRangeError` for a bad range spec, plus the usual
`EncryptedPdfError` / `InvalidPdfError`.

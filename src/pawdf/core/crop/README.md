# `crop` - trim the visible area

```python
from pawdf.core.crop import crop_pdf, Margins

crop_pdf("in.pdf", "out.pdf", margins=Margins.uniform(36))  # half an inch off each edge
crop_pdf("in.pdf", "out.pdf", margins=Margins(left=20, top=50))
crop_pdf("in.pdf", "out.pdf", box=(50, 50, 400, 700), pages="1-3")
```

Measurements are PDF points, 72 to the inch, and `box` is
`(left, bottom, right, top)` from the bottom-left of the page.

## Cropping does not delete anything

It narrows the **CropBox**, which is the rectangle a viewer draws. The content
outside it is still in the file and comes back if the box is widened again.

That makes cropping safe to undo, and **useless for hiding sensitive
material**. Anything that must actually be gone needs redaction, which removes
content rather than hiding it, and is deliberately not what this does.

Requests are clamped to the page's existing box, so a margin larger than the
page produces a small page rather than a zero-area or inverted one. The floor
is 18 points a side: below roughly a quarter-inch, no viewer renders the
result usefully.

Pages with no CropBox of their own inherit the MediaBox, per the spec. That is
the common case, so it is handled rather than treated as an error.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ValueError` unless exactly one of `margins` or `box` is given,
`InvalidPageRangeError` for a bad range spec, plus the usual
`EncryptedPdfError` / `InvalidPdfError`.

# `merge` - concatenate PDFs

```python
from pawdf.core.merge import merge_pdfs

merge_pdfs(["a.pdf", "b.pdf", "c.pdf"], "merged.pdf")  # -> Path
```

Pages are appended in list order. Each source is opened and closed in turn, so
merging a long list doesn't hold every file open at once.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (plus its bundled QPDF: Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ValueError` on an empty list, `EncryptedPdfError` / `InvalidPdfError` from
`core/_shared/errors.py` if any input can't be read.

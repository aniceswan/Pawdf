# `split` - break one PDF into several

```python
from pawdf.core.split import split_by_ranges, split_every_n_pages

split_by_ranges("in.pdf", ["1-3", "4", "5-9"], "out/")  # -> [Path, Path, Path]
split_every_n_pages("in.pdf", 10, "out/")  # 10-page chunks
```

Output files are named `<stem>_part<N>.pdf`; pass `stem=` to override.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (plus its bundled QPDF: Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

Raises `InvalidPageRangeError` for a malformed or out-of-bounds range,
`EncryptedPdfError` for a password-protected input, and `InvalidPdfError` for
a corrupted one - all from `core/_shared/errors.py`.

# `organize` - rotate, reorder, and delete pages

```python
from pawdf.core.organize import apply_page_edits, delete_pages, reorder_pages, rotate_pages

rotate_pages("in.pdf", {0: 90, 2: 180}, "out.pdf")  # 0-indexed -> degrees
delete_pages("in.pdf", [0, 4], "out.pdf")
reorder_pages("in.pdf", [2, 0, 1], "out.pdf")  # omit to drop, repeat to duplicate

# All three at once, which is what the UI actually calls:
apply_page_edits("in.pdf", [(2, 90), (0, 0), (1, 270)], "out.pdf")
```

`apply_page_edits` takes `(original_index, added_rotation)` pairs **in output
order**, so a single call expresses a whole editing session and writes one
file instead of three.

Rotations are relative: they add to whatever rotation the page already had.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (plus its bundled QPDF: Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

To render page thumbnails for a UI, see the sibling `rasterize` package - it's
kept separate so this one doesn't drag in a rendering engine.

## Errors

`InvalidPageRangeError` for out-of-range indices, an empty edit list, or an
attempt to delete every page. `ValueError` for a rotation that isn't a
multiple of 90.

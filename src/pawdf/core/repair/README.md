# `repair` - recover a damaged PDF

```python
from pawdf.core.repair import repair_pdf

result = repair_pdf("damaged.pdf", "fixed.pdf")
result.pages_recovered  # 4
result.was_already_readable  # False -> it really was broken
result.is_now_clean  # True  -> the output needs no recovery
result.warnings  # what QPDF had to reconstruct
```

## How it works, and why the obvious version does not

QPDF rebuilds a missing or wrong cross-reference table by scanning the file
for object definitions. That covers the common damage: a truncated download, a
file written by something that crashed mid-save, a corrupt index over intact
page content.

Two traps this package exists to avoid:

1. **"Did it open?" is not a damage check.** QPDF performs that recovery
   silently on a normal open, so a plain open succeeds for a file that had to
   be rescued. Damage is detected with `attempt_recovery=False`, which is the
   only way to ask whether the file parses on its own terms.
2. **Re-saving a recovered document is not a repair.** The broken trailer
   comes straight through and the output still needs recovery to open.
   Measured: a truncated file re-saved that way still reported *"trailer
   dictionary lacks /Size key"*. So the recovered pages are copied into a
   document built from nothing, which has a correct cross-reference table by
   construction.

The result is verified after writing, not assumed: `is_now_clean` is the
answer to actually re-opening the output with recovery disabled.

What this cannot do is invent bytes that are gone. If page content was in the
lost part of a truncated file, those pages do not come back, which is why
`pages_recovered` is reported rather than hidden.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`InvalidPdfError` when nothing readable could be recovered,
`EncryptedPdfError` for a password-protected file - encrypted is not damaged,
unlock it first.

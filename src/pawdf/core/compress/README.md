# `compress` - shrink a PDF

```python
from pawdf.core.compress import compress_pdf

r = compress_pdf("in.pdf", "out.pdf", preset="ebook")
r.method  # "ghostscript" or "fallback"
r.ratio  # 0.62  -> 62% smaller
```

Presets: `screen`, `ebook` (default), `printer`, `prepress` - Ghostscript's
own `-dPDFSETTINGS` names. Pass `force_fallback=True` to skip Ghostscript even
when it's installed (this is how the tests stay deterministic).

## Two paths, always one that works

**Ghostscript**, if a binary is found. Best results by a wide margin.
Found via, in order: the `PAWDF_GS_PATH` env var, a copy installed into the
app's own data directory, the system `PATH`, then known Windows install
locations.

**Pure-Python fallback**, otherwise: re-saves with stream compression and
object streams, downsampling embedded rasters to 1600px on the long edge and
re-encoding them as quality-60 JPEG. Less aggressive than Ghostscript, but it
needs no setup and cannot be missing.

Images whose colorspace or filter Pillow can't round-trip are left untouched
rather than risked - a slightly larger file beats a corrupted one.

## Ghostscript and licensing

Ghostscript is **AGPL-3.0** and is never bundled, never committed, and never
imported. It is invoked as a **separate process**, which is an arm's-length
relationship in a way that linking a library is not, so a Pawdf build carries
no AGPL code.

If you bundle Ghostscript into a product derived from this, its AGPL terms
apply to that product. The fallback exists partly so you never have to.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0`, `Pillow>=10.4`, `platformdirs>=4.2` |
| Licenses pulled in | pikepdf: MPL-2.0 · Pillow: HPND · platformdirs: MIT |

Copy this directory and `core/_shared/`. `platformdirs` is only used to locate
the vendored-Ghostscript directory in `ghostscript.py`; drop that lookup and
the dependency goes with it.

## Errors

`ValueError` for an unknown preset. `ConversionError` if Ghostscript fails,
times out (300s), or the fallback can't write. `EncryptedPdfError` /
`InvalidPdfError` for unreadable input - checked before either path runs.

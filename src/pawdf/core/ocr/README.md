# `ocr` - make a scanned PDF searchable

```python
from pawdf.core.ocr import ocr_pdf
from pawdf.core.ocr.tesseract import find_tesseract, available_languages

result = ocr_pdf("scan.pdf", "searchable.pdf", language="eng")
result.pages_processed  # 12
result.failed_pages  # [] - pages with no text layer, still present in the output
```

## Why this is worth an external dependency

A scan is a picture of a page. Nothing in it can be searched, selected or
copied, and every text-based tool in this project comes back empty on one:
PDF to Word, PDF to Markdown, even find-in-page in a reader. OCR is the only
thing that changes that.

## How it works

Render each page with pypdfium2, hand the image to Tesseract in its `pdf`
output mode, concatenate the results with pikepdf.

Tesseract's PDF output keeps **the original picture visible and the recognised
text invisible behind it**. That is the important part: the page still looks
exactly like the scan, and the text is there for search and selection only.
Replacing the image with recognised text would mean trusting OCR's reading of
every character, and OCR is never that good.

## Tesseract is not bundled

Same pattern as Ghostscript in `core/compress/`, for a different reason.
Ghostscript is kept out because it is AGPL; Tesseract is Apache-2.0, so
licensing is not the issue. **Size is**: the engine plus one language's
training data is a few hundred megabytes, and adding that to every build to
serve the minority who scan documents is a poor trade.

So it is found at runtime, and `TesseractNotFoundError` carries the install
command for the platform in its message rather than saying "not found".

Found via `PAWDF_TESSERACT_PATH`, then the system PATH, then the usual install
locations on Windows and macOS.

## Resolution

300 dpi by default, clamped to 150-600. That is roughly what Tesseract's
models were trained around: lower loses accuracy quickly, higher costs time
and memory for very little in return.

## Failure is per page

A page Tesseract cannot read is reported in `failed_pages` and **still appears
in the output**, just without a text layer. Losing pages would be worse than
losing searchability on some of them. A missing language pack is different: it
fails identically on every page, so it is detected on the first one and raised
immediately instead of after grinding through the whole document.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pypdfium2>=4.30`, `Pillow>=10.4`, `pikepdf>=9.0` |
| External | `tesseract` (Apache-2.0), invoked as a subprocess |
| Licenses pulled in | pypdfium2: BSD-3-Clause/Apache-2.0 · Pillow: HPND · pikepdf: MPL-2.0 |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed;
in particular this does not import `rasterize` or `merge`, though it does a
little of each.

## Errors

`TesseractNotFoundError` with install instructions, `ConversionError` for a
missing language pack or a document no page of which could be read,
`EncryptedPdfError` for a locked file, `ValueError` for a DPI out of range.

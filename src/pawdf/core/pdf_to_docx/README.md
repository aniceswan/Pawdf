# `pdf_to_docx` - PDF to Word

```python
from pawdf.core.pdf_to_docx import pdf_to_docx

pdf_to_docx("in.pdf", "out.docx")
pdf_to_docx("in.pdf", "out.docx", start_page=0, end_page=3)  # 0-indexed, end exclusive
```

## How it works

```
PDF ──pypdfium2──> positioned glyphs ──extract.py──> DocumentIR ──render_docx.py──> .docx
```

| File | Role | Imports |
|---|---|---|
| `model.py` | The IR: pages, paragraphs, runs, images | nothing |
| `extract.py` | PDF → IR, inferring structure from geometry | pypdfium2 |
| `render_docx.py` | IR → .docx | python-docx |

The IR in the middle has no third-party imports, so each half is testable on
its own: you can build a `DocumentIR` in code and render it without a PDF, or
extract one and assert on it without writing a document.

## What has to be guessed

A `.docx` states its structure. A PDF does not - it stores glyphs at
coordinates. So everything structural here is inferred:

- **Lines** come from PDFium's own reading-order text stream.
- **Paragraphs** are lines merged across small vertical gaps; a gap larger
  than 0.65× the previous line's height starts a new one.
- **Headings** are lines whose font is meaningfully larger than the *whole
  document's* median body size (1.15× → H3, 1.4× → H2, 1.8× → H1). Measuring
  against the document rather than the page means a title page doesn't skew
  itself, and a document that uses one size throughout produces no headings
  at all instead of false ones.
- **Bold/italic** come from the font *name*, not the descriptor flags:
  PDFium reports Helvetica-Oblique with no italic bit set, so the name is what
  actually carries style in practice.
- **Centring** requires the line to be near the page centre *and* not start at
  the left margin, so a full-width line isn't centred by coincidence.

See `docs/conversion_fidelity.md` for the supported/unsupported list. Tables,
multi-column layouts, and lists are explicitly out of scope.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pypdfium2>=4.30`, `python-docx>=1.1` |
| Licenses pulled in | pypdfium2: BSD-3-Clause/Apache-2.0 · python-docx: MIT |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

**Why not `pdf2docx`:** it's MIT itself, but it hard-requires PyMuPDF, which
is AGPL-3.0/commercial and would drag copyleft into anything importing it.
This package exists to avoid that.

## Errors

`EncryptedPdfError` for password-protected input, `ConversionError` for
corrupted input or a failure anywhere in the pipeline.

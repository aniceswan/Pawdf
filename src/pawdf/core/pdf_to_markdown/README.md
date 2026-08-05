# `pdf_to_markdown` - PDF to Markdown

```python
from pawdf.core.pdf_to_markdown import pdf_to_markdown

pdf_to_markdown("report.pdf", "report.md")
pdf_to_markdown("report.pdf", "report.md", start_page=0, end_page=3)
pdf_to_markdown("report.pdf", "report.md", page_separators=True)
```

Images are written to a sibling `report_images/` folder and linked relatively,
so moving the pair keeps the links working.

## How it works

```
PDF --pypdfium2--> positioned glyphs --extract.py--> DocumentIR --render_markdown.py--> .md
```

| File | Role | Imports |
|---|---|---|
| `model.py` | The IR: pages, paragraphs, runs, images | nothing |
| `extract.py` | PDF -> IR, inferring structure from geometry | pypdfium2 |
| `render_markdown.py` | IR -> Markdown text | nothing |

The IR in the middle has no third-party imports, so each half is testable
alone: build a `DocumentIR` in code and check the Markdown without a PDF, or
extract one and assert on its shape without writing a file.

## What has to be guessed

A PDF has no headings, lists or emphasis to read back. It has glyphs at
coordinates. So:

- **Headings** are lines whose font is larger than the *whole document's*
  median body size (1.9x -> `#`, 1.55x -> `##`, 1.28x -> `###`, 1.12x ->
  `####`). Measuring against the document rather than the page means a title
  page is not compared with itself, and a document set in one size produces no
  headings instead of false ones.
- **Bold and italic** come from the font *name*: PDFium reports
  Helvetica-Oblique with no italic bit set, so the flags cannot be trusted.
- **Lists** are recognised from a leading bullet or `1.`, which is all a PDF
  keeps of one. The original marker is stripped, because Markdown supplies its
  own and leaving it produces `- - item`.
- **Paragraphs** are lines merged across small vertical gaps; the line break in
  a PDF is the column width, not the author's intent.

Two details that are easy to get wrong and are handled:

- A **numbered heading** ("1. Introduction") matches the list pattern exactly.
  Only body text is considered for lists, or the section number is thrown away.
- **Ordered lists always emit `1.`**. Markdown renumbers automatically, and
  hard-coding the original numbers breaks the moment an item moves.

Not attempted: tables, multi-column layouts, footnotes, and exact image
placement. See `docs/conversion_fidelity.md`.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pypdfium2>=4.30`, `pikepdf>=9.0` |
| Licenses pulled in | pypdfium2: BSD-3-Clause/Apache-2.0 · pikepdf: MPL-2.0 |

`pikepdf` arrives only through `_shared`; the extractor itself needs just
pypdfium2.

Copy this directory and `core/_shared/`. Nothing else in this repo is needed -
in particular this does **not** import `pdf_to_docx`, even though the two
solve the same first half. Features in this project stay independent so either
one can be lifted out alone.

## Errors

`EncryptedPdfError` for password-protected input, `ConversionError` for
corrupted input or a failure anywhere in the pipeline.

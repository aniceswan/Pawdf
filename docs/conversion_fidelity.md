# Word ↔ PDF conversion: what to expect

Both directions are **best-effort**, not a pixel-perfect match against real
Microsoft Word or LibreOffice output. This is a deliberate trade-off: the app
has no dependency on Word or LibreOffice being installed, so it can stay
100% offline and independent. If you need exact fidelity, use Word/LibreOffice
directly. This tool is aimed at everyday documents, not perfect reproduction.

## PDF → Word (custom converter)

Also built specifically for this project, in `core/pdf_to_docx/`:
`pypdfium2` extracts positioned text and font metrics, `extract.py` infers
structure from them into an intermediate representation, and
`render_docx.py` writes that out with `python-docx`. (The obvious library
here, `pdf2docx`, requires PyMuPDF, which is AGPL and would relicense the
whole project. See `CONTRIBUTING.md`.)

This direction is harder than Word → PDF and should be expected to be
rougher. A `.docx` states its own structure: this paragraph is Heading 2,
this is a list, these cells are a table. A PDF does not. It stores glyphs at
coordinates, so structure has to be **guessed back** from geometry and font
metrics.

**Supported**: text extraction with reading order, paragraphs (lines merged
across wraps, split on vertical gaps), heading detection (font size relative
to the document's median body size, mapped to Heading 1-3), bold and italic
(from font names), centred paragraphs, embedded raster images, page breaks.

**Explicitly not supported**:

- Tables. Cell content is extracted as ordinary paragraphs, and the grid is
  lost entirely.
- Multi-column layouts. Columns are read in PDFium's reading order, which
  may interleave them.
- Lists. Bullets and numbers survive as literal text characters, not as
  Word list formatting.
- Exact image placement. Images are appended after a page's text rather than
  positioned inline where they appeared.
- Fonts, colours, and precise sizes on headings. Heading text adopts Word's
  own heading styles instead.
- Scanned/image-only PDFs. There is no OCR, so a page with no text layer
  produces no text.

## Word → PDF (custom converter)

This direction is a converter built specifically for this project:
`python-docx` parses the `.docx` structure into an intermediate
representation (`core/docx_to_pdf/model.py`), which is then rendered to PDF
with `reportlab` (`core/docx_to_pdf/render_reportlab.py`).

**Supported**: paragraphs and run-level formatting (bold/italic/underline,
font size/color), heading/title styles, bulleted/numbered lists (list-type
detection is a heuristic based on style name and/or `numPr`, not a full read
of the numbering definition), plain tables, inline images, explicit manual
page breaks.

List ordering note: whether a list renders as bulleted or numbered is
inferred from the style name (e.g. "List Number"). Real numbering formats
defined in a document's numbering part aren't consulted, so an unusually
named or custom list style may render as the wrong kind.

**Explicitly not supported** (documents using these will lose that content
or render it approximately):

- Footnotes, endnotes, comments, tracked changes
- Floating text boxes, SmartArt, embedded OLE objects, charts
- Merged-cell tables (rowspan/colspan): merged regions are not detected,
  so content may repeat or the grid may look wrong
- Headers/footers of any kind, including page numbers: not implemented
- Exact line-break/pagination parity with Word: reportlab's flow engine
  doesn't replicate Word's layout engine 1:1
- Custom fonts not present on the system (falls back to a core PDF font)

If your use case depends on any of the above, this converter isn't the right
tool yet. Contributions extending the IR/renderer are welcome (see
`CONTRIBUTING.md`).


## PDF -> Markdown (custom converter)

`core/pdf_to_markdown/`. Same first half as PDF -> Word - pypdfium2 extracts
positioned text and font metrics, and structure is inferred from them - with a
Markdown renderer instead of a `.docx` one.

**Supported**: headings from relative font size, bold, italic, monospace,
bullet and numbered lists, paragraphs merged across wrapped lines, embedded
images written to a sibling folder and linked relatively.

**Not supported**: tables, multi-column layouts, footnotes, links, and exact
image placement. Ordered lists always emit `1.`, because Markdown renumbers
automatically and hard-coded numbers break the moment an item moves.

## Excel -> PDF (custom converter)

`core/xlsx_to_pdf/`. openpyxl reads the workbook, reportlab draws a table.

**Supported**: cell values with reader-friendly formatting (dates as
`YYYY-MM-DD`, booleans as `TRUE`/`FALSE`, whole floats without `.0`), the first
row as a header, per-column widths from the sheet, landscape for wide sheets,
one section per visible worksheet.

**Not supported**: charts, images, conditional formatting, cell fills and
borders, merged-cell layout, freeze panes, and Excel's own pagination.

Read with `data_only=True`, so **calculated cells show their last saved
value**. A workbook written by something that never calculated its formulas
has no cached values, and those cells come out empty.

Sheets are capped at 20,000 cells and 40 columns; past that the output is
truncated and says so on the page.

## PowerPoint -> PDF (custom converter)

`core/pptx_to_pdf/`. python-pptx reads the deck, reportlab draws it, one slide
per page at the deck's own aspect ratio.

**Supported**: text frames at their stated position and size, bold, italic,
explicit font size and colour, paragraph alignment, outline indent level, and
pictures.

**Not supported**: theme inheritance, gradients and shape fills, effects,
transitions, animations, SmartArt, charts, tables, speaker notes.

The inheritance gap is the significant one: python-pptx returns `None` for
anything inherited from a layout or master, and resolving that chain is a
project of its own. Runs with no explicit size fall back to 18pt, so text
stays on the page even when its styling does not survive.

## OCR (Tesseract)

`core/ocr/`. Not a conversion so much as an addition: the recognised text is
placed **invisibly behind the original image**, so the page still looks
exactly like the scan and becomes searchable. Accuracy is Tesseract's, and
depends heavily on scan quality and the right language pack.


### PowerPoint warnings

Pawdf reports every skipped or partially reproduced shape after conversion. The output remains available for review, but shape loss is never silently presented as a fully faithful conversion.

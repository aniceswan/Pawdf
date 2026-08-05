# `xlsx_to_pdf` - Excel to PDF

```python
from pawdf.core.xlsx_to_pdf import xlsx_to_pdf

xlsx_to_pdf("book.xlsx", "book.pdf")
xlsx_to_pdf("book.xlsx", "book.pdf", landscape_wide_sheets=False, show_gridlines=False)
```

One section per visible worksheet, each starting on a new page.

## Supported

Cell values, the first row treated as a header, per-column widths taken from
the sheet, and sensible formatting: dates as `YYYY-MM-DD`, booleans as
`TRUE`/`FALSE`, whole-number floats without a trailing `.0`.

Read with `data_only=True`, so calculated cells show **their last computed
value**. Without that every formula cell would render as `=SUM(A1:A9)`. The
consequence is worth knowing: a workbook saved by something that never
calculated the formulas has no cached values, and those cells come out empty.

Sheets wider than six columns turn landscape, which is the difference between
a readable table and one clipped at the margin.

## Not supported

Charts, images, conditional formatting, cell fills and borders, freeze panes,
merged-cell layout, and Excel's own pagination. This draws a grid of values,
not a reproduction of the workbook.

## Limits, and why they exist

A sheet is capped at 20,000 cells and 40 columns. A spreadsheet with a hundred
thousand rows is not a document, and laying one out means reportlab building a
flowable per cell until memory runs out. Past the cap the output is truncated
and **says so on the page**, rather than failing halfway through or quietly
losing rows.

`max_row` is not trusted either: openpyxl counts cells that were merely
formatted or visited, so a lightly-touched sheet claims thousands of empty
rows. The used range is found by scanning for real values.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `openpyxl>=3.1`, `reportlab>=4.2` |
| Licenses pulled in | openpyxl: MIT · reportlab: BSD-3-Clause |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ConversionError` for an unreadable workbook, one with no visible sheets, or
any failure during rendering.

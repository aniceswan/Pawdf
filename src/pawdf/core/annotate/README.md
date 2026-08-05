# `annotate` - draw notes and marks on a PDF

```python
from pawdf.core.annotate import annotate_pdf, add_note, Highlight, Rectangle, TextNote

add_note("in.pdf", "out.pdf", text="Reviewed 4 Aug", page=0, x=72, y=740)

annotate_pdf(
    "in.pdf",
    "out.pdf",
    [
        Highlight(x=70, y=600, width=300),
        Rectangle(x=60, y=500, width=320, height=90, colour="#1e88e5"),
        TextNote(text="check this figure", x=60, y=480, page=1),
    ],
)
```

Coordinates are PDF points from the **bottom-left** of the page, which is the
coordinate system the file itself uses. Each mark carries its own `page`, so
one call annotates the whole document.

## This is the additive half of "edit a PDF"

Text boxes, boxes, ellipses, lines and highlights placed where you choose.
That half is tractable.

Editing text that is **already** in the document is not here and is not
planned. A PDF stores positioned glyphs against subsetted embedded fonts, so
changing one word means re-encoding the font, reflowing the line, and hoping
the rest of the page still fits. Tools that advertise "edit PDF" mostly do
what this does: add a layer on top.

## Highlight is not redaction

`Highlight` is translucent by design - yellow at 40% - so the text underneath
stays readable, which is the point of a highlight. Nothing here removes
content. A filled black rectangle would still have the text under it, and
anyone can select it.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0`, `reportlab>=4.2` |
| Licenses pulled in | pikepdf: MPL-2.0 · reportlab: BSD-3-Clause |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ValueError` for an empty mark list, a page index outside the document, or a
malformed colour. `ConversionError` for anything else that goes wrong while
drawing.

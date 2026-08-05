# `pptx_to_pdf` - PowerPoint to PDF

```python
from pawdf.core.pptx_to_pdf import pptx_to_pdf

pptx_to_pdf("deck.pptx", "deck.pdf")
```

One slide per page, at the deck's own aspect ratio: a 16:9 deck produces 16:9
pages, a 4:3 deck produces 4:3.

## Supported

Text frames drawn at the position and size the file gives them, with bold,
italic, explicit font size, explicit colour, paragraph alignment and outline
indent level. Pictures are placed at their stated position and size.

## Not supported

Theme inheritance, gradients and shape fills, effects, transitions,
animations, SmartArt, charts, tables, and speaker notes.

The inheritance gap is the one worth understanding: python-pptx returns `None`
for anything a slide inherits from its layout or master, and walking that
chain properly is a project of its own. Runs with no explicit size fall back to
18pt rather than vanishing, so the text stays on the page even when its
styling does not survive.

## One shape never costs the whole deck

Each shape is drawn inside its own try/except. A slide missing a decoration is
still useful; an export that failed because of one unrenderable shape is not.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `python-pptx>=1.0`, `reportlab>=4.2`, `Pillow>=10.4` |
| Licenses pulled in | python-pptx: MIT · reportlab: BSD-3-Clause · Pillow: HPND |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`ConversionError` for an unreadable presentation or a failure during
rendering.

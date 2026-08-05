# `docx_to_pdf` - Word to PDF

```python
from pawdf.core.docx_to_pdf import docx_to_pdf

docx_to_pdf("in.docx", "out.pdf")
```

No Word, no LibreOffice, no headless office process. Best-effort fidelity by
design - that independence is the trade.

## How it works

```
.docx ──python-docx──> parser.py ──> DocumentIR ──render_reportlab.py──> PDF
```

| File | Role | Imports |
|---|---|---|
| `model.py` | The IR: paragraphs, runs, lists, tables, images, breaks | nothing |
| `parser.py` | .docx → IR | python-docx |
| `styles.py` | Word style *names* → reportlab `ParagraphStyle` | reportlab |
| `render_reportlab.py` | IR → PDF | reportlab |

`parser.py` walks the document body in true document order rather than using
python-docx's separate `.paragraphs` / `.tables` lists, which would lose the
interleaving between them.

## Supported

Paragraphs and run formatting (bold, italic, underline, size, colour),
heading and title styles, bulleted and numbered lists, plain tables, inline
images, explicit page breaks.

List type is inferred from the style name plus `numPr`, because real-world
`.docx` files disagree about which one they use: Word writes explicit
numbering XML, while python-docx's own template sets only `pStyle`. The
numbering part itself isn't parsed, so an unusually named custom list style
can render as the wrong kind.

Not supported: footnotes, headers/footers, text boxes, SmartArt, charts,
merged table cells, tracked changes, and exact pagination parity with Word.
See `docs/conversion_fidelity.md`.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `python-docx>=1.1`, `reportlab>=4.2`, `Pillow>=10.4` |
| Licenses pulled in | python-docx: MIT · reportlab: BSD-3-Clause · Pillow: HPND |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

**Why reportlab and not WeasyPrint:** reportlab is pure Python plus a C
extension, with no system Cairo/Pango to find at runtime. That matters a lot
for shipping a single bundled binary across three operating systems.

## Errors

`ConversionError` wrapping anything that goes wrong, `FileNotFoundError` for
a missing input.

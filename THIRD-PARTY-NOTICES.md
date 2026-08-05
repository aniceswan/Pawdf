# Third-party notices

Pawdf's own code is [MIT](LICENSE). The libraries below keep their own
licenses. If you ship Pawdf, or anything built from it, this is the list you
need to satisfy.

## The short version

**Taking `core/` only** (any PDF feature, without the desktop UI): every
dependency is MIT, BSD-3-Clause, Apache-2.0, HPND, or MPL-2.0. **Attribution
is your entire obligation.** Nothing there places conditions on how you
distribute your product, or requires you to publish anything.

**Shipping the desktop app**: adds PySide6, which is **LGPL-3.0**. Still fine
for closed-source products, but it attaches conditions to your *distribution* -
see below.

## core/ dependencies - no copyleft-by-linking

| Library | License | Used by |
|---|---|---|
| [pikepdf](https://github.com/pikepdf/pikepdf) | **MPL-2.0** (bundles QPDF, Apache-2.0) | PDF editing, protection, overlays, forms and image-PDF output |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | BSD-3-Clause / Apache-2.0 (bundles Google's PDFium, BSD-3-Clause) | rasterize, OCR, PDF to Word and PDF to Markdown |
| [reportlab](https://www.reportlab.com/) | BSD-3-Clause | document conversion, annotations, stamps and form fixtures |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | pdf_to_docx, docx_to_pdf |
| [Pillow](https://python-pillow.org/) | HPND (MIT-CMU) | rasterize, images, compression, signatures and Office conversion |
| [platformdirs](https://github.com/tox-dev/platformdirs) | MIT | compress (locating a managed Ghostscript) |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | MIT | xlsx_to_pdf |
| [python-pptx](https://github.com/scanny/python-pptx) | MIT | pptx_to_pdf |
| [lxml](https://lxml.de/) | BSD-3-Clause | transitive, via python-docx, openpyxl and python-pptx |

MPL-2.0 is **file-level** copyleft: if you modify pikepdf's *own source files*,
those files stay MPL and their source must be available. Simply using pikepdf
triggers nothing, and your code is never affected.

## GUI dependency

| Library | License | Used by |
|---|---|---|
| [PySide6](https://wiki.qt.io/Qt_for_Python) (incl. `shiboken6`, Qt) | **LGPL-3.0** | the desktop window, WebEngine view, native file dialogs |

## Bundled assets

| Asset | License |
|---|---|
| [Inter](https://github.com/rsms/inter) (`gui/web/fonts/InterVariable.ttf`) | SIL Open Font License 1.1 |
| [Noto Serif](https://github.com/notofonts/latin-greek-cyrillic) (`gui/web/fonts/NotoSerif-Variable.ttf`) | SIL Open Font License 1.1 |

Full licence text, covering both, is in `src/pawdf/gui/web/fonts/OFL.txt`.

The OFL permits bundling and redistribution, including in commercial products.
Its one restriction is that a font must not be sold on its own.

## Not bundled

**Tesseract** (Apache-2.0) provides OCR and **is never shipped with Pawdf**.
It is invoked as a separate process when installed, and the OCR tool explains
how to install it when it is not. Apache-2.0 would allow bundling; it is left
out because the engine plus one language's training data is a few hundred
megabytes.

**Ghostscript** (AGPL-3.0) improves Compress but **is never shipped with
Pawdf**. It is invoked as a **separate process**, only if you installed it
yourself, and Compress falls back to a pure-Python path when it's absent. A
Pawdf build therefore contains no AGPL code.

If you bundle Ghostscript into a derived product, its AGPL terms apply to that
product. Don't, unless you mean to.

## What you actually have to do

**If you ship binaries of the full app:**

1. Include this file and [LICENSE](LICENSE), plus the license texts of the
   libraries above. Most are attribution-only: keep the copyright notice.
2. **For PySide6 (LGPL-3.0)**, a recipient must be able to substitute their own
   build of the library. The supplied PyInstaller config uses `--onedir`
   partly for this: the Qt shared objects sit as ordinary replaceable files in
   `dist/pawdf/` rather than inside a self-extracting executable. Also state
   somewhere user-visible that the product uses PySide6/Qt under LGPL-3.0, and
   offer its source - a link upstream is normally enough if you haven't
   modified it.
3. **If you modify pikepdf's own source (MPL-2.0)**, those modified files stay
   MPL-2.0 and their source must be available. Your files are unaffected.
4. **If you modify PySide6 or Qt themselves**, those modifications are LGPL-3.0
   and must be published. Again: their code, not yours.

**If you only take `core/` into your own project:** keep the copyright notices
for the libraries you actually use, and you're done. There is no LGPL
obligation, because there's no LGPL dependency.

**If you only use Pawdf's source in your own project without redistributing
builds:** MIT applies to Pawdf's code, so keep the copyright notice.

This summary is written to be practical, not to be legal advice. If the stakes
are high for you, have a lawyer read the actual license texts.


## Distribution layout

Official binary builds place this notice and Pawdf's MIT license under `legal/`, with installed third-party license and package metadata under `legal/third-party/`. The build fails if the main legal files cannot be collected.

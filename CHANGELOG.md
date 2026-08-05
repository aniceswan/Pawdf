# Changelog

All notable changes to this project are documented here.

## [0.2.1] - 2026-08-06

### Fixed

- **Linux AppImage no longer aborts on startup on some systems.** The
  published v0.2.0 asset bundled its own `libstdc++.so.6` (GLIBCXX up to
  3.4.30, from the `ubuntu-22.04` build runner), which shadowed the host's
  own copy at runtime. When the software-rendering GL fallback path tried to
  dlopen a system library that needed a newer GLIBCXX symbol (observed via
  `libSPIRV-Tools.so`, pulled in through llvmpipe/lavapipe), the process
  aborted before a window ever appeared, instead of degrading to software
  rendering as intended. Reproduced against the actual published asset and
  confirmed fixed by excluding the bundled `libstdc++.so*` from the Linux
  build, so the dynamic linker falls through to the host's own copy.
- `install.sh` now exits with a clear message on Linux aarch64 instead of
  attempting to download an AppImage asset that was deferred from v0.2.0 and
  does not exist.
- `scripts/smoke_packaged.py` gained `gui_liveness()`, which launches the
  packaged binary with no arguments and confirms it survives past
  Qt/WebEngine startup - the CLI-only checks that ran before it exited
  before `QApplication` was ever constructed, so none of them could have
  caught either of the above.

## [0.2.0] - 2026-08-05

### Added

<!-- PAWDF_DOC_SYNC_2026_08:changelog -->

- **Code-review reliability fixes.** Excel export now inspects only bounded
  materialized cells and caches worksheet bounds, successful writes remain
  successful when optional result shaping fails, concurrent jobs reserve
  distinct output names, and executable tests cover feature wiring plus
  split/Arrange behavior in the real WebEngine page.


- **Release-based installation and size-optimized runtime.** End users install
  checksummed AppImage, Inno Setup, or DMG releases without Git, Python, pip,
  or local builds. Five hosted targets fresh-install the final artifact,
  import all 22 tools, launch the installed GUI, and enforce runtime content
  and size budgets. Developer dependencies remain available only through
  `.[dev]`.


- **Repository-native three-OS QA launcher.** `scripts/test_all_os.sh` snapshots
  the current working tree into an isolated temporary branch, runs Ubuntu,
  Windows and macOS hosted tests/builds/smokes, downloads the reports, and
  never commits, resets or stashes the developer's active branch.
- **Documentation screenshot generation and visual contracts.** The main
  README screenshot is captured from the current source application, while
  tests pin the three-pad brand geometry, upright open-tool state and expanded
  responsive hero.

- **Central resource limits and archive-bomb protection.** Every core input now receives size checks; PDFs, images and Office ZIP containers receive format-specific limits before parsing.
- **Session recovery and private diagnostics.** The tray survives a restart, missing files are discarded, logs rotate locally, and exported diagnostic ZIPs contain no opened documents.
- **Production release metadata.** Packaged executables run a `--version` smoke test and release artifacts include SHA-256 checksums and a CycloneDX SBOM.
- **Real-world QA infrastructure.** Added a private corpus verifier, repeatable core benchmark, reduced-motion/focus accessibility rules, and Linux, Windows and macOS manual checklists.

- **Fourteen new tools, taking the total to 22.** Rotate, Crop, Repair,
  Protect, Unlock, Watermark, Sign, Page numbers, PDF to Markdown, Excel to
  PDF, PowerPoint to PDF, OCR, Fill form and Annotate.
- **Tools are grouped into five categories** (Organise, Convert, Optimise,
  Secure, Annotate). The ring holds categories and expands one at a time,
  because eight tools fit in a circle and twenty-two do not, and `Ctrl+K`
  searches every tool by name. A package may back several tools, so
  `core/stamp/` serves Watermark, Sign and Page numbers from one overlay
  engine rather than three copies of it.
- **OCR** via Tesseract, found at runtime and never bundled, following the
  Ghostscript pattern. Recognised text goes invisibly behind the original
  image, so a scan stays looking like a scan and becomes searchable. Settings
  gained a Tesseract row beside the Ghostscript one.
- **Excel and PowerPoint converters** on openpyxl and python-pptx, both MIT,
  keeping `core/` free of copyleft.

- **Radial UI.** A central button surrounded by a ring of tools, replacing the
  sidebar and its nine pages. The ring orbits slowly (110s per revolution) and
  pauses on hover so nothing drifts out from under a click; each node
  counter-rotates so labels never tilt. Staggered spring animation on open,
  shared-element transition into each tool, ambient aurora background, dark and
  light themes. Number keys `1`-`8` jump to a tool; `Esc` steps back out.
- **A colour per tool**, declared in `core/registry.py` and used for each
  node's icon, tint, and hover glow, so the ring is learned by position and
  hue instead of by reading every label.
- **Files first, then the tool.** The centre button adds files rather than
  toggling the menu, and the tools stay disabled until there is something to
  act on. One shared selection feeds every tool, so switching between them
  keeps your files - and the ring shows, before you click, which tools can
  open what you added. Choosing one slides the workspace left and opens that
  tool's options on the right, so the files stay visible and reorderable.
- **Arrange: a drop indicator and Move buttons.** Dragging pages already
  worked, but the only feedback was a highlight on the page you were over,
  which left you guessing which side the page would land on. There is now a
  line in the gap where it will go, and which half of a page you hover decides
  before or after. Selected pages can also be nudged one slot with
  Move left / Move right, which is easier than a precise drag for a single step.
- **Page previews.** Every single-PDF tool shows a thumbnail strip of the
  document, and any page can be opened full size with arrow-key navigation.
  In Split, clicking pages builds the range string and typing a range
  highlights the pages back, so ranges no longer have to be picked from
  memory. One shared thumbnail store backs both the preview and Arrange, so a
  document renders once no matter how many tools look at it.
- **F11 full screen**, and the window now remembers its size and position
  between launches. The tool ring scales with the viewport instead of sitting
  at a fixed size in the middle of a maximised window.
- **Windows installer scripts** (`install_windows.ps1` / `uninstall_windows.ps1`),
  and a CI job that builds the Windows bundle and Inno Setup installer on every
  push. The app also claims an explicit AppUserModelID on Windows, without
  which a pinned taskbar shortcut never lights up when the app is running.
- **A file tray** with ordering controls, which is what Merge and Images to
  PDF need; those tools no longer carry their own private file lists.
- **Collision-safe output plus Save and Continue actions.** Every result is first written to the
  user's Downloads folder under a name derived from the input, and nothing is
  ever overwritten - a colliding name gets a numbered variant. `PAWDF_OUTPUT_DIR`
  overrides the destination, which is also what keeps the test suite out of a
  developer's real Downloads folder.
- **A hero panel** on the left stating what the app is, with the tool ring
  moved to the right. Display type is set in Noto Serif (SIL OFL, bundled): a
  tool for documents should be titled in a serif.
- **`core/registry.py`**, describing every feature without importing any of
  them. The UI's tool ring is generated from it, so adding a feature is a
  registry change rather than a markup change. Importing the registry pulls in
  no PDF library at all (asserted by a test).
- **Per-feature READMEs and extras.** Every `core/<feature>/` documents exactly
  what it depends on and which licenses that carries, and
  `pip install pawdf[split]` installs one feature's dependencies alone.
- **`tests/test_architecture.py`**, enforcing the structural promises: no GUI
  import in `core/`, no cross-feature import, a README per feature, `_shared`
  under 300 lines, registry/extras agreement, and no copyleft dependency
  reaching `core/`.
- **WebP** output for PDF → Images, and a `fit` option (`image`/`a4`/`letter`)
  for Images → PDF.
- "Show in folder" on every success message.
- `scripts/generate_icons.py`: the app icons are generated from code, and CI
  fails if the committed files drift from it.

### Changed

- **Relicensing finished: `core/` now has zero copyleft dependencies.**
  `img2pdf` (LGPL-3.0) was the last one, and is replaced by `core/imagepdf/`,
  written for this project on pikepdf. Baseline RGB and greyscale JPEGs are
  embedded byte-for-byte as `/DCTDecode` with no re-encoding; everything else
  is stored losslessly with Flate. Measured output is marginally smaller than
  `img2pdf` for the same input. Anyone lifting a `core/` feature into a
  closed-source product now owes attribution and nothing else.
- **Qt is no longer a base dependency.** `pip install pawdf` now installs
  `core/` and nothing else, so a plain install has no LGPL dependency in the
  tree at all; the desktop app is `pip install "pawdf[gui]"`. `python -m pawdf`
  explains this if PySide6 is missing rather than failing with a traceback. A
  test pins it, because moving PySide6 back into base dependencies would
  silently break the promise without breaking any import.
- **`core/` is organized into self-contained feature packages** plus a
  centralized `_shared/` containing validated limits and common helpers. `errors.py`, `utils.py`, `pdf_io.py`, `split.py`,
  `merge.py`, `pages.py`, `images.py`, `compress.py` and the two
  `ghostscript_*.py` modules are gone; their contents live in
  `core/<feature>/`. `pages` is now `organize`, `images` is split into
  `rasterize` and `imagepdf`, and Ghostscript handling moved inside
  `core/compress/`.
- `PdfToolkitError` renamed to `PawdfError`.
- **Generated three-pad application mark.** The large document-shaped main
  pad now has exactly three smaller copies of the same folded-page primitive
  above it. Every PNG, Windows ICO and Linux hicolor size is still generated
  reproducibly by `scripts/generate_icons.py`.
- **Expanded responsive landing hero.** The message, supporting copy and CTAs
  use more of the available desktop canvas while retaining laptop, tablet and
  narrow-window breakpoints.
- **Light is now the default theme**, with dark available from the toolbar.
- "Organize" is now called **Arrange** in the UI. The feature id stays
  `organize`, because it names the package directory, the extras group and the
  PyInstaller hidden import.
- Tool tiles keep their full colour even when unavailable, marked with a
  dashed edge and a corner dot instead of being drained of colour. Dimming
  them was washing out the ring in the state a new user sees first.
- Em dashes removed from all prose and UI text.
- **Tool tiles are saturated colour**, not a tint behind a coloured icon. Red
  is reserved for the Add-files button, so no tool tile uses it.
- **Restrained, document-tool palette.** The amber-and-violet scheme read as
  a consumer app rather than something you do work in. Replaced with graphite
  neutrals and a single red accent; the drifting three-colour aurora is down
  to two near-neutral washes; per-tool colours are a narrow muted spread
  (clay, ochre, teal, steel, indigo) at low saturation instead of a full
  rainbow; corner radii and shadow bloom reduced throughout.
- PyInstaller bundle excludes unused Qt modules (Quick3D, Charts,
  Multimedia, and others).

### Fixed

- **Tool tiles no longer freeze at a visible angle after selection.** Opening
  a tool now resets the orbit and counter-rotation layers to the same canonical
  transform instead of pausing two animations at slightly different frames.

- **OCR preserves failed pages.** A render, timeout, or recognition failure now
  copies that source page unchanged into the output instead of silently
  shortening and reordering the document.
- **Fill form generates form appearances before flattening.** Flattening now
  fails closed if visual values cannot be generated, preserves unrelated
  annotations, aggregates radio groups, and supports choice fields.
- **Background conversions finish before shutdown.** Worker threads exit from
  their own thread and close waits without issuing a mid-write quit request.
- **Ghostscript installer SHA-256 verification.** The pinned official Windows
  installer is verified before execution and deleted on any mismatch.
- **PowerPoint fidelity warnings.** Unsupported or partially reproduced shapes
  are reported to the GUI and Python callers instead of being discarded
  silently.
- **Distribution legal material.** Binary bundles now contain Pawdf's license,
  third-party notices, and license files collected from installed packages.
- **Release contracts.** Version, tool/package counts, dependency extras,
  workflows, legal files, and American-English category labels are enforced by
  tests.


- **The app failed to start for anyone who had ever maximized it.** Restoring
  the saved window state ran partway through the constructor, and showing a
  maximized window fires `showEvent()` immediately, against an object whose
  drag-and-drop attributes did not exist yet. Geometry is now restored last,
  and there is a regression test that seeds a maximized state and builds the
  window.
- The tool-ring test polled for "did the page reply" rather than "is the ring
  built", so it passed or failed depending on how long the rest of the page
  took to load.

- **Drag-and-drop worked on no page at all.** The webview UI read `file.path`,
  which is a property Electron adds by patching Blink - standard Chromium,
  which QtWebEngine embeds, never exposes filesystem paths to page content, so
  every drop silently fell through to an error message. Drops are now handled
  natively in Qt (`gui/dnd.py`), which has the real URLs, and the page
  suppresses the default so Chromium can't navigate away to the dropped file.
- **Organize could not open a second document.** Its drop zone was hidden
  after the first load and never restored, so changing file meant restarting
  the app. There's now a "Start over" action, and the zone stays available.
- **Thumbnails could mislabel pages, and could hang the grid forever.** Replies
  were assumed to arrive in request order and appended as they came; they now
  carry their page index and land in a pre-allocated slot. Rendering also ran
  on the UI thread and raised on failure, which meant a bad page produced no
  reply at all and left the grid loading indefinitely - it now runs on a worker
  and always answers, with an error marker for pages that fail.
- **Concurrent thumbnail rendering crashed the process.** PDFium is not
  thread-safe and aborts rather than raising, so `core/rasterize` now
  serializes access behind a lock.
- **Background jobs were never released.** The bridge appended every
  `(thread, worker)` pair to a list that nothing ever removed from, so each
  operation leaked for the lifetime of the process.
- Organize's Save button stayed enabled while saving, so a double click
  started two jobs writing the same file.
- Compress reported `NaN%` when the input was zero bytes.
- PDF → Images accepted a negative or absurd DPI, which made PDFium fail
  obscurely or try to allocate enormous amounts of memory. DPI is now
  validated (1-1200).
- The bundled Inter font shipped without its OFL licence text. Restored.
- Closing the window no longer tears down a conversion that is mid-write.

## [0.1.0]

- Initial scaffolding, packaging config, CI, documentation.
- Split, merge, page organize with thumbnails, PDF ↔ image conversion,
  Compress with a Ghostscript-or-fallback strategy, and both directions of
  PDF ↔ Word conversion via converters written for this project.
- PyInstaller packaging with a verified Linux install/uninstall flow.
  Windows/macOS packaging written but not verified on real hardware.
- Relicensed from AGPL-3.0-or-later to MIT, which required moving
  rasterization off PyMuPDF onto pypdfium2 and writing `core/pdf_to_docx/`
  in place of `pdf2docx`.
- Rebranded from "PDF Toolkit" to **Pawdf**.
- Replaced the PySide6 + qfluentwidgets UI with a `QWebEngineView` shell
  rendering HTML/CSS/JS through a `QWebChannel` bridge.

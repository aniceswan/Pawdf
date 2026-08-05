# Architecture

Two rules shape everything here, and both are enforced by
`tests/test_architecture.py` rather than left to good intentions:

1. **`core/` never imports a GUI toolkit.** Every PDF operation is plain
   Python, testable and reusable without Qt.
2. **No feature imports another feature.** Any one of them can be copied out
   of this repo on its own.

```
src/pawdf/
  core/     the PDF work. Eight independent packages + one shared base.
  gui/      a native window hosting an HTML/CSS/JS UI, talking to core/
            through one bridge object.
```

## core/ - eight packages, one shared base

```
core/
  _shared/          errors, path helpers, page-range parsing, pikepdf open/close
    errors.py       the PawdfError hierarchy       (no third-party imports)
    paths.py        ensure_exists / ensure_parent_dir  (stdlib only)
    ranges.py       "1-3,5" -> [0,1,2,4]           (stdlib only)
    pdf_io.py       open_pdf / page_count          (pikepdf, imported lazily)

  split/            merge/          organize/       compress/
  rasterize/        imagepdf/       pdf_to_docx/    docx_to_pdf/

  registry.py       what features exist, without importing any of them
```

A feature package may import `pawdf.core._shared` and its own third-party
libraries. Nothing else. That is what makes "copy this directory plus
`_shared/`" a complete extraction procedure, and each feature's `README.md`
states its pip requirements and the licenses they carry.

`_shared` is capped at 300 lines by a test. It is the tax every feature pays,
so it has to stay something you'd actually want to copy.

### The registry

`registry.py` holds a `Feature` record per tool - id, title, tagline, import
path, pip requirements, accent hue, accepted file extensions - and imports
none of them. Importing it costs nothing (a test asserts no PDF library ends
up in `sys.modules`), which is what lets the UI describe all eight tools at
startup while paying for none.

`registry.load("split")` resolves the module when it's actually needed.

### Lazy imports

Heavy libraries are imported inside functions, not at module scope. pikepdf
alone is ~85ms and `_shared/pdf_io.py` is pulled in by nearly everything, so
importing it eagerly meant every launch paid for it whether or not the user
opened a PDF. The same reasoning applies to pypdfium2, reportlab, and
python-docx.

### Errors

Features raise subclasses of `PawdfError`. The GUI turns those into messages
verbatim and labels anything else as unexpected - so a genuine bug reads
differently from "you picked a locked file", instead of both arriving as an
anonymous red box.

### Thread safety

`rasterize` serializes PDFium behind a module-level lock. PDFium is not
thread-safe, and concurrent calls abort the process rather than raising
something catchable. Any UI that fills a thumbnail grid hits this immediately,
so the guarantee lives in the library rather than in a footnote for each
caller to rediscover.

## gui/ - a native window around a web UI

```
gui/
  app.py          QApplication setup and entry point
  shell.py        MainWindow: QWebEngineView + QWebChannel + drop plumbing
  bridge.py       Bridge(QObject): every slot the page can call, every
                  signal it can listen for
  workers.py      JobRunner: background threads, with references released
                  when work finishes
  dnd.py          native drag-and-drop (see below)
  resources.py    where files live on disk
  web/            index.html, styles.css, app.js - the actual UI
```

Chromium is embedded **inside** the app window. This is still one installed
binary with one icon, not a page opened in a browser.

### Why a web UI in a Qt app

The strongest PDF libraries - pikepdf, pypdfium2, reportlab - are
Python-native, and `core/` calls them in-process. There is no IPC boundary to
a separate Node or Rust backend the way Electron or Tauri would need.
`QWebEngineView` is a *rendering surface*, not a second process talking over a
wire protocol.

What HTML buys is the UI itself: the radial menu, the spring animations, the
theming. Reproducing that in Qt widgets is a great deal of custom painting.

### The bridge contract

- **Every filesystem path** the page knows came from a native dialog or a
  native drop. JavaScript never enumerates or reads the disk itself.
- **Every operation that could take more than a few milliseconds** runs on a
  worker thread and answers with a signal. A blocking slot would freeze the Qt
  event loop *and* the Chromium renderer on top of it - the window would stop
  painting entirely, not just the button that was pressed.
- Payloads cross as JSON strings. QWebChannel's automatic conversion is fussy
  about nested containers, and one `JSON.parse` beats debugging why a list of
  tuples arrived as something unexpected.

### Drag-and-drop has to be native

A dropped `File` in a browser exposes `name`, `size`, `type`, and
`lastModified` - and no path. `File.path` is a property **Electron** adds by
patching Blink; standard Chromium, which QtWebEngine embeds, deliberately
withholds filesystem paths from page content.

So the page can see *that* a PDF was dropped and never *where* it is. `dnd.py`
catches the drag one layer down, where Qt has the real `file://` URLs, and
hands the paths over. The page must still `preventDefault()` its own
dragover/drop events, or Chromium treats the drop as a navigation and replaces
the whole UI with the document.

The filter is installed on the web view's **focus proxy** - the render widget
QWebEngineView creates lazily once shown - because filtering the view itself
catches nothing.

### The UI is generated from the registry

`app.js` builds the tool ring from whatever `bridge.features()` returns, so
adding a feature is a registry change, not a markup change. The per-tool
*forms* are still hand-written in `index.html`; a test checks every registered
feature has a matching panel, so a half-added feature fails CI instead of
showing a node that opens nothing.

## History

The UI was Qt widgets (PySide6 + qfluentwidgets), then a first webview port
with a sidebar and tab-style pages, and is now the radial layout. The webview
move happened because the widget-toolkit look read as generic no matter how
much it was themed; the radial move happened because a sidebar of nine pages
is still navigation the user has to do.

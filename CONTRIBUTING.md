# Contributing

Thanks for considering it. Two rules matter more than everything else, and
both are enforced by `tests/test_architecture.py` - a PR that breaks either
one fails CI.

## Rule 1: `core/` never imports a GUI toolkit

`src/pawdf/core/` is plain, testable Python that does the actual PDF work.
`src/pawdf/gui/` presents it and runs it off the UI thread.

**If you're adding a PDF operation, you almost certainly only touch `core/`
and its tests.** You do not need to know Qt.

CI installs `pip install -e ".[core]"` - with no Qt present at all - and runs
the suite. An accidental `from PySide6 import ...` doesn't fail a grep; it
fails to import.

## Rule 2: no feature imports another feature

Each directory under `core/` is standalone. It may import
`pawdf.core._shared` and its own third-party libraries, and nothing else.

This is what makes the project's central promise true: someone can copy
`core/split/` plus `core/_shared/` into their own project and be done. If two
features need the same helper, it goes in `_shared` - which is capped at 300
lines by a test, so think before adding to it.

## Adding a new PDF operation

1. **Create `core/<feature>/`.** Plain functions: paths and bytes in, paths
   and bytes out. Raise from `core/_shared/errors.py` on failure, never a bare
   `Exception`.
2. **Write `core/<feature>/README.md`.** It must contain a *Lifting this out*
   section listing the pip packages and the licenses they carry. A test checks
   this, because the promise is worthless if it silently rots.
3. **Add tests in `tests/core/`.** Use the fixtures in `tests/conftest.py` to
   generate sample files rather than committing binaries, unless you're
   testing something a generator can't produce (encrypted input, a
   deliberately corrupt file).
4. **Register it** in `core/registry.py`: id, title, tagline, import path, pip
   requirements, accent hue, accepted extensions.
5. **Add an extras group** in `pyproject.toml` matching the id, so
   `pip install pawdf[<feature>]` works. A test compares the two.
6. **If it should be user-facing:** add a `@Slot` in `gui/bridge.py` that
   dispatches through `JobRunner`, add a `<div class="panel"
   data-panel="<id>">` to `gui/web/index.html`, an icon to `ICONS` in
   `gui/web/app.js`, and wire the run button. The ring itself needs no
   changes - it's generated from the registry.
7. **Add it to `hiddenimports`** in `packaging/pyinstaller/pawdf.spec`.
   Features load via `importlib`, which PyInstaller's static analysis can't
   follow, so an unlisted feature works from source and breaks in the bundle.

## Rules that will fail your PR

- Blocking the UI thread. Every long `core/` call goes through
  `JobRunner`. This isn't style: a blocking slot freezes the Qt event loop and
  the Chromium renderer with it, so the whole window stops painting.
- Adding a copyleft dependency. See below.
- Editing icons by hand. They're generated - change
  `scripts/generate_icons.py` and re-run it. CI regenerates and diffs.

## Licensing rules

This project is MIT and stays that way, which constrains what it can depend
on.

**Anything imported by `core/` must be MIT, BSD, Apache-2.0, HPND, or
MPL-2.0.** No LGPL, no GPL, no AGPL. The goal is that someone can lift a
feature into a closed-source product with attribution as their only
obligation, and an LGPL dependency would attach distribution conditions to
that. A test blocks the specific libraries this has already cost work to
avoid.

Already paid for, so please don't undo it:

- **`pypdfium2`, not PyMuPDF.** PyMuPDF has a nicer API, but Artifex
  dual-licenses it AGPL-3.0 or commercial. pypdfium2 wraps the same renderer
  Chromium ships, under BSD-3-Clause/Apache-2.0.
- **`core/pdf_to_docx/`, not `pdf2docx`.** `pdf2docx` is MIT itself but
  hard-requires PyMuPDF, dragging the AGPL back in.
- **`core/imagepdf/`, not `img2pdf`.** `img2pdf` does this job well and is
  LGPL-3.0. Replacing it is what got `core/` to zero copyleft dependencies.

`gui/` may use LGPL (PySide6 is), because it's the part nobody lifts into
their own product. Keep it that way round.

## Dev setup

```bash
pip install -e ".[dev]"
ruff check . && ruff format .
pytest
```

## PR checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest` passes locally
- [ ] New `core/` functions have tests in `tests/core/`
- [ ] New features have a README with a *Lifting this out* section
- [ ] New features are in `registry.py`, `pyproject.toml` extras, and the
      PyInstaller `hiddenimports`
- [ ] No GUI import in `core/`, no cross-feature import

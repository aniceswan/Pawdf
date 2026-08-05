# Ghostscript (Compress)

The Compress tool never requires Ghostscript to work at all. There's always
a pure-Python fallback (see below), but results are noticeably better with
it installed.

## How the app finds Ghostscript

`core/compress/ghostscript.py::find_ghostscript()` checks, in order:

1. The `PAWDF_GS_PATH` environment variable (for devs, CI, or anyone
   who wants to point at a specific binary).
2. A vendored copy under the app's data directory
   (`platformdirs.user_data_dir("pawdf")/vendor/ghostscript/...`),
   populated at runtime by the setup flow below, never committed to git.
3. `shutil.which("gs")` (Linux/macOS) or `shutil.which("gswin64c")` /
   `"gswin32c"` (Windows), which picks up a normal system install.
4. A short list of known default install paths as a last resort.

## Setting it up

Run `python scripts/setup_ghostscript.py`, or use the "Set up Ghostscript"
button on the app's Settings page (so non-technical users never need a
terminal):

- **Windows**: downloads the official installer from Artifex's
  `ghostpdl-downloads` GitHub releases and runs it silently
  (`/VERYSILENT /DIR=<vendor_path>`), then points the locator at the
  resulting `gswin64c.exe`. (This assumes the installer is Inno-Setup-based,
  which has historically been the case. Verify on a real Windows machine
  before relying on it in a release; it hasn't been tested against an
  actual Windows install in this repo's development environment.)
- **Linux**: there is, in practice, **no prebuilt portable Linux binary**
  published by Artifex, only source tarballs and a snap package. So unlike
  Windows, this can't be fetched into an isolated vendor directory. The
  script instead detects the system's package manager (apt/dnf/pacman/
  zypper/apk) and prints the right install command (e.g.
  `sudo apt install ghostscript`).
- **macOS**: Artifex doesn't publish a static macOS build either, so the
  script shows instructions to `brew install ghostscript` (or MacPorts)
  instead of attempting an automatic download.

In practice, most Linux distributions already ship Ghostscript or make it a
one-line install, so the "vendored" path in the locator mostly matters
for Windows.

## If Ghostscript isn't available

Compress falls back to a pure-`pikepdf` + Pillow pass: it re-saves the PDF
with stream compression enabled and downsamples/re-encodes embedded raster
images. This produces a smaller, valid PDF with zero setup, but generally
won't compress as aggressively as Ghostscript's `/ebook` or `/screen`
presets. The app surfaces which path was used after a Compress run.

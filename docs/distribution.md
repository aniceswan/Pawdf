# End-user distribution

Pawdf separates end-user installation from development.

## End users

Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/aniceswan/Pawdf/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/aniceswan/Pawdf/main/install.ps1 | iex
```

`install.ps1` forces TLS 1.2 before its own downloads, since Windows
PowerShell 5.1 does not always enable it by default.

No Git, Python, pip, virtual environment, compiler,
PyInstaller, source checkout, or administrator privileges. They select the
matching architecture, download the latest GitHub release asset, verify
`SHA256SUMS.txt`, install for the current user, and can be re-run to update.

## Developers

```bash
git clone https://github.com/aniceswan/Pawdf.git
cd Pawdf
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

The developer extra remains complete. The release extra contains only the GUI
runtime and PyInstaller; tests, Ruff, coverage, benchmarks, and source-build
helpers never enter the end-user package.

## Published assets

- `Pawdf-Linux-x86_64.AppImage`
- `Pawdf-Windows-x86_64-Setup.exe`
- `Pawdf-macOS-arm64.dmg`
- `Pawdf-macOS-x86_64.dmg`
- `SHA256SUMS.txt`

Linux aarch64 is not currently published: PySide6 6.11.1's Qt WebEngine
requires `libwebp.so.6`, an ABI Ubuntu 22.04's main archive no longer
carries for aarch64 (only the incompatible `libwebp7`). This surfaced only
by actually launching a real hosted aarch64 build, not by any static check,
and is tracked separately rather than blocking the four targets that do
build and launch correctly. `scripts/test_all_os.sh`'s QA snapshot still
exercises aarch64 so a future fix is visible without being rediscovered.
- `release-manifest.json`
- `SBOM.cdx.json`
- per-target size and installed-smoke reports.

## Runtime-size policy

Pawdf remains the complete 22-tool application. Pruning is limited to QML
application packages the Widgets application never loads, unused Qt product
families, non-English Chromium locales, DevTools resources, unused Qt
translations, tests, examples, headers, and build metadata.

Qt Core, GUI, Widgets, Network, WebEngine, WebChannel, PrintSupport,
Positioning, OpenGL, platform and TLS plugins, image plugins, Chromium runtime
resources, Pawdf fonts/assets, and all 22 feature packages remain.

Every target runs source and packaged feature-import self-tests, packaged GUI
liveness, final-installer fresh-install smoke, runtime-content audit, checksum
verification, and installed/download size budgets.

## Optional external runtime

Compression works completely without Ghostscript through Pawdf's built-in
pikepdf and Pillow path. Ghostscript remains an optional accelerator because
redistributing it changes distribution obligations.

OCR code remains in every package, but Tesseract and language data are an
optional external runtime because they are much larger than the base app. The
installer does not silently download hundreds of megabytes. Pawdf reports
whether Tesseract is present and provides the platform-specific setup command.
A separately checksummed OCR pack can be added later without changing the base
installer protocol.

## Signing

The release workflow supports Windows Authenticode and Apple Developer ID,
notarization, and stapling when real certificate secrets are configured.
SmartScreen and Gatekeeper warnings cannot honestly be claimed as solved before
those publisher credentials exist.

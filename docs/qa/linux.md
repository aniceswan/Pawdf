# Linux release QA

Record distribution, desktop environment, Wayland/X11, display scale, Pawdf
version, and artifact checksum.

## Automated baseline

<!-- PAWDF_DOC_SYNC_2026_08:linux-qa -->

Before manual testing, run the repository snapshot through all hosted
environments:

```bash
bash scripts/test_all_os.sh
```

The Linux hosted job must pass tests, packaging, CLI diagnostics and
packaged GUI startup. This establishes an automated baseline only; complete
the real-device checklist below before marking the platform physically
verified.

## Real-device checklist

- Verify SHA-256 against `SHA256SUMS.txt`.
- Test Fedora, Ubuntu, and one additional distribution.
- Test GNOME and KDE where possible.
- Test Wayland and X11.
- Install without sudo, launch from the application menu, and pin to the dock.
- Test Unicode paths, localized Downloads folders, and read-only destinations.
- Test fractional scaling and multiple monitors.
- Run all 22 tools with representative files.
- Verify Tesseract language discovery and Ghostscript fallback behaviour.
- Start a long operation, close the window, and confirm deferred safe closing.
- Export and inspect a diagnostic bundle.
- Run the uninstall script and verify only Pawdf application files are removed.

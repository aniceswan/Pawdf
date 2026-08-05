# macOS release QA

Record macOS version, Intel/Apple Silicon, Pawdf version, signing identity, and
artifact checksum.

## Automated baseline

<!-- PAWDF_DOC_SYNC_2026_08:macos-qa -->

Before manual testing, run the repository snapshot through all hosted
environments:

```bash
bash scripts/test_all_os.sh
```

The macOS hosted job must pass tests, packaging, CLI diagnostics and
packaged GUI startup. This establishes an automated baseline only; complete
the real-device checklist below before marking the platform physically
verified.

## Real-device checklist

- Verify SHA-256 against `SHA256SUMS.txt`.
- Confirm code signature and notarization before calling the build stable.
- Launch from Finder, Spotlight, Dock, and the Applications folder.
- Test Retina and external non-Retina displays.
- Test light/dark appearance and reduced motion.
- Test Downloads/Desktop permission prompts.
- Run all 22 tools with representative files.
- Verify menu-bar, full-screen, close/reopen, and app-quit behaviour.
- Start a long operation, close the window, and confirm it closes after the
  valid output finishes.
- Open generated PDFs in Preview and Adobe Acrobat when available.
- Export and inspect a diagnostic bundle.
- Remove the app and confirm user documents remain untouched.

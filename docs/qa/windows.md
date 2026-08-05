# Windows release QA

Record Windows edition/build, architecture, display scale, Pawdf version, and
artifact checksum.

## Automated baseline

<!-- PAWDF_DOC_SYNC_2026_08:windows-qa -->

Before manual testing, run the repository snapshot through all hosted
environments:

```bash
bash scripts/test_all_os.sh
```

The Windows hosted job must pass tests, packaging, CLI diagnostics and
packaged GUI startup. This establishes an automated baseline only; complete
the real-device checklist below before marking the platform physically
verified.

## Real-device checklist

- Verify SHA-256 against `SHA256SUMS.txt`.
- Install as a standard user and as an administrator.
- Confirm SmartScreen/Defender behaviour and record any warning.
- Launch from Start, desktop shortcut, installer finish page, and taskbar.
- Verify correct icon grouping and pin/unpin behaviour.
- Test 100%, 125%, 150%, and 200% scaling.
- Test a non-ASCII username and file names.
- Test Downloads, OneDrive, a network path, a read-only directory, and a long path.
- Run all 22 tools with representative files.
- Start a long OCR/conversion, close the window, and confirm automatic close
  after a valid output is finished.
- Export a diagnostic bundle and verify no opened document is included.
- Uninstall and confirm shortcuts/application files are removed while user
  documents remain untouched.

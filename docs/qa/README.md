# Pawdf platform QA

<!-- PAWDF_DOC_SYNC_2026_08:qa-index -->

Pawdf separates automated operating-system coverage from physical-device
verification. No successful hosted three-OS report is currently recorded locally.

## Hosted baseline

Run from the repository on Linux:

```bash
bash scripts/test_all_os.sh
```

The launcher snapshots the current working tree into an isolated temporary
worktree and branch, runs GitHub-hosted Ubuntu, Windows and macOS jobs, waits
for completion, and downloads reports under `.git/pawdf-all-os-runs/`.

A hosted PASS covers:

- Ruff and JavaScript syntax;
- CLI version and privacy-safe diagnostics;
- the full pytest suite;
- benchmark smoke;
- PyInstaller packaging;
- packaged CLI and GUI startup;
- release checksums and CycloneDX SBOM;
- the Windows installer build.

It does **not** verify physical GPU/display combinations, platform signing,
SmartScreen, Gatekeeper, taskbar/Dock integration, permission prompts or
assistive technologies.

## Real-device checklists

- [Linux](linux.md)
- [Windows](windows.md)
- [macOS](macos.md)

Record the exact OS/build, architecture, display scaling, Pawdf version and
artifact checksum with every manual result.

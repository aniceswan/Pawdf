# Production readiness

Pawdf treats reliability as a product feature, not only a passing test suite.

## Automated protections now present

- Every direct `pawdf.core` input goes through a central size limit.
- Office containers are checked for unsafe paths, excessive entry counts,
  unreasonable expansion, and suspicious compression ratios before parsing.
- PDFs have a configurable page-count ceiling.
- Images have a configurable decoded-pixel ceiling.
- The desktop bridge repeats preflight checks for nested multi-file requests.
- Only one local rotating application log is kept, with three small backups.
- Diagnostic bundles contain system/version metadata and sanitized Pawdf logs,
  never opened documents.
- File selections are recoverable after a normal restart; missing files are
  discarded on restore and users can forget the stored list from Settings.
- Closing the window while work is active no longer freezes or kills a writer.
  The window closes automatically after active writes finish.
- Release builds expose `--version`, run packaged smoke tests, and publish
  SHA-256 checksums plus a CycloneDX SBOM.
- A local corpus verifier and repeatable benchmark runner are included.
- Reduced-motion and visible keyboard-focus rules are enforced in the UI.

## Hosted cross-platform and visual QA

<!-- PAWDF_DOC_SYNC_2026_08:production-readiness -->

- `scripts/test_all_os.sh` tests the exact current working-tree snapshot on
  GitHub-hosted Ubuntu, Windows and macOS without modifying the active branch.
- Each hosted job runs static checks, the full suite, a benchmark smoke,
  PyInstaller packaging, packaged CLI diagnostics and packaged GUI liveness.
- Brand and layout contracts pin exactly three miniature document pads, an
  upright tool-open state and responsive hero breakpoints.
- `docs/screenshots/main_window.png` is captured from the current source
  application instead of being maintained as an unrelated manual image.
- No successful hosted three-OS report is recorded locally yet.

A hosted PASS is an operating-system environment result, not a physical
hardware certification. Windows SmartScreen/taskbar behaviour and macOS
signing/notarization/Gatekeeper remain manual release gates.

## Configurable limits

All values are positive integers.

| Variable | Default | Meaning |
|---|---:|---|
| `PAWDF_MAX_INPUT_MIB` | 2048 | Maximum size of one input |
| `PAWDF_MAX_TOTAL_INPUT_MIB` | 4096 | Maximum selected input total |
| `PAWDF_MAX_PDF_PAGES` | 10000 | Maximum PDF page count |
| `PAWDF_MAX_IMAGE_MEGAPIXELS` | 200 | Maximum decoded image pixels |
| `PAWDF_MAX_ARCHIVE_MEMBERS` | 50000 | Maximum DOCX/XLSX/PPTX ZIP entries |
| `PAWDF_MAX_ARCHIVE_UNCOMPRESSED_MIB` | 4096 | Maximum expanded Office size |
| `PAWDF_MAX_ARCHIVE_RATIO` | 1000 | Maximum uncompressed/compressed ratio |

Raising a limit transfers the memory/disk risk to the operator.

## Private real-world corpus

Do not commit customer or personal documents. Keep a private local directory
and run:

```bash
python scripts/verify_corpus.py /path/to/corpus --output corpus-report.json
```

The report contains relative file names and validation results. The documents
never leave the machine.

## Performance baseline

Run on the same machine before and after a significant change:

```bash
python benchmarks/benchmark_core.py --pages 500 --repeats 5
```

Store the resulting JSON outside the repository or attach it to the release
issue. Hosted CI timing is not used as a hard gate because runner performance
varies.

## Remaining engineering gaps

The hardening pack does not pretend these are solved:

- cooperative per-operation cancellation with atomic `.part` outputs;
- resumable queues or pause/resume;
- full crash recovery for unsaved form/annotation edits;
- sustained coverage-guided fuzzing;
- digital-signature creation and verification;
- pixel-perfect Office conversion and advanced OCR preprocessing;
- signed automatic updates.

These require feature-specific implementation and compatibility fixtures rather
than a generic thread kill. Pawdf deliberately finishes an active write instead
of corrupting it.

## What still requires humans or real hardware

Automation cannot truthfully replace:

- launching and using the installer on physical Windows machines;
- launching signed/notarized builds on Intel and Apple Silicon Macs;
- visual comparison of complex Word, Excel, and PowerPoint documents;
- accessibility review with NVDA, Narrator, VoiceOver, and keyboard-only use;
- malicious-file fuzzing at sustained scale;
- code-signing certificates and Apple notarization credentials;
- validating output in Adobe Acrobat, Preview, browser viewers, and office apps.

Use the platform checklists under `docs/qa/` and record exact OS/build versions.
A platform must not be marked verified merely because CI produced an artifact.

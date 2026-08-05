# Packaging and release

End users install pre-built artifacts; they do not build Pawdf from source.
See `docs/distribution.md`.

## Release environment

```bash
python -m pip install -e ".[release]" -r requirements/qt-ci.txt
python scripts/build_pyinstaller.py
python scripts/smoke_packaged.py --dist dist
```

`.[dev]` remains for contributors and is deliberately absent from release jobs.

## Linux

```bash
python scripts/package_linux_appimage.py --dist dist
```

Produces an architecture-specific AppImage. The official appimagetool release
is selected from the GitHub API and its published SHA-256 digest is verified
when available.

## Windows

```powershell
iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
```

The solid-LZMA2 Inno Setup package installs per-user under
`%LOCALAPPDATA%\Programs\Pawdf` without administrator rights.

## macOS

```bash
python scripts/package_macos_dmg.py --dist dist
```

Produces a compressed architecture-specific DMG. Signing and notarization are
activated only when real Apple certificate secrets exist.

## Size audit

```bash
python scripts/audit_bundle.py --bundle-root dist/pawdf \
  --artifact dist/Pawdf-Linux-x86_64.AppImage \
  --platform Linux --arch x86_64
```

The audit rejects unused QML/Qt families, developer/test files, missing runtime
assets, and size regressions, and records the 50 largest installed files.

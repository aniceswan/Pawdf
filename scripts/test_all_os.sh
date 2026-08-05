#!/usr/bin/env bash
set -Eeuo pipefail

# Pawdf all-OS QA launcher.
#
# Run this from the Pawdf repository on Fedora/Linux. It creates an isolated
# temporary git worktree, copies the current working-tree snapshot into it,
# adds a temporary GitHub Actions workflow, pushes a qa/all-os-* branch, waits
# for five Linux/Windows/macOS target jobs, downloads their artifacts, and prints a report.
#
# The current branch and working tree are not committed, reset, stashed, or
# otherwise modified. The remote temporary branch is kept for audit unless
# --delete-remote is passed.
#
# Requirements:
#   - git
#   - GitHub CLI (`gh`)
#   - `gh auth login` completed
#   - GitHub Actions enabled for the repository
#   - permission to push branches
#
# Usage:
#   bash ~/Downloads/pawdf_test_all_os.sh
#   bash ~/Downloads/pawdf_test_all_os.sh --delete-remote

DELETE_REMOTE=0
if [[ "${1:-}" == "--delete-remote" ]]; then
  DELETE_REMOTE=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--delete-remote]" >&2
  exit 2
fi

die() {
  echo
  echo "ERROR: $*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || die "git is not installed."
command -v gh >/dev/null 2>&1 || die "GitHub CLI (gh) is not installed."
command -v rsync >/dev/null 2>&1 || die "rsync is not installed."
command -v python3 >/dev/null 2>&1 || die "python3 is not installed."

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" ||
  die "Run this inside the Pawdf git repository."
cd "$ROOT"

[[ -f pyproject.toml && -d src/pawdf ]] ||
  die "This does not look like the Pawdf repository: $ROOT"

git remote get-url origin >/dev/null 2>&1 ||
  die "The repository has no origin remote."

gh auth status >/dev/null 2>&1 ||
  die "GitHub CLI is not authenticated. Run: gh auth login"

# Refuse to upload common secret filenames from untracked files.
while IFS= read -r -d '' file; do
  base="$(basename "$file")"
  lower="${base,,}"
  case "$lower" in
    .env|.env.*|*.pem|*.key|id_rsa|id_ed25519|credentials*|secrets*)
      die "Potential secret would be included in the QA snapshot: $file"
      ;;
  esac
done < <(git ls-files --others --exclude-standard -z)

STAMP="$(date +%Y%m%d-%H%M%S)"
BRANCH="qa/all-os-$STAMP"
WORKTREE="$(mktemp -d -t pawdf-all-os-worktree-XXXXXX)"
RESULT_ROOT="$ROOT/.git/pawdf-all-os-runs/$STAMP"
mkdir -p "$RESULT_ROOT"

RUN_ID=""
PUSHED=0

cleanup() {
  set +e
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1
  git branch -D "$BRANCH" >/dev/null 2>&1

  if [[ "$DELETE_REMOTE" -eq 1 && "$PUSHED" -eq 1 ]]; then
    git push origin --delete "$BRANCH" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

echo "Repository : $ROOT"
echo "QA branch  : $BRANCH"
echo "Results    : $RESULT_ROOT"
echo
echo "Creating an isolated snapshot of the current working tree..."

git worktree add -q -b "$BRANCH" "$WORKTREE" HEAD

# Copy all tracked files plus non-ignored untracked files. This captures the
# exact current state without stashing or committing the user's own branch.
git ls-files -c -o --exclude-standard -z |
  rsync -a --from0 --files-from=- ./ "$WORKTREE/"

# Reflect tracked deletions from the current working tree.
while IFS= read -r -d '' file; do
  rm -rf "$WORKTREE/$file"
done < <(git diff --name-only --diff-filter=D -z HEAD)

mkdir -p "$WORKTREE/.github/workflows" "$WORKTREE/scripts"

cat >"$WORKTREE/scripts/qa_packaged_app.py" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path


def find_binary(dist: Path) -> Path:
    if platform.system() == "Darwin":
        candidates = [
            dist / "pawdf.app" / "Contents" / "MacOS" / "pawdf",
            dist / "pawdf" / "pawdf",
        ]
    elif platform.system() == "Windows":
        candidates = [dist / "pawdf" / "pawdf.exe"]
    else:
        candidates = [dist / "pawdf" / "pawdf"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    matches = []
    for path in dist.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name == "pawdf.exe" or name == "pawdf":
            matches.append(path)
    if not matches:
        raise RuntimeError(f"No packaged Pawdf executable found below {dist}")

    if platform.system() == "Darwin":
        app_matches = [
            candidate
            for candidate in matches
            if ".app" in {part.lower() for part in candidate.parts}
        ]
        if app_matches:
            return sorted(
                app_matches,
                key=lambda item: len(item.parts),
            )[0].resolve()

    return sorted(matches, key=lambda item: len(item.parts))[0].resolve()


def capture(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{command!r} exited {completed.returncode}\n{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout.strip()


def liveness(binary: Path, seconds: int = 7) -> dict:
    started = time.monotonic()
    process = subprocess.Popen(
        [str(binary)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    time.sleep(seconds)
    early_code = process.poll()
    if early_code is not None:
        output = process.stdout.read() if process.stdout else ""
        raise RuntimeError(f"Packaged GUI exited early with code {early_code}\n{output}")

    try:
        if platform.system() == "Windows":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        output, _ = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if platform.system() == "Windows":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate(timeout=5)

    return {
        "aliveSeconds": seconds,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "output": (output or "")[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default="dist")
    parser.add_argument("--report", default="packaged-smoke.json")
    args = parser.parse_args()

    dist = Path(args.dist).resolve()
    report = Path(args.report).resolve()
    binary = find_binary(dist)

    version = capture([str(binary), "--version"])
    diagnostics_raw = capture([str(binary), "--diagnostics-json"])
    diagnostics = json.loads(diagnostics_raw)
    if not diagnostics.get("pawdfVersion"):
        raise RuntimeError("Packaged diagnostics did not contain pawdfVersion")

    payload = {
        "status": "PASS",
        "timestamp": datetime.now().isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "binary": str(binary),
        "version": version,
        "diagnostics": diagnostics,
        "liveness": liveness(binary),
    }
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

cat >"$WORKTREE/.github/workflows/pawdf-all-os-qa.yml" <<'YAML'
name: Pawdf Distribution QA

on:
  push:
    branches:
      - "qa/all-os-*"

permissions:
  contents: read

jobs:
  qa:
    name: ${{ matrix.target }}
    runs-on: ${{ matrix.runner }}
    timeout-minutes: 90
    strategy:
      fail-fast: false
      matrix:
        include:
          - runner: ubuntu-22.04
            target: linux-x86_64
            platform: Linux
            arch: x86_64
            artifact: Pawdf-Linux-x86_64.AppImage
            installed_budget: 700
            artifact_budget: 220
          - runner: ubuntu-22.04-arm
            target: linux-aarch64
            platform: Linux
            arch: aarch64
            artifact: Pawdf-Linux-aarch64.AppImage
            installed_budget: 700
            artifact_budget: 220
          - runner: windows-2025
            target: windows-x86_64
            platform: Windows
            arch: x86_64
            artifact: Pawdf-Windows-x86_64-Setup.exe
            installed_budget: 700
            artifact_budget: 220
          - runner: macos-15
            target: macos-arm64
            platform: macOS
            arch: arm64
            artifact: Pawdf-macOS-arm64.dmg
            installed_budget: 750
            artifact_budget: 260
          - runner: macos-15-intel
            target: macos-x86_64
            platform: macOS
            arch: x86_64
            artifact: Pawdf-macOS-x86_64.dmg
            installed_budget: 750
            artifact_budget: 260

    env:
      PYTEST_QT_API: pyside6
      QT_OPENGL: software
      QT_QUICK_BACKEND: software
      QTWEBENGINE_DISABLE_SANDBOX: "1"
      QTWEBENGINE_CHROMIUM_FLAGS: >-
        --no-sandbox
        --disable-gpu
        --disable-gpu-compositing
        --disable-features=Vulkan
        --disable-dev-shm-usage

    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip
      - uses: actions/setup-node@v6
        with:
          node-version: "24"

      - name: Install Linux Qt and WebEngine runtime
        if: runner.os == 'Linux'
        shell: bash
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            xvfb xauth \
            libegl1 libgl1 libgl1-mesa-dri libglx-mesa0 libopengl0 \
            libgbm1 libdrm2 libdbus-1-3 libfontconfig1 libfreetype6 \
            libglib2.0-0 libnss3 libnspr4 libsm6 libice6 \
            libx11-6 libx11-xcb1 libxext6 libxfixes3 libxi6 \
            libxrender1 libxrandr2 libxcursor1 libxcomposite1 \
            libxdamage1 libxtst6 libxss1 libxshmfence1 \
            libxkbfile1 libxkbcommon0 libxkbcommon-x11-0 \
            libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
            libxcb-keysyms1 libxcb-randr0 libxcb-render0 \
            libxcb-render-util0 libxcb-shape0 libxcb-shm0 \
            libxcb-sync1 libxcb-util1 libxcb-xfixes0 \
            libxcb-xinerama0 libxcb-xkb1 libxcb-dri2-0 \
            libxcb-dri3-0 libxcb-glx0 libxcb-present0

      - name: Install source QA environment
        run: >
          python -m pip install
          -e ".[dev]"
          -r requirements/qt-ci.txt

      - name: Ruff
        run: |
          python -m ruff check .
          python -m ruff format --check .

      - name: JavaScript syntax
        run: |
          node --check src/pawdf/gui/web/app.js
          node --check src/pawdf/gui/web/enhancements.js

      - name: CLI metadata and all-feature source self-test
        run: |
          python -m pawdf --version
          python -m pawdf --diagnostics-json
          python -m pawdf --self-test-json

      - name: Cross-platform non-GUI tests
        env:
          PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"
        run: >
          python scripts/run_ci_test_partitions.py
          non-gui
          --timeout 900

      - name: Isolated Linux GUI and WebEngine tests
        if: runner.os == 'Linux'
        env:
          QT_QPA_PLATFORM: xcb
          LIBGL_ALWAYS_SOFTWARE: "1"
        run: >
          xvfb-run
          --auto-servernum
          --server-args="-screen 0 1440x900x24 -nolisten tcp"
          python scripts/run_ci_test_partitions.py
          gui
          --timeout 150

      - name: Native macOS geometry persistence smoke
        if: runner.os == 'macOS'
        env:
          QT_QPA_PLATFORM: cocoa
        run: >
          python scripts/run_ci_test_partitions.py
          gui
          --match test_geometry_survives_a_restart
          --timeout 120

      - name: Create clean release environment
        shell: bash
        run: |
          RELEASE_VENV="$RUNNER_TEMP/pawdf-release-venv"
          python -m venv "$RELEASE_VENV"
          if [[ "$RUNNER_OS" == "Windows" ]]; then
            RELEASE_PYTHON="$RELEASE_VENV/Scripts/python.exe"
          else
            RELEASE_PYTHON="$RELEASE_VENV/bin/python"
          fi
          "$RELEASE_PYTHON" -m pip install --upgrade pip
          "$RELEASE_PYTHON" -m pip install -e ".[release]" -r requirements/qt-ci.txt
          echo "RELEASE_PYTHON=$RELEASE_PYTHON" >> "$GITHUB_ENV"

      - name: Build PyInstaller runtime
        shell: bash
        run: '"$RELEASE_PYTHON" scripts/build_pyinstaller.py'

      - name: Smoke raw Linux runtime
        if: runner.os == 'Linux'
        shell: bash
        env:
          QT_QPA_PLATFORM: xcb
          LIBGL_ALWAYS_SOFTWARE: "1"
        run: |
          export XDG_RUNTIME_DIR="$RUNNER_TEMP/pawdf-raw-runtime"
          mkdir -p "$XDG_RUNTIME_DIR"
          chmod 700 "$XDG_RUNTIME_DIR"
          xvfb-run --auto-servernum \
            --server-args="-screen 0 1440x900x24 -nolisten tcp" \
            "$RELEASE_PYTHON" scripts/smoke_packaged.py --dist dist

      - name: Smoke raw Windows and macOS runtime
        if: runner.os != 'Linux'
        shell: bash
        run: '"$RELEASE_PYTHON" scripts/smoke_packaged.py --dist dist'

      - name: Package Linux AppImage
        if: runner.os == 'Linux'
        shell: bash
        run: '"$RELEASE_PYTHON" scripts/package_linux_appimage.py --dist dist'

      - name: Build Windows installer
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          choco install innosetup -y --no-progress
          $Version = & $env:RELEASE_PYTHON -c "from pawdf import __version__; print(__version__)"
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
            "/DAppVersion=$Version" packaging\windows\installer.iss
          if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

      - name: Package macOS DMG
        if: runner.os == 'macOS'
        shell: bash
        run: '"$RELEASE_PYTHON" scripts/package_macos_dmg.py --dist dist'

      - name: Generate checksums, manifest, and SBOM
        shell: bash
        run: '"$RELEASE_PYTHON" scripts/release_manifest.py --root dist'

      - name: Audit runtime size and contents
        shell: bash
        run: |
          if [[ "${{ runner.os }}" == "macOS" ]]; then
            BUNDLE_ROOT="dist/pawdf.app"
          else
            BUNDLE_ROOT="dist/pawdf"
          fi
          "$RELEASE_PYTHON" scripts/audit_bundle.py \
            --bundle-root "$BUNDLE_ROOT" \
            --artifact "dist/${{ matrix.artifact }}" \
            --platform "${{ matrix.platform }}" \
            --arch "${{ matrix.arch }}" \
            --installed-budget-mb "${{ matrix.installed_budget }}" \
            --artifact-budget-mb "${{ matrix.artifact_budget }}" \
            --report "dist/release-size-${{ matrix.target }}.json"

      - name: Fresh-install Linux release
        if: runner.os == 'Linux'
        shell: bash
        env:
          QT_QPA_PLATFORM: xcb
          LIBGL_ALWAYS_SOFTWARE: "1"
          PAWDF_RELEASE_DIR: ${{ github.workspace }}/dist
          PAWDF_INSTALL_ROOT: ${{ runner.temp }}/pawdf-installed
          PAWDF_BIN_DIR: ${{ runner.temp }}/pawdf-bin
          PAWDF_APPLICATIONS_DIR: ${{ runner.temp }}/applications
        run: |
          bash install.sh --no-launch
          export XDG_RUNTIME_DIR="$RUNNER_TEMP/pawdf-installed-runtime"
          mkdir -p "$XDG_RUNTIME_DIR"
          chmod 700 "$XDG_RUNTIME_DIR"
          xvfb-run --auto-servernum \
            --server-args="-screen 0 1440x900x24 -nolisten tcp" \
            "$RELEASE_PYTHON" scripts/verify_installed.py \
              --binary "$PAWDF_INSTALL_ROOT/Pawdf.AppImage" \
              --report "installed-smoke-${{ matrix.target }}.json"

      - name: Fresh-install Windows release
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          .\install.ps1 `
            -SourceDirectory (Resolve-Path dist) `
            -InstallDirectory "$env:RUNNER_TEMP\Pawdf" `
            -NoLaunch
          & $env:RELEASE_PYTHON scripts\verify_installed.py `
            --binary "$env:RUNNER_TEMP\Pawdf\pawdf.exe" `
            --report "installed-smoke-${{ matrix.target }}.json"

      - name: Fresh-install macOS release
        if: runner.os == 'macOS'
        shell: bash
        env:
          PAWDF_RELEASE_DIR: ${{ github.workspace }}/dist
          PAWDF_INSTALL_ROOT: ${{ runner.temp }}/Applications
        run: |
          bash install.sh --no-launch
          python scripts/verify_installed.py \
            --binary "$PAWDF_INSTALL_ROOT/Pawdf.app/Contents/MacOS/pawdf" \
            --report "installed-smoke-${{ matrix.target }}.json"

      - name: Upload QA artifacts
        if: always()
        uses: actions/upload-artifact@v6
        with:
          name: pawdf-${{ matrix.target }}-qa
          path: |
            dist/${{ matrix.artifact }}
            dist/SHA256SUMS.txt
            dist/release-manifest.json
            dist/SBOM.cdx.json
            dist/release-size-${{ matrix.target }}.json
            installed-smoke-${{ matrix.target }}.json
          if-no-files-found: warn
YAML

chmod +x "$WORKTREE/scripts/qa_packaged_app.py"

(
  cd "$WORKTREE"
  git add -A
  git -c user.name="Pawdf QA Bot" \
      -c user.email="pawdf-qa@users.noreply.github.com" \
      commit -q -m "test: run Pawdf QA across Ubuntu Windows and macOS"
)

HEAD_SHA="$(git -C "$WORKTREE" rev-parse HEAD)"
REPOSITORY="$(
  gh repo view --json nameWithOwner --jq '.nameWithOwner'
)"

echo "Pushing isolated QA branch to GitHub..."
git -C "$WORKTREE" push -u origin "$BRANCH"
PUSHED=1

echo "Waiting for GitHub Actions to create the five-target distribution run..."
for _ in $(seq 1 120); do
  RUN_ID="$(
    gh api --method GET \
      "repos/$REPOSITORY/actions/runs" \
      -f head_sha="$HEAD_SHA" \
      -f event=push \
      -f per_page=100 \
      --jq '
        .workflow_runs[]
        | select(.path == ".github/workflows/pawdf-all-os-qa.yml")
        | .id
      ' 2>/dev/null |
      head -n 1 || true
  )"
  [[ -n "$RUN_ID" ]] && break
  sleep 3
done

if [[ -z "$RUN_ID" ]]; then
  gh api --method GET \
    "repos/$REPOSITORY/actions/runs" \
    -f branch="$BRANCH" \
    -f per_page=100 \
    >"$RESULT_ROOT/branch-runs.json" 2>/dev/null || true
  gh api \
    "repos/$REPOSITORY/commits/$HEAD_SHA/check-suites" \
    >"$RESULT_ROOT/check-suites.json" 2>/dev/null || true
  die "No Actions run was discoverable for commit $HEAD_SHA. Diagnostics: $RESULT_ROOT"
fi

RUN_URL="$(
  gh run view "$RUN_ID" --json url --jq '.url'
)"

echo
echo "GitHub Actions run: $RUN_URL"
echo "Watching all five distribution jobs..."
echo

set +e
gh run watch "$RUN_ID" --exit-status
WATCH_STATUS=$?
set -e

gh run view "$RUN_ID" \
  --json conclusion,status,url,headBranch,createdAt,updatedAt,jobs \
  >"$RESULT_ROOT/run-summary.json"

echo
echo "Downloading available QA artifacts..."
gh run download "$RUN_ID" --dir "$RESULT_ROOT/artifacts" || true

if [[ "$WATCH_STATUS" -ne 0 ]]; then
  echo
  echo "One or more OS jobs failed. Saving failed logs..."
  gh run view "$RUN_ID" --log-failed \
    >"$RESULT_ROOT/failed.log" 2>&1 || true

  echo
  echo "PAWDF ALL-OS QA: FAIL"
  echo "Run     : $RUN_URL"
  echo "Summary : $RESULT_ROOT/run-summary.json"
  echo "Logs    : $RESULT_ROOT/failed.log"
  echo "Artifacts: $RESULT_ROOT/artifacts"
  exit 1
fi

echo
echo "PAWDF ALL-OS QA: PASS"
echo "Linux x86_64/aarch64, Windows x86_64, and macOS arm64/Intel all passed."
echo "Run      : $RUN_URL"
echo "Summary  : $RESULT_ROOT/run-summary.json"
echo "Artifacts: $RESULT_ROOT/artifacts"

if [[ "$DELETE_REMOTE" -eq 0 ]]; then
  echo
  echo "The remote QA branch was kept for audit:"
  echo "  $BRANCH"
  echo "Delete it later with:"
  echo "  git push origin --delete '$BRANCH'"
fi

echo
echo "Important: this verifies five hosted distribution targets and their"
echo "packaged apps. It does not replace physical-hardware checks, Windows code"
echo "signing/SmartScreen, or macOS signing/notarization/Gatekeeper verification."

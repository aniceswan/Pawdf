#!/usr/bin/env bash
# Build Pawdf and install it as a real desktop application, for the current
# user only. No sudo: everything lands under $HOME using standard XDG paths.
#
# Safe to re-run - it replaces a previous install in place.
#
#     bash packaging/linux/install_linux.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VENV_DIR="$REPO_ROOT/.venv"
DIST_DIR="$REPO_ROOT/dist/pawdf"

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/pawdf"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
DESKTOP_ENTRY="$APPLICATIONS_DIR/pawdf.desktop"

# ---------------------------------------------------------------- output --

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    B=$'\033[1m'; DIM=$'\033[2m'; OK=$'\033[32m'; WARN=$'\033[33m'
    ERR=$'\033[31m'; ACCENT=$'\033[38;5;215m'; R=$'\033[0m'
else
    B=""; DIM=""; OK=""; WARN=""; ERR=""; ACCENT=""; R=""
fi

STEP=0
TOTAL=5
step() { STEP=$((STEP + 1)); printf '\n%s[%d/%d]%s %s%s%s\n' "$ACCENT" "$STEP" "$TOTAL" "$R" "$B" "$1" "$R"; }
info() { printf '      %s%s%s\n' "$DIM" "$1" "$R"; }
good() { printf '      %s+%s %s\n' "$OK" "$R" "$1"; }
warn() { printf '      %s!%s %s\n' "$WARN" "$R" "$1"; }
die()  { printf '\n%serror:%s %s\n\n' "$ERR" "$R" "$1" >&2; exit 1; }

printf '\n%s' "$ACCENT"
cat <<'BANNER'
   /\_/\    Pawdf
  ( o.o )   offline PDF tools
   > ^ <
BANNER
printf '%s' "$R"

# ------------------------------------------------------- 1. requirements --

step "Checking requirements"

command -v python3 >/dev/null 2>&1 || die "python3 is not installed.
  Fedora/RHEL:   sudo dnf install python3
  Debian/Ubuntu: sudo apt install python3"

PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || die "Python 3.10 or newer is required (found $PY_VERSION)."
good "python3 $PY_VERSION"

# Debian and Ubuntu ship venv separately, and without it the failure is a
# confusing traceback rather than a useful message.
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || die "Python's venv module is missing.
  Debian/Ubuntu: sudo apt install python3-venv python3-pip
  Fedora/RHEL:   sudo dnf install python3-pip"
good "venv available"

FREE_KB="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
if [ "${FREE_KB:-0}" -lt 2500000 ]; then
    warn "less than ~2.5 GB free in $HOME; the build needs room for Qt"
fi

# -------------------------------------------------------- 2. dependencies --

step "Setting up the Python environment"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    info "creating a virtualenv at .venv"
    python3 -m venv "$VENV_DIR" || die "could not create a virtualenv at $VENV_DIR"
fi

info "installing dependencies (a few minutes on first run)"
"$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
# [dev] pulls in the [gui] extra plus PyInstaller, which the build needs.
"$VENV_DIR/bin/python" -m pip install --quiet -e "$REPO_ROOT[dev]" \
    || die "dependency installation failed. Scroll up for pip's output."
good "dependencies installed"

# --------------------------------------------------------------- 3. build --

step "Building the application"

if [ -d "$DIST_DIR" ] && [ "${PAWDF_REBUILD:-}" != "1" ]; then
    info "reusing the existing build in dist/ (set PAWDF_REBUILD=1 to force)"
else
    info "bundling with PyInstaller (this is the slow part)"
    # PyInstaller is extremely chatty and writes to stderr, so its output goes
    # to a log and is only surfaced when something actually went wrong.
    BUILD_LOG="$REPO_ROOT/build/install-build.log"
    mkdir -p "$(dirname "$BUILD_LOG")"
    if ! "$VENV_DIR/bin/python" "$REPO_ROOT/scripts/build_pyinstaller.py" \
            >"$BUILD_LOG" 2>&1; then
        tail -25 "$BUILD_LOG" | sed 's/^/        /' >&2
        die "the build failed. Full log: $BUILD_LOG"
    fi
fi

[ -x "$DIST_DIR/pawdf" ] || die "the build did not produce $DIST_DIR/pawdf"
good "built $(du -sh "$DIST_DIR" | cut -f1) bundle"

# ------------------------------------------------------------- 4. install --

step "Installing to $INSTALL_DIR"

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$DIST_DIR/." "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/pawdf"
good "application files"

# Every size the icon theme spec defines. A shell that wants 24px for the
# panel will downscale a 512px icon if that is all it finds, and it shows.
ICON_COUNT=0
for icon in "$REPO_ROOT/packaging/icons/hicolor"/*/apps/pawdf.png; do
    [ -f "$icon" ] || continue
    size_dir="$(basename "$(dirname "$(dirname "$icon")")")"
    mkdir -p "$ICON_ROOT/$size_dir/apps"
    cp "$icon" "$ICON_ROOT/$size_dir/apps/pawdf.png"
    ICON_COUNT=$((ICON_COUNT + 1))
done
[ "$ICON_COUNT" -gt 0 ] || die "no icons found under packaging/icons/hicolor/"
good "$ICON_COUNT icon sizes"

mkdir -p "$APPLICATIONS_DIR"
sed "s|__INSTALL_DIR__|$INSTALL_DIR|g" "$SCRIPT_DIR/pawdf.desktop" > "$DESKTOP_ENTRY"
chmod +x "$DESKTOP_ENTRY"

if command -v desktop-file-validate >/dev/null 2>&1; then
    if desktop-file-validate "$DESKTOP_ENTRY" 2>/dev/null; then
        good "launcher entry (validated)"
    else
        warn "launcher entry written, but desktop-file-validate reported:"
        desktop-file-validate "$DESKTOP_ENTRY" 2>&1 | sed 's/^/        /' || true
    fi
else
    good "launcher entry"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
fi

# The Desktop folder is localised - it may be "Escritorio", "Bureau", or
# something else entirely depending on the session language.
DESKTOP_DIR=""
if command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
[ -n "$DESKTOP_DIR" ] || DESKTOP_DIR="$HOME/Desktop"

if [ -d "$DESKTOP_DIR" ] && [ "$DESKTOP_DIR" != "$HOME" ]; then
    cp "$DESKTOP_ENTRY" "$DESKTOP_DIR/pawdf.desktop"
    chmod +x "$DESKTOP_DIR/pawdf.desktop"
    # Without this GNOME shows "Untrusted application launcher" and refuses to
    # run it on a double-click.
    if command -v gio >/dev/null 2>&1; then
        gio set "$DESKTOP_DIR/pawdf.desktop" metadata::trusted true 2>/dev/null || true
    fi
    good "desktop shortcut in $(basename "$DESKTOP_DIR")/"
else
    info "no Desktop folder found - skipping the desktop shortcut"
fi

# -------------------------------------------------------------- 5. verify --

step "Verifying"

[ -x "$INSTALL_DIR/pawdf" ] || die "the installed binary is missing or not executable"
good "binary is executable"

[ -f "$INSTALL_DIR/_internal/pawdf/gui/web/index.html" ] \
    || die "the UI files did not make it into the bundle"
good "UI assets bundled"

if grep -q '^StartupWMClass=pawdf$' "$DESKTOP_ENTRY"; then
    good "launcher identity matches the app (pinning will work)"
else
    warn "StartupWMClass is missing - pinning to the dock may misbehave"
fi

printf '\n  %s%sPawdf is installed.%s\n\n' "$OK" "$B" "$R"
printf '  Find it in your applications menu, or on your Desktop.\n'
printf '  %sTo pin it:%s open it, then right-click its icon in the dock and choose\n' "$B" "$R"
printf '  "Pin to Dash" / "Pin to Taskbar" / "Add to Favourites".\n\n'
printf '  Run from a terminal:  %s%s/pawdf%s\n' "$DIM" "$INSTALL_DIR" "$R"
printf '  Remove completely:    %sbash packaging/linux/uninstall_linux.sh%s\n\n' "$DIM" "$R"

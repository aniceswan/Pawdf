#!/usr/bin/env bash
# The exact reverse of install_linux.sh: removes the installed files, both
# launcher entries, and every icon size, for the current user.
#
# No sudo needed, because nothing was installed outside $HOME. This does not
# touch the cloned repository or its .venv/ and dist/ directories.
#
#     bash packaging/linux/uninstall_linux.sh
#
set -euo pipefail

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/pawdf"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    DIM=$'\033[2m'; OK=$'\033[32m'; R=$'\033[0m'
else
    DIM=""; OK=""; R=""
fi
gone() { printf '  %s-%s %s\n' "$OK" "$R" "$1"; }

printf '\nRemoving Pawdf...\n\n'

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    gone "application files"
fi

if [ -f "$APPLICATIONS_DIR/pawdf.desktop" ]; then
    rm -f "$APPLICATIONS_DIR/pawdf.desktop"
    gone "launcher entry"
fi

# The Desktop folder is localised, so ask rather than assume "Desktop".
DESKTOP_DIR=""
if command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
[ -n "$DESKTOP_DIR" ] || DESKTOP_DIR="$HOME/Desktop"

if [ -f "$DESKTOP_DIR/pawdf.desktop" ]; then
    rm -f "$DESKTOP_DIR/pawdf.desktop"
    gone "desktop shortcut"
fi

# Installed across every theme size, so removed the same way rather than
# hard-coding one directory and leaving the rest behind.
ICON_COUNT=0
for icon in "$ICON_ROOT"/*/apps/pawdf.png; do
    [ -f "$icon" ] || continue
    rm -f "$icon"
    ICON_COUNT=$((ICON_COUNT + 1))
done
[ "$ICON_COUNT" -gt 0 ] && gone "$ICON_COUNT icon sizes"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
fi

printf '\n  %sPawdf has been uninstalled.%s\n' "$OK" "$R"
printf '  %sThe cloned repository, .venv/ and dist/ were left alone.%s\n\n' "$DIM" "$R"

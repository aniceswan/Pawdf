#!/usr/bin/env bash
# Pawdf end-user installer for Linux and macOS.
#
# Downloads a pre-built release. No Git, Python, pip, compiler, or source tree.
set -Eeuo pipefail

REPOSITORY="aniceswan/Pawdf"
VERSION="latest"
INSTALL_DIR=""
NO_LAUNCH=0
UNINSTALL=0

usage() {
    cat <<'HELP'
Usage: install.sh [--version TAG] [--install-dir PATH] [--no-launch] [--uninstall]

Automated-QA environment overrides:
  PAWDF_RELEASE_DIR       read release assets from a local directory
  PAWDF_RELEASE_BASE_URL override the GitHub release download base URL
  PAWDF_INSTALL_ROOT     override the application directory
  PAWDF_BIN_DIR          override ~/.local/bin on Linux
  PAWDF_APPLICATIONS_DIR override the XDG application directory
HELP
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            [[ $# -ge 2 ]] || { echo "error: --version needs a value" >&2; exit 2; }
            VERSION="$2"; shift 2 ;;
        --install-dir)
            [[ $# -ge 2 ]] || { echo "error: --install-dir needs a value" >&2; exit 2; }
            INSTALL_DIR="$2"; shift 2 ;;
        --no-launch) NO_LAUNCH=1; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

OS_NAME="$(uname -s)"
MACHINE="$(uname -m)"

case "$OS_NAME" in
    Linux)
        case "$MACHINE" in
            x86_64|amd64) ARCH="x86_64" ;;
            aarch64|arm64)
                echo "error: Linux aarch64 is not shipped in this release yet (deferred; see CHANGELOG.md)." >&2
                echo "Only Linux x86_64 AppImages are currently published." >&2
                exit 1
                ;;
            *) echo "error: unsupported Linux architecture: $MACHINE" >&2; exit 1 ;;
        esac
        ASSET="Pawdf-Linux-${ARCH}.AppImage"
        DEFAULT_INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/pawdf"
        ;;
    Darwin)
        case "$MACHINE" in
            arm64|aarch64) ARCH="arm64" ;;
            x86_64|amd64) ARCH="x86_64" ;;
            *) echo "error: unsupported macOS architecture: $MACHINE" >&2; exit 1 ;;
        esac
        ASSET="Pawdf-macOS-${ARCH}.dmg"
        DEFAULT_INSTALL_ROOT="$HOME/Applications"
        ;;
    *)
        echo "error: this script supports Linux and macOS only." >&2
        echo "Windows: irm https://raw.githubusercontent.com/aniceswan/Pawdf/main/install.ps1 | iex" >&2
        exit 1
        ;;
esac

INSTALL_ROOT="${INSTALL_DIR:-${PAWDF_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}}"

if [[ "$UNINSTALL" -eq 1 ]]; then
    if [[ "$OS_NAME" == "Linux" ]]; then
        BIN_DIR="${PAWDF_BIN_DIR:-$HOME/.local/bin}"
        APPLICATIONS_DIR="${PAWDF_APPLICATIONS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
        ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
        rm -rf "$INSTALL_ROOT"
        rm -f "$BIN_DIR/pawdf" "$APPLICATIONS_DIR/pawdf.desktop" "$ICON_DIR/pawdf.png"
        command -v update-desktop-database >/dev/null 2>&1 \
            && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
    else
        rm -rf "$INSTALL_ROOT/Pawdf.app"
    fi
    printf '\nPawdf has been removed for the current user.\n'
    exit 0
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pawdf-install.XXXXXX")"
MOUNT_POINT=""
cleanup() {
    set +e
    if [[ -n "$MOUNT_POINT" && -d "$MOUNT_POINT" ]]; then
        hdiutil detach "$MOUNT_POINT" -quiet >/dev/null 2>&1
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fetch() {
    local source_name="$1"
    local destination="$2"

    if [[ -n "${PAWDF_RELEASE_DIR:-}" ]]; then
        [[ -f "$PAWDF_RELEASE_DIR/$source_name" ]] || {
            echo "error: missing local release asset: $PAWDF_RELEASE_DIR/$source_name" >&2
            exit 1
        }
        cp "$PAWDF_RELEASE_DIR/$source_name" "$destination"
        return
    fi

    local base
    if [[ -n "${PAWDF_RELEASE_BASE_URL:-}" ]]; then
        base="${PAWDF_RELEASE_BASE_URL%/}"
    elif [[ "$VERSION" == "latest" ]]; then
        base="https://github.com/$REPOSITORY/releases/latest/download"
    else
        base="https://github.com/$REPOSITORY/releases/download/$VERSION"
    fi

    if command -v curl >/dev/null 2>&1; then
        curl --fail --location --retry 3 --retry-delay 2 \
            --output "$destination" "$base/$source_name"
    elif command -v wget >/dev/null 2>&1; then
        wget --tries=3 --output-document="$destination" "$base/$source_name"
    else
        echo "error: curl or wget is required to download Pawdf." >&2
        exit 1
    fi
}

sha256_file() {
    local path="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$path" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$path" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 "$path" | awk '{print $NF}'
    else
        echo "error: no SHA-256 tool is available." >&2
        exit 1
    fi
}

ASSET_PATH="$TMP_DIR/$ASSET"
SUMS_PATH="$TMP_DIR/SHA256SUMS.txt"

printf '\nPawdf installer\n'
printf '  Platform : %s %s\n' "$OS_NAME" "$ARCH"
printf '  Asset    : %s\n' "$ASSET"
printf '  Install  : %s\n\n' "$INSTALL_ROOT"

fetch "$ASSET" "$ASSET_PATH"
fetch "SHA256SUMS.txt" "$SUMS_PATH"

EXPECTED="$(
    awk -v target="$ASSET" '
        {
            name=$2
            sub(/^\*/, "", name)
            count=split(name, parts, "/")
            if (parts[count] == target) {
                print $1
                exit
            }
        }
    ' "$SUMS_PATH"
)"
[[ -n "$EXPECTED" ]] || {
    echo "error: $ASSET is not listed in SHA256SUMS.txt" >&2
    exit 1
}

ACTUAL="$(sha256_file "$ASSET_PATH")"
[[ "$ACTUAL" == "$EXPECTED" ]] || {
    echo "error: SHA-256 verification failed for $ASSET" >&2
    echo "expected: $EXPECTED" >&2
    echo "actual  : $ACTUAL" >&2
    exit 1
}
printf '  + SHA-256 verified\n'

if [[ "$OS_NAME" == "Linux" ]]; then
    BIN_DIR="${PAWDF_BIN_DIR:-$HOME/.local/bin}"
    APPLICATIONS_DIR="${PAWDF_APPLICATIONS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
    ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"

    mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"
    INSTALLED_IMAGE="$INSTALL_ROOT/Pawdf.AppImage"
    install -m 0755 "$ASSET_PATH" "$INSTALLED_IMAGE"

    cat >"$BIN_DIR/pawdf" <<WRAPPER
#!/usr/bin/env bash
set -e
APPIMAGE="$INSTALLED_IMAGE"
if [[ "\${PAWDF_FORCE_EXTRACT_AND_RUN:-}" == "1" || ! -e /dev/fuse ]]; then
    exec env APPIMAGE_EXTRACT_AND_RUN=1 "\$APPIMAGE" "\$@"
fi
exec "\$APPIMAGE" "\$@"
WRAPPER
    chmod 0755 "$BIN_DIR/pawdf"

    EXTRACT_DIR="$TMP_DIR/appimage"
    mkdir -p "$EXTRACT_DIR"
    (
        cd "$EXTRACT_DIR"
        "$INSTALLED_IMAGE" \
            --appimage-extract pawdf.png pawdf.desktop >/dev/null 2>&1 || true
    )
    if [[ -f "$EXTRACT_DIR/squashfs-root/pawdf.png" ]]; then
        install -m 0644 "$EXTRACT_DIR/squashfs-root/pawdf.png" "$ICON_DIR/pawdf.png"
    fi

    cat >"$APPLICATIONS_DIR/pawdf.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Pawdf
Comment=Offline PDF tools
Exec=$BIN_DIR/pawdf %F
Icon=pawdf
Terminal=false
Categories=Office;Utility;
StartupWMClass=pawdf
MimeType=application/pdf;
DESKTOP
    chmod 0644 "$APPLICATIONS_DIR/pawdf.desktop"
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

    printf '  + installed application and launcher\n'
    printf '\nPawdf is installed. Run: %s\n' "$BIN_DIR/pawdf"
    if [[ "$NO_LAUNCH" -eq 0 ]]; then
        nohup "$BIN_DIR/pawdf" >/dev/null 2>&1 &
    fi
else
    command -v hdiutil >/dev/null 2>&1 || {
        echo "error: hdiutil is unavailable on this Mac." >&2
        exit 1
    }

    mkdir -p "$INSTALL_ROOT"
    MOUNT_POINT="$TMP_DIR/mount"
    mkdir -p "$MOUNT_POINT"
    hdiutil attach "$ASSET_PATH" -nobrowse -readonly -mountpoint "$MOUNT_POINT" -quiet

    SOURCE_APP="$(find "$MOUNT_POINT" -maxdepth 2 -type d -name 'Pawdf.app' -print -quit)"
    [[ -n "$SOURCE_APP" ]] || {
        echo "error: Pawdf.app was not found inside $ASSET" >&2
        exit 1
    }

    rm -rf "$INSTALL_ROOT/Pawdf.app"
    ditto "$SOURCE_APP" "$INSTALL_ROOT/Pawdf.app"
    hdiutil detach "$MOUNT_POINT" -quiet
    MOUNT_POINT=""

    printf '  + installed Pawdf.app\n'
    printf '\nPawdf is installed at: %s/Pawdf.app\n' "$INSTALL_ROOT"
    if [[ "$NO_LAUNCH" -eq 0 ]]; then
        open "$INSTALL_ROOT/Pawdf.app"
    fi
fi

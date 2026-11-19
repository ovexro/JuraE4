#!/usr/bin/env bash
# Build jura-desktop_<version>_all.deb from this repo checkout.
#
#   ./packaging/build-deb.sh
#
# Output goes to dist/ at the repo root. Needs: dpkg-deb, fakeroot (both in
# the `dpkg-dev` / base system on Debian, Ubuntu, Mint).
#
# This only BUILDS the .deb; it does not install anything on this machine.
# A maintainer installs/tests it with `sudo apt install ./dist/*.deb` and
# removes it with `sudo apt remove jura-desktop`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d ' \t\n' < "$ROOT/VERSION")"
PKG="jura-desktop"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$ROOT"
for tool in dpkg-deb fakeroot; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Error: '$tool' is required (apt install dpkg-dev fakeroot)." >&2; exit 1; }
done

echo "Building ${PKG} ${VERSION}..."

# --- App files -> /opt/jura-desktop ------------------------------------
APPDIR="$STAGE/opt/jura-desktop"
mkdir -p "$APPDIR/tools"
cp jura_app.py jura_wifi_v2.py jura_protocol.py "$APPDIR/"
cp icon.svg icon_48.png icon_64.png icon_128.png icon_256.png "$APPDIR/"
cp tools/extract_hash.py "$APPDIR/tools/"
cp README.md "$APPDIR/"
# jura_wifi.py (legacy ESP32 bridge) and esp32/ are dead code -- not shipped.

# --- Launcher -> /usr/bin ------------------------------------------------
mkdir -p "$STAGE/usr/bin"
cat > "$STAGE/usr/bin/jura-desktop" <<'LAUNCHER'
#!/bin/sh
exec python3 /opt/jura-desktop/jura_app.py "$@"
LAUNCHER
chmod 755 "$STAGE/usr/bin/jura-desktop"

# --- Menu entry ------------------------------------------------------------
mkdir -p "$STAGE/usr/share/applications"
cp packaging/jura-desktop.desktop "$STAGE/usr/share/applications/"

# --- Icon, in the standard hicolor theme sizes (Icon=jura-desktop) ---------
for size in 48 64 128 256; do
    dir="$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    cp "icon_${size}.png" "$dir/jura-desktop.png"
done
mkdir -p "$STAGE/usr/share/icons/hicolor/scalable/apps"
cp icon.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/jura-desktop.svg"

# --- Copyright (Debian policy expects one; also our legal disclaimer) -----
mkdir -p "$STAGE/usr/share/doc/jura-desktop"
{
    echo "Independent, unofficial project. Not affiliated with JURA Elektroapparate AG."
    echo "Full disclaimer: see /opt/jura-desktop/README.md (section 'Disclaimer')."
    echo
    echo "Upstream: https://github.com/ovexro/JuraE4"
} > "$STAGE/usr/share/doc/jura-desktop/copyright"

# --- Control file ------------------------------------------------------
mkdir -p "$STAGE/DEBIAN"
sed "s/__VERSION__/$VERSION/" packaging/control.in > "$STAGE/DEBIAN/control"
cp packaging/postinst packaging/postrm "$STAGE/DEBIAN/"
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/postrm"

# Ownership root:root, permissions sane, regardless of who runs this script
find "$STAGE" -mindepth 1 -path "$STAGE/DEBIAN" -prune -o -type d -exec chmod 755 {} \;
find "$STAGE" -mindepth 1 -path "$STAGE/DEBIAN/*" -prune -o -type f -exec chmod 644 {} \;
chmod 755 "$STAGE/usr/bin/jura-desktop"

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/${PKG}_${VERSION}_all.deb"
fakeroot dpkg-deb --build --root-owner-group "$STAGE" "$OUT"

echo
echo "Built: ${OUT#"$ROOT"/}"
echo "Install with:   sudo apt install ./${OUT#"$ROOT"/}"
echo "Remove with:    sudo apt remove jura-desktop"

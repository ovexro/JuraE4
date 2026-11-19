#!/usr/bin/env bash
# JURA Desktop Control -- uninstaller (undoes install.sh).
#
#   ~/.local/share/jura-desktop/uninstall.sh            # remove the app, keep your settings
#   ~/.local/share/jura-desktop/uninstall.sh --purge    # also delete ~/.config/jura-desktop
#
# Your settings folder holds the saved dongle auth hash and brew preferences,
# so it is kept unless you pass --purge (handy if you reinstall later).
set -euo pipefail

INSTALL_DIR="${JURA_INSTALL_DIR:-$HOME/.local/share/jura-desktop}"
CONFIG_DIR="$HOME/.config/jura-desktop"
purge=0; [ "${1:-}" = "--purge" ] && purge=1

note() { printf '  %s\n' "$1"; }
rmq()  { if [ -e "$1" ] || [ -L "$1" ]; then rm -rf "$1" && note "removed $1"; fi; }

printf '\n\033[1mRemoving JURA Desktop Control...\033[0m\n'

# Stop a running instance first (best effort; only our own process)
pkill -f "$INSTALL_DIR/.*jura_app.py" 2>/dev/null || true

rmq "$HOME/.local/share/applications/jura-desktop.desktop"
rmq "$HOME/.config/autostart/jura-desktop.desktop"     # "Start at login", if it was enabled
rmq "$HOME/.local/bin/jura-desktop"

# Remove the install dir last -- this script may be running from inside it, which is fine on Linux
rmq "$INSTALL_DIR"

if [ "$purge" -eq 1 ]; then
    rmq "$CONFIG_DIR"
else
    [ -d "$CONFIG_DIR" ] && note "kept $CONFIG_DIR (settings + saved auth hash); delete it with --purge"
fi

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
printf '\nDone.\n'

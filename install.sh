#!/usr/bin/env bash
# JURA Desktop Control -- one-command installer.
#
#   curl -fsSL https://raw.githubusercontent.com/ovexro/JuraE4/main/install.sh | bash
#
# Clones the repo into ~/.local/share/jura-desktop (override with
# JURA_INSTALL_DIR), creates a Python virtualenv there, installs the
# dependencies, and adds a menu entry + a `jura-desktop` command. Safe to
# run again: it updates the existing install in place and never touches
# ~/.config/jura-desktop (your saved auth hash and preferences).
#
# Tested on Linux Mint / Ubuntu / Debian (apt). Best-effort on Fedora (dnf)
# and Arch (pacman); PyQt5 always comes from pip inside the venv either way.
set -euo pipefail

REPO_URL="${JURA_REPO_URL:-https://github.com/ovexro/JuraE4.git}"
INSTALL_DIR="${JURA_INSTALL_DIR:-$HOME/.local/share/jura-desktop}"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"

note()  { printf '  %s\n' "$1"; }
step()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
die()   { printf '\nError: %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. System packages (git, python3, venv, pip) -- best-effort per distro
# ---------------------------------------------------------------------------
step "Checking system packages..."

need=()   # generic names; translated per package manager below
command -v git >/dev/null 2>&1 || need+=(git)
command -v python3 >/dev/null 2>&1 || need+=(python3)
python3 -c "import ensurepip" >/dev/null 2>&1 || need+=(venv)
python3 -c "import pip" >/dev/null 2>&1 || need+=(pip)

if [ "${#need[@]}" -gt 0 ]; then
    note "Missing: ${need[*]}"
    if command -v apt-get >/dev/null 2>&1; then
        pkgs=(); for n in "${need[@]}"; do
            case "$n" in venv) pkgs+=(python3-venv);; pip) pkgs+=(python3-pip);; *) pkgs+=("$n");; esac
        done
        sudo apt-get update -qq && sudo apt-get install -y "${pkgs[@]}"
    elif command -v dnf >/dev/null 2>&1; then
        pkgs=(); for n in "${need[@]}"; do          # Fedora ships venv inside python3
            case "$n" in venv) pkgs+=(python3);; pip) pkgs+=(python3-pip);; *) pkgs+=("$n");; esac
        done
        sudo dnf install -y "${pkgs[@]}"
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --needed --noconfirm git python python-pip
    else
        die "Unsupported package manager. Please install manually: ${need[*]}"
    fi
else
    note "All present."
fi

for cmd in git python3; do
    command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is still missing after the install step."
done

# ---------------------------------------------------------------------------
# 2. Get the code (clone, or pull if already installed)
# ---------------------------------------------------------------------------
step "Fetching JURA Desktop Control..."

if [ -d "$INSTALL_DIR/.git" ]; then
    note "Existing install found at $INSTALL_DIR -- updating."
    git -C "$INSTALL_DIR" pull --ff-only
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# ---------------------------------------------------------------------------
# 3. Virtualenv + Python dependencies
# ---------------------------------------------------------------------------
step "Setting up the Python environment..."

cd "$INSTALL_DIR"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# ---------------------------------------------------------------------------
# 4. Desktop entry + launcher command
# ---------------------------------------------------------------------------
step "Adding the menu entry and the jura-desktop command..."

chmod +x "$INSTALL_DIR/run.sh"
mkdir -p "$APPS_DIR" "$BIN_DIR"

cat > "$APPS_DIR/jura-desktop.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=JURA Desktop Control
Comment=Control your JURA E4 coffee machine
Exec=$INSTALL_DIR/run.sh
Icon=$INSTALL_DIR/icon_256.png
Terminal=false
Categories=Utility;
StartupWMClass=jura_app
DESKTOP

cat > "$BIN_DIR/jura-desktop" <<LAUNCHER
#!/usr/bin/env bash
exec "$INSTALL_DIR/run.sh" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/jura-desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
step "Done!"
note "Installed to:  $INSTALL_DIR"
note "Launch it from your application menu (\"JURA Desktop Control\"),"
note "or by running:  jura-desktop"
case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *) printf '\n  Note: %s is not on your PATH yet -- open a new terminal,\n' "$BIN_DIR"
       note "  or use the menu entry, to run the jura-desktop command." ;;
esac
note ""
note "First launch walks you through a one-time setup (pairing with your"
note "WiFi Connect V2 dongle). See README.md if you'd rather do it by hand."

#!/usr/bin/env bash
# Orca Resource Monitor -- Installer
#
# Installs Resource Monitor as an Orca 51 user extension, into
# ~/.local/share/orca/extensions/, and approves it so Orca will load it.
#
# Re-running is safe. Because approval is by content hash, the script
# re-approves on every run -- which is what you want after editing.
#
# This add-on is a single module rather than a package, so the approval key
# is the filename including the extension: resource_monitor.py.

set -euo pipefail

ADDON_NAME="resource_monitor.py"
ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
EXTENSIONS_DIR="$ORCA_DIR/extensions"
ADDON_PATH="$EXTENSIONS_DIR/$ADDON_NAME"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/$ADDON_NAME"

BEGIN_MARKER="# --- resource-monitor begin ---"
END_MARKER="# --- resource-monitor end ---"

info()  { echo "  [+] $*"; }
warn()  { echo "  [!] $*"; }
error() { echo "  [ERROR] $*" >&2; exit 1; }

echo ""
echo "=== Orca Resource Monitor -- Installer ==="
echo ""

# Probe via extension_loader, not orca.extension: importing orca.extension
# first hits a circular import inside Orca itself (live_region_presenter
# imports it mid-initialisation). extension_loader pulls in command_manager
# ahead of it, so this import order is the one that works.
if ! python3 -c "import orca.extension_loader" 2>/dev/null; then
    error "Orca 51 or later with extension support not found."
fi
info "Orca with extension support found."

if ! python3 -c "import psutil" 2>/dev/null; then
    error "psutil not found. Install it (python-psutil, python3-psutil, or pip install psutil)."
fi
info "psutil available."

[ -f "$SOURCE" ] || error "Source file '$SOURCE' not found."

mkdir -p "$EXTENSIONS_DIR"
cp "$SOURCE" "$ADDON_PATH"
info "Installed $ADDON_NAME to $EXTENSIONS_DIR/"

# Versions before 2.0.0 were loaded by a block appended to
# orca-customizations.py, importing the module from $ORCA_DIR. Leaving that
# in place registers all ten commands a second time on every Orca start --
# Orca logs "Unexpected re-registration" and the later registration silently
# replaces the earlier one. Remove it, and the module it loaded.
if [ -f "$CUSTOMIZATIONS" ] && grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    info "Removed the pre-2.0.0 loader block from orca-customizations.py"
fi
if [ -f "$ORCA_DIR/$ADDON_NAME" ]; then
    rm -f "$ORCA_DIR/$ADDON_NAME"
    info "Removed the pre-2.0.0 copy from $ORCA_DIR/"
fi

if orca --approve-extension "$ADDON_NAME" >/dev/null 2>&1; then
    info "Approved '$ADDON_NAME' with Orca."
else
    error "Could not approve the extension. Run: orca --approve-extension $ADDON_NAME"
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "  Restart Orca to activate:"
echo "    orca --replace &"
echo ""
echo "  Orca+Shift+1 through 0 report processor, memory, storage, network,"
echo "  battery, uptime, OS, audio out, audio in, and system load."
echo "  Orca+Ctrl+Shift+4 runs a network speed test."
echo ""

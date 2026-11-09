#!/usr/bin/env bash
# Orca Resource Monitor -- Uninstaller
#
# Removes the extension and revokes its Orca approval, and clears the
# pre-2.0.0 loader block if it is still present.

set -euo pipefail

ADDON_NAME="resource_monitor.py"
ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
ADDON_PATH="$ORCA_DIR/extensions/$ADDON_NAME"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"

BEGIN_MARKER="# --- resource-monitor begin ---"
END_MARKER="# --- resource-monitor end ---"

info() { echo "  [+] $*"; }

echo ""
echo "=== Orca Resource Monitor -- Uninstaller ==="
echo ""

# Revoke first: once the file is gone Orca can no longer identify it.
if orca --revoke-extension "$ADDON_NAME" >/dev/null 2>&1; then
    info "Revoked Orca's approval of '$ADDON_NAME'."
else
    info "No Orca approval to revoke (already removed)."
fi

if [ -f "$ADDON_PATH" ]; then
    rm -f "$ADDON_PATH"
    info "Removed $ADDON_PATH"
else
    info "No installed extension at $ADDON_PATH (already removed)."
fi

if [ -f "$CUSTOMIZATIONS" ] && grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    info "Removed the pre-2.0.0 loader block from orca-customizations.py"
fi
[ -f "$ORCA_DIR/$ADDON_NAME" ] && rm -f "$ORCA_DIR/$ADDON_NAME" && info "Removed the pre-2.0.0 copy."

echo ""
echo "=== Uninstall complete ==="
echo ""
echo "  Restart Orca for the change to take effect:"
echo "    orca --replace &"
echo ""

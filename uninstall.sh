#!/usr/bin/env bash
# Uninstall Orca Resource Monitor add-on
set -euo pipefail

ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"
MODULE="$ORCA_DIR/resource_monitor.py"

BEGIN_MARKER="# --- resource-monitor begin ---"
END_MARKER="# --- resource-monitor end ---"

# Remove the module
if [ -f "$MODULE" ]; then
    rm "$MODULE"
    echo "Removed $MODULE"
else
    echo "Module not found at $MODULE (already removed?)"
fi

# Remove the loader block from customizations
if [ -f "$CUSTOMIZATIONS" ] && grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    # Clean up any trailing blank lines left behind
    sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$CUSTOMIZATIONS"
    echo "Removed resource-monitor block from $CUSTOMIZATIONS"
else
    echo "No resource-monitor block found in customizations (already removed?)"
fi

# Remove bytecode cache
rm -f "$ORCA_DIR/__pycache__/resource_monitor"*.pyc 2>/dev/null
rm -rf "$ORCA_DIR/__pycache__" 2>/dev/null && echo "Removed bytecode cache" || true

echo ""
echo "Uninstall complete. Restart Orca to apply:"
echo "  orca --replace"

#!/usr/bin/env bash
# Install Orca Resource Monitor add-on
set -euo pipefail

ORCA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/orca"
CUSTOMIZATIONS="$ORCA_DIR/orca-customizations.py"
MODULE="resource_monitor.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

BEGIN_MARKER="# --- resource-monitor begin ---"
END_MARKER="# --- resource-monitor end ---"

LOADER_BLOCK="${BEGIN_MARKER}
try:
    import sys as _sys, os as _os
    _orca_dir = _os.path.join(
        _os.environ.get(\"XDG_DATA_HOME\", _os.path.expanduser(\"~/.local/share\")),
        \"orca\"
    )
    if _orca_dir not in _sys.path:
        _sys.path.insert(0, _orca_dir)
    from resource_monitor import register as _resmon_register
    _resmon_register()
except Exception as _e:
    import logging as _logging
    _logging.getLogger(\"orca-resource-monitor\").error(
        f\"Failed to load resource monitor: {_e}\", exc_info=True
    )
${END_MARKER}"

# Ensure Orca user directory exists
if [ ! -d "$ORCA_DIR" ]; then
    echo "Error: Orca data directory not found at $ORCA_DIR"
    exit 1
fi

# Copy the module
cp "$SCRIPT_DIR/$MODULE" "$ORCA_DIR/$MODULE"
echo "Installed $MODULE to $ORCA_DIR/"

# Create customizations file if it doesn't exist
if [ ! -f "$CUSTOMIZATIONS" ]; then
    touch "$CUSTOMIZATIONS"
    echo "Created $CUSTOMIZATIONS"
fi

# Remove any existing resource-monitor block, then append fresh
if grep -q "$BEGIN_MARKER" "$CUSTOMIZATIONS" 2>/dev/null; then
    # Use sed to delete from begin marker to end marker (inclusive)
    sed -i "/${BEGIN_MARKER//\//\\/}/,/${END_MARKER//\//\\/}/d" "$CUSTOMIZATIONS"
    echo "Removed previous resource-monitor block from customizations"
fi

# Append the loader block
printf '\n%s\n' "$LOADER_BLOCK" >> "$CUSTOMIZATIONS"
echo "Appended resource-monitor loader to $CUSTOMIZATIONS"

echo ""
echo "Installation complete. Restart Orca to activate:"
echo "  orca --replace"

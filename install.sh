#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_FILE="htmldispatch.desktop"
DESKTOP_DEST="$HOME/.local/share/applications/$DESKTOP_FILE"
BIN_LINK="$HOME/.local/bin/htmldispatch"

# Install as editable with uv
cd "$SCRIPT_DIR"
uv sync

# Create a wrapper script that uses uv run
cat > "$BIN_LINK" << WRAPPER
#!/bin/bash
cd "$SCRIPT_DIR"
exec uv run htmldispatch "\$@"
WRAPPER
chmod +x "$BIN_LINK"

echo "Installed $BIN_LINK"

# Install desktop file
install -m 644 "$SCRIPT_DIR/$DESKTOP_FILE" "$DESKTOP_DEST"

echo "Installed $DESKTOP_DEST"

# Update desktop database
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Set as default handler for http/https
xdg-settings set default-web-browser "$DESKTOP_FILE" 2>/dev/null || true
xdg-mime default "$DESKTOP_FILE" x-scheme-handler/http 2>/dev/null || true
xdg-mime default "$DESKTOP_FILE" x-scheme-handler/https 2>/dev/null || true

echo ""
echo "htmldispatch is now the default web browser/URL handler."
echo ""
echo "Config file: ~/.config/htmldispatch/config.yaml"
echo "Manager GUI: htmldispatch --manage"

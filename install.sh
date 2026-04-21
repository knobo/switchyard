#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_FILE="htmldispatch.desktop"
DESKTOP_DEST="$HOME/.local/share/applications/$DESKTOP_FILE"
BIN_LINK="$HOME/.local/bin/htmldispatch"

# Install as editable with uv
cd "$SCRIPT_DIR"
uv sync

# Create a wrapper that calls the venv binary directly, so it works from
# processes with a minimal PATH (e.g. Slack/Electron) that don't have
# ~/.local/bin or uv/pyenv on PATH.
cat > "$BIN_LINK" << WRAPPER
#!/bin/bash
exec "$SCRIPT_DIR/.venv/bin/htmldispatch" "\$@"
WRAPPER
chmod +x "$BIN_LINK"

echo "Installed $BIN_LINK"

# Install desktop file with absolute path to the wrapper so apps whose
# PATH lacks ~/.local/bin (e.g. Slack/Electron) can still launch it.
sed "s|^Exec=htmldispatch |Exec=$BIN_LINK |" "$SCRIPT_DIR/$DESKTOP_FILE" > "$DESKTOP_DEST"
chmod 644 "$DESKTOP_DEST"

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

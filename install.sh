#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_FILE="switchyard.desktop"
DESKTOP_DEST="$HOME/.local/share/applications/$DESKTOP_FILE"
BIN_LINK="$HOME/.local/bin/switchyard"

# Remove the install from when this app was called htmldispatch
rm -f "$HOME/.local/bin/htmldispatch" "$HOME/.local/share/applications/htmldispatch.desktop"
rm -f "$HOME"/.local/share/icons/hicolor/*/apps/htmldispatch.*

# Install as editable with uv
cd "$SCRIPT_DIR"
uv sync

# Create a wrapper that calls the venv binary directly, so it works from
# processes with a minimal PATH (e.g. Slack/Electron) that don't have
# ~/.local/bin or uv/pyenv on PATH.
cat > "$BIN_LINK" << WRAPPER
#!/bin/bash
exec "$SCRIPT_DIR/.venv/bin/switchyard" "\$@"
WRAPPER
chmod +x "$BIN_LINK"

echo "Installed $BIN_LINK"

# Install the app icon into the user icon theme (Icon=switchyard resolves here)
ICON_DEST="$HOME/.local/share/icons/hicolor"
mkdir -p "$ICON_DEST"
cp -r "$SCRIPT_DIR/icons/hicolor/." "$ICON_DEST/"
gtk-update-icon-cache -f -t "$ICON_DEST" 2>/dev/null || true

echo "Installed icons in $ICON_DEST"

# Install desktop file with absolute path to the wrapper so apps whose
# PATH lacks ~/.local/bin (e.g. Slack/Electron) can still launch it.
sed "s|^Exec=switchyard |Exec=$BIN_LINK |" "$SCRIPT_DIR/$DESKTOP_FILE" > "$DESKTOP_DEST"
chmod 644 "$DESKTOP_DEST"

echo "Installed $DESKTOP_DEST"

# Update desktop database
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Set as default handler for http/https
xdg-settings set default-web-browser "$DESKTOP_FILE" 2>/dev/null || true
xdg-mime default "$DESKTOP_FILE" x-scheme-handler/http 2>/dev/null || true
xdg-mime default "$DESKTOP_FILE" x-scheme-handler/https 2>/dev/null || true

# claude:// deep links carry no hint about which browser profile you clicked
# them from, so route them through the dispatcher to pick a Claude profile.
if command -v claude-desktop >/dev/null 2>&1; then
    xdg-mime default "$DESKTOP_FILE" x-scheme-handler/claude 2>/dev/null || true
fi

echo ""
echo "switchyard is now the default web browser/URL handler."
echo ""
echo "Config file: ~/.config/switchyard/config.yaml"
echo "Manager GUI: switchyard --manage"

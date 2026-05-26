#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXE="$APP_DIR/eMeX"
ICON="$APP_DIR/_internal/docs/assets/icon_eMeX.png"
DESKTOP_NAME="emex.desktop"

if [ ! -f "$EXE" ] || [ ! -x "$EXE" ]; then
  echo "Missing executable: $EXE" >&2
  exit 1
fi

if [ ! -f "$ICON" ]; then
  ICON="$APP_DIR/docs/assets/icon_eMeX.png"
fi
if [ ! -f "$ICON" ]; then
  echo "Missing icon_eMeX.png" >&2
  exit 1
fi

desktop_quote() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g'
}

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPLICATIONS_DIR="$DATA_HOME/applications"
mkdir -p "$APPLICATIONS_DIR"

EXEC_ESCAPED="$(desktop_quote "$EXE")"
ICON_ESCAPED="$(desktop_quote "$ICON")"

write_entry() {
  local target="$1"
  cat > "$target" <<EOF
[Desktop Entry]
Type=Application
Name=eMeX
Comment=Markdown math editor with AI assistance
Exec="$EXEC_ESCAPED"
Icon=$ICON_ESCAPED
Terminal=false
Categories=Education;Office;
StartupNotify=true
StartupWMClass=eMeX
EOF
  chmod 755 "$target" || true
}

write_entry "$APPLICATIONS_DIR/$DESKTOP_NAME"
write_entry "$APP_DIR/eMeX.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "Desktop entry installed: $APPLICATIONS_DIR/$DESKTOP_NAME"

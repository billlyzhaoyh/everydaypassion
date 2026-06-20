#!/usr/bin/env bash
# Install the LaunchAgent that opens the morning ritual on first login each day.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"
PLIST_SRC="$REPO_DIR/scripts/com.everydaypassion.open.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.everydaypassion.open.plist"
API_KEY="${ANTHROPIC_API_KEY:-}"

if [ ! -x "$PYTHON" ]; then
  echo "Python not found at $PYTHON — set PYTHON=/path/to/python and retry." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.everydaypassion"

sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__HOME__|$HOME|g" \
    -e "s|__REPO__|$REPO_DIR|g" \
    -e "s|__ANTHROPIC_API_KEY__|$API_KEY|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed $PLIST_DST"
echo "It will open the ritual on your next login. Test now with: $PYTHON -m everydaypassion open --force"

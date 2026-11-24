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

if [ -n "$API_KEY" ]; then
  # Keep the key's block, drop only the marker comments.
  ENV_EDIT=(-e "/__ENV_START__/d" -e "/__ENV_END__/d")
else
  # No key exported: leave EnvironmentVariables out entirely. An empty
  # ANTHROPIC_API_KEY would hide the key in .env (load_dotenv never overrides).
  ENV_EDIT=(-e "/__ENV_START__/,/__ENV_END__/d")
  echo "No ANTHROPIC_API_KEY exported — the agent will use the key in $REPO_DIR/.env, if any."
fi

# The plist may hold the API key: create it readable by you only.
( umask 077
  sed "${ENV_EDIT[@]}" \
      -e "s|__PYTHON__|$PYTHON|g" \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__REPO__|$REPO_DIR|g" \
      -e "s|__ANTHROPIC_API_KEY__|$API_KEY|g" \
      "$PLIST_SRC" > "$PLIST_DST" )
chmod 600 "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed $PLIST_DST"
echo "It will open the ritual at login and each morning (06:00, or first wake after). Test now with: $PYTHON -m everydaypassion open --force"

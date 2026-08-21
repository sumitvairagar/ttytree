#!/usr/bin/env bash
# ttytree :: uninstaller — removes the symlinks and the Stop hook.
# Your trees in ~/.claude/ttytree are left alone; delete that directory yourself
# if you want them gone.
set -euo pipefail
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
SETTINGS="$CLAUDE_HOME/settings.json"

[ -L "$CLAUDE_HOME/skills/ttytree" ] && rm -f "$CLAUDE_HOME/skills/ttytree" && echo "  ✔ skill removed"
[ -L "$BIN_DIR/ttytree" ]            && rm -f "$BIN_DIR/ttytree"            && echo "  ✔ cli removed"

if [ -f "$SETTINGS" ] && command -v jq >/dev/null 2>&1; then
  cp "$SETTINGS" "$SETTINGS.ttytree-backup.$(date +%Y%m%d%H%M%S)"
  tmp=$(mktemp)
  jq '
      if .hooks.Stop then
        .hooks.Stop |= map(select( ((.hooks // []) | map(.command // "")
                          | any(test("ttytree-log"))) | not ))
      else . end
    | if (.hooks.Stop? | length) == 0 then del(.hooks.Stop) else . end
    | if (.hooks? | length) == 0 then del(.hooks) else . end
  ' "$SETTINGS" > "$tmp"
  if jq -e . "$tmp" >/dev/null 2>&1; then mv "$tmp" "$SETTINGS"; echo "  ✔ hook unregistered"
  else rm -f "$tmp"; echo "  ✘ settings.json left unchanged" >&2; fi
fi
echo "  · trees kept at $CLAUDE_HOME/ttytree"

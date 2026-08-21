#!/usr/bin/env bash
# ttytree :: installer
#
#   ./install.sh            install for the current user
#   ./install.sh --dry-run  show what would change
#
# Installs three things:
#   1. the /ttytree skill  -> ~/.claude/skills/ttytree      (symlink)
#   2. the ttytree CLI     -> ~/.local/bin/ttytree          (symlink)
#   3. a Stop hook          -> ~/.claude/settings.json        (backed up first)
#
# Symlinks, so `git pull` in this repo updates your install.

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
SETTINGS="$CLAUDE_HOME/settings.json"
HOOK="$REPO/hooks/ttytree-log.sh"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

say()  { printf '  %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
run()  { if [ "$DRY" = 1 ]; then say "would: $*"; else eval "$@"; fi; }

step "ttytree installer"
say "repo: $REPO"
[ "$DRY" = 1 ] && say "(dry run — nothing will be written)"

# --- dependencies ------------------------------------------------------------
step "1/4  dependencies"
missing=0
for dep in jq awk; do
  if command -v "$dep" >/dev/null 2>&1; then say "✔ $dep"; else say "✘ $dep — required"; missing=1; fi
done
if [ "$missing" = 1 ]; then
  echo; echo "Install the missing dependency first (macOS: brew install jq)." >&2
  exit 1
fi
command -v git >/dev/null 2>&1 && say "✔ git (optional, enables branch/dirty info)" || say "· git not found — branch info disabled"

# --- skill -------------------------------------------------------------------
step "2/4  skill  ->  $CLAUDE_HOME/skills/ttytree"
run "mkdir -p '$CLAUDE_HOME/skills'"
if [ -e "$CLAUDE_HOME/skills/ttytree" ] && [ ! -L "$CLAUDE_HOME/skills/ttytree" ]; then
  say "✘ a real directory already exists there — move it aside first"; exit 1
fi
run "ln -sfn '$REPO/skills/ttytree' '$CLAUDE_HOME/skills/ttytree'"
say "✔ /ttytree available in new sessions"

# --- cli ---------------------------------------------------------------------
step "3/4  cli  ->  $BIN_DIR/ttytree"
run "mkdir -p '$BIN_DIR'"
run "ln -sfn '$REPO/bin/ttytree' '$BIN_DIR/ttytree'"
case ":$PATH:" in
  *":$BIN_DIR:"*) say "✔ $BIN_DIR is on PATH" ;;
  *) say "! $BIN_DIR is not on PATH — add this to your shell rc:"
     say "    export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# --- stop hook ---------------------------------------------------------------
step "4/4  Stop hook  ->  $SETTINGS"
chmod +x "$HOOK" 2>/dev/null || true
if [ "$DRY" = 1 ]; then
  say "would register: $HOOK"
else
  [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
  cp "$SETTINGS" "$SETTINGS.ttytree-backup.$(date +%Y%m%d%H%M%S)"
  tmp=$(mktemp)
  jq --arg cmd "$HOOK" '
      .hooks //= {}
    | .hooks.Stop //= []
    # drop any previous ttytree registration, then add exactly one
    | .hooks.Stop |= ( map(select( ((.hooks // []) | map(.command // "")
                                    | any(test("ttytree-log"))) | not )) )
    | .hooks.Stop += [ { hooks: [ { type: "command", command: $cmd } ] } ]
  ' "$SETTINGS" > "$tmp"
  if jq -e . "$tmp" >/dev/null 2>&1; then
    mv "$tmp" "$SETTINGS"
    say "✔ hook registered (previous settings backed up)"
  else
    rm -f "$tmp"; say "✘ failed to update settings.json — left unchanged"; exit 1
  fi
fi

step "done"
cat <<'TXT'
  Restart Claude Code (or open a new session) to pick up the skill and hook.

    ttytree            show this terminal's tree
    ttytree --all      every tracked session
    /ttytree           update the tree, then show it

  The hook starts collecting facts on your next turn. Trees appear once you
  run /ttytree at least once in a session.
TXT

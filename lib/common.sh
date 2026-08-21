#!/usr/bin/env bash
# Shared helpers for ttytree.
# Sourced by bin/ttytree and hooks/tree-log.sh. No side effects on source.

TTYTREE_HOME="${TTYTREE_HOME:-$HOME/.claude/ttytree}"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"

# Walk up the process tree from $1 (default: current shell) until we hit the
# `claude` process that owns this terminal, then read the session registry
# Claude Code maintains at ~/.claude/sessions/<pid>.json.
# Echoes the session id, or nothing if not running under Claude Code.
tt_resolve_session() {
  local p="${1:-$PPID}" i cmd
  for i in 1 2 3 4 5 6 7 8; do
    case "$p" in ""|0|1) return 0 ;; esac
    cmd=$(ps -o comm= -p "$p" 2>/dev/null) || return 0
    case "$cmd" in
      *claude)
        if [ -f "$CLAUDE_HOME/sessions/$p.json" ]; then
          jq -r '.sessionId // empty' "$CLAUDE_HOME/sessions/$p.json" 2>/dev/null
        fi
        return 0
        ;;
    esac
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
  done
  return 0
}

# Session metadata straight from Claude Code's own registry.
# tt_session_meta <session-id> -> compact json {sessionId,cwd,name,status,tty}
tt_session_meta() {
  local sid="$1" f pid
  for f in "$CLAUDE_HOME"/sessions/*.json; do
    [ -f "$f" ] || continue
    if [ "$(jq -r '.sessionId // empty' "$f" 2>/dev/null)" = "$sid" ]; then
      pid=$(basename "$f" .json)
      jq -c --arg tty "$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')" \
         '{sessionId,cwd,name,status,pid,tty:$tty}' "$f" 2>/dev/null
      return 0
    fi
  done
}

tt_dir()    { printf '%s/%s' "$TTYTREE_HOME" "$1"; }
tt_tree()   { printf '%s/%s/tree.md' "$TTYTREE_HOME" "$1"; }
tt_events() { printf '%s/%s/events.jsonl' "$TTYTREE_HOME" "$1"; }

tt_ensure() { mkdir -p "$(tt_dir "$1")" 2>/dev/null || true; }

# Human-readable age from an epoch seconds value.
tt_ago() {
  local d=$(( $(date +%s) - ${1:-0} ))
  if   [ "$d" -lt 60 ]    ; then printf '%ds' "$d"
  elif [ "$d" -lt 3600 ]  ; then printf '%dm' "$((d/60))"
  elif [ "$d" -lt 86400 ] ; then printf '%dh' "$((d/3600))"
  else                          printf '%dd' "$((d/86400))"
  fi
}

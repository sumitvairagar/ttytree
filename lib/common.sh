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

# --- icons -----------------------------------------------------------------
# Does this terminal look like it can render wide emoji?
tt_unicode_ok() {
  case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
    *UTF-8*|*utf8*|*UTF8*|*utf-8*) return 0 ;;
  esac
  return 1
}

# Category icons are inferred from the item text — nothing to write by hand,
# so old trees light up too. Format: icon=regex;icon=regex;...  First match
# wins, so specific domains come before generic verbs. Lowercased before
# matching. Keep every icon two cells wide or the tree stops lining up.
tt_icon_rules() {
  printf '%s' \
'🚀=deploy|release|ship|publish|rollout|launch|prod|staging|testflight|app store;'\
'🐛=bug|crash|regress|broken|fail|panic|flaky|stack trace|traceback;'\
'🧪=test|spec|e2e|coverage|snapshot|fixture|verif;'\
'📝=doc|readme|changelog|write.up|blog post|comment;'\
'🔀=commit|merge|rebase|pull request|branch|cherry.pick|conflict;'\
'💾=database|schema|migration|postgres|sqlite|mysql|redis|query|table|backfill|sync|import|export|seed;'\
'🔐=auth|login|sign|oauth|credential|permission|secret|security|password|key;'\
'🔌=api|endpoint|route|webhook|graphql|grpc|payload|queue|worker|cron|middleware|integration;'\
'🎨=ui|screen|page|css|style|layout|component|design|theme|button|modal|onboarding|icon;'\
'📈=perf|slow|latency|optimi|cache|benchmark|profil|metric|analytic|rate limit|throttl;'\
'🧹=refactor|cleanup|clean up|rename|tidy|dead code|lint|dedup|duplicat;'\
'🔍=research|investigate|explore|spike|debug|root cause|reproduce|figure out|audit;'\
'📦=package|bundle|npm|yarn|docker|dependenc|upgrade|version;'\
'🔧=config|setup|install|env|tooling|script|flag|alert|log'
}

# Project name for a session — the registry knows it while the session is
# alive, the last event remembers it afterwards.
tt_project_of() {
  local sid="$1" cwd
  cwd=$(tt_session_meta "$sid" 2>/dev/null | jq -r '.cwd // empty' 2>/dev/null)
  [ -n "$cwd" ] || cwd=$(tail -1 "$(tt_events "$sid")" 2>/dev/null | jq -r '.cwd // empty' 2>/dev/null)
  [ -n "$cwd" ] && basename "$cwd"
}

# All tracked session ids, newest tree first.
tt_all_sessions() {
  local d
  for d in "$TTYTREE_HOME"/*/; do
    [ -d "$d" ] || continue
    printf '%s\t%s\n' "$(stat -f %m "$d/tree.md" 2>/dev/null || stat -c %Y "$d/tree.md" 2>/dev/null || echo 0)" "$(basename "$d")"
  done | sort -rn | cut -f2
}

# Resolve a user-typed target to a session id: exact id, id prefix, exact
# project name, then project prefix. Newest tree wins a tie.
tt_match_session() {
  local want="$1" sid proj lw
  [ -n "$want" ] || return 1
  lw=$(printf '%s' "$want" | tr '[:upper:]' '[:lower:]')
  for sid in $(tt_all_sessions); do
    case "$sid" in "$want"*) printf '%s' "$sid"; return 0 ;; esac
  done
  for sid in $(tt_all_sessions); do
    proj=$(tt_project_of "$sid" | tr '[:upper:]' '[:lower:]')
    [ "$proj" = "$lw" ] && { printf '%s' "$sid"; return 0; }
  done
  for sid in $(tt_all_sessions); do
    proj=$(tt_project_of "$sid" | tr '[:upper:]' '[:lower:]')
    case "$proj" in "$lw"*) printf '%s' "$sid"; return 0 ;; esac
  done
  return 1
}

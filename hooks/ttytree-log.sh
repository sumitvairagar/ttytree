#!/usr/bin/env bash
# ttytree :: Stop hook — the zero-token fact collector.
#
# Runs as a plain shell script after every assistant turn. It never calls a
# model, so it costs zero tokens. It reads only the bytes appended to the
# transcript since the previous turn (tracked by a byte offset), so its cost
# stays flat no matter how large the session grows.
#
# Output: one compact JSON line per turn in
#   ~/.claude/ttytree/<session-id>/events.jsonl
#
# This hook must never break a turn: it always exits 0.

set -uo pipefail
# resolve through symlinks — this file is installed as a symlink
_src="${BASH_SOURCE[0]}"
while [ -L "$_src" ]; do
  _dir="$(cd -P "$(dirname "$_src")" && pwd)"
  _src="$(readlink "$_src")"
  case "$_src" in /*) ;; *) _src="$_dir/$_src" ;; esac
done
SELF_DIR="$(cd -P "$(dirname "$_src")" && pwd)"
# shellcheck source=../lib/common.sh
. "$SELF_DIR/../lib/common.sh"

MAX_EVENTS="${TTYTREE_MAX_EVENTS:-500}"

main() {
  command -v jq >/dev/null 2>&1 || return 0

  local payload sid transcript cwd
  payload=$(cat 2>/dev/null) || return 0
  [ -n "$payload" ] || return 0

  sid=$(printf '%s' "$payload"        | jq -r '.session_id // empty' 2>/dev/null)
  transcript=$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)
  cwd=$(printf '%s' "$payload"        | jq -r '.cwd // empty' 2>/dev/null)
  [ -n "$sid" ] || return 0

  tt_ensure "$sid"
  local dir off_file events size off new_bytes
  dir=$(tt_dir "$sid")
  off_file="$dir/offset"
  events=$(tt_events "$sid")

  # --- incremental transcript read -----------------------------------------
  local facts='{}' saw_new=0
  if [ -n "$transcript" ] && [ -f "$transcript" ]; then
    size=$(stat -f %z "$transcript" 2>/dev/null || stat -c %s "$transcript" 2>/dev/null || echo 0)
    off=$(cat "$off_file" 2>/dev/null || echo 0)
    case "$off" in ''|*[!0-9]*) off=0 ;; esac
    [ "$off" -gt "$size" ] && off=0          # transcript rotated or truncated

    if [ "$size" -gt "$off" ]; then
      new_bytes=$(tail -c "+$((off + 1))" "$transcript" 2>/dev/null | head -c "$((size - off))")
      facts=$(printf '%s' "$new_bytes" | extract_facts) || facts='{}'
      printf '%s' "$size" > "$off_file" 2>/dev/null || true
      saw_new=1
    fi
  fi

  # Nothing new since the last turn: don't pad the log with empty events.
  [ "$saw_new" -eq 1 ] || return 0

  # --- cheap repo state ----------------------------------------------------
  local branch='' dirty=0
  if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
    dirty=$(git -C "$cwd" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  fi

  # --- append one event ----------------------------------------------------
  printf '%s' "$facts" | jq -c \
      --argjson ts "$(date +%s)" \
      --arg cwd "$cwd" --arg branch "$branch" --argjson dirty "${dirty:-0}" \
      '. + {ts:$ts, cwd:$cwd, branch:$branch, dirty:$dirty}' \
      >> "$events" 2>/dev/null || true

  # --- bound the log -------------------------------------------------------
  local count
  count=$(wc -l < "$events" 2>/dev/null | tr -d ' ')
  if [ -n "$count" ] && [ "$count" -gt "$MAX_EVENTS" ]; then
    tail -n "$MAX_EVENTS" "$events" > "$events.tmp" 2>/dev/null &&
      mv "$events.tmp" "$events" 2>/dev/null || true
  fi
}

# Condense one turn's worth of transcript lines into a small fact object.
extract_facts() {
  jq -nR '
    [ inputs | fromjson? ]                              as $msgs
    | ( [ $msgs[] | select(.type == "assistant")
          | .message.content[]? | select(.type == "tool_use") ] )  as $tools
    | ( [ $msgs[] | select(.type == "user")
          | .message.content
          | if type == "array"
            then ( [ .[] | select(.type == "text") | .text ] | join(" ") )
            else (. // "" | tostring) end ]
        | map(select(length > 0)) | last // "" )        as $prompt
    | ( [ $msgs[] | select(.type == "assistant")
          | .message.content[]? | select(.type == "text") | .text ]
        | last // "" )                                  as $reply
    | {
        tools:  ( $tools | group_by(.name)
                  | map({ (.[0].name): length }) | add // {} ),
        files:  ( [ $tools[] | .input.file_path // .input.notebook_path // empty ]
                  | unique | .[0:12] ),
        cmds:   ( [ $tools[] | select(.name == "Bash") | .input.command // empty
                    | gsub("\n"; " ") | .[0:100] ] | .[0:6] ),
        prompt: ( $prompt | gsub("\\s+"; " ") | .[0:180] ),
        reply:  ( $reply  | gsub("\\s+"; " ") | .[0:180] )
      }
  ' 2>/dev/null || echo '{}'
}

main "$@" || true
exit 0

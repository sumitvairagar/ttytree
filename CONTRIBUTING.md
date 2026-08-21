# Contributing

Small, focused pull requests are very welcome.

## Before you start

Read [`docs/DESIGN.md`](docs/DESIGN.md). Two constraints are non-negotiable, and
most rejected changes violate one of them:

1. **Capture costs zero tokens.** Anything that runs automatically must be a
   shell script, never a model call.
2. **Never read the session transcript from the skill.** It is tens of megabytes.
   The `Stop` hook reads it incrementally by byte offset; nothing else touches it.

## Environment

Requires `bash`, `jq`, and `awk`. Target macOS and Linux.

macOS ships **BWK awk**, not gawk. No 3-arg `match()`, no `gensub()`. If you
write awk, test it with `/usr/bin/awk` on macOS, not just `gawk` on Linux.

## Testing a change

Point the tool at a scratch directory so you don't touch real data:

```bash
export TTYTREE_HOME=/tmp/ttytree-test

# exercise the hook against a copy of a transcript
cp ~/.claude/projects/<some-project>/<session>.jsonl /tmp/frozen.jsonl
printf '{"session_id":"test","transcript_path":"/tmp/frozen.jsonl","cwd":"'$PWD'"}' \
  | ./hooks/ttytree-log.sh
cat "$TTYTREE_HOME/test/events.jsonl" | jq .

# running it again on a frozen transcript must add no new event
```

Then check syntax and render:

```bash
bash -n bin/ttytree hooks/ttytree-log.sh lib/common.sh install.sh
./bin/ttytree --session test --no-color
```

## Things that would genuinely help

See the roadmap in the [README](README.md). The board view and terminal tab
colouring are the highest-value open items.

Please don't add a daemon, a database, or a config file without discussing it in
an issue first — the absence of all three is a feature.

# Design notes

Why `ttytree` is shaped the way it is. Read this before adding a feature — most
rejected ideas were rejected for one of the reasons below.

## 1. The terminal is the unit, not the project

A project routinely owns several terminals: a dev server, a test watcher, an
agent session. "What is this project's state" is a different, coarser question
than "what is happening *in this tab*", and only the second one is answerable
without guessing. Session id — not repo path — is therefore the primary key.

Project-level rollup is a **later** view built by aggregating session trees. It
is deliberately not the storage model.

## 2. Capture must cost zero tokens

The single design constraint everything else follows from.

A feature that quietly spends tokens on every turn gets uninstalled, however good
it is. So capture happens in a `Stop` hook, which is a shell script: no model, no
tokens, no context. It records *facts* — tool names, file paths, commands, git
state — and never opinions. Interpretation is the expensive part, so it happens
only when the user explicitly asks.

## 3. Never re-derive from the transcript

The obvious implementation is "read the session transcript and summarise it."
Measured on real sessions, transcript directories reach **16–37 MB**. That is
millions of tokens per invocation, and it grows without bound as the session
continues.

Instead the hook tracks a **byte offset** and reads only what was appended since
the previous turn. Cost is proportional to one turn's output, not to session
length. This is why `offset` is a first-class file rather than an optimisation.

Corollary: the skill is explicitly forbidden from reading
`~/.claude/projects/**/*.jsonl`. If you add a feature that needs history, add it
to the hook, not the skill.

## 4. The state is a small Markdown file

`tree.md` is Markdown checkboxes because:

- a human can edit it in any editor, mid-session, without tooling;
- a model can update it with a targeted edit rather than a rewrite;
- it diffs legibly if someone commits it;
- it renders acceptably even with `ttytree` uninstalled.

The tree is a **map, not a log**. The skill is instructed to keep it under ~25
lines and roll finished detail up into parents. An append-only structure would
grow until reading it stopped being cheap, which would defeat §2.

At most one `[~]` per level is a rule, not a convention — it is what makes the
tree answer "what am I doing right now" rather than "what is open".

## 5. Session resolution without a daemon

To answer "which session am I?", walk up the process tree from the current shell
until hitting the owning `claude` process, then read Claude Code's own registry:

```
~/.claude/sessions/<pid>.json
  → { sessionId, cwd, name, status, ... }
```

This reuses state Claude Code already maintains. No daemon, no environment
variable to plumb through, no registry of our own to keep in sync, and it works
from any subshell — including one the user opens by hand.

The fallback path matters: outside Claude Code, `ttytree --all` still works, so
the tool is useful from a plain terminal.

## 6. Failure must be invisible

The hook runs on every turn. If it errors, it must not disturb the session, so it
traps everything and always `exit 0`. A missing `jq`, an unreadable transcript, a
rotated file, a repo with no commits — all degrade to a smaller event or no event
at all, never to a broken turn.

Same principle in the renderer: an unparseable tree falls back to printing the
raw file rather than showing nothing.

## 7. Portability

Target: macOS and Linux with a POSIX-ish shell.

Notably, macOS ships BWK awk, **not** gawk — so no 3-argument `match()`, no
`gensub()`, no `asort()`. The tree parser counts indentation by hand for this
reason. `stat` differs too (`-f %z` vs `-c %s`); both forms are attempted.

## Extension points

- **New captured facts** → `extract_facts()` in `hooks/ttytree-log.sh`. Keep the
  output small and keep the jq total-failure fallback (`// {}`).
- **New rendering** → `render_tree()` in `bin/ttytree`. Stay within BWK awk.
- **New reconciliation behaviour** → `skills/ttytree/SKILL.md`. Changes here cost
  tokens on every invocation, so they must earn their length.
- **New surfaces** (tab colours, board, statusline) → new consumers of
  `events.jsonl` and `tree.md`. Don't add state; derive.

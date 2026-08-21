---
name: ttytree
description: Show and update a tree of what this Claude Code session is working on — done, in progress, next, blocked. Always ends by running `ttytree` and showing its rendered output. Use when the user runs /ttytree, or asks "what are we doing in this session", "where were we", "what's left", "what's the state of this terminal". Maintains a small per-session tree file; never reads the raw transcript.
---

# ttytree

A per-session **work tree**: what's done, what's in progress, what's next, what's
blocked — for *this terminal's* session.

Claude Code already records the session transcript and a session registry, but it
tracks no structure of the work. This skill maintains that structure in a small
file and renders it.

## The token contract — read this first

This skill must stay cheap. A full run should cost **well under 2k tokens**.

**Never read the session transcript** (`~/.claude/projects/**/*.jsonl`). Those
files reach tens of megabytes; deriving the tree from them is the one thing that
makes this feature unaffordable. The transcript is already summarised for free by
a zero-token `Stop` hook into a small `events.jsonl`.

Read exactly two things: the tree file, and recent events. Nothing else.

## Step 1 — resolve this session

```bash
ttytree --path        # prints the tree file path for THIS session
```

If `ttytree` is not on PATH, resolve manually — walk up the process tree to
the owning `claude` process and read Claude Code's own session registry:

```bash
p=$PPID; for i in 1 2 3 4 5 6; do
  case "$(ps -o comm= -p $p 2>/dev/null)" in
    *claude) jq -r .sessionId ~/.claude/sessions/$p.json; break;;
  esac
  p=$(ps -o ppid= -p $p | tr -d ' ')
done
```

The tree lives at `~/.claude/ttytree/<session-id>/tree.md`, events at
`events.jsonl` in the same directory.

## Step 2 — read the current tree and only what's new

```bash
SID=$(ttytree --path | sed 's|.*/ttytree/||; s|/tree.md||')
D=~/.claude/ttytree/$SID
cat "$D/tree.md" 2>/dev/null
# only events newer than the tree, capped — this is the whole delta
MT=$(stat -f %m "$D/tree.md" 2>/dev/null || echo 0)
jq -c --argjson t "$MT" 'select(.ts > $t)
  | {ts, tools, files, cmds, dirty, prompt}' "$D/events.jsonl" 2>/dev/null | tail -30
```

If `tree.md` does not exist, **seed it from your own context window** — you
already know what this session has been doing, and that costs nothing. Do not go
read files to reconstruct history.

An event of the form `{"cold_start": true}` marks the moment ttytree began
watching this session. Anything before it was never captured, so treat it as a
boundary, not as activity: seed from context for that period rather than assuming
nothing happened.

## Step 3 — reconcile

Fold the new events into the tree:

- An item whose files/commands show completed work → mark `[x]`.
- Work clearly underway → `[~]`. Keep **at most one** `[~]` at each level; that
  is what makes the tree answer "what am I doing *right now*".
- New work that appeared → add as `[ ]`, nested under the right parent.
- An API error, rate limit, failing command, or an unanswered question in the
  events → `[!]` with a short reason.
- Work abandoned → `[-]` rather than deleting it; the history is the value.

Keep the tree **small and structural**: aim for under 25 lines. It is a map, not
a log. Roll finished detail up into its parent instead of letting the tree grow.

## Step 4 — write the tree

Write `tree.md` in this format (two spaces per level of nesting):

```markdown
# <project> · <one-line goal for this session>
<!-- ttytree:meta session=<id> updated=<iso8601> -->

- [x] JWT auth middleware
- [~] Webhook delivery
  - [x] signing + replay protection
  - [~] retry with exponential backoff
    - [ ] dead-letter queue
  - [ ] delivery metrics
- [!] waiting on staging credentials
- [ ] Deploy to staging
```

Markers: `[ ]` next · `[~]` in progress · `[x]` done · `[!]` blocked · `[-]` dropped.

The marker carries the state — write `- [!] staging credentials expired`, never
`- [!] BLOCKED: staging credentials expired`.

## Step 5 — ALWAYS render. This step is not optional.

The user ran this to **see the tree**. Finishing without showing it fails the
request, no matter how good your prose summary was.

```bash
ttytree
```

Show that output verbatim. Never hand-draw the tree yourself, never replace it
with a description of what's in it, and never stop at "seeded from context" or
"folded in N turns" — those are things you say *alongside* the tree, not instead
of it.

After the tree, add at most two lines: what changed since last time, and the
obvious next action.

This applies to every invocation, including the first one in a session where you
just created the tree from context. Especially that one — it's the user's first
sight of the thing they installed.

## Arguments

- `/ttytree` — reconcile and show (default)
- `/ttytree show` — render only, change nothing (cheapest path)
- `/ttytree add <text>` — append a `[ ]` item
- `/ttytree done <text>` — mark the matching item `[x]`
- `/ttytree block <reason>` — mark the current `[~]` item `[!]`
- `/ttytree next` — print only the next actionable `[ ]` items
- `/ttytree all` — `ttytree --all`, every tracked session

## Notes

- The tree is per **session**, not per project. One project can own several
  terminals; each keeps its own tree. That is deliberate.
- `ttytree` (the CLI) renders with zero tokens and works from any shell,
  including outside Claude Code. Reach for it before the skill when you only
  want to look.
- The `Stop` hook is a shell script. It never calls a model, so keeping the tree
  fed costs nothing between invocations.

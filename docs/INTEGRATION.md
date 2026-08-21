# Integrating ttytree

`ttytree` is deliberately a **data layer**, not a session switcher. Tools like
[agent-deck](https://github.com/asheshgoplani/agent-deck),
[ccmanager](https://github.com/kbwo/ccmanager),
[opensessions](https://github.com/Ataraxy-Labs/opensessions) and
[claude-squad](https://github.com/smtg-ai/claude-squad) already solve *which
session needs me and take me there*, and solve it well. None of them know **what
the work inside a session actually is**.

That's the hole this fills. If you maintain one of those tools, `ttytree --json`
is meant for you.

## The contract

```bash
ttytree --json          # this terminal's session
ttytree --json --all    # every tracked session
```

Always exits `0` and always prints valid JSON, including when nothing is
installed or tracked:

```json
{"version": 1, "generated_at": 1787310870, "sessions": []}
```

**Never special-case its absence.** If `ttytree` isn't installed, the command
won't be found — treat that identically to an empty `sessions` array and render
nothing. Users of your tool should not have to install ttytree for your tool to
work.

## Schema

```jsonc
{
  "version": 1,                    // bumped only on breaking change
  "generated_at": 1787310870,
  "sessions": [
    {
      "session_id": "4e1b8a03-…",  // matches Claude Code's own session id
      "name": "orchard-api-12",    // Claude Code's derived session name
      "cwd": "/Users/you/code/orchard-api",
      "project": "orchard-api",    // basename of cwd, for convenience
      "tty": "ttys000",
      "pid": 48213,
      "session_status": "idle",    // from Claude Code: busy | idle | gone
      "has_tree": true,            // false = hook running, no tree written yet

      "tree_updated": 1787309434,  // epoch seconds; 0 if no tree

      "current": "retry with exponential backoff",   // the active item, or null
      "blocked": ["waiting on staging credentials"], // may be empty
      "next":    ["dead-letter queue"],              // may be empty

      "summary": { "done": 5, "in_progress": 1, "next": 3,
                   "blocked": 1, "dropped": 0 },

      "items": [                   // the full tree, in document order
        { "depth": 0, "state": "done",        "text": "JWT auth middleware" },
        { "depth": 0, "state": "in_progress", "text": "Webhook delivery" },
        { "depth": 1, "state": "next",        "text": "dead-letter queue" }
      ],

      "since_update": {            // activity the tree hasn't absorbed yet
        "turns": 3, "files": 5, "dirty": 4
      }
    }
  ]
}
```

`state` is one of `done`, `in_progress`, `next`, `blocked`, `dropped`.

The convenience fields (`current`, `blocked`, `next`) have a redundant leading
state word stripped, so `- [!] BLOCKED: keys expired` surfaces as
`"blocked": ["keys expired"]`. `items[].text` is always verbatim from the file —
use it when you need exactly what the user wrote.

### Stability

- Fields are **added**, never removed or repurposed, within a `version`.
- `version` bumps only on a breaking change, and the old shape stays available
  for at least one release.
- `session_id` is the join key. It matches what Claude Code writes to
  `~/.claude/sessions/<pid>.json`, so if you already track sessions by that id,
  no mapping is needed.

## Rendering suggestions

Most integrations want three fields and can ignore the rest:

| You want to show | Use |
|---|---|
| one line of "what's happening here" | `current` (fall back to `next[0]`) |
| an attention badge | `blocked` non-empty |
| a progress hint | `summary.done` / total |
| "tree is stale" | `since_update.turns > 0` |
| the full tree in a sidebar | `items` — `depth` gives the indentation |

A minimal sidebar row:

```
orchard-api  ▸ retry with exponential backoff     5/9  ⛔1
```

Drawing the full tree from `items` is a straight indentation walk — `depth` is
already computed, so you never need to parse Markdown.

## Reading the files directly

If shelling out doesn't suit you, the on-disk format is also stable:

```
~/.claude/ttytree/<session-id>/
  tree.md        Markdown checkboxes; [x] done [~] in progress [ ] next [!] blocked [-] dropped
  events.jsonl   one object per turn, appended by the Stop hook, capped at 500 lines
  offset         transcript byte offset (internal; don't rely on it)
```

`tree.md` is safe to read and safe for a user to hand-edit. **Please don't write
to it from a tool** without the user asking — it's their file, and the skill
reconciles it on the assumption that edits are intentional.

`events.jsonl` entries look like:

```json
{"ts":1787309434,"tools":{"Edit":6,"Bash":11},"files":["internal/webhook/retry.go"],
 "cmds":["go test ./internal/webhook/..."],"prompt":"add backoff with jitter",
 "reply":"…","dirty":4,"branch":"main","cwd":"/Users/you/code/orchard-api"}
```

A `{"ts":…,"cold_start":true,"cwd":…}` entry marks the point ttytree started
watching a session; anything earlier was never captured.

## Wiring it up without our hook

`ttytree --json` works whether or not the `Stop` hook is installed — without it,
`since_update` just stays at zero and trees only change when the user runs
`/ttytree`. So you can surface the data for users who have it, and show nothing
for users who don't, with no branching in your code.

## Questions, or want a field added?

Open an issue: https://github.com/sumitvairagar/ttytree/issues — happy to add
fields that make an integration cleaner, and happy to write the PR against your
tool if that's easier.

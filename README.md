# ttytree

**A live tree of what each Claude Code terminal is working on** — done, in
progress, next, blocked. Per terminal, kept up to date for you, and free to keep
up to date.

```console
$ ttytree

pocketledger  ttys004 · idle · 7f3a1c92
├─ ✔ Screens scaffolded
├─ ▸ Onboarding flow
│  ├─ ✔ intro + permission screens
│  ├─ ▸ timer selection screen
│  │  └─ ○ persist choice to storage
│  └─ ○ analytics events
├─ ⛔ BLOCKED: monthly spend limit hit
└─ ○ Ship to TestFlight

   3 turns, 5 files touched since this tree was updated
```

---

## The problem

If you live in the terminal across many projects, you lose the thread. You switch
to a tab you haven't touched in an hour and have no idea what's in flight, what
you'd already finished, or what you meant to do next — so you type *"what were we
working on?"* and pay to have it re-derived from scratch.

Here's the actual snapshot that started this project — eight iTerm tabs, every
one a long-lived Claude session:

```console
$ ps -eo pid,tty,command | grep claude

ttys000   claude --resume 4e1b8a03…    orchard-api      running 2d 5h
ttys001   claude --resume              tidepool         running 3d 23h
ttys002   claude                       warehouse-etl    running 21h
ttys003   claude                       lumen-docs       running 18h
ttys004   claude --resume              pocketledger     running 3d 3h
ttys006   claude                       dotfiles         running 4h
ttys008   claude                       tidepool         running 2d
ttys009   claude --resume              orchard-api      running 2d
```

Three of those had been silently dead for 50 minutes — two on API errors, one on
a spend limit — and nothing in the terminal said so.

Claude Code already stores plenty: a full transcript per session, and a registry
with each session's pid, cwd, name and busy/idle status. What it does **not**
store is any *structure* of the work — no notion of done vs. in progress vs.
next. `ttytree` adds exactly that, and nothing else.

The unit is the **terminal**, not the project. One project often owns three tabs
(dev server, tests, agent); each keeps its own tree. That's deliberate — see
[`docs/DESIGN.md`](docs/DESIGN.md).

---

## Why it's cheap

The obvious way to build this is to re-read the session transcript and summarise
it. That doesn't scale. Measured on a real session:

| | size | cost to read |
|---|---|---|
| The session transcript | 578 KB | ~**144,600 tokens** |
| What `ttytree` stores instead | 1,006 bytes | ~**251 tokens** |

Roughly **575× less** — and it stays flat as the session grows, because:

- A **`Stop` hook** — a plain shell script, so **zero tokens** — runs after each
  turn and condenses *only the bytes appended since the previous turn* (tracked
  by a byte offset) into a few hundred bytes of facts.
- The **`/ttytree` skill** reads two small files, reconciles them, writes the
  tree back. Well under 2k tokens per run.
- The **`ttytree` CLI** renders with **zero tokens**. If you only want to look,
  no model is involved at all.

Facts get captured for free. Interpretation happens only when you ask.

---

## Install

Requires `jq` and `awk` (macOS and most Linux ship `awk`; `brew install jq`).

```bash
git clone https://github.com/sumitvairagar/ttytree.git
cd ttytree
./install.sh              # --dry-run to preview every change first
```

```console
$ ./install.sh

ttytree installer
  repo: /Users/you/code/ttytree

1/4  dependencies
  ✔ jq
  ✔ awk
  ✔ git (optional, enables branch/dirty info)

2/4  skill  ->  ~/.claude/skills/ttytree
  ✔ /ttytree available in new sessions

3/4  cli  ->  ~/.local/bin/ttytree
  ✔ ~/.local/bin is on PATH

4/4  Stop hook  ->  ~/.claude/settings.json
  ✔ hook registered (previous settings backed up)
```

Everything is symlinked, so `git pull` updates your install. `./uninstall.sh`
reverses all of it, including the `settings.json` edit. **Restart Claude Code**
to pick up the skill and hook.

---

## Examples

### Coming back to a cold terminal

You switch to a tab you left before lunch. Instead of asking Claude anything:

```console
$ ttytree

lumen-docs  ttys003 · idle · 5a71c3d9
├─ ✔ Supabase schema + RLS policies
├─ ✔ Auth flow (magic link)
├─ ▸ Audio player
│  ├─ ✔ waveform component
│  ├─ ▸ scrubbing + seek
│  │  ├─ ✔ pointer events
│  │  └─ ○ keyboard a11y
│  └─ ○ playback speed control
├─ ○ Offline caching
└─ ○ Deploy preview to Vercel

   7 turns, 12 file(s) touched since this tree was updated — run /ttytree to fold them in
```

That last line is the tell: work happened after the tree was last updated. Run
`/ttytree` and Claude folds those 7 turns in — reading ~250 tokens of captured
facts, not 144k of transcript.

### Every terminal at once

```console
$ ttytree --all

orchard-api  ttys000 · idle · 4e1b8a03
├─ ✔ Terraform modules split per environment
├─ ▸ GitLab runner autoscaling
│  └─ ○ verify spot instance drain
└─ ○ Write the runbook

pocketledger  ttys004 · idle · 7f3a1c92
├─ ✔ Screens scaffolded
├─ ▸ Onboarding flow
│  └─ ○ persist choice to storage
├─ ⛔ BLOCKED: monthly spend limit hit
└─ ○ Ship to TestFlight

orchard-api  ttys009 · idle · 2b9d51e7
├─ ✔ Radar chart renderer
├─ ▸ Shorts pipeline
│  └─ ○ caption burn-in
└─ ⛔ BLOCKED: API error — session stalled 50m ago
```

Two blocked terminals, visible in one glance, without entering either tab.

### Updating the tree

```
> /ttytree

  Folded in 7 turns. Scrubbing is done — you finished pointer events and the
  seek handler; keyboard a11y is still open. Next obvious step is playback
  speed control.

lumen-docs  ttys003 · busy · 5a71c3d9
├─ ✔ Supabase schema + RLS policies
├─ ✔ Auth flow (magic link)
├─ ▸ Audio player
│  ├─ ✔ waveform component
│  ├─ ✔ scrubbing + seek
│  ├─ ▸ keyboard a11y
│  └─ ○ playback speed control
├─ ○ Offline caching
└─ ○ Deploy preview to Vercel
```

### Quick edits without a model

```console
$ ttytree                              # look — 0 tokens
$ ttytree --next                       # just what's actionable
$ $EDITOR "$(ttytree --path)"          # it's plain Markdown, edit freely
```

```
> /ttytree add write migration tests
> /ttytree done keyboard a11y
> /ttytree block waiting on design review
```

### What the hook actually captured

```console
$ ttytree --events 3

{"ts":1787309434,"tools":{"Edit":6,"Bash":11,"Read":4},"files":["src/player/Scrub.tsx","src/player/index.ts"],"dirty":4,"branch":"main","prompt":"make the scrubber keyboard accessible"}
{"ts":1787309981,"tools":{"Bash":3},"files":[],"dirty":4,"branch":"main","prompt":"run the tests"}
{"ts":1787310402,"tools":{"Edit":2,"Bash":5},"files":["src/player/Scrub.test.tsx"],"dirty":6,"branch":"main","prompt":"fix the failing case"}
```

Facts only — no summaries, no opinions, no model call. That's what makes it free.

---

## Commands

| Command | What it does | Tokens |
|---|---|---|
| `ttytree` | this terminal's tree | 0 |
| `ttytree --all` | every tracked session | 0 |
| `ttytree --events [n]` | raw facts the hook captured | 0 |
| `ttytree --next` | only what's actionable right now | 0 |
| `ttytree --path` | tree file path, for hand-editing | 0 |
| `ttytree --session <id>` | a specific session | 0 |
| `ttytree --no-color` | plain output, for piping | 0 |
| `/ttytree` | reconcile with recent activity, then show | < 2k |
| `/ttytree show` | render only, change nothing | minimal |
| `/ttytree add <text>` | append an item | small |
| `/ttytree done <text>` | mark an item complete | small |
| `/ttytree block <reason>` | mark the active item blocked | small |
| `/ttytree next` | just the next actionable items | small |

### The tree format

Plain Markdown — edit it by hand any time:

```markdown
# lumen-docs · ship the audio player
<!-- ttytree:meta session=5a71c3d9 updated=2026-08-21 -->

- [x] Auth flow (magic link)
- [~] Audio player
  - [x] waveform component
  - [~] scrubbing + seek
    - [ ] keyboard a11y
- [!] BLOCKED: waiting on design review
- [-] Dropped: custom codec support
```

| Marker | Means | Renders |
|---|---|---|
| `[x]` | done | ✔ |
| `[~]` | in progress | ▸ |
| `[ ]` | next | ○ |
| `[!]` | blocked | ⛔ |
| `[-]` | dropped | · |

At most **one `[~]` per level** — that rule is what makes the tree answer *"what
am I doing right now"* rather than *"what's open"*.

---

## How it works

```
   your turn ends
        │
        ▼
  Stop hook (shell, 0 tokens)
        │  reads only the transcript bytes added since last turn
        ▼
  ~/.claude/ttytree/<session>/events.jsonl     ← small, bounded, rotated
        │
        │  you run /ttytree
        ▼
  skill reconciles events into tree.md         ← < 2k tokens
        │
        ▼
  ttytree CLI renders it                       ← 0 tokens
```

Sessions identify themselves by walking up the process tree from the shell to the
owning `claude` process, then reading Claude Code's own registry at
`~/.claude/sessions/<pid>.json`. No daemon, no config file, no state of our own to
keep in sync.

### Data layout

```
~/.claude/ttytree/<session-id>/
  tree.md        the tree (Markdown; yours to edit)
  events.jsonl   facts from the Stop hook (bounded to 500 lines)
  offset         transcript byte offset — how the hook stays O(new bytes)
```

All local files. Nothing is sent anywhere.

---

## Known limitations

- **Files touched are read from tool inputs** (`Edit`, `Write`, `Read`). If a
  session writes files through shell heredocs instead, `files` comes back empty.
  Parsing paths out of arbitrary shell is fragile, so it isn't attempted.
- **Trees appear only after the first `/ttytree`** in a session. The hook starts
  collecting immediately, but nothing renders until there's a tree to render.
- **macOS and Linux only.** Depends on `ps`, `stat`, and a POSIX-ish shell.

## Roadmap

- [ ] `ttytree --board` — all terminals with derived status: needs-you / working
      / errored / blocked
- [ ] iTerm & tmux tab colour + title driven by tree state, so a stuck terminal
      is visible without asking
- [ ] jump-to-terminal from the board (focus an iTerm tab by session id)
- [ ] `SessionStart` hook that reloads the tree into context on resume
- [ ] roll session trees up into a project view across terminals
- [ ] time-in-state — a `[~]` stuck for two days should say so
- [ ] `ttytree --since yesterday` for a standup-shaped summary

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Prior art / not the same thing

- [`tty-tree`](https://github.com/piotrmurach/tty-tree) — a Ruby gem for printing
  *directory* trees, part of the TTY toolkit. Unrelated project, similar name.

## License

MIT — see [LICENSE](LICENSE).

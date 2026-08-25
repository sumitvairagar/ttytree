# ttytree

**A live tree of what each Claude Code terminal is working on** — done, in
progress, next, blocked. Per terminal, kept up to date for you, and free to keep
up to date.

```console
$ ttytree

pocketledger  ttys004 · idle · 7f3a1c92
├─ ✔   Receipt OCR pipeline
├─ ▸   Expense categorisation
│  ├─ ✔   rules engine
│  ├─ ▸   merchant matching
│  │  └─ ○ 🧹 collapse duplicate merchants
│  └─ ○   user-defined categories
├─ ⛔ 🔐 Plaid sandbox keys expired
└─ ○ 🚀 Ship to TestFlight

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
ttys001   claude                       tidepool         running 3d 23h
ttys002   claude --resume              warehouse-etl    running 21h
ttys003   claude                       lumen-docs       running 18h
ttys004   claude --resume 7f3a1c92…    pocketledger     running 3d 3h
ttys006   claude                       dotfiles         running 4h
ttys008   claude                       tidepool         running 2d
ttys009   claude --resume              orchard-api      running 2d
```

Three of those had been silently dead for the better part of an hour — two on API
errors, one on a rate limit — and nothing in the terminal said so. Note also that
`tidepool` and `orchard-api` each own **two** tabs; the thing you switch between
is a terminal, not a project.

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

Facts get captured for free. Interpretation happens only when you ask — the
hook never writes the tree itself, because turning "6 edits, 11 commands" into
"▸ retry with exponential backoff" needs a model.

The tree lives on disk, outside the context window, so `/compact` and
`claude --resume` don't touch it. Compaction appends to the same transcript and
keeps the same session id, so the byte offset stays valid and the next turn is
still O(new bytes). After a compact is exactly when `/ttytree` is worth the most:
the model lost its context, the tree didn't.

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
reverses all of it, including the `settings.json` edit.

Already-running sessions pick the hook up **live** — verified on a session that
had been running for over two days. If a session doesn't seem to be collecting,
restart it.

---

## Examples

### Coming back to a cold terminal

You switch to a tab you left before lunch. Instead of asking Claude anything:

```console
$ ttytree

orchard-api  ttys000 · idle · 4e1b8a03
├─ ✔ 💾 Postgres schema + migrations
├─ ✔ 🔐 JWT auth middleware
├─ ▸ 🔌 Webhook delivery
│  ├─ ✔ 🔐 signing + replay protection
│  ├─ ▸   retry with exponential backoff
│  │  ├─ ✔   jitter
│  │  └─ ○ 🔌 dead-letter queue
│  └─ ○ 📈 delivery metrics
├─ ○ 📈 Per-tenant rate limiting
└─ ○ 🚀 Deploy to staging

   7 turns, 12 file(s) touched since this tree was updated — run /ttytree to fold them in
```

That last line is the tell: work happened after the tree was last updated. Run
`/ttytree` and Claude folds those 7 turns in — reading ~250 tokens of captured
facts, not 144k of transcript.

### Every terminal at once

`ttytree --all` gives you one line per terminal. Blocked sessions sort to the
top, then busy, then whatever you touched most recently:

```console
$ ttytree --all

ttytree · 4 sessions · 2 blocked · 4 with unrecorded turns

⛔ orchard-api      9/14   7m   +1   staging credentials expired
⛔ pocketledger     12/18  36m  +2   🚀 pricing still unset in App Store Connect
● orchard-web      14/16  3d   +11  ▸ checkout redesign
○ warehouse-etl    16/27  3d   +4   ▸ 💾 backfill 2024 orders

   ttytree <name>  one tree in full · --all --full  every tree · --serve  browser
```

`+11` means eleven turns happened that the tree hasn't absorbed yet. Four
sessions is 6 lines instead of 93; eight terminals still fits on one screen.

Then drill in by name — no session ids to copy:

```console
$ ttytree orchard-api
```

Sometimes you want the shape, not the summary — `--all --full` prints every
tree:

```console
$ ttytree --all --full

orchard-api  ttys000 · idle · 4e1b8a03
├─ ✔ 💾 Postgres schema + migrations
├─ ✔ 🔐 JWT auth middleware
├─ ▸ 🔌 Webhook delivery
│  ├─ ✔ 🔐 signing + replay protection
│  ├─ ▸   retry with exponential backoff
│  │  ├─ ✔   jitter
│  │  └─ ○ 🔌 dead-letter queue
│  └─ ○ 📈 delivery metrics
├─ ○ 📈 Per-tenant rate limiting
└─ ○ 🚀 Deploy to staging

pocketledger  ttys004 · idle · 7f3a1c92
├─ ✔   Receipt OCR pipeline
├─ ▸   Expense categorisation
│  ├─ ✔   rules engine
│  ├─ ▸   merchant matching
│  │  └─ ○ 🧹 collapse duplicate merchants
│  └─ ○   user-defined categories
├─ ⛔ 🔐 Plaid sandbox keys expired
└─ ○ 🚀 Ship to TestFlight

warehouse-etl  ttys002 · idle · c8f04a17
├─ ✔ 💾 Nightly sync job
├─ ▸ 💾 Backfill 2024 orders
│  └─ ○ 🧪 verify row counts against source
└─ ⛔ 🔌 API error — session stalled 50m ago
```

Two blocked terminals, visible in one glance, without entering either tab.

### Updating the tree

```
> /ttytree

  Folded in 7 turns. Backoff is done — jitter and the dead-letter queue both
  landed, and the retry tests pass. Delivery metrics is now the open thread;
  nothing is blocked.

orchard-api  ttys000 · busy · 4e1b8a03
├─ ✔ 💾 Postgres schema + migrations
├─ ✔ 🔐 JWT auth middleware
├─ ▸ 🔌 Webhook delivery
│  ├─ ✔ 🔐 signing + replay protection
│  ├─ ✔   retry with exponential backoff
│  ├─ ▸ 📈 delivery metrics
│  └─ ○ 🐛 alert on repeated failures
├─ ○ 📈 Per-tenant rate limiting
└─ ○ 🚀 Deploy to staging
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

{"ts":1787309434,"tools":{"Edit":6,"Bash":11,"Read":4},"files":["internal/webhook/retry.go","internal/webhook/queue.go"],"dirty":4,"branch":"main","prompt":"add exponential backoff with jitter"}
{"ts":1787309981,"tools":{"Bash":3},"files":[],"dirty":4,"branch":"main","prompt":"run the retry tests"}
{"ts":1787310402,"tools":{"Edit":2,"Bash":5},"files":["internal/webhook/retry_test.go"],"dirty":6,"branch":"main","prompt":"fix the flaky backoff case"}
```

Facts only — no summaries, no opinions, no model call. That's what makes it free.

---

### Always on: the statusline

The one surface that's visible in *every* session without running anything.
`install.sh` wires it up (and leaves an existing statusline alone):

```
orchard-api · ▸ retry with exponential backoff
7/11 done · 3 turn(s) unrecorded · next: dead-letter queue
⛔ waiting on staging credentials
```

Line one is what you're doing. Line two is how far along, whether the tree has
fallen behind, and what's next. Line three appears only when something is
blocked. It costs nothing — the statusline runs the CLI, not the model.

### The dashboard

For the whole picture at once, `ttytree --serve` runs a local page you keep in a
browser tab. It re-reads every 10 seconds, so refreshing is optional:

```console
$ ttytree --serve
ttytree dashboard  http://localhost:7777
  live · localhost only · ctrl-c to stop
```

One card per terminal, sorted the same way the board is: progress bar, what's
active, blockers called out in red, and completed items folded behind a
disclosure. It binds to `127.0.0.1` only — your session names never leave the
machine. Needs `python3` (the terminal views don't).

`ttytree --html > board.html` writes the same page as a static snapshot.

### A live view

Keep one plain terminal open as a control tower:

```console
$ ttytree --watch

ttytree · 09:14:02 · refreshing every 5s · ctrl-c to quit

ttytree · 3 sessions · 1 blocked

⛔ pocketledger    12/18  36m  🔐 Plaid sandbox keys expired
● orchard-api     9/14   2m   ▸ 🔌 retry with exponential backoff
○ warehouse-etl   4/9    2h   ▸ 💾 backfill 2024 orders
```

`ttytree --watch 2` to refresh faster, `--watch --full` for whole trees. Because
that tab has no Claude session in it, watching costs nothing at all. If you'd
rather have it in a browser, that's `--serve` above.

### Running it from inside Claude Code

Type `!ttytree` — the `!` prefix runs a shell command directly. Typing plain
`ttytree` would send it to Claude as a message, which is the slowest and most
expensive way to see a tree.

## Commands

| Command | What it does | Tokens |
|---|---|---|
| `ttytree` | this terminal's tree | 0 |
| `ttytree <name>` | a session by project name | 0 |
| `ttytree --all` | the board — one line per session | 0 |
| `ttytree --all --full` | every tree in full | 0 |
| `ttytree --serve [port]` | live dashboard in the browser (default 7777) | 0 |
| `ttytree --html` | write the dashboard to stdout | 0 |
| `ttytree --watch [n]` | live view, redraws every n seconds (default 5) | 0 |
| `ttytree --statusline` | 2–3 line summary for Claude Code's statusLine | 0 |
| `ttytree --events [n]` | raw facts the hook captured | 0 |
| `ttytree --next` | only what's actionable right now | 0 |
| `ttytree --json` | machine-readable output for other tools | 0 |
| `ttytree --path` | tree file path, for hand-editing | 0 |
| `ttytree --session <id>` | a specific session | 0 |
| `ttytree --no-color` | plain output, for piping | 0 |
| `ttytree --no-icons` | state marks only, no category icons | 0 |
| `ttytree --ascii` | ASCII marks, for terminals without unicode | 0 |
| `/ttytree` | reconcile with recent activity, then show | < 2k |
| `/ttytree show` | render only, change nothing | minimal |
| `/ttytree add <text>` | append an item | small |
| `/ttytree done <text>` | mark an item complete | small |
| `/ttytree block <reason>` | mark the active item blocked | small |
| `/ttytree next` | just the next actionable items | small |

### The tree format

Plain Markdown — edit it by hand any time:

```markdown
# orchard-api · ship webhook delivery
<!-- ttytree:meta session=4e1b8a03 updated=2026-08-21 -->

- [x] JWT auth middleware
- [~] Webhook delivery
  - [x] signing + replay protection
  - [~] retry with exponential backoff
    - [ ] dead-letter queue
- [!] waiting on staging credentials
- [-] gRPC transport
```

| Marker | Means | Renders |
|---|---|---|
| `[x]` | done | ✔ |
| `[~]` | in progress | ▸ |
| `[ ]` | next | ○ |
| `[!]` | blocked | ⛔ |
| `[-]` | dropped | · |

The marker carries the state, so don't repeat it in the text — write
`- [!] staging credentials expired`, not `- [!] BLOCKED: staging credentials expired`.

At most **one `[~]` per level** — that rule is what makes the tree answer *"what
am I doing right now"* rather than *"what's open"*.

### Icons

The state marks come from the marker. The second icon is **inferred from the
text** — nothing to write by hand, so trees you wrote last month light up too:

```console
├─ ✔ 💾 Postgres schema + migrations
├─ ✔ 🔐 JWT auth middleware
├─ ▸ 🔌 Webhook delivery
│  └─ ○ 🧪 contract tests against the sandbox
└─ ○ 🚀 Deploy to staging
```

It is a keyword match, not a model — free, instant, and occasionally wrong.
Matching happens at word starts only, so `portable` isn't a database and
`transcripts` isn't a script.

| | | | |
|---|---|---|---|
| 🚀 deploy | 🐛 bug | 🧪 test | 📝 docs |
| 🔀 git | 💾 data | 🔌 api | 🔐 auth |
| 🎨 ui | 📈 perf | 🧹 cleanup | 🔍 research |
| 📦 packaging | 🔧 config | | |

Turn them off with `ttytree --no-icons`, or permanently with
`export TTYTREE_ICONS=0`. On a terminal that isn't UTF-8, ttytree drops to
ASCII marks (`x > o !`) on its own; force it with `--ascii`. The icons are a
display layer only — `tree.md` and `--json` stay plain text, so anything
consuming ttytree picks its own.

---

## Where this fits

There are excellent Claude Code session managers already —
[claude-squad](https://github.com/smtg-ai/claude-squad),
[ccmanager](https://github.com/kbwo/ccmanager),
[agent-deck](https://github.com/asheshgoplani/agent-deck),
[opensessions](https://github.com/Ataraxy-Labs/opensessions). They tell you
**which session needs you, and take you there.**

None of them know **what the work inside a session is**. There's no notion of
done vs. in progress vs. next vs. blocked — only running / waiting / idle.

`ttytree` is that missing layer, and it's built to be consumed rather than to
compete. `ttytree --json` is a stable, documented interface designed for exactly
those tools to render — see [`docs/INTEGRATION.md`](docs/INTEGRATION.md). If you
maintain one of them and want a "what's happening in this session" line or a tree
in your sidebar, the data is one shell-out away and PRs are welcome in both
directions.

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
- **The tree does not update itself.** The hook records facts every turn for
  free; only `/ttytree` folds them into the tree. A terminal you never run it in
  will collect events and report `N turn(s) unrecorded` — the tree stays where
  you left it. That's the trade for zero background token spend.
- **Big trees stay fast but stop being useful.** Rendering 200 lines takes
  ~0.05s and costs the skill ~2k tokens, so nothing breaks — but a tree that
  long has stopped answering "what am I doing now". Keep it under ~25 lines;
  let finished branches collapse into one done item.
- **macOS and Linux only.** Depends on `ps`, `stat`, and a POSIX-ish shell.

## Roadmap

Deliberately **not** on this list: a session board, tab colouring, or
jump-to-terminal. Those are solved well by the tools above; duplicating them
would trade this project's one advantage for a fight it can't win.

- [x] ~~Always-on statusline and a live `--watch` view.~~
- [x] ~~A board across all terminals, and a browser dashboard.~~
- [ ] **Per-item time-in-state** — the header shows tree age; individual items
      don't carry timestamps yet, so a `[~]` stuck for two days can't say so.
- [ ] **Project rollup** — aggregate the session trees of every terminal in one
      repo into a project-level view.
- [ ] **`--since yesterday`** — a standup-shaped summary across sessions, built
      from trees rather than from git log.
- [ ] **`SessionStart` hook** — reload the tree into context on resume, so a
      resumed session knows where it left off without being asked.
- [ ] **Richer capture** — file paths written via shell redirection, test
      pass/fail, dev-server ports (all in the hook, all still zero-token).
- [ ] **Integrations** — reference patches for agent-deck and opensessions.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Prior art / not the same thing

- [`tty-tree`](https://github.com/piotrmurach/tty-tree) — a Ruby gem for printing
  *directory* trees, part of the TTY toolkit. Unrelated project, similar name.
- **Session managers** (claude-squad, ccmanager, agent-deck, opensessions) —
  complementary, not competing. They handle *where*; this handles *what*. Use
  both.
- [`domux`](https://github.com/pranav7/domux) — per-worktree TODOs in tmux. The
  closest idea, but manual and tmux-only.

## License

MIT — see [LICENSE](LICENSE).

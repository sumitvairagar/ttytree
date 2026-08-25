#!/usr/bin/env python3
"""ttytree dashboard — renders the --json contract as a web page.

  dashboard.py --once            read JSON on stdin, print HTML
  dashboard.py --serve 7777      serve a live page (binds 127.0.0.1 only)

No third-party packages, no CDN: the page is self-contained so it works with
the network off. The server shells out to the ttytree CLI on each request, so
the page and the terminal always read the same data.
"""
import argparse, json, os, subprocess, sys, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ttytree</title>
<style>
/* light is the base palette; dark overrides it, and an explicit choice
   (data-theme) wins over the system setting in both directions */
:root {
  --bg:#f7f6f3; --card:#fff; --ink:#1a1917; --dim:#6f6b64; --faint:#9b968e;
  --line:#e4e0d9; --now:#8a6d1f; --nowbg:#fbf4e0; --nowline:#e0c980;
  --blocked:#b03a2b; --blockedbg:#fcf0ed; --ok:#2f7d33; --shadow:0 1px 2px rgba(0,0,0,.05);
  --fs:15px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#141317; --card:#1c1b21; --ink:#eae8e4; --dim:#918c85; --faint:#6b6760;
    --line:#2c2a33; --now:#e3b158; --nowbg:#2a2317; --nowline:#5c4a24;
    --blocked:#e8796b; --blockedbg:#2d1e1c; --ok:#74c078; --shadow:none;
  }
}
:root[data-theme="dark"] {
  --bg:#141317; --card:#1c1b21; --ink:#eae8e4; --dim:#918c85; --faint:#6b6760;
  --line:#2c2a33; --now:#e3b158; --nowbg:#2a2317; --nowline:#5c4a24;
  --blocked:#e8796b; --blockedbg:#2d1e1c; --ok:#74c078; --shadow:none;
}
* { box-sizing:border-box; }
html { font-size:var(--fs); }
body {
  margin:0; padding:0 0 40px; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:1rem; line-height:1.5;
}
.wrap { max-width:1500px; margin:0 auto; padding:0 24px; }

/* ---- top bar ---- */
.bar {
  position:sticky; top:0; z-index:5; background:var(--bg);
  border-bottom:1px solid var(--line); padding:14px 0 12px; margin-bottom:22px;
}
.bar .wrap { display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
h1 { font-size:1.05rem; margin:0; font-weight:650; letter-spacing:-.01em; }
#sub { color:var(--dim); font-size:.85rem; }
.controls { margin-left:auto; display:flex; gap:8px; align-items:center; }
.seg { display:flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.seg button {
  font:inherit; font-size:.75rem; padding:5px 10px; border:0; cursor:pointer;
  background:transparent; color:var(--dim); min-width:38px;
}
.seg button:hover { color:var(--ink); }
.seg button[aria-pressed="true"] { background:var(--line); color:var(--ink); font-weight:600; }
.seg button + button { border-left:1px solid var(--line); }
#meta { color:var(--faint); font-size:.75rem; width:100%; text-align:right; }

/* ---- where you are ---- */
.now {
  display:grid; gap:14px; margin-bottom:22px;
  grid-template-columns:minmax(0,2fr) minmax(0,1fr);
}
@media (max-width:820px) { .now { grid-template-columns:1fr; } }
.hero {
  background:var(--card); border:1px solid var(--nowline); border-left:4px solid var(--now);
  border-radius:12px; padding:16px 20px; box-shadow:var(--shadow);
}
.label {
  font-size:.68rem; letter-spacing:.11em; text-transform:uppercase;
  color:var(--faint); font-weight:600; margin-bottom:7px;
}
.hero .who { font-size:.9rem; color:var(--dim); margin-bottom:4px; }
.hero .who b { color:var(--ink); font-size:1rem; }
.hero .what {
  font-size:1.45rem; line-height:1.3; font-weight:600; color:var(--now);
  margin:2px 0 8px; overflow-wrap:anywhere;
}
.hero .then { font-size:.9rem; color:var(--dim); overflow-wrap:anywhere; }
.hero .then b { color:var(--ink); font-weight:600; }
.attn {
  background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:16px 20px; box-shadow:var(--shadow);
}
.attn.has { border-color:var(--blocked); }
.attn ul { margin:0; padding:0; list-style:none; }
.attn li { padding:5px 0; font-size:.9rem; overflow-wrap:anywhere; }
.attn li + li { border-top:1px solid var(--line); }
.attn .p { color:var(--blocked); font-weight:600; }
.attn .clear { color:var(--dim); font-size:.9rem; }

/* ---- cards ---- */
.grid {
  display:grid; gap:16px; align-items:start;
  grid-template-columns:repeat(auto-fill,minmax(360px,1fr));
}
.card {
  background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:15px 18px; display:flex; flex-direction:column; gap:11px;
  box-shadow:var(--shadow);
}
.card.blocked { border-color:var(--blocked); }
.card.here { border-color:var(--now); }
.top { display:flex; align-items:baseline; gap:9px; flex-wrap:wrap; }
.proj { font-weight:650; font-size:1.05rem; letter-spacing:-.01em; }
.pill {
  font-size:.65rem; text-transform:uppercase; letter-spacing:.07em; font-weight:600;
  padding:2px 8px; border-radius:20px; border:1px solid var(--line); color:var(--dim);
}
.pill.busy { color:var(--ok); border-color:var(--ok); }
.pill.blocked { color:var(--blocked); border-color:var(--blocked); }
.age { margin-left:auto; color:var(--faint); font-size:.78rem; white-space:nowrap; }
.bar2 { height:6px; background:var(--line); border-radius:4px; overflow:hidden; }
.bar2 > i { display:block; height:100%; background:var(--ok); border-radius:4px; }
.counts { color:var(--dim); font-size:.8rem; margin-top:-4px; }
.counts b { color:var(--ink); font-weight:650; }
.stale { color:var(--now); }
.block {
  background:var(--nowbg); border-radius:9px; padding:9px 12px;
}
.block .txt { font-size:1.05rem; font-weight:600; color:var(--now); overflow-wrap:anywhere; }
.block.stop { background:var(--blockedbg); }
.block.stop .txt { color:var(--blocked); font-size:.95rem; font-weight:600; }
.block.stop .txt + .txt { margin-top:5px; }
.nextlist { font-size:.92rem; }
.nextlist div { padding:2.5px 0; overflow-wrap:anywhere; color:var(--ink); }
.nextlist div:before { content:"○ "; color:var(--faint); }
.quiet { color:var(--dim); font-style:italic; font-size:.9rem; }
details > summary {
  cursor:pointer; color:var(--dim); font-size:.8rem; list-style:none;
  padding:3px 0; user-select:none;
}
details > summary::-webkit-details-marker { display:none; }
details > summary:before { content:"▸ "; }
details[open] > summary:before { content:"▾ "; }
.tree { font-size:.88rem; margin-top:5px; }
.item { display:flex; gap:7px; padding:1.5px 0; align-items:baseline; }
.item .g { width:1.15em; flex:none; text-align:center; color:var(--faint); }
.item .t { min-width:0; overflow-wrap:anywhere; }
.item.done .t, .item.dropped .t { color:var(--dim); }
.item.dropped .t { text-decoration:line-through; }
.item.in_progress .t { color:var(--now); font-weight:600; }
.item.blocked .t { color:var(--blocked); }
footer { color:var(--faint); font-size:.78rem; margin-top:24px; }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.9em;
       background:var(--line); padding:1px 5px; border-radius:4px; }
</style></head>
<body>
<div class="bar"><div class="wrap">
  <h1>ttytree</h1><span id="sub"></span>
  <div class="controls">
    <div class="seg" id="theme">
      <button data-t="auto">Auto</button><button data-t="light">Light</button><button data-t="dark">Dark</button>
    </div>
    <div class="seg">
      <button id="fdown" title="Smaller text">A&minus;</button><button id="fup" title="Bigger text">A+</button>
    </div>
  </div>
  <div id="meta"></div>
</div></div>

<div class="wrap">
  <section class="now" id="now"></section>
  <div class="grid" id="grid"></div>
  <footer id="foot"></footer>
</div>

<script>
const LIVE = __LIVE__;
const SNAPSHOT = __DATA__;
const ICON_MAP = __ICONS__;

/* ---- preferences: theme + text size, remembered per browser ---- */
function get(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
function applyTheme(t) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  document.querySelectorAll("#theme button").forEach(b =>
    b.setAttribute("aria-pressed", b.dataset.t === t));
  set("ttytree.theme", t);
}
function applyFont(px) {
  px = Math.max(13, Math.min(22, px));
  document.documentElement.style.setProperty("--fs", px + "px");
  set("ttytree.fs", px);
  return px;
}
let FS = applyFont(parseInt(get("ttytree.fs", "15"), 10) || 15);
applyTheme(get("ttytree.theme", "auto"));
document.querySelectorAll("#theme button").forEach(b =>
  b.onclick = () => applyTheme(b.dataset.t));
document.getElementById("fup").onclick = () => { FS = applyFont(FS + 1); };
document.getElementById("fdown").onclick = () => { FS = applyFont(FS - 1); };

/* ---- same category icons the CLI uses ---- */
const RULES = ICON_MAP.split(";").filter(Boolean).map(r => {
  const i = r.indexOf("=");
  return { icon: r.slice(0, i), re: new RegExp(" (" + r.slice(i + 1) + ")") };
});
function icon(text) {
  const lt = (" " + text.toLowerCase() + " ").replace(/[^a-z0-9]+/g, " ");
  for (const r of RULES) if (r.re.test(lt)) return r.icon + " ";
  return "";
}
const GLYPH = { done:"✔", in_progress:"▸", next:"○", blocked:"⛔", dropped:"·" };
function ago(sec) {
  if (!sec) return "";
  const d = Math.floor(Date.now() / 1000) - sec;
  if (d < 60) return d + "s ago";
  if (d < 3600) return Math.floor(d / 60) + "m ago";
  if (d < 86400) return Math.floor(d / 3600) + "h ago";
  return Math.floor(d / 86400) + "d ago";
}
function rank(s) {
  if (s.blocked.length) return 0;
  if (s.session_status === "busy") return 1;
  if (s.session_status === "idle") return 2;
  return 3;
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/* ---- where you are: the one thing this page exists to answer ---- */
function hero(ss) {
  const now = document.getElementById("now");
  now.textContent = "";
  const live = ss.filter(s => s.has_tree && s.current);
  const s = live.find(x => x.session_status === "busy") || live[0];
  const h = el("div", "hero");
  h.append(el("div", "label", "where you are"));
  if (!s) {
    h.append(el("div", "what", "Nothing in progress"));
    h.append(el("div", "then", "No terminal has an active item. Pick one below, "
      + "or run /ttytree where you left off."));
  } else {
    const who = el("div", "who");
    who.append(el("b", null, s.project || "?"));
    who.append(document.createTextNode(
      " · " + [s.tty, s.session_status, ago(s.tree_updated)].filter(Boolean).join(" · ")));
    h.append(who);
    h.append(el("div", "what", icon(s.current) + s.current));
    const then = el("div", "then");
    const total = s.summary.done + s.summary.in_progress + s.summary.next;
    then.append(el("b", null, s.summary.done + "/" + total + " done"));
    if (s.next.length) {
      then.append(document.createTextNode(" · then "));
      then.append(el("b", null, s.next[0]));
    }
    if (s.since_update.turns)
      then.append(document.createTextNode(
        " · " + s.since_update.turns + " turn"
        + (s.since_update.turns === 1 ? "" : "s") + " the tree hasn't absorbed"));
    h.append(then);
  }
  now.append(h);

  const stuck = ss.filter(x => x.blocked.length);
  const a = el("div", "attn" + (stuck.length ? " has" : ""));
  a.append(el("div", "label", stuck.length ? "needs you" : "nothing blocked"));
  if (!stuck.length) {
    a.append(el("div", "clear", "No terminal is waiting on anything."));
  } else {
    const ul = el("ul");
    stuck.forEach(x => x.blocked.forEach(b => {
      const li = el("li");
      li.append(el("span", "p", x.project + " — "));
      li.append(document.createTextNode(b));
      ul.append(li);
    }));
    a.append(ul);
  }
  now.append(a);
}

function itemRow(it) {
  const d = el("div", "item " + it.state);
  d.style.paddingLeft = (it.depth * 15) + "px";
  d.append(el("span", "g", GLYPH[it.state] || "○"));
  d.append(el("span", "t", icon(it.text) + it.text));
  return d;
}

function card(s, heroId) {
  const e = el("div", "card" + (s.blocked.length ? " blocked" : "")
                            + (s.session_id === heroId ? " here" : ""));
  const top = el("div", "top");
  top.append(el("div", "proj", s.project || "?"));
  const pill = el("span", "pill " + (s.blocked.length ? "blocked" : s.session_status),
                  s.blocked.length ? "blocked" : s.session_status);
  top.append(pill);
  top.append(el("span", "age",
    [s.tty, ago(s.tree_updated)].filter(Boolean).join(" · ")));
  e.append(top);

  if (!s.has_tree) {
    e.append(el("div", "quiet", "no tree yet — run /ttytree in that terminal"));
    return e;
  }
  const total = s.summary.done + s.summary.in_progress + s.summary.next;
  const bar = el("div", "bar2");
  const fill = el("i");
  fill.style.width = (total ? (100 * s.summary.done / total) : 0) + "%";
  bar.append(fill);
  e.append(bar);
  const c = el("div", "counts");
  c.append(el("b", null, s.summary.done + "/" + total));
  c.append(document.createTextNode(" done"));
  if (s.since_update.turns) {
    c.append(document.createTextNode(" · "));
    c.append(el("span", "stale", s.since_update.turns + " unrecorded"));
  }
  e.append(c);

  if (s.current) {
    const b = el("div", "block");
    b.append(el("div", "label", "now"));
    b.append(el("div", "txt", icon(s.current) + s.current));
    e.append(b);
  }
  if (s.blocked.length) {
    const b = el("div", "block stop");
    b.append(el("div", "label", "blocked"));
    s.blocked.forEach(t => b.append(el("div", "txt", "⛔ " + t)));
    e.append(b);
  }
  if (s.next.length) {
    const n = el("div");
    n.append(el("div", "label", "next"));
    const list = el("div", "nextlist");
    s.next.slice(0, 3).forEach(t => list.append(el("div", null, icon(t) + t)));
    if (s.next.length > 3)
      list.append(el("div", "quiet", "+" + (s.next.length - 3) + " more"));
    n.append(list);
    e.append(n);
  }
  if (!s.current && !s.blocked.length && !s.next.length)
    e.append(el("div", "quiet", "nothing open — tree is clear"));

  if (s.items.length) {
    const det = el("details");
    det.append(el("summary", null, "full tree (" + s.items.length + ")"));
    const t = el("div", "tree");
    s.items.forEach(i => t.append(itemRow(i)));
    det.append(t);
    e.append(det);
  }
  return e;
}

function render(data) {
  const ss = data.sessions.slice().sort(
    (a, b) => rank(a) - rank(b) || b.tree_updated - a.tree_updated);
  hero(ss);
  const live = ss.filter(s => s.has_tree && s.current);
  const heroId = (live.find(x => x.session_status === "busy") || live[0] || {}).session_id;
  const grid = document.getElementById("grid");
  grid.textContent = "";
  ss.forEach(s => grid.append(card(s, heroId)));
  const nb = ss.filter(s => s.blocked.length).length;
  document.getElementById("sub").textContent =
    "· " + ss.length + " terminal" + (ss.length === 1 ? "" : "s")
    + (nb ? " · " + nb + " blocked" : "");
  document.getElementById("meta").textContent =
    (LIVE ? "live · " : "snapshot · ") + "updated " + new Date().toLocaleTimeString();
  document.getElementById("foot").innerHTML =
    "Same data as <code>ttytree --json</code>. "
    + (LIVE ? "Re-reads every 10s." : "Static snapshot — regenerate to update.");
}
function tick() {
  if (!LIVE) return;
  fetch("api", { cache: "no-store" }).then(r => r.json()).then(render).catch(() => {});
}
render(SNAPSHOT);
if (LIVE) setInterval(tick, 10000);
</script>
</body></html>
"""

def page(data, icons, live):
    return (PAGE.replace("__DATA__", json.dumps(data))
                .replace("__ICONS__", json.dumps(icons))
                .replace("__LIVE__", "true" if live else "false"))


def cli_json(cli):
    out = subprocess.run([cli, "--json", "--all"], capture_output=True, text=True)
    return json.loads(out.stdout or '{"version":1,"sessions":[]}')


def serve(port, cli, icons):
    class H(BaseHTTPRequestHandler):
        def _send(self, body, ctype):
            b = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path = self.path.split("?")[0].rstrip("/") or "/"
            try:
                if path == "/":
                    self._send(page(cli_json(cli), icons, True), "text/html; charset=utf-8")
                elif path == "/api":
                    self._send(json.dumps(cli_json(cli)), "application/json")
                else:
                    self.send_error(404)
            except BrokenPipeError:
                pass

        def log_message(self, *a):
            pass

    ThreadingHTTPServer.allow_reuse_address = True
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    except OSError as e:
        if e.errno in (48, 98):          # EADDRINUSE on mac / linux
            sys.exit("ttytree: port %d is already in use — "
                     "try `ttytree --serve %d`" % (port, port + 1))
        raise
    print("ttytree dashboard  http://localhost:%d" % port)
    print("  live · localhost only · ctrl-c to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
    srv.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--serve", type=int, metavar="PORT")
    ap.add_argument("--cli", default="ttytree")
    ap.add_argument("--icon-map", default="")
    a = ap.parse_args()
    if a.serve:
        serve(a.serve, a.cli, a.icon_map)
    else:
        sys.stdout.write(page(json.load(sys.stdin), a.icon_map, False))

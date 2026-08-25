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
:root {
  --bg:#faf9f7; --card:#fff; --ink:#1c1b19; --dim:#78746e; --line:#e6e2dc;
  --done:#9a958d; --now:#b8860b; --nowbg:#fdf6e3; --blocked:#c0392b;
  --blockedbg:#fdf0ee; --ok:#2e7d32; --accent:#3b6ea5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#16151a; --card:#1e1d24; --ink:#e8e6e3; --dim:#8b8780; --line:#2e2c35;
    --done:#6f6b66; --now:#e0a93b; --nowbg:#2a2418; --blocked:#e8776b;
    --blockedbg:#2c1d1c; --ok:#6fbf73; --accent:#7aa7d9;
  }
}
* { box-sizing:border-box; }
body {
  margin:0; padding:24px; background:var(--bg); color:var(--ink);
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
header {
  display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;
  max-width:1400px; margin:0 auto 20px;
}
h1 { font-size:17px; margin:0; letter-spacing:-.01em; }
h1 span { color:var(--dim); font-weight:400; }
.meta { color:var(--dim); font-size:12px; margin-left:auto; }
.grid {
  max-width:1400px; margin:0 auto; display:grid; gap:14px; align-items:start;
  grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
}
.card {
  background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; display:flex; flex-direction:column; gap:10px;
}
.card.blocked { border-color:var(--blocked); }
.top { display:flex; align-items:baseline; gap:8px; }
.proj { font-weight:600; font-size:15px; }
.pill {
  font-size:10.5px; text-transform:uppercase; letter-spacing:.06em;
  padding:2px 7px; border-radius:20px; border:1px solid var(--line);
  color:var(--dim);
}
.pill.busy { color:var(--ok); border-color:var(--ok); }
.pill.blocked { color:var(--blocked); border-color:var(--blocked); }
.age { margin-left:auto; color:var(--dim); font-size:12px; white-space:nowrap; }
.bar { height:5px; background:var(--line); border-radius:3px; overflow:hidden; }
.bar > i { display:block; height:100%; background:var(--ok); }
.counts { color:var(--dim); font-size:12px; }
.counts b { color:var(--ink); font-weight:600; }
.stale { color:var(--now); }
.items { font-size:13px; }
.item { display:flex; gap:7px; padding:1.5px 0; align-items:baseline; }
.item .g { width:1.1em; flex:none; text-align:center; }
.item .t { min-width:0; overflow-wrap:anywhere; }
.item.done .t { color:var(--done); }
.item.dropped .t { color:var(--done); text-decoration:line-through; }
.item.in_progress { background:var(--nowbg); border-radius:5px; margin:1px -6px; padding:3px 6px; }
.item.in_progress .t { font-weight:600; color:var(--now); }
.item.blocked { background:var(--blockedbg); border-radius:5px; margin:1px -6px; padding:3px 6px; }
.item.blocked .t { color:var(--blocked); }
details summary {
  cursor:pointer; color:var(--dim); font-size:12px; list-style:none;
  padding:2px 0; user-select:none;
}
details summary::-webkit-details-marker { display:none; }
details summary:before { content:"▸ "; }
details[open] summary:before { content:"▾ "; }
.empty { color:var(--dim); font-style:italic; font-size:13px; }
footer { max-width:1400px; margin:20px auto 0; color:var(--dim); font-size:12px; }
code { font:12px ui-monospace,SFMono-Regular,Menlo,monospace;
       background:var(--line); padding:1px 5px; border-radius:4px; }
</style></head>
<body>
<header>
  <h1>ttytree <span id="sub"></span></h1>
  <div class="meta" id="meta"></div>
</header>
<div class="grid" id="grid"></div>
<footer id="foot"></footer>
<script>
const ICON_MAP = __ICONS__;
const RULES = ICON_MAP.split(";").filter(Boolean).map(r => {
  const i = r.indexOf("=");
  return { icon: r.slice(0, i), re: new RegExp(" (" + r.slice(i + 1) + ")") };
});
function icon(text) {
  const lt = (" " + text.toLowerCase() + " ").replace(/[^a-z0-9]+/g, " ");
  for (const r of RULES) if (r.re.test(lt)) return r.icon + " ";
  return "";
}
const GLYPH = { done:"✔", in_progress:"▸", next:"○",
                blocked:"⛔", dropped:"·" };
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
function itemRow(it) {
  const d = document.createElement("div");
  d.className = "item " + it.state;
  d.style.paddingLeft = (it.depth * 15) + "px";
  const g = document.createElement("span");
  g.className = "g"; g.textContent = GLYPH[it.state] || "○";
  const t = document.createElement("span");
  t.className = "t"; t.textContent = icon(it.text) + it.text;
  d.append(g, t);
  return d;
}
function card(s) {
  const el = document.createElement("div");
  el.className = "card" + (s.blocked.length ? " blocked" : "");
  const top = document.createElement("div");
  top.className = "top";
  const p = document.createElement("div");
  p.className = "proj"; p.textContent = s.project || "?";
  const pill = document.createElement("span");
  pill.className = "pill " + (s.blocked.length ? "blocked" : s.session_status);
  pill.textContent = s.blocked.length ? "blocked" : s.session_status;
  const age = document.createElement("span");
  age.className = "age";
  age.textContent = [s.tty, ago(s.tree_updated)].filter(Boolean).join(" · ");
  top.append(p, pill, age);
  el.append(top);

  if (!s.has_tree) {
    const e = document.createElement("div");
    e.className = "empty";
    e.textContent = "no tree yet — run /ttytree in that terminal";
    el.append(e);
    return el;
  }
  const total = s.summary.done + s.summary.in_progress + s.summary.next;
  const bar = document.createElement("div");
  bar.className = "bar";
  const fill = document.createElement("i");
  fill.style.width = (total ? (100 * s.summary.done / total) : 0) + "%";
  bar.append(fill);
  const counts = document.createElement("div");
  counts.className = "counts";
  counts.innerHTML = "<b>" + s.summary.done + "/" + total + "</b> done" +
    (s.summary.blocked ? " · " + s.summary.blocked + " blocked" : "") +
    (s.since_update.turns
      ? " · <span class='stale'>" + s.since_update.turns + " turn" +
        (s.since_update.turns === 1 ? "" : "s") + " unrecorded</span>"
      : "");
  el.append(bar, counts);

  const open = s.items.filter(i => i.state !== "done");
  const done = s.items.filter(i => i.state === "done");
  const list = document.createElement("div");
  list.className = "items";
  open.forEach(i => list.append(itemRow(i)));
  if (!open.length) {
    const e = document.createElement("div");
    e.className = "empty"; e.textContent = "nothing open — tree is clear";
    list.append(e);
  }
  el.append(list);
  if (done.length) {
    const det = document.createElement("details");
    const sum = document.createElement("summary");
    sum.textContent = done.length + " done";
    det.append(sum);
    const dl = document.createElement("div");
    dl.className = "items";
    done.forEach(i => dl.append(itemRow(i)));
    det.append(dl);
    el.append(det);
  }
  return el;
}
function render(data) {
  const ss = data.sessions.slice().sort(
    (a, b) => rank(a) - rank(b) || b.tree_updated - a.tree_updated);
  const grid = document.getElementById("grid");
  grid.textContent = "";
  ss.forEach(s => grid.append(card(s)));
  const nb = ss.filter(s => s.blocked.length).length;
  document.getElementById("sub").textContent =
    "· " + ss.length + " session" + (ss.length === 1 ? "" : "s") +
    (nb ? " · " + nb + " blocked" : "");
  document.getElementById("meta").textContent =
    "updated " + new Date().toLocaleTimeString();
  document.getElementById("foot").innerHTML =
    "Reads the same data as <code>ttytree --json</code>. " +
    (LIVE ? "Refreshes every 10s." : "Static snapshot — regenerate to update.");
}
const LIVE = __LIVE__;
const SNAPSHOT = __DATA__;
function tick() {
  if (!LIVE) return;
  fetch("api", { cache: "no-store" })
    .then(r => r.json()).then(render).catch(() => {});
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

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
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

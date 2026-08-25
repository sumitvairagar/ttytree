#!/usr/bin/env python3
"""ttytree dashboard — renders the --json contract as a web app.

  dashboard.py --once            read JSON on stdin, print HTML
  dashboard.py --serve 7777      serve a live page (binds 127.0.0.1 only)

No third-party packages, no CDN, no build step: the page is one self-contained
file so it works with the network off and ships with a shell tool. The server
shells out to the ttytree CLI on each request, so the page and the terminal
always read the same data.
"""
import argparse, json, os, subprocess, sys

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ttytree</title>
<style>
/* ---------------------------------------------------------------- tokens */
/* light is the base; dark overrides it, and an explicit data-theme wins
   over the system setting in both directions */
:root {
  --bg:#faf9f7; --panel:#fff; --rail:#f1efeb; --sunk:#f5f3ef;
  --ink:#16151a; --dim:#67635d; --faint:#9c968d;
  --line:#e5e1d9; --line2:#d3cec4;
  --amber:#9a6c00; --amber-bg:#fdf6e3; --amber-line:#e3c778;
  --red:#b03626; --red-bg:#fdf0ed; --red-line:#eab5aa;
  --green:#3f7a45;
  --sel:#eceae4;
  --shadow:0 1px 2px rgba(20,18,14,.05), 0 4px 16px rgba(20,18,14,.04);
  --fs:15px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#111014; --panel:#191820; --rail:#151419; --sunk:#1e1d25;
    --ink:#ecebe7; --dim:#918c85; --faint:#67625b;
    --line:#27252e; --line2:#38353f;
    --amber:#e2ae55; --amber-bg:#241d12; --amber-line:#5a4623;
    --red:#e8796b; --red-bg:#26181a; --red-line:#5c3230;
    --green:#78bd7e;
    --sel:#22212a;
    --shadow:none;
  }
}
:root[data-theme="dark"] {
  --bg:#111014; --panel:#191820; --rail:#151419; --sunk:#1e1d25;
  --ink:#ecebe7; --dim:#918c85; --faint:#67625b;
  --line:#27252e; --line2:#38353f;
  --amber:#e2ae55; --amber-bg:#241d12; --amber-line:#5a4623;
  --red:#e8796b; --red-bg:#26181a; --red-line:#5c3230;
  --green:#78bd7e;
  --sel:#22212a;
  --shadow:none;
}

*,*::before,*::after { box-sizing:border-box; }
html { font-size:var(--fs); }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  font-size:1rem; line-height:1.5; -webkit-font-smoothing:antialiased;
}
.mono { font-family:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace; }
button { font:inherit; color:inherit; background:none; border:0; cursor:pointer; }
button:focus { outline:none; }
button:focus-visible { outline:2px solid var(--line2); outline-offset:1px; }
a { color:inherit; }

/* label: the small uppercase section marker used throughout */
.lbl {
  font-family:ui-monospace,"SF Mono",SFMono-Regular,Menlo,monospace;
  font-size:.66rem; letter-spacing:.13em; text-transform:uppercase;
  color:var(--faint); font-weight:600;
}

/* ----------------------------------------------------------------- shell */
.app { display:grid; grid-template-columns:264px minmax(0,1fr); min-height:100vh; }

/* ------------------------------------------------------------------ rail */
.rail {
  background:var(--rail); border-right:1px solid var(--line);
  display:flex; flex-direction:column; position:sticky; top:0;
  height:100vh; overflow:hidden;
}
.brand { padding:18px 16px 12px; }
.brand h1 {
  margin:0; font-size:.95rem; font-weight:600; letter-spacing:-.005em;
  display:flex; align-items:baseline; gap:8px;
}
.brand .tick { font-size:.7rem; color:var(--faint); }
.brand .tick i { font-style:normal; color:var(--green); }
.brand p { margin:3px 0 0; font-size:.75rem; color:var(--dim); }

.nav { padding:0 8px 6px; }
.navitem {
  width:100%; text-align:left; display:flex; align-items:center; gap:9px;
  padding:7px 8px; border-radius:7px; font-size:.86rem; color:var(--dim);
}
.navitem:hover { background:var(--sel); color:var(--ink); }
.navitem[aria-current="page"] { background:var(--sel); color:var(--ink); font-weight:600; }
.navitem .k { margin-left:auto; font-size:.66rem; color:var(--faint); }
.navitem .badge {
  margin-left:auto; font-size:.68rem; font-weight:700; color:var(--red);
  background:var(--red-bg); border:1px solid var(--red-line);
  border-radius:20px; padding:0 6px; line-height:1.5;
}

.railhead {
  padding:12px 16px 6px; display:flex; align-items:baseline; gap:6px;
  border-top:1px solid var(--line); margin-top:4px;
}
.list { overflow-y:auto; flex:1; padding:0 8px 12px; }

.term {
  display:block; width:100%; text-align:left; position:relative;
  padding:8px 10px 9px 12px; border-radius:7px; margin-bottom:1px;
}
.term:hover { background:var(--sel); }
.term[aria-current="page"] { background:var(--panel); box-shadow:var(--shadow); }
.term[aria-current="page"]::before {
  content:""; position:absolute; left:3px; top:9px; bottom:9px;
  width:2px; border-radius:2px; background:var(--ink);
}
.term.stop[aria-current="page"]::before { background:var(--red); }
.term .l1 { display:flex; align-items:center; gap:7px; }
.term .nm {
  font-size:.85rem; font-weight:550; letter-spacing:-.01em; color:var(--ink);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.self {
  font-size:.6rem; letter-spacing:.08em; text-transform:uppercase; font-weight:700;
  color:var(--dim); border:1px solid var(--line2); border-radius:4px;
  padding:1px 5px; line-height:1.5; flex:none; white-space:nowrap;
  font-family:ui-monospace,"SF Mono",SFMono-Regular,Menlo,monospace;
}
.term .l2 {
  font-size:.7rem; color:var(--faint); margin:2px 0 6px 15px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.term .l2 b { color:var(--dim); font-weight:600; }

/* status dot */
.dot { width:8px; height:8px; border-radius:50%; flex:none; position:relative; }
.dot.busy { background:var(--amber); }
.dot.busy::after {
  content:""; position:absolute; inset:-3px; border-radius:50%;
  border:1px solid var(--amber); opacity:.5; animation:ping 2.4s ease-out infinite;
}
.dot.idle { background:transparent; box-shadow:inset 0 0 0 1.5px var(--line2); }
.dot.gone { background:var(--line2); transform:scale(.7); }
.dot.stop { background:var(--red); }
@keyframes ping { 0%{transform:scale(.85);opacity:.6} 70%,100%{transform:scale(1.5);opacity:0} }
@media (prefers-reduced-motion:reduce) { .dot.busy::after { animation:none; } }

/* meter */
.meter { height:3px; border-radius:2px; background:var(--line); overflow:hidden; margin-left:15px; }
.meter i { display:block; height:100%; background:var(--dim); border-radius:2px; }
.meter.stop i { background:var(--red); }
.meter.busy i { background:var(--amber); }

/* rail footer */
.railfoot { border-top:1px solid var(--line); padding:10px 12px; display:grid; gap:8px; }
.ctlrow { display:flex; align-items:center; gap:8px; }
.seg { display:flex; border:1px solid var(--line2); border-radius:7px; overflow:hidden; background:var(--panel); }
.seg button { font-size:.7rem; padding:4px 9px; color:var(--dim); }
.seg button:hover { color:var(--ink); }
.seg button[aria-pressed="true"] { background:var(--sel); color:var(--ink); font-weight:650; }
.seg button + button { border-left:1px solid var(--line); }
.hint { font-size:.66rem; color:var(--faint); line-height:1.6; }
.hint kbd {
  font-family:ui-monospace,Menlo,monospace; font-size:.9em; border:1px solid var(--line2);
  border-bottom-width:2px; border-radius:4px; padding:0 4px; color:var(--dim);
}

/* ------------------------------------------------------------------ main */
.main { min-width:0; padding:30px 34px 64px; }
.page { max-width:960px; }
.phead { margin-bottom:22px; }
.phead h2 {
  margin:0; font-size:1.5rem; font-weight:600; letter-spacing:-.02em;
  display:flex; align-items:center; gap:11px; flex-wrap:wrap;
}
.phead .sub { margin:6px 0 0; color:var(--dim); font-size:.85rem; }

.pill {
  font-size:.66rem; letter-spacing:.09em; text-transform:uppercase; font-weight:700;
  border-radius:20px; padding:2px 9px; border:1px solid var(--line2); color:var(--dim);
}
.pill.busy { color:var(--amber); border-color:var(--amber-line); background:var(--amber-bg); }
.pill.stop { color:var(--red); border-color:var(--red-line); background:var(--red-bg); }

/* stat strip */
.stats {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(122px,1fr));
  border:1px solid var(--line); border-radius:12px; background:var(--panel);
  overflow:hidden; margin-bottom:26px; box-shadow:var(--shadow);
}
.stat { padding:13px 16px; border-right:1px solid var(--line); }
.stat:last-child { border-right:0; }
.stat .n { font-size:1.5rem; font-weight:600; letter-spacing:-.03em; line-height:1.15; }
.stat .n.stop { color:var(--red); }
.stat .n.warn { color:var(--amber); }
.stat .n.zero { color:var(--faint); font-weight:500; }
.stat .c { font-size:.72rem; color:var(--dim); margin-top:2px; }

section { margin-bottom:30px; }
.shead { display:flex; align-items:baseline; gap:10px; margin-bottom:10px; }
.shead .note { font-size:.75rem; color:var(--faint); margin-left:auto; }

/* attention rows */
.alert {
  display:flex; gap:12px; align-items:flex-start; width:100%; text-align:left;
  background:var(--red-bg); border:1px solid var(--red-line); border-left-width:3px;
  border-radius:10px; padding:12px 14px; margin-bottom:7px;
}
.alert:hover { border-color:var(--red); }
.alert .who {
  font-size:.78rem; font-weight:650; color:var(--red); flex:none;
  width:158px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
@media (max-width:700px) { .alert { flex-wrap:wrap; } .alert .who { width:auto; } }
.alert .what { font-size:.9rem; color:var(--ink); min-width:0; }
.alert .go { margin-left:auto; color:var(--red); opacity:.55; flex:none; }
.alert:hover .go { opacity:1; }
.calm {
  border:1px solid var(--line); border-radius:10px; background:var(--panel);
  padding:13px 15px; font-size:.87rem; color:var(--dim); display:flex; gap:9px; align-items:center;
}
.calm b { color:var(--green); font-weight:600; }

/* terminal table */
.tbl { border:1px solid var(--line); border-radius:12px; background:var(--panel); overflow:hidden; box-shadow:var(--shadow); }
.trow {
  display:grid; grid-template-columns:196px minmax(0,1fr) 108px 84px;
  align-items:center; gap:16px; width:100%; text-align:left;
  padding:12px 16px; border-top:1px solid var(--line);
}
.trow:first-child { border-top:0; }
.trow:hover { background:var(--sunk); }
.trow .c1 { display:flex; align-items:center; gap:8px; min-width:0; }
.trow .nm { font-size:.86rem; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.trow .work { font-size:.86rem; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.trow .work.on { color:var(--ink); }
.trow .work.stop { color:var(--red); }
.trow .work .ic { margin-right:7px; opacity:.85; }
.trow .prog { display:flex; align-items:center; gap:8px; }
.trow .prog .meter { flex:1; margin:0; }
.trow .prog span { font-size:.7rem; color:var(--faint); font-variant-numeric:tabular-nums; }
.trow .when { font-size:.72rem; color:var(--faint); text-align:right; font-variant-numeric:tabular-nums; }
.trow .when em { font-style:normal; display:block; color:var(--amber); font-size:.68rem; }
@media (max-width:900px) {
  .trow { grid-template-columns:1fr auto; }
  .trow .prog, .trow .work { grid-column:1 / -1; }
}

/* ---------------------------------------------------------------- detail */
.dhead { border-bottom:1px solid var(--line); padding-bottom:18px; margin-bottom:20px; }
.dhead .path { font-size:.75rem; color:var(--faint); margin-top:7px; }
.dhead .facts { display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:11px; font-size:.74rem; color:var(--dim); }
.dhead .facts span b { color:var(--faint); font-weight:500; }

.callout { border-radius:10px; padding:13px 16px; margin-bottom:9px; border:1px solid; border-left-width:3px; }
.callout.now { background:var(--amber-bg); border-color:var(--amber-line); border-left-color:var(--amber); }
.callout.stop { background:var(--red-bg); border-color:var(--red-line); border-left-color:var(--red); }
.callout .lbl { margin-bottom:5px; }
.callout.now .lbl { color:var(--amber); }
.callout.stop .lbl { color:var(--red); }
.callout .txt { font-size:1.02rem; line-height:1.45; }

/* tree document */
.tree { border:1px solid var(--line); border-radius:12px; background:var(--panel); padding:10px 4px 12px; box-shadow:var(--shadow); }
.item { display:flex; align-items:flex-start; padding:4px 14px 4px 10px; border-radius:6px; }
.item:hover { background:var(--sunk); }
.guide { width:20px; flex:none; align-self:stretch; border-left:1px solid var(--line); margin-left:8px; }
.item .g { width:19px; flex:none; text-align:center; font-size:.8rem; line-height:1.55; color:var(--faint); }
.item .ic { width:22px; flex:none; text-align:center; font-size:.82rem; line-height:1.5; opacity:.8; }
.item .t { min-width:0; font-size:.9rem; }
.item.d0 .t { font-weight:550; }
.item.done .g { color:var(--green); }
.item.done .t { color:var(--dim); }
.item.in_progress { background:var(--amber-bg); }
.item.in_progress .g { color:var(--amber); }
.item.in_progress .t { font-weight:650; }
.item.blocked .g, .item.blocked .t { color:var(--red); }
.item.dropped .t { color:var(--faint); text-decoration:line-through; }

.empty {
  border:1px dashed var(--line2); border-radius:12px; padding:26px;
  text-align:center; color:var(--dim); font-size:.88rem;
}
.empty code { background:var(--sunk); border:1px solid var(--line); border-radius:5px; padding:1px 6px; font-size:.85em; }
.foot { margin-top:34px; padding-top:14px; border-top:1px solid var(--line); font-size:.74rem; color:var(--faint); }
.foot code { color:var(--dim); }

@media (max-width:820px) {
  .app { grid-template-columns:1fr; }
  .rail { position:static; height:auto; max-height:none; }
  .list { max-height:230px; }
  .main { padding:22px 18px 48px; }
}
</style>
</head>
<body>
<div class="app">
  <nav class="rail">
    <div class="brand">
      <h1>ttytree <span class="tick" id="tick"></span></h1>
      <p id="brandsub"></p>
    </div>
    <div class="nav">
      <button class="navitem" id="navdash" onclick="go('/')">
        <span>Dashboard</span><span class="k">D</span>
      </button>
    </div>
    <div class="railhead"><span class="lbl">Terminals</span><span class="lbl" id="ncount"></span></div>
    <div class="list" id="list"></div>
    <div class="railfoot">
      <div class="ctlrow">
        <div class="seg" id="theme">
          <button data-t="auto">Auto</button><button data-t="light">Light</button><button data-t="dark">Dark</button>
        </div>
        <div class="seg" style="margin-left:auto">
          <button onclick="bump(-1)" title="Smaller text">A&minus;</button><button onclick="bump(1)" title="Larger text">A+</button>
        </div>
      </div>
      <div class="hint"><kbd>D</kbd> dashboard &nbsp;<kbd>J</kbd><kbd>K</kbd> move &nbsp;<kbd>1</kbd>&hellip;<kbd>9</kbd> jump</div>
    </div>
  </nav>
  <main class="main" id="main"></main>
</div>

<script>
const SNAPSHOT = __DATA__, ICON_RULES = __ICONS__, LIVE = __LIVE__, SELF = __SELF__;
let DATA = SNAPSHOT, ORDER = [];

/* ------------------------------------------------------------ preferences */
function get(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

function applyTheme(t) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  set("ttytree.theme", t);
  document.querySelectorAll("#theme button").forEach(b =>
    b.setAttribute("aria-pressed", b.dataset.t === t));
}
function applyFont(px) {
  px = Math.max(13, Math.min(22, px));
  document.documentElement.style.setProperty("--fs", px + "px");
  set("ttytree.fs", px);
  return px;
}
let FS = applyFont(parseInt(get("ttytree.fs", "15"), 10) || 15);
function bump(d) { FS = applyFont(FS + d); }
applyTheme(get("ttytree.theme", "auto"));
document.querySelectorAll("#theme button").forEach(b =>
  b.onclick = () => applyTheme(b.dataset.t));

/* ----------------------------------------------------------------- helpers */
function el(tag, cls, txt) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt !== undefined && txt !== null) n.textContent = txt;
  return n;
}
function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.floor(Date.now() / 1000) - ts);
  if (s < 60) return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "m";
  if (s < 86400) return Math.floor(s / 3600) + "h";
  return Math.floor(s / 86400) + "d";
}
/* same word-start matching the terminal renderer uses, so a line gets the
   same icon in both places */
const RULES = ICON_RULES.split(";").filter(Boolean).map(r => {
  const i = r.indexOf("=");
  return { ic: r.slice(0, i), re: new RegExp(" (" + r.slice(i + 1) + ")") };
});
function icon(t) {
  const lt = (" " + (t || "").toLowerCase() + " ").replace(/[^a-z0-9]+/g, " ");
  for (const r of RULES) if (r.re.test(lt)) return r.ic;
  return "";
}
function total(s) {
  const m = s.summary || {};
  return (m.done || 0) + (m.in_progress || 0) + (m.next || 0) + (m.blocked || 0);
}
function state(s) { return s.blocked.length ? "stop" : s.session_status; }
function rank(s) {
  if (s.blocked.length) return 0;
  if (s.session_status === "busy") return 1;
  if (s.session_status === "idle") return 2;
  return 3;
}

/* -------------------------------------------------------------------- rail */
function railItem(s, i) {
  const st = state(s), t = total(s), done = (s.summary || {}).done || 0;
  const b = el("button", "term" + (st === "stop" ? " stop" : ""));
  b.onclick = () => go("/s/" + s.session_id);

  const l1 = el("div", "l1");
  l1.append(el("span", "dot " + st));
  l1.append(el("span", "nm mono", s.project || "?"));
  if (s.session_id === SELF) l1.append(el("span", "self", "here"));
  b.append(l1);

  const meta = [];
  if (s.tty) meta.push(s.tty);
  if (s.has_tree) meta.push(done + "/" + t);
  if (s.tree_updated) meta.push(ago(s.tree_updated));
  const l2 = el("div", "l2 mono");
  l2.append(document.createTextNode(meta.join(" · ")));
  if (s.since_update && s.since_update.turns) {
    l2.append(document.createTextNode(" · "));
    l2.append(el("b", null, "+" + s.since_update.turns));
  }
  b.append(l2);

  const m = el("div", "meter " + st);
  const fi = el("i");
  fi.style.width = (t ? 100 * done / t : 0) + "%";
  m.append(fi);
  b.append(m);
  b.dataset.idx = i;
  return b;
}

function drawRail(ss) {
  const list = document.getElementById("list");
  list.textContent = "";
  ss.forEach((s, i) => list.append(railItem(s, i)));
  document.getElementById("ncount").textContent = ss.length;

  const nb = ss.filter(s => s.blocked.length).length;
  const nr = ss.filter(s => s.session_status === "busy").length;
  document.getElementById("brandsub").textContent =
    ss.length + " terminal" + (ss.length === 1 ? "" : "s")
    + (nr ? " · " + nr + " running" : "");
  const kb = document.getElementById("navdash").querySelector(".k, .badge");
  kb.className = nb ? "badge" : "k";
  kb.textContent = nb ? nb : "D";

  const t = document.getElementById("tick");
  t.textContent = "";
  if (LIVE) { t.append(el("i", null, "●")); t.append(document.createTextNode(" live")); }
  else t.textContent = "snapshot";
}

/* --------------------------------------------------------------- dashboard */
function statBox(n, caption, tone) {
  const b = el("div", "stat");
  b.append(el("div", "n " + (n ? (tone || "") : "zero"), String(n)));
  b.append(el("div", "c", caption));
  return b;
}

function dashboard(ss) {
  const m = document.getElementById("main");
  m.textContent = "";
  const p = el("div", "page");

  const trees = ss.filter(s => s.has_tree);
  const done = trees.reduce((a, s) => a + (s.summary.done || 0), 0);
  const open = trees.reduce((a, s) => a + total(s) - (s.summary.done || 0), 0);
  const blockers = [];
  ss.forEach(s => s.blocked.forEach(t => blockers.push({ s: s, t: t })));
  const drift = trees.reduce((a, s) => a + ((s.since_update || {}).turns || 0), 0);

  const h = el("div", "phead");
  h.append(el("h2", null, "Dashboard"));
  const running = ss.filter(s => s.session_status === "busy");
  h.append(el("p", "sub", blockers.length
    ? blockers.length + " thing" + (blockers.length === 1 ? "" : "s") + " waiting on you across "
      + ss.length + " terminal" + (ss.length === 1 ? "" : "s") + "."
    : (running.length ? running.length + " terminal" + (running.length === 1 ? "" : "s")
       + " working, nothing blocked." : "Nothing blocked, nothing running.")));
  p.append(h);

  const st = el("div", "stats");
  st.append(statBox(blockers.length, blockers.length === 1 ? "blocker" : "blockers", "stop"));
  st.append(statBox(open, "items open"));
  st.append(statBox(done, "items done"));
  st.append(statBox(drift, "turns unrecorded", "warn"));
  p.append(st);

  const att = el("section");
  const ah = el("div", "shead");
  ah.append(el("span", "lbl", "Needs you"));
  att.append(ah);
  if (blockers.length) {
    blockers.forEach(b => {
      const r = el("button", "alert");
      r.onclick = () => go("/s/" + b.s.session_id);
      r.append(el("span", "who mono", b.s.project));
      r.append(el("span", "what", b.t));
      r.append(el("span", "go", "→"));
      att.append(r);
    });
  } else {
    const c = el("div", "calm");
    c.append(el("b", null, "✓"));
    c.append(document.createTextNode("Nothing is blocked. Every terminal can keep going on its own."));
    att.append(c);
  }
  p.append(att);

  const sec = el("section");
  const sh = el("div", "shead");
  sh.append(el("span", "lbl", "Every terminal"));
  sh.append(el("span", "note", "newest tree first"));
  sec.append(sh);
  const tbl = el("div", "tbl");
  ss.forEach(s => tbl.append(tableRow(s)));
  sec.append(tbl);
  p.append(sec);

  const f = el("div", "foot");
  f.innerHTML = "Reads the same <code>ttytree --json</code> contract as the terminal. "
    + (LIVE ? "Re-reads every 10 seconds." : "Static snapshot — regenerate to update.");
  p.append(f);
  m.append(p);
}

function tableRow(s) {
  const st = state(s), t = total(s), done = (s.summary || {}).done || 0;
  const r = el("button", "trow");
  r.onclick = () => go("/s/" + s.session_id);

  const c1 = el("div", "c1");
  c1.append(el("span", "dot " + st));
  c1.append(el("span", "nm mono", s.project || "?"));
  if (s.session_id === SELF) c1.append(el("span", "self", "here"));
  r.append(c1);

  let text = "", cls = "work";
  if (!s.has_tree) { text = "no tree yet"; }
  else if (s.blocked.length) { text = s.blocked[0]; cls += " stop"; }
  else if (s.current) { text = s.current; cls += " on"; }
  else if (s.next.length) { text = "next: " + s.next[0]; }
  else { text = "tree is clear"; }
  const w = el("div", cls);
  const ic = s.has_tree ? icon(text) : "";
  if (ic) w.append(el("span", "ic", ic));
  w.append(document.createTextNode(text));
  r.append(w);

  const pr = el("div", "prog");
  if (s.has_tree) {
    const m = el("div", "meter " + st);
    const fi = el("i");
    fi.style.width = (t ? 100 * done / t : 0) + "%";
    m.append(fi);
    pr.append(m);
    pr.append(el("span", "mono", done + "/" + t));
  }
  r.append(pr);

  const wn = el("div", "when mono");
  wn.append(document.createTextNode(s.tree_updated ? ago(s.tree_updated) + " ago" : "—"));
  const turns = (s.since_update || {}).turns || 0;
  if (turns) wn.append(el("em", null, "+" + turns + " turns"));
  r.append(wn);
  return r;
}

/* ------------------------------------------------------------------ detail */
function detail(s) {
  const m = document.getElementById("main");
  m.textContent = "";
  const p = el("div", "page");
  const st = state(s), t = total(s), done = (s.summary || {}).done || 0;

  const h = el("div", "dhead");
  const h2 = el("h2");
  h2.append(el("span", "mono", s.project || "?"));
  h2.append(el("span", "pill " + st, st === "stop" ? "blocked" : s.session_status));
  if (s.session_id === SELF) h2.append(el("span", "self", "this terminal"));
  h.append(h2);
  if (s.cwd) h.append(el("div", "path mono", s.cwd));

  const facts = el("div", "facts mono");
  const add = (k, v) => {
    if (!v) return;
    const sp = el("span");
    sp.append(el("b", null, k + " "));
    sp.append(document.createTextNode(v));
    facts.append(sp);
  };
  add("tty", s.tty);
  add("pid", s.pid ? String(s.pid) : "");
  add("session", (s.session_id || "").slice(0, 8));
  add("tree", s.tree_updated ? ago(s.tree_updated) + " old" : "");
  const turns = (s.since_update || {}).turns || 0;
  add("unrecorded", turns ? turns + " turns" : "");
  h.append(facts);
  p.append(h);

  if (!s.has_tree) {
    const e = el("div", "empty");
    e.innerHTML = "No tree in this terminal yet.<br>Run <code>/ttytree</code> there and it will write one.";
    p.append(e);
    m.append(p);
    return;
  }

  const stat = el("div", "stats");
  stat.append(statBox(done + "/" + t, "done"));
  stat.append(statBox(s.summary.in_progress || 0, "in progress", "warn"));
  stat.append(statBox(s.summary.next || 0, "queued"));
  stat.append(statBox(s.summary.blocked || 0, "blocked", "stop"));
  p.append(stat);

  s.blocked.forEach(b => {
    const c = el("div", "callout stop");
    c.append(el("div", "lbl", "Blocked"));
    c.append(el("div", "txt", b));
    p.append(c);
  });
  if (s.current) {
    const c = el("div", "callout now");
    c.append(el("div", "lbl", "Working on"));
    c.append(el("div", "txt", s.current));
    p.append(c);
  }
  if (!s.current && !s.blocked.length) {
    const c = el("div", "calm");
    c.append(document.createTextNode(s.next.length
      ? "Nothing marked in progress — next up is “" + s.next[0] + "”."
      : "Nothing open. This tree is finished."));
    p.append(c);
  }

  const sec = el("section");
  sec.style.marginTop = "26px";
  const sh = el("div", "shead");
  sh.append(el("span", "lbl", "The tree"));
  sh.append(el("span", "note", s.items.length + " items"));
  sec.append(sh);
  const tree = el("div", "tree");
  s.items.forEach(i => tree.append(itemRow(i)));
  sec.append(tree);
  p.append(sec);

  if (turns) {
    const f = el("div", "foot");
    f.innerHTML = "This tree has not absorbed the last <b>" + turns + "</b> turns. "
      + "Run <code>/ttytree</code> in " + (s.tty || "that terminal") + " to reconcile it.";
    p.append(f);
  }
  m.append(p);
}

const GLYPH = { done:"✓", in_progress:"▸", next:"○", blocked:"!", dropped:"×" };
function itemRow(i) {
  const r = el("div", "item d" + i.depth + " " + i.state);
  for (let d = 0; d < i.depth; d++) r.append(el("span", "guide"));
  r.append(el("span", "g", GLYPH[i.state] || "·"));
  r.append(el("span", "ic", icon(i.text)));
  r.append(el("span", "t", i.text));
  return r;
}

/* ------------------------------------------------------------------ router */
function go(path) {
  location.hash = "#" + path;
  const a = document.activeElement;          /* don't strand the focus ring */
  if (a && a.blur && a.tagName === "BUTTON") a.blur();
}
function route() {
  const h = location.hash.replace(/^#/, "") || "/";
  const dash = document.getElementById("navdash");
  document.querySelectorAll(".term").forEach(b => b.removeAttribute("aria-current"));
  if (h.startsWith("/s/")) {
    const id = h.slice(3);
    const s = ORDER.find(x => x.session_id === id);
    if (!s) { go("/"); return; }
    dash.removeAttribute("aria-current");
    const i = ORDER.indexOf(s);
    const b = document.querySelector('.term[data-idx="' + i + '"]');
    if (b) { b.setAttribute("aria-current", "page"); }
    document.title = "ttytree — " + (s.project || "session");
    detail(s);
  } else {
    dash.setAttribute("aria-current", "page");
    document.title = "ttytree";
    dashboard(ORDER);
  }
}

function render(data) {
  DATA = data;
  ORDER = data.sessions.slice().sort(
    (a, b) => rank(a) - rank(b) || (b.tree_updated || 0) - (a.tree_updated || 0));
  drawRail(ORDER);
  route();
}

/* --------------------------------------------------------------- keyboard */
document.addEventListener("keydown", e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea") return;
  const h = location.hash.replace(/^#/, "") || "/";
  const cur = h.startsWith("/s/") ? ORDER.findIndex(x => x.session_id === h.slice(3)) : -1;
  if (e.key === "d" || e.key === "D") { go("/"); }
  else if (e.key === "j" || e.key === "ArrowDown") {
    if (ORDER.length) { e.preventDefault(); go("/s/" + ORDER[Math.min(ORDER.length - 1, cur + 1)].session_id); }
  } else if (e.key === "k" || e.key === "ArrowUp") {
    if (cur > 0) { e.preventDefault(); go("/s/" + ORDER[cur - 1].session_id); }
    else if (cur === 0) { e.preventDefault(); go("/"); }
  } else if (/^[1-9]$/.test(e.key)) {
    const s = ORDER[parseInt(e.key, 10) - 1];
    if (s) go("/s/" + s.session_id);
  }
});
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------- live */
let LAST = JSON.stringify(SNAPSHOT);
function tick() {
  fetch("api", { cache: "no-store" }).then(r => r.json()).then(d => {
    const s = JSON.stringify(d);
    if (s === LAST) return;           /* nothing moved — leave the DOM alone */
    LAST = s;
    const y = window.scrollY;
    render(d);
    window.scrollTo(0, y);
  }).catch(() => {});
}
render(SNAPSHOT);
if (LIVE) setInterval(tick, 10000);
</script>
</body></html>
"""


def page(data, icons, live, self_id):
    return (PAGE.replace("__DATA__", json.dumps(data))
                .replace("__ICONS__", json.dumps(icons))
                .replace("__LIVE__", "true" if live else "false")
                .replace("__SELF__", json.dumps(self_id or "")))


def cli_json(cli):
    out = subprocess.run([cli, "--json", "--all"], capture_output=True, text=True)
    return json.loads(out.stdout or '{"version":1,"sessions":[]}')


def serve(port, cli, icons, self_id):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
                    self._send(page(cli_json(cli), icons, True, self_id),
                               "text/html; charset=utf-8")
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
    ap.add_argument("--self", dest="self_id", default="")
    a = ap.parse_args()
    if a.serve:
        serve(a.serve, a.cli, a.icon_map, a.self_id)
    else:
        sys.stdout.write(page(json.load(sys.stdin), a.icon_map, False, a.self_id))

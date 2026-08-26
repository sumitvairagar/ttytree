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
  --bg:#fbfaf8; --rail:#f3f1ec; --sunk:#f1efe9; --sel:#e8e5dd;
  --ink:#191713; --muted:#5b564e;
  --line:#e2ded5; --line2:#cdc7bb;
  --amber:#875f0c; --amber-bg:#f9f0da;
  --red:#a53020;   --red-bg:#faeae6;
  --green:#2e6b38;
  --fs:17px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#100f13; --rail:#16151a; --sunk:#1d1c23; --sel:#26242e;
    --ink:#eeece8; --muted:#a49e95;
    --line:#292730; --line2:#403c49;
    --amber:#e8b662; --amber-bg:#2a2114;
    --red:#f08a79;   --red-bg:#2d1c1b;
    --green:#8aca90;
  }
}
:root[data-theme="dark"] {
  --bg:#100f13; --rail:#16151a; --sunk:#1d1c23; --sel:#26242e;
  --ink:#eeece8; --muted:#a49e95;
  --line:#292730; --line2:#403c49;
  --amber:#e8b662; --amber-bg:#2a2114;
  --red:#f08a79;   --red-bg:#2d1c1b;
  --green:#8aca90;
}

/* Two voices. Mono carries the structure — this is a terminal tool and its
   numbers should line up. The text face carries the prose. Four sizes only,
   a perfect fourth apart, so the hierarchy is never ambiguous. */
:root {
  --mono:"SF Mono",SFMono-Regular,"JetBrains Mono","IBM Plex Mono","Roboto Mono",ui-monospace,Menlo,monospace;
  --text:"Avenir Next","Segoe UI Variable Text",Avenir,"Nimbus Sans","Helvetica Neue",sans-serif;
  --t0:0.75rem;    /* labels, meta, controls  */
  --t1:1rem;       /* body, tree items        */
  --t2:1.333rem;   /* what you are doing      */
  --t3:1.777rem;   /* page titles, big counts */
}

*,*::before,*::after { box-sizing:border-box; }
html { font-size:var(--fs); }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font-family:var(--text); font-size:var(--t1); line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.mono { font-family:var(--mono); }
button { font:inherit; color:inherit; background:none; border:0; cursor:pointer; }
button:focus { outline:none; }
button:focus-visible { outline:2px solid var(--line2); outline-offset:2px; }

.lbl {
  font-family:var(--mono); font-size:var(--t0); letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); font-weight:600;
}

/* ----------------------------------------------------------------- shell */
.app { display:grid; grid-template-columns:302px minmax(0,1fr); min-height:100vh; }

/* ------------------------------------------------------------------ rail */
.rail {
  background:var(--rail); border-right:1px solid var(--line);
  display:flex; flex-direction:column; position:sticky; top:0;
  height:100vh; overflow:hidden;
}
.brand { padding:20px 20px 14px; }
.brand h1 {
  margin:0; font-family:var(--mono); font-size:var(--t1); font-weight:600;
  display:flex; align-items:baseline; gap:10px;
}
.brand .tick { font-size:var(--t0); color:var(--muted); font-weight:500; }
.brand .tick i { font-style:normal; color:var(--green); }
.brand p { margin:4px 0 0; font-size:var(--t0); font-family:var(--mono); color:var(--muted); }

.nav { padding:0 10px 8px; }
.navitem {
  width:100%; text-align:left; display:flex; align-items:center; gap:10px;
  padding:10px 12px; border-radius:8px; font-size:var(--t0);
  font-family:var(--mono); letter-spacing:.06em; text-transform:uppercase;
  font-weight:600; color:var(--muted); min-height:40px;
}
.navitem:hover { background:var(--sel); color:var(--ink); }
.navitem[aria-current="page"] { background:var(--sel); color:var(--ink); }
.navitem .k { margin-left:auto; color:var(--muted); font-weight:500; }
.navitem .badge {
  margin-left:auto; font-weight:700; color:var(--red);
  background:var(--red-bg); border-radius:20px; padding:2px 9px;
}

.railhead {
  padding:14px 20px 8px; display:flex; align-items:baseline; gap:8px;
  border-top:1px solid var(--line); margin-top:6px;
}
.list { overflow-y:auto; flex:1; padding:0 10px 14px; }

/* no left-edge accent bar: the selected row is a filled block, which reads
   as selection without the side-tab tell */
.term {
  display:block; width:100%; text-align:left;
  padding:11px 12px 12px; border-radius:8px; margin-bottom:2px;
}
.term:hover { background:var(--sel); }
.term[aria-current="page"] { background:var(--sel); }
.term .l1 { display:flex; align-items:center; gap:9px; }
.term .nm {
  font-family:var(--mono); font-size:var(--t1); font-weight:600; color:var(--ink);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; letter-spacing:-.01em;
}
.term[aria-current="page"] .nm { text-decoration:underline; text-underline-offset:4px;
  text-decoration-thickness:2px; text-decoration-color:var(--line2); }
.term .l2 {
  font-family:var(--mono); font-size:var(--t0); color:var(--muted);
  margin:4px 0 8px 19px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  font-variant-numeric:tabular-nums;
}
.term .l2 b { color:var(--ink); font-weight:600; }

.self {
  font-family:var(--mono); font-size:var(--t0); letter-spacing:.07em;
  text-transform:uppercase; font-weight:700; color:var(--muted);
  border:1px solid var(--line2); border-radius:5px; padding:1px 6px;
  flex:none; white-space:nowrap; line-height:1.4;
}

.dot { width:10px; height:10px; border-radius:50%; flex:none; position:relative; }
.dot.busy { background:var(--amber); }
.dot.busy::after {
  content:""; position:absolute; inset:-3px; border-radius:50%;
  border:1px solid var(--amber); opacity:.5; animation:ping 2.4s ease-out infinite;
}
.dot.idle { background:transparent; box-shadow:inset 0 0 0 2px var(--line2); }
.dot.gone { background:var(--line2); transform:scale(.65); }
.dot.stop { background:var(--red); }
@keyframes ping { 0%{transform:scale(.85);opacity:.55} 70%,100%{transform:scale(1.5);opacity:0} }
@media (prefers-reduced-motion:reduce) { .dot.busy::after { animation:none; } }

.meter { height:4px; border-radius:2px; background:var(--line); overflow:hidden; margin-left:19px; }
.meter i { display:block; height:100%; background:var(--muted); border-radius:2px; }
.meter.stop i { background:var(--red); }
.meter.busy i { background:var(--amber); }

.railfoot { border-top:1px solid var(--line); padding:12px 14px; display:grid; gap:10px; }
.ctlrow { display:flex; align-items:center; gap:10px; }
.seg { display:flex; border:1px solid var(--line2); border-radius:8px; overflow:hidden; }
.seg button {
  font-family:var(--mono); font-size:var(--t0); padding:8px 12px; min-height:38px;
  color:var(--muted); letter-spacing:.03em;
}
.seg button:hover { color:var(--ink); background:var(--sel); }
.seg button[aria-pressed="true"] { background:var(--sel); color:var(--ink); font-weight:700; }
.seg button + button { border-left:1px solid var(--line2); }
.hint { font-family:var(--mono); font-size:var(--t0); color:var(--muted);
  line-height:1.9; display:grid; gap:2px; }
.hint span { white-space:nowrap; }
.hint kbd {
  font-family:var(--mono); border:1px solid var(--line2); border-bottom-width:2px;
  border-radius:4px; padding:0 5px; color:var(--ink); font-size:.92em;
}

/* ------------------------------------------------------------------ main */
.main { min-width:0; padding:38px 44px 80px; }
.page { max-width:1080px; }
.phead { margin-bottom:30px; }
.phead h2 {
  margin:0; font-size:var(--t3); font-weight:600; letter-spacing:-.022em;
  display:flex; align-items:center; gap:14px; flex-wrap:wrap; line-height:1.15;
}
.phead .sub { margin:10px 0 0; color:var(--muted); font-size:var(--t1); max-width:58ch; }

.pill {
  font-family:var(--mono); font-size:var(--t0); letter-spacing:.08em;
  text-transform:uppercase; font-weight:700; border-radius:20px;
  padding:3px 11px; color:var(--muted); background:var(--sunk);
}
.pill.busy { color:var(--amber); background:var(--amber-bg); }
.pill.stop { color:var(--red); background:var(--red-bg); }

/* counts read as a row of figures, not four boxes */
.stats {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:10px 30px; padding:22px 0 24px; margin-bottom:8px;
  border-top:1px solid var(--line); border-bottom:1px solid var(--line);
}
.stat .n {
  font-family:var(--mono); font-size:var(--t3); font-weight:600;
  letter-spacing:-.03em; line-height:1.1; font-variant-numeric:tabular-nums;
}
.stat .n.stop { color:var(--red); }
.stat .n.warn { color:var(--amber); }
.stat .n.zero { color:var(--muted); font-weight:400; }
.stat .c { font-family:var(--mono); font-size:var(--t0); color:var(--muted); margin-top:6px; }

section { margin-bottom:38px; }
.shead { display:flex; align-items:baseline; gap:12px; margin-bottom:14px; }
.shead .note { font-family:var(--mono); font-size:var(--t0); color:var(--muted); margin-left:auto; }

/* a tinted block, no left rule */
.alert {
  display:flex; gap:18px; align-items:baseline; width:100%; text-align:left;
  background:var(--red-bg); border-radius:10px; padding:16px 18px; margin-bottom:8px;
}
.alert:hover { background:var(--red-bg); filter:brightness(1.04); }
.alert .who {
  font-family:var(--mono); font-size:var(--t0); font-weight:700; color:var(--red);
  flex:none; width:15ch; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  letter-spacing:.02em;
}
.alert .what { font-size:var(--t1); color:var(--ink); min-width:0; max-width:62ch; }
.alert .go { margin-left:auto; color:var(--red); flex:none; font-size:var(--t1); }
@media (max-width:760px) { .alert { flex-wrap:wrap; gap:6px; } .alert .who { width:auto; } }

.calm {
  font-size:var(--t1); color:var(--muted); display:flex; gap:12px;
  align-items:baseline; padding:4px 0;
}
.calm b { color:var(--green); font-weight:600; }

/* hairline-separated rows, not a boxed table */
.trow {
  display:grid; grid-template-columns:22ch minmax(0,1fr) 12ch 10ch;
  align-items:center; gap:20px; width:100%; text-align:left;
  padding:16px 12px 16px 0; border-top:1px solid var(--line);
}
.tbl { border-bottom:1px solid var(--line); }
.trow:hover { background:var(--sunk); padding-left:12px; padding-right:12px;
  margin:0 -12px; border-radius:8px; border-top-color:transparent; }
.trow .c1 { display:flex; align-items:center; gap:10px; min-width:0; }
.trow .nm {
  font-family:var(--mono); font-size:var(--t1); font-weight:600;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.trow .work { font-size:var(--t1); color:var(--muted); overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; }
.trow .work.on { color:var(--ink); }
.trow .work.stop { color:var(--red); }
.trow .work .ic { margin-right:9px; }
.trow .prog { display:flex; align-items:center; gap:10px; }
.trow .prog .meter { flex:1; margin:0; }
.trow .prog span { font-family:var(--mono); font-size:var(--t0); color:var(--muted);
  font-variant-numeric:tabular-nums; }
.trow .when { font-family:var(--mono); font-size:var(--t0); color:var(--muted);
  text-align:right; font-variant-numeric:tabular-nums; line-height:1.45; }
.trow .when em { font-style:normal; display:block; color:var(--amber); }
@media (max-width:900px) {
  .trow { grid-template-columns:1fr auto; gap:8px 16px; }
  .trow .prog, .trow .work { grid-column:1 / -1; }
}

/* ---------------------------------------------------------------- detail */
.dhead { border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:26px; }
.dhead .path { font-family:var(--mono); font-size:var(--t0); color:var(--muted); margin-top:12px; }
.dhead .facts {
  display:flex; flex-wrap:wrap; gap:8px 26px; margin-top:14px;
  font-family:var(--mono); font-size:var(--t0); color:var(--ink);
  font-variant-numeric:tabular-nums;
}
.dhead .facts span b { color:var(--muted); font-weight:500; letter-spacing:.06em;
  text-transform:uppercase; }

.callout { border-radius:10px; padding:18px 20px; margin-bottom:10px; }
.callout.now { background:var(--amber-bg); }
.callout.stop { background:var(--red-bg); }
.callout .lbl { margin-bottom:8px; }
.callout.now .lbl { color:var(--amber); }
.callout.stop .lbl { color:var(--red); }
.callout .txt { font-size:var(--t2); line-height:1.35; letter-spacing:-.012em; }

.tree { padding:2px 0 4px; }
.item { display:flex; align-items:flex-start; padding:5px 12px 5px 0; border-radius:7px; }
.item:hover { background:var(--sunk); padding-left:12px; margin:0 -12px 0 -12px; }
.guide { width:1.4em; flex:none; align-self:stretch; border-left:1px solid var(--line); margin-left:.5em; }
.item .g { width:1.5em; flex:none; text-align:center; font-family:var(--mono);
  font-size:var(--t0); line-height:1.9; color:var(--muted); }
.item .ic { width:1.55em; flex:none; text-align:center; font-size:.85em;
  line-height:1.75; padding-right:.3em; }
.item .t { min-width:0; font-size:var(--t1); }
.item.d0 .t { font-weight:600; }
.item.done .g { color:var(--green); }
.item.done .t { color:var(--muted); font-weight:400; }
.item.in_progress { background:var(--amber-bg); padding-left:12px; margin:0 -12px; }
.item.in_progress .g { color:var(--amber); }
.item.in_progress .t { font-weight:700; }
.item.blocked { background:var(--red-bg); padding-left:12px; margin:0 -12px; }
.item.blocked .g, .item.blocked .t { color:var(--red); }
.item.dropped .t { color:var(--muted); text-decoration:line-through; }

.empty {
  border:1px dashed var(--line2); border-radius:10px; padding:34px;
  text-align:center; color:var(--muted); font-size:var(--t1);
}
.empty code, .foot code { font-family:var(--mono); font-size:.9em; color:var(--ink); }
.foot {
  margin-top:14px; padding-top:18px; border-top:1px solid var(--line);
  font-size:var(--t0); font-family:var(--mono); color:var(--muted); line-height:1.7;
}

@media (max-width:860px) {
  .app { grid-template-columns:1fr; }
  .rail { position:static; height:auto; }
  .list { max-height:260px; }
  .main { padding:26px 20px 56px; }
  .page { max-width:none; }
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
      <div class="hint">
        <span><kbd>D</kbd> dashboard &nbsp; <kbd>J</kbd> <kbd>K</kbd> move</span>
        <span><kbd>1</kbd>&ndash;<kbd>9</kbd> jump to a terminal</span>
      </div>
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
  px = Math.max(14, Math.min(26, px));
  document.documentElement.style.setProperty("--fs", px + "px");
  set("ttytree.fs", px);
  return px;
}
let FS = applyFont(parseInt(get("ttytree.fs", "17"), 10) || 17);
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
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
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
  if (turns) wn.append(el("em", null, "+" + plural(turns, "turn")));
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
  add("unrecorded", turns ? plural(turns, "turn") : "");
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

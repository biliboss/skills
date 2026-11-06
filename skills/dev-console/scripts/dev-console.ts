/**
 * dev-console: a read-only, full-screen console for an event-sourced project in development.
 * One file: Hono on Bun, light style only. (Before 0.33 this was FastHTML in Python, ~8.6k lines in eight files.)
 *
 * Run:   bun --cwd <skill> scripts/dev-console.ts --project <a/dev_console_project.py> [--project <b/...>] [--port 5057] [--no-live]
 *        bun --cwd <skill> --watch scripts/dev-console.ts ...   # live: the server restarts on a save of this file
 *        bun --cwd <skill> scripts/dev-console.ts playground import [<dados dir>] [--force]
 *
 * Each project file is one domain, served in its own context at /domain/<slug> (SLUG, else the skill folder name).
 * The PROJECT CONTRACT (references/project-contract.md) is Python, so the projects are loaded by ONE helper process,
 * scripts/console_project_host.py, that this file talks to over stdin/stdout (see `Host`): the ast reading of SOURCE,
 * the journals, the widgets (FastHTML components rendered to HTML) and the ACTIONS stay there. Everything else is here:
 * the routes, the pages (domain, home, agents, browser, playground), the SQLite home, the agents tailer, the playground
 * server side, the money-bar routes and the live reload.
 *
 * Layout: the work area (entity rail on the left, the selected record on the right) and one status line at the bottom
 * (domain · module · money); ⌘K switches the domain, ⌘P the module (no tab bar). Domain (first tab) = the state
 * machine drawn from the code. Keys (vim-style goto): g d Domain, g m Model, g h home; Esc closes the popup, then the
 * sidebar. All UI state lives in the query string, so a reload or a shared link reopens the same view.
 * A module may be a project widget (MODULE_WIDGETS), and / is the home (the SQLite `home` table).
 */
import { Database } from "bun:sqlite";
import { Hono } from "hono";
import { createHash, randomUUID } from "node:crypto";
import {
  appendFileSync, closeSync, cpSync, existsSync, mkdirSync, openSync, readFileSync, readSync, readdirSync,
  realpathSync, renameSync, rmSync, statSync, lstatSync, watch as fsWatch, writeFileSync, type FSWatcher,
} from "node:fs";
import { homedir } from "node:os";
import { basename, delimiter, dirname, isAbsolute, join, resolve, sep } from "node:path";

export const HERE = import.meta.dir;
const HOME = homedir();
const expand = (p: string) => (p === "~" ? HOME : p.startsWith("~/") ? join(HOME, p.slice(2)) : p);
const env = (k: string, d = "") => process.env[k] ?? d;
const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const jsonResponse = (data: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", ...headers } });
const readText = (p: string) => readFileSync(p, "utf8");
const isFile = (p: string) => { try { return statSync(p).isFile(); } catch { return false; } };
const isDir = (p: string) => { try { return statSync(p).isDirectory(); } catch { return false; } };
const mtimeOf = (p: string) => { try { return statSync(p).mtimeMs / 1000; } catch { return 0; } };

// ------------------------------------------------------------------------------------------------------------------
// The project host: the Python half (scripts/console_project_host.py), one long-lived process per (re)load.
// ------------------------------------------------------------------------------------------------------------------
export type DomainInfo = {
  slug: string; name: string; path: string; origin: string; entity: string; entity_plural: string; source: string;
  draft: string; cost_center: string | null; console_home: string | null; media: string | null; actions: string[]; live_dirs: string[];
};
type Ready = { domains: DomainInfo[]; watch: string[]; catalog: any[]; costs: boolean; clock_driver: boolean };

export class Host {
  proc!: ReturnType<typeof Bun.spawn>;
  info!: Ready;
  private pending = new Map<number, { ok: (v: any) => void; no: (e: Error) => void; timer: ReturnType<typeof setTimeout> }>();
  private seq = 0;
  private buf = "";
  private onReady: ((r: any) => void) | null = null;
  constructor(private flags: string[], private registeredPaths: string[], private script = join(HERE, "console_project_host.py")) {}

  /** Start the helper and wait for its first line (every project loaded), or throw with the Python traceback. */
  async start(): Promise<Ready> {
    const ready = new Promise<any>((ok) => (this.onReady = ok));
    this.proc = Bun.spawn(["uv", "run", "--quiet", "--script", this.script, ...this.flags.flatMap((f) => ["--project", f])], {
      stdin: "pipe", stdout: "pipe", stderr: "inherit",
      env: { ...process.env, DEV_CONSOLE_REGISTERED: this.registeredPaths.join(delimiter) },
    });
    this.pump(this.proc.stdout as ReadableStream<Uint8Array>);
    const first = await ready;
    if (!first.ok) throw new Error(`project host failed:\n${first.error}`);
    this.info = first;
    return first;
  }

  private async pump(stream: ReadableStream<Uint8Array>) {
    const dec = new TextDecoder();
    for await (const chunk of stream as any) {
      this.buf += dec.decode(chunk, { stream: true });
      let i: number;
      while ((i = this.buf.indexOf("\n")) >= 0) {
        const line = this.buf.slice(0, i);
        this.buf = this.buf.slice(i + 1);
        if (!line.trim()) continue;
        let msg: any;
        try { msg = JSON.parse(line); } catch { continue; }
        if (msg.op === "ready") { this.onReady?.(msg); this.onReady = null; continue; }
        const p = this.pending.get(msg.id);
        if (!p) continue;
        this.pending.delete(msg.id);
        clearTimeout(p.timer);
        if (msg.ok) p.ok(msg.data); else p.no(new Error(msg.error || "host error"));
      }
    }
    this.onReady?.({ ok: false, error: "the project host exited before answering" });
    for (const [, p] of this.pending) { clearTimeout(p.timer); p.no(new Error("the project host exited")); }
    this.pending.clear();
  }

  call<T = any>(op: string, args: Record<string, unknown> = {}, timeoutMs = 60_000): Promise<T> {
    const id = ++this.seq;
    return new Promise<T>((ok, no) => {
      const timer = setTimeout(() => { this.pending.delete(id); no(new Error(`host op ${op} timed out`)); }, timeoutMs);
      this.pending.set(id, { ok, no, timer });
      try {
        (this.proc.stdin as any).write(JSON.stringify({ id, op, ...args }) + "\n");
        (this.proc.stdin as any).flush?.();
      } catch (e) { clearTimeout(timer); this.pending.delete(id); no(e as Error); }
    });
  }

  stop() { try { this.proc.kill(); } catch { /* already gone */ } }
}

// ------------------------------------------------------------------------------------------------------------------
// Settings read from the environment (the same names the Python console used).
// ------------------------------------------------------------------------------------------------------------------
export const REGISTRY = () => resolve(expand(env("DEV_CONSOLE_REGISTRY", "~/.local/state/dev-console/domains.txt")));
export function registered(): string[] {
  const reg = REGISTRY();
  const lines = isFile(reg) ? readText(reg).split("\n") : [];
  return lines.map((l) => l.trim()).filter((l) => l && !l.startsWith("#") && existsSync(expand(l))).map((l) => realpathSync(expand(l)));
}
const PLAYGROUND_SLUG = "playground";
const PLAYGROUND_COST_CENTER = env("DEV_CONSOLE_PLAYGROUND_COST_CENTER", "biliboss-skills");
const CLOCK_LOG = () => resolve(expand(env("CLOCK_LOG", "~/.local/state/clock.log")));
const FOCUS_LOG = () => resolve(expand(env("FOCUS_LOG", "~/.local/state/dev-console/focus/focus.jsonl")));
const COSTS_DIR = () => resolve(expand(env("COSTS_DIR", "~/.local/share/costs")));

// ------------------------------------------------------------------------------------------------------------------
// The page assets, inlined (client-side CSS and JS as template literals: a backslash is doubled, a backtick or ${ escaped).
// ------------------------------------------------------------------------------------------------------------------
// The one stylesheet of every page (Tailwind does the rest, from the CDN).
const CSS = `#pop-body.sim { background-image: repeating-linear-gradient(135deg, transparent 0 14px, rgba(127,127,127,.06) 14px 15px); }
#pop-body.sim::before { content: "SIMULADO · os botões funcionam, nada é gravado nem enviado"; display: block; margin-bottom: 14px; font-size: 11px; letter-spacing: .12em; color: #8a8a8a; }

html,body{height:100%;overflow:hidden}
/* Nerd Font symbols (Font Awesome range): one small icon before each tab label */
@font-face { font-family: "Symbols Nerd Font Mono"; font-display: swap;
  src: url("https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.2.1/patched-fonts/NerdFontsSymbolsOnly/SymbolsNerdFontMono-Regular.ttf") format("truetype"); }
.nf { font-family: "Symbols Nerd Font Mono"; font-style: normal; display: inline-block; width: 1.25em; margin-right: .3em; text-align: center; opacity: .75; }
/* ?embed=side: the right menu alone, full width (RightMenu widget) */
html[data-embed=side] #graph-col, html[data-embed=side] #ev-close,
html[data-embed=code] #graph-col, html[data-embed=code] #ev-side > div:not(#ev-body) { display: none !important; }
html[data-embed=side] #ev-side { width: 100% !important; border-left: 0; }
/* ?embed=code: the right menu's Code tab alone (Code widget) */
html[data-embed=code] #ev-side { width: 100% !important; border-left: 0; }
html[data-embed=code] #ev-body > details:not([data-part=Code]), html[data-embed=code] #ev-body > details > summary { display: none !important; }
/* ?embed=switcher: the Domain Switcher alone, open (DomainSwitcher widget) */
html[data-embed=switcher] #bar, html[data-embed=switcher] #work { visibility: hidden; }
html[data-embed=switcher] #dom { padding-top: 24px; }
/* ?embed=toolbar: the real status line alone (Toolbar widget) */
html[data-embed=toolbar] #work, html[data-embed=money] #work { display: none !important; }
html[data-embed=toolbar] #bar, html[data-embed=money] #bar { border-top: 0; }
/* the status line: one thin row at the bottom (VS Code, vim); the hint on the right is faint */
#bar [data-ov]{cursor:pointer} #bar [data-ov]:hover{color:rgb(23 23 23)}
.rec.sel{background:rgb(229 229 229)}
.mermaid svg{max-width:100%}
/* the money bar: one number ticks, the rest is still; an embed never shows it */
#money [data-act]{cursor:pointer} #money [data-act]:focus-visible{outline:1px solid currentColor;outline-offset:2px}
#money .over{color:rgb(220 38 38)} html[data-embed]:not([data-embed=money]) #money{display:none !important}
/* ?embed=money: the money bar alone (CostToolbar widget) */
html[data-embed=money] #bar > :not(#money) { display: none !important; }
html[data-embed=money] #money { border-left: 0; }
/* the right menu's expandable parts: no Pico margins, the chevron right after the title */
#ev-body details { margin: 0; padding: 0; } #ev-body details summary { margin: 0; list-style: none; }
#ev-body details summary::after { float: none; margin-left: .25rem; }
/* a project widget hosted by the console (a module, a sidebar part): the status line or the part already names it,
   so the widget's own leading title hides (it shows in the popup) */
[data-w-host] > div > h2:first-child { display: none; }
`;

// The domain page's script: the graph (Cytoscape; metro, branch, clock, force layouts), the sidebar, the popup, the switcher.
const JS = `import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
mermaid.initialize({startOnLoad:false, theme:'base', fontFamily:'inherit', themeVariables:{
  primaryColor: '#fafafa', primaryBorderColor: '#a3a3a3',
  primaryTextColor: '#262626', lineColor: '#a3a3a3'}});
window.mermaid = mermaid;  // widgets render their own diagrams (a fenced mermaid block in a report)

const M = () => D.model;  // derived from the project's EVENTS, refreshed live
const E = D.events, byId = Object.fromEntries(E.map(e => [e.id, e]));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when = iso => new Date(iso).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const brief = v => v.value ?? v.proposal ?? v.outcome ?? v.conclusion ?? v.statement ?? v.reason ?? v.title ?? v.target ?? JSON.stringify(v);
const of = cat => E.filter(e => e.event.startsWith(cat + '.'));
const label = t => \`<p class="text-[11px] uppercase tracking-widest text-neutral-500">\${t}</p>\`;
const row = (e, cells) => \`<div class="rec flex gap-4 px-4 py-2 cursor-pointer border-b border-neutral-100 hover:bg-neutral-100" data-id="\${e.id}">\${cells}</div>\`;
const meta = (e, extra='') => \`<span class="w-24 shrink-0 tabular-nums text-neutral-400">\${when(e.value.observed_at || e.at)}</span>\${extra}\`;
const empty = t => \`<p class="px-4 py-6 text-neutral-400">\${t}</p>\`;
const list = (es, cells) => es.length ? es.map((e, i) => row(e, cells(e, i))).join('') : empty('Nada aqui.');
const jsonPre = x => \`<pre class="m-0 p-4 !bg-transparent whitespace-pre-wrap text-neutral-600">\${esc(JSON.stringify(x, null, 2))}</pre>\`;

function items() {  // linked things and their last observed state
  const it = {};
  for (const e of E) {
    const v = e.value;
    if (e.event === 'relationship.linked') it[v.target] = {id: v.target, title: v.title || '', state: null, ev: e};
    if (e.event === 'relationship.unlinked') delete it[v.target];
    if (e.event.startsWith('observation.') && v.target in it && v.state) it[v.target].state = v.state;
  }
  return Object.values(it);
}
const isDone = s => ['done','merged','completed','closed'].includes(String(s).toLowerCase());

function proposals() {
  const acts = of('action');
  return acts.filter(e => e.event === 'action.proposed').map(p => {
    const steps = acts.filter(e => e.value.proposal_id === p.id);
    const last = steps.at(-1);
    return {p, steps, status: last ? last.event.split('.')[1] : 'proposed', last};
  });
}
const PT = {proposed:'proposta', started:'em andamento', completed:'concluída', failed:'falhou'};

function renderModel(m) {
  const box = $('model'); if (!box) return;
  $('model-file').textContent = \`\${m.file} · salvo \${new Date(m.mtime * 1000).toLocaleTimeString('pt-BR')}\`;
  box.innerHTML = '<div class="px-2 pb-4 pt-2 leading-6 text-neutral-700">' + m.lines.map(l => {
    const pad = (l.code.match(/^ */) || [''])[0].length;
    return \`<div class="flex"><span class="w-10 shrink-0 pr-3 text-right select-none text-neutral-300">\${l.line ?? ''}</span>\`
      + \`<span class="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]" style="padding-left:\${pad + 4}ch;text-indent:-4ch">\${codeBlock(l.code.trimStart()) || '&nbsp;'}</span></div>\`;
  }).join('') + '</div>';
}
new EventSource(D.base + '/source/stream').onmessage = ev => {
  D.model = JSON.parse(ev.data);
  if (GRAPH(tab) && $('cy')) { drawGraph(); if (side.id) openSide(side.id); }
};

function codeBlock(src) {  // grayscale highlight: weight, not colour
  return src.split('\\n').map(l => {
    const i = l.indexOf('#');
    const code = i < 0 ? l : l.slice(0, i), note = i < 0 ? '' : l.slice(i);
    const h = esc(code)
      .replace(/\\b(class|def)(\\s+)(\\w+)/g, '<span class="text-neutral-500">$1</span>$2<span class="font-semibold text-neutral-900">$3</span>')
      .replace(/\\b(self|cls)\\b/g, '<span class="text-neutral-500">$1</span>');
    return h + (note ? \`<span class="text-neutral-400">\${esc(note)}</span>\` : '');
  }).join('\\n');
}

let graphRO = null;  // the resize observer of the drawing on screen (a redraw disconnects it)
const layoutKey = () => \`dev-console:layout:\${D.base}\`;
function toggleLayout() {  // \`L\` only (no button): branch <-> metro (rays), remembered per domain; the name shows as a brief toast
  const m = localStorage.getItem(layoutKey()) || M().layout, next = m === 'branch' ? 'metro' : 'branch';
  localStorage.setItem(layoutKey(), next);
  drawGraph();
  let t = $('layout-toast');
  if (!t) { t = document.createElement('div'); t.id = 'layout-toast';
    t.className = 'fixed right-4 top-4 z-50 px-2 py-1 rounded text-xs bg-neutral-900 text-white pointer-events-none'; document.body.appendChild(t); }
  t.textContent = ({branch: 'ramos', metro: 'raios'})[next]; t.style.display = '';
  clearTimeout(t._h); t._h = setTimeout(() => { t.style.display = 'none'; }, 1200);
}

function drawGraph() {
  if (graphRO) graphRO.disconnect();
  if (window.__cy) { try { window.__cy.destroy(); } catch (e) {} window.__cy = null; }
  const used = {}; E.forEach(e => used[e.event] = (used[e.event] || 0) + 1);
  const ink = '#171717', mute = '#d4d4d4', soft = '#a3a3a3', bg = '#ffffff';
  const nodes = [], edges = [];
  const PATH = {management:'#4338ca', observation:'#0f766e', reasoning:'#a16207', relationship:'#0369a1', action:'#be123c'};
  const PAL = ['#4338ca', '#0f766e', '#a16207', '#0369a1', '#be123c', '#4d7c0f'];
  Object.keys(M().lifecycle).forEach((c, i) => { PATH[c] ??= PAL[i % PAL.length]; });
  // the drawing: the person's choice (L toggles branch / metro, kept per domain), else the project's LAYOUT, else metro
  const stored = localStorage.getItem(layoutKey());
  const MODE = stored === 'branch' || stored === 'metro' ? stored : M().layout;
  const BR = MODE === 'branch', METRO = MODE === 'metro' || BR;  // see the METRO and BRANCH blocks below
  let BRINFO = null;  // branch: the lanes' y bands and the stages' x bands, for the headless checks (cy.scratch('branch'))
  if (METRO) Object.keys(M().lifecycle).forEach((c, i) => { PATH[c] = \`hsl(\${Math.round(i * 137.5) % 360}, 65%, 38%)\`; });
  const colorOf = id => PATH[id.split('.')[0]];
  // Entity.Event: management happens to the Tension itself; the others to the Value Object of their category.
  const ENT = D.entities || {};
  const pascal = w => w.split('_').map(x => x[0].toUpperCase() + x.slice(1)).join('');
  const name = id => { const [c, v] = id.split('.'); return \`\${ENT[c] || pascal(c)}.\${pascal(v)}\`; };
  const CENTER = M().hub || M().root;
  const depth = {[CENTER]: 0}, queue = [CENTER];  // rings: steps from the centre (the hub, else created)
  while (queue.length) { const a = queue.shift(); (M().next[a] || []).forEach(b => { if (!(b in depth)) { depth[b] = depth[a] + 1; queue.push(b); } }); }
  Object.entries(M().lifecycle).forEach(([cat, verbs]) => verbs.forEach(v => {
    const id = \`\${cat}.\${v}\`;
    nodes.push({data: {id, color: PATH[cat], label: name(id).replace('.', '\\n')}, classes: [D.journal_types[id] ? 'used' : '', id === M().root ? 'root' : ''].join(' ')});
  }));
  // ISO 9241-210 (human-centred design): a generic Human is who acts; the first command creates the Tension.
  nodes.push({data: {id: 'human', label: 'Human', color: ink}, classes: 'human'});
  {  // seed: ring = steps from the Human, angle = order; fCoSE refines from here (randomize: false)
    const hd = {human: 0}, q = ['human'], start = M().initial || [M().root];
    start.forEach(s => { hd[s] = 1; q.push(s); }); q.shift();
    while (q.length) { const a = q.shift(); (M().next[a] || []).forEach(b => { if (!(b in hd)) { hd[b] = hd[a] + 1; q.push(b); } }); }
    nodes.forEach((n, i) => { const d = hd[n.data.id] ?? 3, t = 2 * Math.PI * i / nodes.length;
      n.position = d ? {x: Math.cos(t) * d * 160, y: Math.sin(t) * d * 160} : {x: 0, y: 0}; });
  }
  (M().initial || [M().root]).forEach(s => edges.push({data: {id: \`human>\${s}\`, source: 'human', target: s, color: colorOf(s),
    label: M().commands[s]}, classes: D.journal_types[s] ? 'walked' : ''}));
  Object.entries(M().next).forEach(([a, bs]) => bs.forEach(b =>
    edges.push({data: {id: \`\${a}>\${b}\`, source: a, target: b, color: colorOf(b), label: (M().edge_cmd || {})[\`\${a}>\${b}\`] || M().commands[b]}, classes: [D.journal_types[a] && D.journal_types[b] ? 'walked' : '', (M().next[b] || []).includes(a) ? 'loop' : ''].join(' ')})));
  const STARTS = M().initial || [M().root];
  // each start keeps its own side: what only the left start reaches stays left of the Human, what only the right one
  // reaches stays right, so no edge has to cross the Human (shared nodes, like a hub, go where the forces put them)
  const reach = s => { const seen = new Set([s]), q = [s];
    while (q.length) (M().next[q.shift()] || []).forEach(b => { if (!seen.has(b)) { seen.add(b); q.push(b); } }); return seen; };
  const SIDES = STARTS.length > 1 ? (() => { const L = reach(STARTS[0]), R = reach(STARTS[1]);
    return [...[...L].filter(n => !R.has(n) && n !== STARTS[0]).map(n => ({left: n, right: 'human', gap: 200})),
            ...[...R].filter(n => !L.has(n) && n !== STARTS[1]).map(n => ({left: 'human', right: n, gap: 200}))]; })() : [];
  // LAYOUT = "clock" (project file): the code's EVENTS order is the clock. The first category sits at 12 o'clock and
  // the others follow clockwise; inside a category its events run outward from the Human. The order lives in the
  // code, so the drawing never drifts from it.
  const CLOCK = MODE === 'clock';
  if (CLOCK) {
    const cats = Object.keys(M().lifecycle), N = cats.length;
    const pos = {human: {x: 0, y: 0}};
    cats.forEach((c, i) => { const t = -Math.PI / 2 + 2 * Math.PI * i / N;
      M().lifecycle[c].forEach((v, k) => { const r = 230 + k * 140; pos[\`\${c}.\${v}\`] = {x: Math.cos(t) * r, y: Math.sin(t) * r}; }); });
    nodes.forEach(n => { n.position = pos[n.data.id] || {x: 0, y: 0}; });
  }

  // LAYOUT = "metro" (project file): a Tokyo Metro map read from the clock, deterministic (preset positions, no force
  // layout). Octilinear layout, after the metro-map literature (Nöllenburg & Wolff 2011, "Drawing and Labeling
  // High-Quality Metro Maps by Mixed-Integer Programming"): every segment lies on one of 8 directions (multiples of 45°).
  // Each category of EVENTS is a line in its own colour; its clock hour (the first category at 12 o'clock, the others
  // clockwise) snapped to the nearest of the 8 directions says where it leaves the Human. Categories that snap to the
  // same direction are fanned: each next one runs parallel, one TRACK further to the counter-clockwise side. Stations
  // are one constant STEP apart, in EVENTS order, the first one RING from the Human. The label sits on the side of its
  // line that faces away from the Human's middle (right on the right half, left on the left half; below an eastbound
  // line, above a westbound one), always the same side per direction, horizontal text, never rotated; a fanned line
  // runs on the opposite side, so the labels fall in the gap between tracks. A colliding label is pushed outward.
  const STEP = 170, TRACK = 180, HUMAN_R = 56, LABEL_CHARS = 14, LABEL_PUSH = 14;
  const LINE_POINTS = [], DASH_POINTS = [];   // thick line and dashed edge polylines (model coordinates), for the label collision test
  const SHIFT = [0, 1, 0, -1, 0, -1, 0, 1];   // diagonals (NE SE SW NW): the label leaves its own line, down (+1) or up (-1)
  const metroLabelOf = id => { const [c, v] = id.split('.'), ent = ENT[c] || pascal(c);
    const parts = pascal(v).match(/[A-Z][a-z0-9]*|[a-z0-9]+/g) || [pascal(v)], lines = [];
    parts.forEach(p => { const last = lines.length - 1; if (last >= 0 && lines[last].length + p.length <= LABEL_CHARS) lines[last] += p; else lines.push(p); });
    return [ent, ...lines].join('\\n'); };
  if (METRO) {
    const DIRS = [[0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]].map(([x, y]) => { const l = Math.hypot(x, y); return [x / l, y / l]; });
    const SIDE = ['r', 'r', 'b', 'r', 'l', 'l', 't', 'l'];   // N NE E SE S SW W NW: the label's side, fixed per direction
    const FAN = [1, 1, 1, -1, 1, 1, 1, -1];                    // which way a fanned track goes: +1 counter-clockwise, -1 clockwise (never the label's side)
    const cats = Object.keys(M().lifecycle), N = cats.length, dirOf = {}, group = {}, count = {};
    // the clock as the sun's rays: the categories share the whole turn evenly from 12h, in EVENTS order
    cats.forEach((c, i) => { const d = Math.round(8 * i / N) % 8; dirOf[c] = d; group[c] = count[d] || 0; count[d] = group[c] + 1; });
    const BRANCH = HUMAN_R + 4, RING = BRANCH + (Math.max(...Object.values(count)) - 1) * TRACK + 110;   // the fan leaves the Human's rim, then runs straight
    const at = (c, k) => { const [dx, dy] = DIRS[dirOf[c]], o = FAN[dirOf[c]] * group[c] * TRACK, r = RING + k * STEP;   // ccw side = (dy, -dx)
      return {x: dy * o + dx * r, y: -dx * o + dy * r}; };
    const pos = {human: {x: 0, y: 0}}, st = {}, where = {}, parent = {};
    // a line follows TRANSITIONS: a station's parent is its earliest in-line predecessor by a forward edge (EVENTS order;
    // a backward edge, like a reactivation, is a loop and stays a dashed cross edge). Where a station forks, the child
    // with the longest path below it continues the trunk; the others are branches (Tokyo's Marunouchi branch) leaving
    // at 45°, alternating sides, each a STEP further out
    const rot = ([x, y], q) => { const a = q * Math.PI / 4, c = Math.cos(a), sn = Math.sin(a); return [x * c - y * sn, x * sn + y * c]; };
    (BR ? [] : cats).forEach(c => { const vs = M().lifecycle[c], ids = vs.map(v => \`\${c}.\${v}\`), k = Object.fromEntries(ids.map((id, i) => [id, i]));
      const kids = Object.fromEntries(ids.map(id => [id, []]));
      ids.forEach(b => { const a = ids.find(a => k[a] < k[b] && edges.some(e => e.data.source === a && e.data.target === b));
        if (a) { parent[b] = a; kids[a].push(b); } });
      const depth = id => 1 + Math.max(0, ...kids[id].map(depth));
      const place = (id, P, dir, n) => { pos[id] = P; where[id] = {c, k: n}; st[id] = {side: SIDE[dirOf[c]], dir: dirOf[c]};
        const ks = [...kids[id]].sort((x, y) => depth(y) - depth(x) || k[x] - k[y]);
        ks.forEach((ch, j) => { const d = j === 0 ? dir : rot(dir, (j % 2 ? 1 : -1)), r = j === 0 ? STEP : STEP * Math.ceil(j / 2) * Math.SQRT2;
          place(ch, {x: P.x + d[0] * r, y: P.y + d[1] * r}, d, n + 1); }); };
      let n = 0; ids.filter(id => !parent[id]).forEach(root => { const P = at(c, n); place(root, P, DIRS[dirOf[c]], n);
        n += 1 + (function trunk(id) { const ks = [...kids[id]].sort((x, y) => depth(y) - depth(x) || k[x] - k[y]); return ks.length ? 1 + trunk(ks[0]) : 0; })(root); }); });
    nodes.forEach(n => { const id = n.data.id; n.position = pos[id] || {x: 0, y: 0};
      if (id !== 'human' && st[id]) { n.classes = (n.classes || '') + ' station'; n.data.mlabel = metroLabelOf(id); n.data.side = st[id].side; n.data.dir = st[id].dir; } });
    // a segment route: from S through the bends Bs to T; cytoscape wants each bend as a weight and a distance:
    // point = S + w (T - S) + d (-dy, dx) / |T - S|
    const route = (S, T, Bs) => { const dx = T.x - S.x, dy = T.y - S.y, L2 = dx * dx + dy * dy;
      return {w: Bs.map(B => ((B.x - S.x) * dx + (B.y - S.y) * dy) / L2), d: Bs.map(B => ((B.y - S.y) * dx - (B.x - S.x) * dy) / Math.sqrt(L2))}; };
    const octi = (S, T, skip) => { const dx = T.x - S.x, dy = T.y - S.y, m = Math.min(Math.abs(dx), Math.abs(dy));
      if (m < 1 || Math.abs(Math.abs(dx) - Math.abs(dy)) < 1) return null;   // already 0 / 45 / 90: straight
      // one bend, two ways: the diagonal first or the straight run first; keep the one that stays clear of the Human
      // and of the other stations (a route through them reads as a line through them)
      const diag = {x: S.x + Math.sign(dx) * m, y: S.y + Math.sign(dy) * m};
      const run = {x: S.x + (Math.abs(dx) > Math.abs(dy) ? Math.sign(dx) * (Math.abs(dx) - m) : 0),
                   y: S.y + (Math.abs(dy) > Math.abs(dx) ? Math.sign(dy) * (Math.abs(dy) - m) : 0)};
      const cost = B => { let c = 0; [[S, B], [B, T]].forEach(([p, q]) => { const len = Math.hypot(q.x - p.x, q.y - p.y);
        for (let t = 0; t <= len; t += 8) { const x = p.x + (q.x - p.x) * t / len, y = p.y + (q.y - p.y) * t / len;
          if (Math.hypot(x, y) < HUMAN_R + 16) c += 3;
          Object.entries(pos).forEach(([id, o]) => { if (id !== 'human' && id !== skip[0] && id !== skip[1] && Math.hypot(x - o.x, y - o.y) < 18) c += 1; }); } }); return c; };
      return cost(run) < cost(diag) ? run : diag; };
    const stub = c => { const [dx, dy] = DIRS[dirOf[c]], o = group[c] * TRACK;   // leaves the trunk at the Human's rim, a 45° leg into its track
      const track = at(c, 0), run = {x: track.x - dx * (RING - BRANCH - o), y: track.y - dy * (RING - BRANCH - o)};   // where the leg meets the track
      return o ? [{x: dx * BRANCH, y: dy * BRANCH}, run] : null; };
    const adjacent = (a, b) => parent[b] === a;
    const made = new Set();
    // LAYOUT = "branch" (project file, or \`L\` on any domain): a git graph read left to right (\`git log --graph\`, the most
    // familiar flow drawing). The Human is the root, at the top left. Each category of EVENTS is a horizontal lane (a
    // branch), top to bottom in EVENTS order; inside a lane a line follows TRANSITIONS as the metro does (the longest path
    // is the trunk, a fork drops into a short 45° spur inside the lane, a back edge is a dashed arrow). A lane is born
    // where its transition comes from: its first station sits one column right of the station that leads into it, joined
    // by a 45° connector (a vertical gutter between two 45° legs when the lane is far below); a lane nothing leads into
    // starts from the Human along a grey spine. Any other edge into another lane is a merge: thin, grey, dashed, one bend,
    // with its command label. Columns are the funnel stages when the project declares STAGES and STAGE_ORDER (a band of
    // columns per stage, a faint header at the top, a station inside its stage's band, ordered by the path); without
    // them a column is the longest step count from the Human. Labels are horizontal, below the station (above on a
    // spur that rises), pushed apart by the same collision pass as the metro.
    const COL = 170, SPURY = 72, GAP = 40, LANE_ABOVE = 80, LANE_BELOW = 88, LANE_PAD = 34, LANE_SKIP = 12, HEADER = 84;
    const branchLayout = () => {
      const lanes = cats.map(c => ({c, ids: M().lifecycle[c].map(v => \`\${c}.\${v}\`)})), laneOf = {};
      lanes.forEach((l, i) => l.ids.forEach(id => { laneOf[id] = i; }));
      const adj = {}; edges.forEach(e => { (adj[e.data.source] ??= []).push(e.data.target); });
      // reverse post-order of a depth-first walk from the Human (then from what it does not reach, in lane order): every
      // edge but the back edges (loops) points forward, so a longest path gives the columns
      // the walk also follows the order of each lane (a station before the next one), so a station that nothing leads
      // to is placed after the one before it
      const walkAdj = Object.fromEntries(Object.entries(adj).map(([a, bs]) => [a, [...bs]]));
      lanes.forEach(l => l.ids.slice(1).forEach((id, i) => { (walkAdj[l.ids[i]] ??= []).push(id); }));
      const seen = new Set(), onStack = new Set(), back = new Set();
      const dfs = (a, out) => { seen.add(a); onStack.add(a);
        (walkAdj[a] || []).forEach(b => { if (onStack.has(b)) back.add(\`\${a}>\${b}\`); else if (!seen.has(b)) dfs(b, out); });
        onStack.delete(a); out.push(a); };
      const order = ['human', ...lanes.flatMap(l => l.ids)].flatMap(r => { if (seen.has(r)) return []; const out = []; dfs(r, out); return out.reverse(); });
      // the funnel stages (STAGES, STAGE_ORDER): columns are bands, one per stage. An edge that goes back to an earlier
      // stage would run leftwards: it is a loop, a dashed arrow, like any back edge
      const ST = M().stages || {}, SO = [...(M().stage_order || [])];
      Object.values(ST).forEach(s => { if (!SO.includes(s)) SO.push(s); });
      const staged = SO.length > 0; if (!staged) SO.push('');
      if (staged) edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (ST[a] != null && ST[b] != null && SO.indexOf(ST[b]) < SO.indexOf(ST[a])) back.add(\`\${a}>\${b}\`); });
      // the stage of a station is STAGES[id]; one that is not named takes its parent's or its predecessors' latest,
      // else the previous station of its lane
      const preds = {}; edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (a !== b && !back.has(\`\${a}>\${b}\`)) (preds[b] ??= []).push(a); });
      // inside a lane: a station's parent is its earliest in-lane predecessor by a forward edge; the longest path below a
      // fork stays on the lane's row, the other children drop (below first, then above, then further) into a 45° spur
      const parentOf = {}, kidsOf = {}, slot = {};
      lanes.forEach(l => { const k = Object.fromEntries(l.ids.map((id, i) => [id, i]));
        l.ids.forEach(id => { kidsOf[id] = []; });
        l.ids.forEach(b => { const a = l.ids.find(a => k[a] < k[b] && (preds[b] || []).includes(a)); if (a) { parentOf[b] = a; kidsOf[a].push(b); } });
        const dep = id => 1 + Math.max(0, ...kidsOf[id].map(dep));
        const walk = (id, s) => { slot[id] = s; [...kidsOf[id]].sort((x, y) => dep(y) - dep(x) || k[x] - k[y])
          .forEach((ch, j) => walk(ch, j === 0 ? s : s + (j % 2 ? 1 : -1) * Math.ceil(j / 2))); };
        l.ids.filter(id => !parentOf[id]).forEach(r => walk(r, 0)); });
      const stage = {}, local = {}, occ = new Set();
      const prevOf = id => { const l = lanes[laneOf[id]], i = l.ids.indexOf(id); return i > 0 ? l.ids[i - 1] : null; };
      order.forEach(id => { if (id === 'human') return;
        let s = staged && ST[id] != null ? SO.indexOf(ST[id]) : -1;
        if (s < 0) { const ps = (preds[id] || []).filter(a => stage[a] != null).map(a => stage[a]), pv = prevOf(id);
          s = stage[parentOf[id]] ?? (ps.length ? Math.max(...ps) : (pv && stage[pv] != null ? stage[pv] : 0)); }
        stage[id] = s; });
      // a column inside the stage's band: one right of its latest predecessor in the same stage; a later root of a lane
      // continues from the station before it; two stations never share a lane row and a column
      order.forEach(id => { if (id === 'human') return;
        let base = Math.max(0, ...(preds[id] || []).filter(a => a !== 'human' && local[a] != null && stage[a] === stage[id]).map(a => local[a] + 1));
        const pv = prevOf(id); if (!parentOf[id] && pv && local[pv] != null && stage[pv] === stage[id]) base = Math.max(base, local[pv] + 1);
        const key = c => \`\${laneOf[id]}|\${slot[id]}|\${stage[id]}|\${c}\`; while (occ.has(key(base))) base++;
        occ.add(key(base)); local[id] = base; });
      const width = SO.map(() => 0); Object.keys(local).forEach(id => { width[stage[id]] = Math.max(width[stage[id]], local[id] + 1); });
      const bandStart = []; let cc = 1; SO.forEach((s, i) => { bandStart[i] = cc; cc += width[i]; });
      const xOf = id => (bandStart[stage[id]] + local[id]) * COL + stage[id] * GAP;
      // the lanes, top to bottom in EVENTS order; the Human sits on the first lane's row
      let y = 0; lanes.forEach(l => { const ss = l.ids.map(id => slot[id]), lo = Math.min(...ss), hi = Math.max(...ss);
        l.top = y; l.row = y + (lo < 0 ? -lo * SPURY + LANE_ABOVE : LANE_PAD); l.bottom = l.row + hi * SPURY + LANE_BELOW; y = l.bottom + LANE_SKIP; });
      const y0 = lanes[0].row;
      lanes.forEach(l => { l.top -= y0; l.row -= y0; l.bottom -= y0; l.ids.forEach(id => { pos[id] = {x: xOf(id), y: l.row + slot[id] * SPURY}; }); });
      nodes.forEach(n => { const id = n.data.id; if (id === 'human') return;
        n.position = pos[id]; n.classes = (n.classes || '') + ' station'; n.data.mlabel = metroLabelOf(id);
        n.data.side = slot[id] < 0 ? 't' : 'b'; n.data.dir = 2; n.data.lane = laneOf[id]; n.data.stage = SO[stage[id]]; });
      const top = lanes[0].top - (staged ? HEADER : 0), bottom = lanes[lanes.length - 1].bottom;
      const bands = SO.map((s, i) => ({stage: s, x1: bandStart[i] * COL + i * GAP - COL / 2, x2: (bandStart[i] + width[i]) * COL + i * GAP - COL / 2}));
      if (staged) bands.forEach((b, i) => { if (!width[i]) return;
        nodes.unshift({data: {id: \`stage:\${i}\`, label: (M().stage_labels || {})[b.stage] ?? b.stage, w: b.x2 - b.x1, h: bottom - top, tone: i % 2 ? 0.05 : 0.025},
          position: {x: (b.x1 + b.x2) / 2, y: (top + bottom) / 2}, classes: 'stagehdr', selectable: false, grabbable: false}); });
      BRINFO = {lanes: lanes.map(l => ({cat: l.c, y1: l.top, y2: l.bottom, row: l.row, ids: l.ids})), bands: staged ? bands.filter((b, i) => width[i]) : [],
        stage: Object.fromEntries(Object.entries(stage).map(([id, i]) => [id, SO[i]]))};
      // the edges. A lane's birth: the transition into its first station from the leftmost source outside the lane
      lanes.forEach(l => { l.first = l.ids.find(id => !parentOf[id]); });
      const birth = {};
      lanes.forEach((l, i) => { const ps = (preds[l.first] || []).filter(a => laneOf[a] !== i).sort((a, b) => pos[a].x - pos[b].x); if (ps.length) birth[l.first] = ps[0]; });
      const kindOf = (a, b) => parentOf[b] === a ? 'inlane'
        : (laneOf[b] != null && lanes[laneOf[b]].first === b && birth[b] === a && !back.has(\`\${a}>\${b}\`)) ? 'branch' : 'merge';
      // a spur leaves its parent at 45° and then runs along its own row; the others bend once
      const spurRoute = (a, b) => { const S = pos[a], T = pos[b], dy = T.y - S.y, dx = T.x - S.x;
        if (Math.abs(dy) < 1) return [];
        if (Math.abs(dy) < dx - 1) return [{x: S.x + Math.abs(dy), y: T.y}];
        const B = octi(S, T, [a, b]); return B ? [B] : []; };
      // a branch from a station far below (or above) leaves at 45°, drops along its own gutter, and enters its lane at 45°;
      // each branch leaving the same station takes its own gutter, the farthest lane the innermost, so they never cross
      const groups = {};
      edges.forEach(e => { const a = e.data.source, b = e.data.target;
        if (a !== 'human' && a !== b && kindOf(a, b) === 'branch') (groups[\`\${a}|\${Math.sign(pos[b].y - pos[a].y)}\`] ??= {a, bs: []}).bs.push(b); });
      const gutter = {};
      Object.values(groups).forEach(({a, bs}) => bs.sort((p, q) => Math.abs(pos[q].y - pos[a].y) - Math.abs(pos[p].y - pos[a].y))
        .forEach((b, i) => { gutter[\`\${a}>\${b}\`] = Math.min(46 + i * 26, COL - 40); }));  // a full track apart: 10 px read as one line
      const branchRoute = (a, b) => { const S = pos[a], T = pos[b], dy = T.y - S.y, dx = T.x - S.x, s = Math.sign(dy);
        if (a === 'human') return Math.abs(dy) >= dx ? [{x: 0, y: T.y - s * dx}] : spurRoute(a, b);
        const h = gutter[\`\${a}>\${b}\`];
        if (Math.abs(dy) < COL || dx < COL - 1 || h == null) return spurRoute(a, b);
        const Bs = [{x: S.x + h, y: S.y + s * h}, {x: S.x + h, y: T.y - s * (COL - h)}, {x: S.x + COL, y: T.y}];
        if (dx - COL < 1) Bs.pop(); return Bs; };
      // the interchange: lines leaving one station down (or up) a 45° leg are ranked by the leg's length; rank k leaves
      // k·PAR lower-left of the centre (source-endpoint) and turns 2·k·PAR earlier, so the legs are parallel tracks
      const PAR = 9, legs = {}, rank = {};
      const rawBs = (a, b) => { const k = kindOf(a, b); return k === 'merge' || a === 'human' || a === b ? [] : k === 'inlane' ? spurRoute(a, b) : branchRoute(a, b); };
      edges.forEach(e => { const a = e.data.source, b = e.data.target, B = rawBs(a, b)[0]; if (!B) return;
        const lx = B.x - pos[a].x, ly = B.y - pos[a].y; if (lx < 1 || Math.abs(Math.abs(ly) - lx) > 1) return;
        (legs[\`\${a}|\${Math.sign(ly)}\`] ??= []).push({b, lx}); });
      Object.entries(legs).forEach(([key, ls]) => { const a = key.split('|')[0];
        ls.sort((p, q) => q.lx - p.lx).forEach((l, k) => { rank[\`\${a}>\${l.b}\`] = k; }); });
      const shifted = (a, b, Bs) => { const k = rank[\`\${a}>\${b}\`] || 0; if (!k || !Bs.length) return Bs;
        const sg = Math.sign(Bs[0].y - pos[a].y) || 1, d = 2 * k * PAR, nx = Bs[1] || pos[b];
        const horiz = Math.abs(nx.y - Bs[0].y) < 1;  // a leg that then runs along a row turns earlier; one that drops, lower
        return [horiz ? {x: Bs[0].x - d, y: Bs[0].y} : {x: Bs[0].x, y: Bs[0].y + sg * d}, ...Bs.slice(1)]; };
      const done = new Set(), born = new Set();
      edges.forEach(e => { const a = e.data.source, b = e.data.target, cl = (e.classes || '').replace(/\\bloop\\b/, '').trim();
        if (a === b) return;
        const kind = kindOf(a, b); done.add(\`\${a}>\${b}\`); let Bs = [];
        if (kind === 'merge' && back.has(\`\${a}>\${b}\`)) {  // a loop runs leftwards: an arc above the rows, never along a line
          const dx = Math.abs(pos[b].x - pos[a].x), dy = pos[b].y - pos[a].y;
          e.classes = \`\${cl} cross backloop\`; e.data.cpd = (pos[b].x <= pos[a].x ? 1 : -1) * (SPURY * 0.9 + Math.min(dx, 4 * COL) * 0.12 + Math.abs(dy) * 0.1); }
        else if (kind === 'merge') { e.classes = \`\${cl} cross\`; const B = octi(pos[a], pos[b], [a, b]); Bs = B ? [B] : []; DASH_POINTS.push([pos[a], ...Bs, pos[b]]); }
        else { Bs = shifted(a, b, kind === 'inlane' ? spurRoute(a, b) : branchRoute(a, b)); e.data.label = '';
          const k = rank[\`\${a}>\${b}\`] || 0, sg = Math.sign(pos[b].y - pos[a].y) || 1;
          if (k) e.data.sep = \`\${-k * PAR}px \${sg * k * PAR}px\`;
          const spine = a === 'human' && Math.abs(pos[b].y - pos[a].y) >= 1;
          e.classes = \`\${cl} \${spine ? 'spine' : 'line'}\${e.data.sep ? ' parallel' : ''}\`; if (spine) e.data.color = soft; if (kind === 'branch') born.add(b);
          LINE_POINTS.push([k ? {x: pos[a].x - k * PAR, y: pos[a].y + sg * k * PAR} : pos[a], ...Bs, pos[b]]); }  // the shifted start, for the label test
        if (Bs.length) e.data.route = route(pos[a], pos[b], Bs); });
      // a lane is continuous: where the model has no edge between a station and the one before it, a faint rail carries the
      // line on; a lane nothing leads into hangs from the Human on the grey spine
      const rail = (a, b, color, cls, Bs) => { edges.push({data: {id: \`rail:\${a}>\${b}\`, source: a, target: b, color, label: '', ...(Bs.length ? {route: route(pos[a], pos[b], Bs)} : {})}, classes: cls});
        LINE_POINTS.push([pos[a], ...Bs, pos[b]]); };
      lanes.forEach(l => { const pairs = l.ids.slice(1).map(id => [parentOf[id] || prevOf(id), id]).filter(([a, b]) => a !== b && !done.has(\`\${a}>\${b}\`));
        if (!born.has(l.first)) pairs.unshift(['human', l.first]);
        pairs.forEach(([a, b]) => { if (a === 'human') { const far = Math.abs(pos[b].y) >= 1; rail(a, b, far ? soft : PATH[l.c], far ? 'spine' : 'rail', far ? branchRoute(a, b) : []); }
          else rail(a, b, PATH[l.c], 'rail', spurRoute(a, b)); }); });
    };
    if (BR) branchLayout();
    (BR ? [] : edges).forEach(e => { const a = e.data.source, b = e.data.target, cl = (e.classes || '').replace(/\\bloop\\b/, '').trim();
      made.add(\`\${a}>\${b}\`);
      const lineEdge = a === 'human' ? where[b] && where[b].k === 0 : adjacent(a, b);
      if (lineEdge) { e.classes = \`\${cl} line\`; e.data.label = ''; const c = where[b].c;
        const Bs = a === 'human' ? stub(c) : null;
        if (Bs) { e.data.route = route(pos[a], pos[b], Bs); LINE_POINTS.push([pos[a], ...Bs, pos[b]]); } else LINE_POINTS.push([pos[a], pos[b]]); }
      else { e.classes = \`\${cl} cross\`; const B = octi(pos[a], pos[b], [a, b]); if (B) e.data.route = route(pos[a], pos[b], [B]); } });
    // a line is continuous: where the model has no edge between two neighbours (or the Human and the first station)
    // a faint rail carries the line on, so the category still reads as one track
    (BR ? [] : cats).forEach(c => { const ids = M().lifecycle[c].map(v => \`\${c}.\${v}\`), c0 = ids[0];
      // only roots after the first have no parent: a later root continues the trunk from the station before it
      const pairs = ids.slice(1).map(id => [parent[id] || ids[Math.max(0, ids.indexOf(id) - 1)], id]).filter(([a, b]) => a !== b);
      if (!made.has(\`human>\${c0}\`)) pairs.unshift(['human', c0]);
      pairs.forEach(([a, b]) => { if (made.has(\`\${a}>\${b}\`)) return;
        const Bs = a === 'human' ? stub(c) : null;
        edges.push({data: {id: \`rail:\${a}>\${b}\`, source: a, target: b, color: PATH[c], label: '', ...(Bs ? {route: route(pos[a], pos[b], Bs)} : {})}, classes: 'rail'});
        LINE_POINTS.push(Bs ? [pos[a], ...Bs, pos[b]] : [pos[a], pos[b]]); }); });
  }
  const cy = cytoscape({
    // the wheel is ours (below the layout): two fingers pan, a pinch or ⌘ + scroll zooms, as in Figma and Maps
    container: $('cy'), elements: {nodes, edges}, userZoomingEnabled: false,
    // fCoSE: force-directed, the Human pinned in the centre; seeded (randomize false + fixed seed positions) so a
    // reload draws the same picture. nodeRepulsion and idealEdgeLength leave room for the edge labels.
    layout: (CLOCK || METRO) ? {name: 'preset', padding: 24} : {name: 'fcose', quality: 'proof', randomize: false, animate: false, padding: 24,
             nodeDimensionsIncludeLabels: true, idealEdgeLength: () => 130, nodeRepulsion: () => 45000,
             edgeElasticity: () => 0.45, gravity: 0.4, gravityRange: 2.5, numIter: 5000, nodeSeparation: 90,
             fixedNodeConstraint: [{nodeId: 'human', position: {x: 0, y: 0}}],
             // the starts sit in line with the Human, one on each side; what follows them hangs below
             ...(STARTS.length > 1 ? {alignmentConstraint: {horizontal: [['human', ...STARTS]]},
               relativePlacementConstraint: [{left: STARTS[0], right: 'human', gap: 160}, {left: 'human', right: STARTS[1], gap: 160}, ...SIDES,
                 ...(M().hub ? [{top: 'human', bottom: M().hub, gap: 140},
                   ...(M().next[M().hub] || []).map(b => ({top: M().hub, bottom: b, gap: 90}))] : [])]} : {})}, maxZoom: 3,
    style: [
      {selector: 'node', style: {shape: 'round-rectangle', width: n => Math.max(...n.data('label').split('\\n').map(l => l.length)) * 10 + 28, height: 56,
        'text-wrap': 'wrap', 'line-height': 1.3,
        'background-color': bg, 'border-width': 1.5, 'border-color': 'data(color)', 'border-opacity': 0.7,
        label: 'data(label)', 'text-valign': 'center', 'font-family': 'ui-monospace, monospace',
        'font-size': 16, color: 'data(color)'}},
      {selector: 'node.used', style: {'background-color': 'data(color)', 'border-width': 0, color: bg, 'font-weight': 700}},
      {selector: 'node.root', style: {'font-size': 19, width: n => Math.max(...n.data('label').split('\\n').map(l => l.length)) * 12 + 36, height: 66}},
      // UML initial pseudostate: a filled dot, named Human (who triggers the first transition).
      // the Human is the centre of every domain: twice an event node's height (56)
      {selector: 'node.human', style: {shape: 'ellipse', width: 112, height: 112, 'background-color': ink,
        'border-width': 0, color: ink, 'font-size': 22, 'font-weight': 700, 'text-valign': 'bottom', 'text-margin-y': 12,
        'font-family': 'ui-sans-serif, system-ui'}},
      {selector: 'edge', style: {label: 'data(label)', 'font-family': 'ui-monospace, monospace', 'font-size': 15,
        color: 'data(color)', 'text-background-color': bg, 'text-background-opacity': 1, 'text-background-padding': '3px',
        'text-rotation': 'autorotate'}},
      {selector: 'edge', style: {width: 2, 'line-color': 'data(color)', 'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle', 'arrow-scale': 0.8, 'curve-style': 'straight', 'line-opacity': 0.45}},
      {selector: 'edge.walked', style: {width: 3.5, 'line-opacity': 1}},
      // a loop (A -> B and B -> A, from TRANSITIONS): two curved edges, side by side, so neither hides the other
      {selector: 'edge.loop', style: {'curve-style': 'bezier', 'control-point-step-size': 60}},
      ...(METRO ? [
        {selector: 'node.station', style: {shape: 'ellipse', width: 16, height: 16, 'background-color': bg, 'border-width': 3,
          'border-color': 'data(color)', 'border-opacity': 1, label: 'data(mlabel)', 'font-size': 14, 'font-weight': 400,
          color: '#525252', 'text-wrap': 'wrap', 'line-height': 1.15, 'text-valign': 'center', 'text-halign': 'center'}},
        {selector: 'node.station.used', style: {'background-color': 'data(color)', 'border-width': 0, width: 18, height: 18, color: ink}},
        {selector: 'node.station[side="r"]', style: {'text-halign': 'right', 'text-valign': 'center', 'text-justification': 'left'}},
        {selector: 'node.station[side="l"]', style: {'text-halign': 'left', 'text-valign': 'center', 'text-justification': 'right'}},
        {selector: 'node.station[side="b"]', style: {'text-halign': 'center', 'text-valign': 'bottom', 'text-justification': 'center'}},
        {selector: 'node.station[side="t"]', style: {'text-halign': 'center', 'text-valign': 'top', 'text-justification': 'center'}},
        {selector: 'node.human', style: {'text-valign': 'center', color: bg, 'text-margin-y': 0, 'font-size': 20}},
        {selector: 'edge.line', style: {width: 6, 'line-color': 'data(color)', 'line-opacity': 1, 'target-arrow-shape': 'none', label: '', 'z-index': 3}},
        {selector: 'node.stagehdr', style: {shape: 'rectangle', width: 'data(w)', height: 'data(h)', 'background-color': ink, 'background-opacity': 'data(tone)',
          'border-width': 0, label: 'data(label)', 'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': 40, 'font-size': 20, 'font-weight': 600,
          'font-family': 'ui-sans-serif, system-ui', color: soft, 'text-opacity': 0.85, events: 'no', 'z-index': 0}},
        {selector: 'edge.spine', style: {width: 4, 'line-color': soft, 'line-opacity': 0.55, 'target-arrow-shape': 'none', label: '', events: 'no', 'z-index': 1}},
        {selector: 'edge.rail', style: {width: 6, 'line-color': 'data(color)', 'line-opacity': 0.5, 'target-arrow-shape': 'none', label: '', events: 'no', 'z-index': 1}},
        {selector: 'edge.parallel', style: {'source-endpoint': 'data(sep)'}},
        {selector: 'edge.backloop', style: {'curve-style': 'unbundled-bezier', 'control-point-distances': 'data(cpd)', 'control-point-weights': 0.5, 'z-index': 1}},
        {selector: 'edge.cross', style: {width: 2, 'line-color': soft, 'line-style': 'dashed', 'line-dash-pattern': [7, 5], 'line-opacity': 0.9,
          'target-arrow-color': soft, 'target-arrow-shape': 'triangle', 'arrow-scale': 1, color: soft, 'font-size': 14, 'text-rotation': 'none', 'z-index': 2}},
      ] : []),
      {selector: ':selected', style: {'border-width': 4, 'border-color': ink, 'border-opacity': 1}},
    ],
  });
  if (METRO) {
    // octilinear routes: a bend point per edge that needs one (computed above as weight and distance)
    cy.edges().forEach(e => { const r = e.data('route'); if (!r) return;
      e.style({'curve-style': 'segments', 'segment-weights': r.w, 'segment-distances': r.d, 'edge-distances': 'node-position'}); });
    // labels: the clockwise side first; a label that touches another label, a station or a line is pushed outward
    const box = (n, labels) => n.boundingBox({includeNodes: !labels, includeEdges: false, includeLabels: !!labels, includeOverlays: false});
    const hit = (a, b, m) => a.x1 - m < b.x2 && b.x1 - m < a.x2 && a.y1 - m < b.y2 && b.y1 - m < a.y2;
    const bodies = cy.nodes().not('.stagehdr').map(n => ({id: n.id(), b: box(n, false)}));
    const onLine = (bx, set = LINE_POINTS) => set.some(pts => pts.slice(1).some((p, i) => { const q = pts[i], len = Math.hypot(p.x - q.x, p.y - q.y);
      for (let t = 0; t <= len; t += 4) { const x = q.x + (p.x - q.x) * t / len, y = q.y + (p.y - q.y) * t / len;
        if (x > bx.x1 - 4 && x < bx.x2 + 4 && y > bx.y1 - 4 && y < bx.y2 + 4) return true; } return false; }));
    const uni = (a, b) => ({x1: Math.min(a.x1, b.x1), y1: Math.min(a.y1, b.y1), x2: Math.max(a.x2, b.x2), y2: Math.max(a.y2, b.y2)});
    const placed = [], unions = [], PUSH = {r: [1, 0], l: [-1, 0], b: [0, 1], t: [0, -1]};
    cy.nodes('.station').forEach(n => {
      const pref = n.data('side'), dir = n.data('dir'), cands = BR ? [pref, pref === 'b' ? 't' : 'b'] : [pref];   // branch: a station that branches downwards may carry its label above
      let best = null;
      for (const side of cands) {
        n.data('side', side);
        const [px, py] = PUSH[side], h = box(n, true), lh = h.y2 - h.y1;
        let mx = px * 9, my = py * 9;
        // on a diagonal the label centred on the station would sit on its own line: shift it off, to the clockwise side
        if (SHIFT[dir]) my += SHIFT[dir] * (lh / 2 + 3);
        for (let i = 0; i < 10; i++) {
          n.style({'text-margin-x': mx, 'text-margin-y': my});
          const lb = box(n, true);   // the label alone (includeNodes false)
          const ub = uni(lb, box(n, false));
          const hits = placed.filter(p => hit(p, lb, 4)).length + unions.filter(p => hit(p, ub, 2)).length
            + bodies.filter(o => o.id !== n.id() && hit(o.b, ub, 3)).length + (onLine(lb) || onLine(lb, DASH_POINTS) ? 1 : 0);
          if (!best || hits < best.hits) best = {hits, side, m: [mx, my]};   // never worse than the least-clashing step
          if (!hits) break;
          mx += px * LABEL_PUSH; my += py * LABEL_PUSH;
        }
        if (best.hits === 0) break;
      }
      n.data('side', best.side); n.style({'text-margin-x': best.m[0], 'text-margin-y': best.m[1]});
      placed.push(box(n, true)); unions.push(uni(box(n, true), box(n, false)));
    });
    // a dashed edge's label (the command): the midpoint first, then nudged around it until it clears everything
    const eplaced = [], NUDGE = [];
    for (let dy = -224; dy <= 224; dy += 16) for (let dx = -224; dx <= 224; dx += 28) NUDGE.push([dx, dy]);   // a grid around the midpoint, nearest first
    NUDGE.sort((a, b) => Math.hypot(...a) - Math.hypot(...b));
    cy.edges('.cross').forEach(e => { if (!e.data('label')) return;
      let best = null, bestHits = 1e9;
      for (const [nx, ny] of NUDGE) { e.style({'text-margin-x': nx, 'text-margin-y': ny});
        const lb = e.boundingBox({includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false});
        const hits = placed.filter(p => hit(p, lb, 3)).length + eplaced.filter(p => hit(p, lb, 3)).length
          + unions.filter(p => hit(p, lb, 3)).length + bodies.filter(o => hit(o.b, lb, 3)).length + (onLine(lb) ? 1 : 0);
        if (hits < bestHits) { bestHits = hits; best = [nx, ny]; } if (!hits) break; }
      e.style({'text-margin-x': best[0], 'text-margin-y': best[1]});
      eplaced.push(e.boundingBox({includeNodes: false, includeEdges: false, includeLabels: true, includeOverlays: false})); });
  }
  // Legible at his window: no label renders below 14 px on screen. Font sizes are in model units, so the zoom has a
  // floor (14 / the smallest label's font); fit, the home view and a pinch stop there, and a big domain opens larger
  // than the window, read by panning. Nothing is hidden or resized: every label keeps the room the layout gave it.
  const LEGIBLE = 14, fonts = cy.elements().filter(e => e.style('label')).map(e => parseFloat(e.style('font-size')));
  if (fonts.length) cy.minZoom(Math.min(cy.maxZoom(), LEGIBLE / Math.min(...fonts)));
  // The wheel, as in Figma and Maps: two fingers (or a mouse wheel) pan; a pinch zooms around the pointer (Chrome and
  // Firefox send it as wheel + ctrlKey; Safari as gesture events), and so does ⌘ + scroll.
  const pane = $('cy'), at = e => { const r = pane.getBoundingClientRect();
    return Number.isFinite(e.clientX) ? {x: e.clientX - r.left, y: e.clientY - r.top} : {x: r.width / 2, y: r.height / 2}; };
  const zoomTo = (z, e) => cy.zoom({level: Math.min(cy.maxZoom(), Math.max(cy.minZoom(), z)), renderedPosition: at(e)});
  let pinch = 0;   // the zoom when a WebKit pinch began; 0 = none
  const input = {
    wheel: e => {
      e.preventDefault();   // the page never scrolls under the graph
      const k = e.deltaMode === 1 ? 40 : e.deltaMode === 2 ? cy.height() : 1;   // lines, pages or pixels
      let dx = e.deltaX * k, dy = e.deltaY * k;
      if (e.ctrlKey || e.metaKey) {   // a pinch is small steps; a ctrl or ⌘ mouse notch is capped at about a quarter
        if (!pinch) zoomTo(cy.zoom() * Math.exp(-Math.max(-0.3, Math.min(0.3, dy * (e.ctrlKey ? 0.01 : 0.002)))), e);
        return; }
      if (e.shiftKey && !dx) [dx, dy] = [dy, 0];   // shift + mouse wheel goes sideways
      cy.panBy({x: -dx, y: -dy}); },
    gesturestart: e => { e.preventDefault(); pinch = cy.zoom(); },
    gesturechange: e => { e.preventDefault(); if (pinch && e.scale) zoomTo(pinch * e.scale, e); },
    gestureend: e => { e.preventDefault(); pinch = 0; }};
  // a redraw (L, new events) keeps the pane: drop the last drawing's handlers, or one wheel would pan once per drawing
  Object.entries(pane._graphInput || {}).forEach(([t, f]) => pane.removeEventListener(t, f));
  pane._graphInput = input;
  Object.entries(input).forEach(([t, f]) => pane.addEventListener(t, f, {passive: false}));
  let box = '';
  graphRO = new ResizeObserver(([e]) => {
    const k = \`\${Math.round(e.contentRect.width)}x\${Math.round(e.contentRect.height)}\`;
    if (k === box || !e.contentRect.width) return;  // same size: do nothing (this guard stops the flicker loop)
    box = k; cy.resize(); cy.fit(undefined, 20); centreHuman();
  });
  graphRO.observe($('cy'));
  // open centred on the Human (fit keeps the zoom, then the Human goes to the middle); off centre, a button brings it back
  // branch: the Human at the top left with a margin, the zoom fitting the height down to the legible floor (pan to read on)
  function homeView() {
    const bb = cy.elements().boundingBox({includeLabels: true, includeOverlays: false}), m = 40;
    const zoom = Math.max(cy.minZoom(), Math.min(1, (cy.height() - 2 * m) / Math.max(bb.y2 - bb.y1, 1)));   // the legible floor
    return {zoom, pan: {x: m - bb.x1 * zoom, y: m - bb.y1 * zoom}};
  }
  function centreHuman() {
    const h = cy.$('#human'); if (h.empty()) { offCentre(); return; }
    if (BR) { const v = homeView(); cy.zoom(v.zoom); cy.pan(v.pan); offCentre(); return; }
    cy.center(h);
    // centred on the Human, every node must still show: zoom out around the Human until the farthest one fits
    const bb = cy.elements().renderedBoundingBox(), cx = cy.width() / 2, cy0 = cy.height() / 2, pad = 24;
    const k = Math.min(1, (cx - pad) / Math.max(cx - bb.x1, bb.x2 - cx, 1), (cy0 - pad) / Math.max(cy0 - bb.y1, bb.y2 - cy0, 1));
    if (k < 1) cy.zoom({level: cy.zoom() * k, renderedPosition: {x: cx, y: cy0}});
    offCentre();
  }
  function offCentre() {
    const h = cy.$('#human'), b = $('centre-human'); if (!b || h.empty()) return;
    const p = h.renderedPosition(), v = BR ? homeView() : null,
      tx = v ? h.position().x * v.zoom + v.pan.x : cy.width() / 2, ty = v ? h.position().y * v.zoom + v.pan.y : cy.height() / 2,
      far = Math.hypot(p.x - tx, p.y - ty) > 40;
    b.classList.toggle('hidden', !far);
  }
  cy.on('pan zoom', offCentre);
  cy.ready(centreHuman);
  if ($('centre-human')) $('centre-human').onclick = () => cy.animate(BR ? {zoom: homeView().zoom, pan: homeView().pan, duration: 250, complete: offCentre}
    : {center: {eles: cy.$('#human')}, duration: 250, complete: offCentre});
  cy.scratch('branch', BRINFO);
  $('legend').innerHTML = Object.entries(PATH).filter(([c]) => c in M().lifecycle).map(([c, col]) => \`<span style="color:\${col}">● \${c}</span>\`).join('')
    + '';
  cy.on('tap', ev => { if (ev.target === cy) closeSide(); });
  cy.on('tap', 'node', ev => { if (Q.get('embed') !== 'graph') openSide(ev.target.id()); });  // embed=graph: the graph alone
  window.__cy = cy;
}

// --- the event sidebar: contextual, with its own tabs -----------------------------------------------------
// UI state lives in the URL query: tab, ev (event in the sidebar), side (sidebar tab), w (widget popup).
const Q = new URLSearchParams(location.search);
function setQ(k, v) { v ? Q.set(k, v) : Q.delete(k); const q = Q.toString();
  history.replaceState(null, '', location.pathname + (q ? '?' + q : '')); }
let side = {id: null, tab: Q.get('side') || 'Widgets'};
const SIDE_TABS = {
  // Description: what the event means, for a human: the code comment of its command in EVENTS
  'Description': id => Promise.resolve((M().descriptions || {})[id]
    ? \`<p class="px-4 py-2 font-sans text-[15px] leading-relaxed text-neutral-800">\${esc(M().descriptions[id])}</p>\`
    : '<p class="px-4 py-2 text-neutral-400">sem descrição: escreva um comentário no comando, em EVENTS</p>'),
  'Widgets': id => frag(\`\${D.base}/w/\${D.state.id}/\${id}?e=\${Q.get('e') || ''}\`),
  // Code: pseudo-code of the clicked event's context, read from the real model (EVENTS, the projector): the command
  // that records it, where it comes from and what it opens, and the entity it changes. Short on purpose.
  'Code': id => {
    const m = M(), ENT = D.entities || {}, [c, v] = id.split('.');
    const P = w => w.split('_').map(x => x[0].toUpperCase() + x.slice(1)).join('');
    const nm = e => { const [k, x] = e.split('.'); return \`\${ENT[k] || P(k)}.\${P(x)}\`; };
    const from = Object.entries(m.next).filter(([, bs]) => bs.includes(id)).map(([a]) => nm(a));
    if ((m.initial || [m.root]).includes(id)) from.unshift('Human');
    const to = (m.next[id] || []).map(nm), cmd = m.commands[id];
    const at = (m.lines.find(l => l.code.trim().startsWith(\`def \${cmd}(\`)) || {}).line;
    const root = m.root.split('.')[0], ent = ENT[c] || P(c);
    // Subsections, in order of relevance: the entity (the command and its class) and the value object this event
    // carries open by default; the other value objects, then the types (enums) last, closed. Each item remembers
    // being opened or closed in localStorage, by name, so it stays that way on every node.
    const line = (n, code) => {
      const hit = code.trim().startsWith(\`def \${cmd}(\`) || n === at && n != null;
      const pad = (code.match(/^ */) || [''])[0].length;
      return \`<div class="flex \${hit ? 'bg-neutral-200' : ''}"><span class="w-10 shrink-0 pr-3 text-right select-none text-neutral-300">\${n ?? ''}</span>\`
        + \`<span class="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]" style="padding-left:\${pad + 4}ch;text-indent:-4ch">\${codeBlock(code.trimStart()) || '&nbsp;'}</span></div>\`;
    };
    const key = name => \`dev-console:code:\${D.base}:\${name}\`;
    const item = (name, label, rows, open) => {
      const saved = localStorage.getItem(key(name)), isOpen = saved ? saved === 'open' : open;
      return \`<details data-code-item="\${esc(name)}" \${isOpen ? 'open' : ''} class="mb-1">\`
        + \`<summary class="flex items-center gap-2 px-2 h-7 cursor-pointer select-none text-neutral-500 hover:text-neutral-900">\${label}</summary>\`
        + \`<div class="pb-2">\${rows.map(([n, code]) => line(n, code)).join('')}</div></details>\`;
    };
    const group = title => \`<div class="px-2 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-400">\${title}</div>\`;
    const entityRows = [
      [at, \`\${ent}.\${cmd}(value) -> \${nm(id)}\`],
      [null, \`    from  \${from.join(', ') || '—'}\`],
      [null, \`    then  \${to.join(', ') || '—'}\`],
      [null, ''],
      [null, \`class \${ent}:  # \${c === root ? 'the aggregate root, folded by the projector' : 'held by ' + (ENT[root] || P(root))}\`],
      ...(c === root ? [[null, \`    \${(m.props || []).join(', ')}\`]] : []),
      ...Object.entries(m.commands).filter(([e]) => e.startsWith(c + '.')).map(([e, k]) => [null, \`    def \${k}(value) -> \${nm(e)}\`]),
    ];
    const vos = m.value_objects || [];
    const voRows = vo => [[vo.line, \`@value class \${vo.name}:  # \${vo.doc}\`], ...vo.fields.map(([f, t, ln]) => [ln, \`    \${f}: \${t}\`])];
    const mine = vos.filter(vo => !vo.members && vo.event === id);
    const others = vos.filter(vo => !vo.members && vo.event !== id);
    const types = vos.filter(vo => vo.members);
    const html = item(\`entity:\${ent}\`, \`\${ent} · \${cmd}\`, entityRows, true)
      + mine.map(vo => item(\`vo:\${vo.name}\`, \`\${vo.name} · o valor de \${nm(id)}\`, voRows(vo), true)).join('')
      + (others.length ? group('Value objects') + others.map(vo => item(\`vo:\${vo.name}\`, vo.name, voRows(vo), false)).join('') : '')
      + (types.length ? group('Tipos') + types.map(vo => item(\`type:\${vo.name}\`, \`\${vo.name} <span class="text-neutral-400">· \${esc(vo.members.join(' | '))}</span>\`,
          [[vo.line, \`@enum \${vo.name}: \${vo.members.join(' | ')}  # \${vo.doc}\`]], false)).join('') : '');
    // save only what the person toggles (a click on the summary), never the default state of a first render
    setTimeout(() => document.querySelectorAll('[data-code-item] > summary').forEach(s => s.onclick = () => {
      const d = s.parentElement; setTimeout(() => localStorage.setItem(key(d.dataset.codeItem), d.open ? 'open' : 'closed'), 0); }), 0);
    return Promise.resolve(\`<p class="px-4 pt-3 text-neutral-400">pseudo-código · de \${esc(m.file)} · ao vivo</p><div class="px-2 py-2 leading-6 text-neutral-700">\${html}</div>\`);
  },
  'JSON': id => Promise.resolve(jsonPre(E.filter(e => e.event === id))),
  // every event has it, so it is a tab of the right menu (the last), not a widget in the list
  'Observability': id => frag(\`\${D.base}/w/\${D.state.id}/\${id}/Observability?e=\${Q.get('e') || ''}\`).then(h => \`<div class="p-4">\${h}</div>\`),
};
function openSide(id) {
  side.id = id; setQ('ev', id);
  $('ev-side').classList.remove('hidden');
  if (id === 'human') {
    $('ev-name').textContent = 'Human';
    $('ev-sub').textContent = 'estado inicial · ISO 9241-210';
    $('ev-tabs').innerHTML = '';
    $('ev-body').innerHTML = \`<p class="p-4 font-sans text-sm text-neutral-700">Quem age. Começa por \${(M().initial || [M().root]).map(s => \`<b>\${M().commands[s]}</b> (grava \${s})\`).join(' ou ')}.</p>\`;
    return;
  }
  const [c, v] = id.split('.'), n = E.filter(e => e.event === id).length, w = (M().coverage || {})[id] || [];
  $('ev-name').textContent = \`\${c}.\${v}\`;
  $('ev-sub').textContent = \`comando \${M().commands[id]} · \${n} \${n === 1 ? 'evento' : 'eventos'} · \${w.length ? \`\${w.length} \${w.length === 1 ? 'widget' : 'widgets'}\` : 'sem widgets'}\`;
  renderSide();
}
// The right menu is a column of expandable parts (Widgets only when the event has widgets; Code, JSON, and
// Observability last, since every event has it). Every part starts open; each node remembers which parts the user
// closed, in localStorage (key per domain, event and part).
const sideParts = id => Object.keys(SIDE_TABS).filter(t => t !== 'Widgets' || ((M().coverage || {})[id] || []).length);
const partKey = (id, p) => \`dev-console:part:\${D.base}:\${id}:\${p}\`;
// one expandable part of the sidebar, the same markup for an event's parts and an entity's (a module's card)
const partHtml = (p, open) => \`<details data-part="\${esc(p)}" \${open ? 'open' : ''}
      class="border-b border-neutral-200">
      <summary class="flex items-center gap-2 px-4 h-9 cursor-pointer select-none text-[11px] uppercase tracking-widest text-neutral-500 hover:text-neutral-900">\${esc(p)}</summary>
      <div class="part-body pb-2"><p class="px-4 text-neutral-400">carregando…</p></div></details>\`;
function renderSide() {
  const want = side.id, parts = sideParts(want);
  $('ev-tabs').innerHTML = '';
  $('ev-body').innerHTML = parts.map(p => partHtml(p, localStorage.getItem(partKey(want, p)) !== 'closed')).join('');
  $('ev-body').querySelectorAll('details').forEach(d => d.ontoggle = () =>
    d.open ? localStorage.removeItem(partKey(want, d.dataset.part)) : localStorage.setItem(partKey(want, d.dataset.part), 'closed'));
  parts.forEach(p => SIDE_TABS[p](want).then(html => {
    if (side.id !== want) return;
    const el = $('ev-body').querySelector(\`details[data-part="\${p}"] .part-body\`);
    inject(el, html);
    if (p === 'Widgets') wireRows(el, want);
    if (p === 'Code') {  // scroll only the sidebar to the event's command (scrollIntoView would also scroll #main)
      const hit = el.querySelector('#hit'), body = $('ev-body');
      if (hit) body.scrollTop = hit.offsetTop - body.clientHeight / 2;
    }
  }));
}

const frag = u => fetch(u, {headers: {'HX-Request': 'true'}}).then(r => r.text());
// --- Switcher overlay: fuzzy subsequence match (fzf-style), matched letters in bold. One finder, two lists:
// ⌘K the domains only (Enter opens /domain/<slug>), ⌘P the modules (D.modules: Domain, TABS, Playground) ---------
let domSel = 0, domHits = [], ovMode = 'domain';
function fuzzy(q, s) {  // every letter of q, in order, inside s; a lower score is a tighter match
  q = q.toLowerCase(); const low = s.toLowerCase(); let i = -1, last = -1, gaps = 0; const at = [];
  for (const ch of q) { i = low.indexOf(ch, i + 1); if (i < 0) return null; if (last >= 0) gaps += i - last - 1; at.push(i); last = i; }
  return {score: gaps + (at[0] || 0), at};
}
const ovItems = () => ovMode === 'module'
  ? D.modules.map(m => ({name: m.name, href: m.href, tag: m.href ? '' : [COUNT[m.name] ? COUNT[m.name]() : '', KEYS[m.name] ? 'g ' + KEYS[m.name] : ''].filter(Boolean).join('  '),
      cur: m.href ? m.href === D.module : m.name === tab}))
  : D.domains.map(d => ({name: d.name, href: \`/domain/\${d.slug}\`, tag: d.entity, cur: d.slug === D.base.split('/').pop()}));
function domRender() {
  const q = $('dom-q').value.trim();
  domHits = ovItems().map(d => ({d, m: fuzzy(q, d.name)})).filter(x => x.m).sort((a, b) => a.m.score - b.m.score);
  domSel = Math.min(domSel, Math.max(domHits.length - 1, 0));
  $('dom-list').innerHTML = domHits.length ? domHits.map(({d, m}, i) => {
    const name = [...d.name].map((ch, k) => m.at.includes(k) ? \`<b class="text-neutral-900">\${esc(ch)}</b>\` : esc(ch)).join('');
    return \`<div class="dom-row flex items-center justify-between gap-4 px-4 h-9 cursor-pointer \${i === domSel ? 'bg-neutral-100' : ''}" data-i="\${i}">
      <span class="text-neutral-600">\${name}\${d.cur ? '<span class="ml-2 text-neutral-400">· atual</span>' : ''}</span>
      <span class="text-neutral-400">\${esc(d.tag)}</span></div>\`;
  }).join('') : \`<p class="px-4 h-9 leading-9 text-neutral-400">nenhum \${ovMode === 'module' ? 'módulo' : 'domínio'}</p>\`;
  $('dom-list').querySelectorAll('.dom-row').forEach(r => { r.onclick = () => { domSel = +r.dataset.i; domGo(); }; r.onmousemove = () => { if (domSel !== +r.dataset.i) { domSel = +r.dataset.i; domRender(); } }; });
}
const domGo = () => {  // an href navigates; a module with none (a tab of this domain) is shown in place
  const h = domHits[domSel]; if (!h) return;
  if (h.d.href) { location.href = h.d.href; return; }
  domClose(); show(h.d.name);
};
const domIsOpen = () => !$('dom').classList.contains('hidden');
function domOpen(mode = 'domain') {
  ovMode = mode; $('dom-q').placeholder = mode === 'module' ? 'módulo…' : 'domínio…';
  $('dom').classList.remove('hidden'); $('dom').classList.add('flex'); $('dom-q').value = ''; domSel = 0; domRender(); $('dom-q').focus();
}
function domClose() { if (Q.get('embed') === 'switcher') return; $('dom').classList.add('hidden'); $('dom').classList.remove('flex'); }
const ovToggle = mode => { if (domIsOpen() && ovMode === mode) domClose(); else domOpen(mode); };
$('dom-open').onclick = () => domOpen('domain');
if ($('mod-open')) $('mod-open').onclick = () => domOpen('module');
$('dom').onclick = e => { if (e.target === $('dom')) domClose(); };
$('dom-q').oninput = () => { domSel = 0; domRender(); };
$('dom-q').onkeydown = e => {
  if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) { domSel = Math.min(domSel + 1, domHits.length - 1); domRender(); e.preventDefault(); }
  else if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) { domSel = Math.max(domSel - 1, 0); domRender(); e.preventDefault(); }
  else if (e.key === 'Enter') { domGo(); e.preventDefault(); }
  else if (e.key === 'Escape') { domClose(); e.preventDefault(); e.stopPropagation(); }
};
document.addEventListener('keydown', e => {
  if (!(e.metaKey || e.ctrlKey)) return;
  const k = e.key.toLowerCase();
  if (k === 'k') { ovToggle('domain'); e.preventDefault(); }
  else if (k === 'p') {
    e.preventDefault();  // never the browser's print panel
    if (e.ctrlKey && !e.metaKey && e.target === $('dom-q')) return;  // inside the finder Ctrl+P is "up"
    if (!Q.get('embed')) ovToggle('module');
  }
}, true);  // capture: a canvas (tldraw) that stops the key in its own handlers must not eat ⌘K and ⌘P
function wireRows(el, ev) {  // a WidgetList row opens its widget: click anywhere on it, or Enter / Space when focused
  el.querySelectorAll('.w-row').forEach(r => {
    const go = () => openWidget(ev || r.dataset.ev, r.dataset.w, ev ? D.base : r.dataset.base);
    r.onclick = go;
    r.onkeydown = k => { if (k.key === 'Enter' || k.key === ' ') { k.preventDefault(); go(); } };
  });
}
function inject(el, h) {
  el.innerHTML = h;
  el.querySelectorAll('script').forEach(o => { const n = document.createElement('script'); n.textContent = o.textContent; o.replaceWith(n); });
  if (window.htmx) htmx.process(el);
}
const MODE = () => Q.get('mode') === 'sim' ? 'sim' : 'real';
function paintMode() {
  document.querySelectorAll('#pop-mode .mode').forEach(m => {
    const on = m.dataset.mode === MODE();
    m.classList.toggle('font-semibold', on);
    m.classList.toggle('bg-neutral-900', on); m.classList.toggle('text-white', on);
    m.classList.toggle('', on); m.classList.toggle('', on);
    m.classList.toggle('text-neutral-500', !on);
  });
  $('pop-body').classList.toggle('sim', MODE() === 'sim');
}
document.querySelectorAll('#pop-mode .mode').forEach(m => m.onclick = () => {
  setQ('mode', m.dataset.mode === 'sim' ? 'sim' : '');
  const id = Q.get('ev'), name = Q.get('w');
  if (id && name) openWidget(id, name);
});
function openWidget(id, name, base = D.base) {
  setQ('w', name); paintMode();
  $('pop-mode').classList.remove('hidden');
  $('pop-name').textContent = name;
  $('pop-sub').textContent = Q.get('e') ? \`\${id} · evento \${Q.get('e').slice(0, 8)}\` : \`\${id} · primeiro evento real do diário\`;
  $('pop-body').innerHTML = '<p class="text-neutral-400">carregando…</p>';
  $('pop').classList.remove('hidden'); $('pop').classList.add('flex');
  frag(\`\${base}/w/\${D.state.id}/\${id}/\${encodeURIComponent(name)}?e=\${base === D.base ? Q.get('e') || '' : ''}&mode=\${MODE()}\`).then(h => {
    inject($('pop-body'), h);
    // a widget generated from a real source (data-real-only: a SKILL.md, the code) has nothing to simulate: no REAL | SIMULADO
    if ($('pop-body').querySelector('[data-real-only]')) { setQ('mode', ''); $('pop-mode').classList.add('hidden'); }
    // a composed WidgetList inside the popup: its abrir opens that widget here (in its own domain)
    wireRows($('pop-body'));
  });
}
function closeWidget() { setQ('mode', ''); setQ('w', ''); $('pop').classList.add('hidden'); $('pop').classList.remove('flex'); }
const popOpen = () => !$('pop').classList.contains('hidden');
$('pop-close').onclick = closeWidget;
$('pop').onclick = e => { if (e.target === $('pop')) closeWidget(); };
function closeSide() { side.id = null; setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('e', ''); setQ('ent', ''); markEntity(null);
  const el = $('ev-side'); if (el) el.classList.add('hidden'); }

// The contextual sidebar: one markup for every view that opens it (a graph node, a module's entity)
const SIDE_HTML = \`<aside id="ev-side" class="hidden w-[min(380px,34vw)] shrink-0 flex flex-col border-l border-neutral-200">
        <div class="shrink-0 flex items-start justify-between gap-3 px-4 pt-3 pb-2">
          <div class="min-w-0"><p id="ev-name" class="font-sans text-base font-semibold text-neutral-900"></p>
            <p id="ev-sub" class="text-neutral-400"></p></div>
          <button id="ev-close" title="Esc" class="shrink-0 px-1.5 text-neutral-400 hover:text-neutral-900">✕</button></div>
        <div id="ev-tabs" class="shrink-0 flex px-2 border-b border-neutral-200"></div>
        <div id="ev-body" class="relative flex-1 min-h-0 overflow-y-auto"></div>
      </aside>\`;

const TABS = {
  // Domain (DDD, Evans 2003) is the first tab and reuses the Model graph and sidebar: one graph, one style.
  'Domain': () => TABS['Model'](),
  // Task Results (fixed, second): the tasks executed for this domain, from the tasks domain's own Tasks widget (composed)
  'Task Results': () => '<div id="task-results" class="h-full overflow-auto px-6 py-5"><p class="text-neutral-400">carregando…</p></div>',
  'Model': () => \`<div class="h-full flex">
      <div id="graph-col" class="flex-1 min-w-0 flex flex-col">
        <div class="flex items-center gap-4 px-4 pt-3 min-w-0">
          <span id="legend" class="flex flex-wrap gap-x-3 gap-y-1 text-sm text-neutral-400 min-w-0"></span>
          <span class="ml-auto shrink-0 cursor-help text-neutral-500" title="Máquina de estados a partir do Human · aresta: comando (transição) · nó: evento (estado alcançado) · cheio: já no diário">?</span></div>
        <div class="relative flex-1 min-h-0"><div id="cy" class="absolute inset-0"></div>
          <button id="centre-human" class="hidden absolute right-3 bottom-3 z-10 px-3 py-1.5 rounded-md text-sm border border-neutral-300 bg-white/90 text-neutral-700 hover:text-neutral-950">◎ Centralizar Human</button></div>
      </div>
      \${SIDE_HTML}</div>\`,
  'Visão': () => {
    if (D.home.length) return \`<div id="home" class="max-w-4xl px-8 py-8"><p class="text-neutral-400">carregando…</p></div>\`;
    const it = items(), done = it.filter(i => isDone(i.state)).length, ps = proposals();
    let g = 'flowchart LR\\n  hoje(["Hoje"])\\n  desejado(["Desejado"])\\n';
    it.forEach((i, n) => {
      const mark = i.state ? (isDone(i.state) ? '✓ ' : '● ') : '';
      g += \`  w\${n}["\${mark}\${i.id}"]\\n  hoje --- w\${n} --> desejado\\n  class w\${n} \${i.state ? (isDone(i.state) ? 'done' : 'open') : 'none'}\\n\`;
    });
    g += '  classDef done stroke-dasharray:3 3,color:#a3a3a3\\n  classDef open stroke-width:2px,font-weight:600\\n  classDef ends font-weight:600,stroke-width:2px\\n  class hoje,desejado ends';
    return \`<div class="max-w-3xl px-8 py-8 font-sans">
      \${label('Hoje')}<p class="mt-2 text-lg leading-8 text-neutral-800">\${esc(D.state.actual)}</p>
      <div class="mt-8">\${label('Desejado')}<p class="mt-2 text-lg leading-8 text-neutral-800">\${esc(D.state.desired)}</p></div>
      <div class="mt-10 grid grid-cols-3 gap-6 border-y border-neutral-200 py-5">
        <div>\${label('Trabalho ligado')}<p class="mt-1 text-2xl font-semibold tabular-nums">\${done} <span class="text-neutral-400 font-normal">de \${it.length}</span></p></div>
        <div>\${label('Observações')}<p class="mt-1 text-2xl font-semibold tabular-nums">\${of('observation').length}</p></div>
        <div>\${label('Propostas')}<p class="mt-1 text-2xl font-semibold tabular-nums">\${ps.length} <span class="text-neutral-400 font-normal">· \${ps.filter(x => x.status === 'completed').length} concluída(s)</span></p></div>
      </div>
      <pre class="mermaid mt-8 !bg-transparent">\${g}</pre></div>\`;
  },
  'Proposed Actions': () => {
    const ps = proposals();
    if (!ps.length) return empty('Nenhuma proposta ainda.');
    return ps.map(({p, steps, last}, n) => row(p,
      \`<span class="w-6 shrink-0 text-neutral-400 tabular-nums">\${n + 1}</span>
       <div class="min-w-0 flex-1 font-sans">
         <p class="text-sm leading-6 text-neutral-900">\${esc(p.value.proposal ?? brief(p.value))}</p>
         <p class="mt-1 text-xs text-neutral-400">\${['proposed', ...steps.map(s => s.event.split('.')[1])].map((s, i, a) =>
            \`<span class="\${i === a.length - 1 ? 'font-semibold text-neutral-700' : ''}">\${PT[s]}</span>\`).join(' → ')}
            · \${esc(p.actor)} · \${when(p.at)}</p>
         \${last && last.value.outcome ? \`<p class="mt-2 text-sm text-neutral-600">\${esc(last.value.outcome)}</p>\` : ''}
       </div>\`)).join('');
  },
  'Observations': () => list(of('observation').slice().reverse(), e =>
    meta(e, \`<span class="w-20 shrink-0 text-neutral-500">\${esc(e.value.source || e.actor)}</span>
             <span class="flex-1 min-w-0 font-sans text-sm text-neutral-800">\${esc(brief(e.value))}</span>
             \${e.event !== 'observation.recorded' ? \`<span class="text-neutral-500">\${e.event.split('.')[1]}</span>\` : ''}\`)),
  'Relationships': () => {
    const it = items();
    if (!it.length) return empty('Nada ligado.');
    return it.map(i => row(i.ev,
      \`<span class="w-5 shrink-0 text-neutral-500">\${i.state ? (isDone(i.state) ? '✓' : '●') : '·'}</span>
       <span class="w-20 shrink-0 font-semibold">\${esc(i.id)}</span>
       <span class="flex-1 min-w-0 truncate font-sans text-sm \${isDone(i.state) ? 'text-neutral-400' : 'text-neutral-800'}">\${esc(i.title)}</span>
       <span class="text-neutral-500">\${esc(i.state || '')}</span>\`)).join('');
  },
  'Management': () => list(of('management'), e =>
    meta(e, \`<span class="w-24 shrink-0 text-neutral-500">\${e.event.split('.')[1]}</span>
             <span class="flex-1 min-w-0 font-sans text-sm text-neutral-800">\${esc(e.value.reason || e.value.title || e.value.actual || brief(e.value))}</span>\`)),
  'Eventos': () => list(E, (e, i) =>
    \`<span class="w-6 shrink-0 text-right text-neutral-400 tabular-nums">\${i + 1}</span>\${meta(e)}
     <span class="w-56 shrink-0 font-semibold text-neutral-700">\${e.event}</span>
     <span class="w-10 shrink-0 text-neutral-500">\${esc(e.actor)}</span>
     <span class="flex-1 min-w-0 truncate text-neutral-500">\${esc(brief(e.value))}</span>\`),
  'Tipos': () => {
    const used = {}; E.forEach(e => used[e.event] = (used[e.event] || 0) + 1);
    return \`<div class="px-4 py-4 grid grid-cols-5 gap-6">\` + Object.entries(M().lifecycle).map(([cat, verbs]) =>
      \`<div>\${label(cat)}<div class="mt-2 space-y-1">\${verbs.map(v => {
        const k = \`\${cat}.\${v}\`;
        return \`<div class="flex justify-between \${used[k] ? 'font-semibold text-neutral-800' : 'text-neutral-400'}"><span>\${v}</span><span>\${used[k] || ''}</span></div>\`;
      }).join('')}</div></div>\`).join('') + \`</div>\`;
  },
};
const COUNT = {'Proposed Actions': () => proposals().length, 'Observations': () => of('observation').length,
  'Relationships': () => items().length,
  'Management': () => of('management').length, 'Eventos': () => E.length};

const GRAPH = t => t === 'Domain' || t === 'Model';  // tabs drawn by drawGraph
const KEYS = {'Domain': 'd', 'Task Results': 'k', 'Model': 'm', 'Visão': 'v', 'Proposed Actions': 'p', 'Observations': 'o', 'Relationships': 'r',
              'Management': 't', 'Eventos': 'e', 'Tipos': 'y'};
// Nerd Font icon per tab (Font Awesome codepoints: sitemap, cubes, eye, lightbulb, search, link, cog, list, tags)
const ICON = {'Domain': '\\uf0e8', 'Task Results': '\\uf00c', 'Model': '\\uf1b3', 'Visão': '\\uf06e', 'Proposed Actions': '\\uf0eb', 'Observations': '\\uf002',
              'Relationships': '\\uf0c1', 'Management': '\\uf013', 'Eventos': '\\uf03a', 'Tipos': '\\uf02c'};
const nf = t => ICON[t] ? \`<i class="nf">\${ICON[t]}</i>\` : '';
const keyed = t => { const k = KEYS[t]; if (!k) return t; const i = t.toLowerCase().indexOf(k);
  return i < 0 ? t : \`\${t.slice(0, i)}<span class="underline underline-offset-4">\${t[i]}</span>\${t.slice(i + 1)}\`; };
// --- a module drawn by one of the project's widgets (MODULE_WIDGETS: the Kanban module): full width, its leading
// title hidden (the status line names it), beside the same contextual sidebar. An element of it with data-entity opens
// that sidebar for its entity (click, Enter, Space): the project's ENTITY_PARTS widgets rendered for it, then its JSON;
// ?ent= keeps it open across a reload. Its goto key is the first free letter of its name.
const MW = D.module_widgets || {};
const isModule = t => Object.prototype.hasOwnProperty.call(MW, t);
Object.keys(MW).forEach(name => {
  TABS[name] = () => \`<div class="h-full flex"><div id="module-view" data-w-host class="flex-1 min-w-0 min-h-0 overflow-auto">
      <p class="px-4 py-3 text-neutral-400">carregando…</p></div>\${SIDE_HTML}</div>\`;
  if (!KEYS[name]) { const used = new Set(Object.values(KEYS)); KEYS[name] = [...name.toLowerCase()].find(c => /[a-z]/.test(c) && !used.has(c)); }
});
function loadModule(name) {
  const [ev, w] = MW[name], box = $('module-view');
  box.onclick = e => { const el = e.target.closest('[data-entity]'); if (el) openEntity(el.dataset.entity); else closeSide(); };
  box.onkeydown = e => { const el = e.target.closest('[data-entity]');
    if (el && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openEntity(el.dataset.entity); } };
  frag(\`\${D.base}/w/\${D.state.id}/\${ev}/\${encodeURIComponent(w)}\`).then(h => {
    if (tab !== name) return;
    inject(box, h);
    if (Q.get('ent')) openEntity(Q.get('ent'));
  });
}
function markEntity(id) {  // the open entity looks selected (the rail's look); a style rule survives the module's own redraws
  let st = $('ent-sel');
  if (!st) { if (!id) return; st = document.createElement('style'); st.id = 'ent-sel'; document.head.appendChild(st); }
  const s = id ? \`#module-view [data-entity="\${CSS.escape(id)}"]\` : '';
  st.textContent = id ? \`\${s}{background:rgb(229 229 229);border-left-color:rgb(23 23 23)}{background:rgb(38 38 38);border-left-color:rgb(245 245 245)}\` : '';
}
function openEntity(id) {
  const el = document.querySelector(\`#module-view [data-entity="\${CSS.escape(id)}"]\`);
  if (!el) { setQ('ent', ''); return; }
  side.id = null; setQ('ev', ''); setQ('ent', id); markEntity(id);
  $('ev-side').classList.remove('hidden');
  $('ev-name').textContent = el.dataset.entityName || id;
  $('ev-sub').textContent = el.dataset.entitySub || '';
  $('ev-tabs').innerHTML = '';
  const parts = [...Object.entries(D.entity_parts || {}), ['JSON', null]], key = p => partKey('entity', p);
  $('ev-body').innerHTML = parts.map(([p]) => partHtml(p, localStorage.getItem(key(p)) !== 'closed')).join('');
  $('ev-body').querySelectorAll('details').forEach(d => d.ontoggle = () =>
    d.open ? localStorage.removeItem(key(d.dataset.part)) : localStorage.setItem(key(d.dataset.part), 'closed'));
  // each part is a project widget for this entity, on the root event (every entity has it); JSON is its events
  parts.forEach(([p, w]) => (w
    ? frag(\`\${D.base}/w/\${encodeURIComponent(id)}/\${M().root}/\${encodeURIComponent(w)}?task=\${encodeURIComponent(id)}\`)
        .then(h => \`<div data-w-host class="px-4 pt-1">\${h}</div>\`)
    : fetch(\`\${D.base}/state.json?task=\${encodeURIComponent(id)}\`).then(r => r.json()).then(d => jsonPre(d.events || d)))
    .then(html => { if (Q.get('ent') !== id) return;
      const body = $('ev-body').querySelector(\`details[data-part="\${CSS.escape(p)}"] .part-body\`); if (body) inject(body, html); }));
}
let tab = Q.get('tab') || (location.hash ? decodeURIComponent(location.hash.slice(1)) : 'Domain');
tab = (D.module_aliases || {})[tab] || tab;  // a module renamed by the project (MODULE_ALIASES): old links still open it
if (!(tab in TABS) || !D.tabs.includes(tab)) tab = 'Domain';
function show(name) {
  if (name !== tab) { setQ('ev', ''); setQ('side', ''); setQ('w', ''); setQ('ent', ''); markEntity(null); side.id = null; }
  tab = name; setQ('tab', name === 'Domain' ? '' : name);
  $('mod-name').textContent = Q.get('embed') === 'toolbar' && Q.get('sim_tab') ? Q.get('sim_tab') : tab;  // SIMULADO: an example module
  const wide = GRAPH(tab) || tab === 'Task Results' || isModule(tab);  // full width: no entity rail, no JSON inspector
  $('rail').style.display = $('side').style.display = wide ? 'none' : '';
  $('main').innerHTML = TABS[tab]();
  $('main').querySelectorAll('.rec').forEach(r => r.onclick = () => select(r.dataset.id));
  if (tab === 'Task Results') {
    const slug = D.base.split('/').pop();
    frag(\`/domain/tasks/w/_/task.executed/Tasks?domain=\${slug}&task=\${Q.get('task') || ''}\`).then(h => inject($('task-results'), h));
  }
  if (tab === 'Visão' && D.home.length)
    frag(\`\${D.base}/w/\${D.state.id}/\${D.home[0]}/\${encodeURIComponent(D.home[1])}\`).then(h => inject($('home'), h));
  else if (tab === 'Visão') mermaid.run({querySelector: '#main .mermaid'});
  if (GRAPH(tab)) { drawGraph(); $('ev-close').onclick = closeSide; }
  if (isModule(tab)) { loadModule(tab); $('ev-close').onclick = closeSide; }
}
function select(id) {
  document.querySelectorAll('.rec').forEach(r => r.classList.toggle('sel', r.dataset.id === id));
  $('inspector').textContent = JSON.stringify(byId[id], null, 2);
}
// Vim-style goto (like \`g t\` in vim / \`g i\` in Gmail): g, then the tab's letter. c toggles the code panel.
let pending = null;
document.addEventListener('keydown', e => {
  if (e.metaKey || e.ctrlKey || e.altKey || /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (pending) {
    clearTimeout(pending); pending = null; $('keyhint').textContent = '';
    const t = Object.keys(KEYS).find(name => KEYS[name] === e.key);
    if (t && t in TABS && D.tabs.includes(t)) { show(t); e.preventDefault(); }
    return;
  }
  if (e.key === 'g') { $('keyhint').textContent = 'g…'; pending = setTimeout(() => { pending = null; $('keyhint').textContent = ''; }, 1200); return; }
  if ((e.key === 'l' || e.key === 'L') && GRAPH(tab) && !popOpen()) { toggleLayout(); e.preventDefault(); return; }
  if (e.key === 'Escape') { popOpen() ? closeWidget() : closeSide(); return; }
  if (popOpen()) return;
});
$('inspector').textContent = JSON.stringify(D.state, null, 2);
if (Q.get('embed') && !['toolbar', 'money'].includes(Q.get('embed'))) $('bar').style.display = 'none';  // ?embed=1: a widget embeds this view, without the status line
show(tab);
if (Q.get('embed')) document.documentElement.dataset.embed = Q.get('embed');
if (Q.get('embed') === 'switcher') domOpen();  // the DomainSwitcher widget: the real switcher, open  // CSS hides what an embed leaves out
if (GRAPH(tab) && Q.get('ev')) {
  const ev = Q.get('ev'), w = Q.get('w');
  openSide(ev);
  if (w) openWidget(ev, w);
}
`;

// The money bar: ticks every second while the clock runs; Start / Pause is explicit.
const MONEY_JS = `// The money bar: spent today in the cost center ticks every second while the clock runs; Start / Pause is explicit.
// The clock stops by itself on Pause, another domain's page (the server ends that one), the page hidden, and 5 min
// idle (the page's own input).
// Never on window blur. Coming back does not restart it. The server is the only writer of the Costs journal.
const $ = id => document.getElementById(id);
const D = JSON.parse($('data').textContent), Q = new URLSearchParams(location.search);
const box = $('money');
const EMB = Q.get('embed') === 'money';  // the CostToolbar widget: it shows the bar and the ▶ works on click, but it never enters, beats or stops by itself
if (box && D.money && (!Q.get('embed') || EMB)) {
  let mine = false, S = D.money, t0 = performance.now(), last = Date.now(), leaving = false, popOpen = false;
  const brl = (v, d = 2) => 'R$ ' + v.toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
  const hm = sec => { const m = Math.floor(sec / 60); return Math.floor(m / 60) + 'h' + String(m % 60).padStart(2, '0'); };
  const units = ['min', 'hora', 'dia'];
  const unit = () => { const u = localStorage.getItem('dc.rate'); return units.includes(u) ? u : 'min'; };
  const rateText = () => ({min: brl(S.rate.minute) + '/min', hora: brl(S.rate.hour) + '/h', dia: brl(S.rate.day) + '/dia'})[unit()];
  const live = () => S.running ? S.elapsed + (performance.now() - t0) / 1000 : 0;
  const spentNow = () => S.closed_money + live() * S.rate_hour_running / 3600;
  const secondsNow = () => S.closed_seconds + live();
  const dim = 'text-neutral-400', mute = 'text-neutral-500', strong = 'text-neutral-800';
  const button = () => \`<span data-act="toggle" tabindex="0" aria-label="\${S.running ? 'pausar' : 'iniciar'}" title="\${S.running ? 'pausar' : 'iniciar'}"
    class="px-1.5 select-none \${strong} hover:text-neutral-500">\${S.running ? '⏸' : '▶'}</span>\`;
  const name = () => \`<span data-act="center" tabindex="0" title="hoje, por centro de custo" class="\${mute} hover:text-neutral-900">\${S.name}</span>\`;
  function draw() {
    const spent = spentNow(), secs = secondsNow();
    if (S.investment) {
      box.innerHTML = \`\${name()}<span class="\${dim}">·</span><span class="tabular-nums font-semibold \${strong}">\${brl(spent)} hoje</span>
        <span data-act="rate" tabindex="0" title="min · hora · dia" class="tabular-nums \${mute} hover:text-neutral-900">\${rateText()}</span>\${button()}\`;
    } else {
      const over = spent > S.budget, pct = Math.min(100, spent / S.budget * 100);
      const eff = secs > 0 ? S.budget / (secs / 3600) : null;
      box.innerHTML = \`\${name()}
        <div class="flex flex-col"><div>
          <span class="tabular-nums font-semibold \${over ? 'over' : strong}">\${brl(spent)}</span>
          <span class="tabular-nums \${dim}">de \${brl(S.budget)}</span>
          \${over && eff ? \`<span class="ml-2 text-[10px]"><span class="over">passou do orçamento</span><span class="\${dim}"> · hoje a \${S.name} pagou \${brl(eff, 0)}/h</span></span>\` : ''}</div>
          <div class="mt-0.5 h-[2px] bg-neutral-200"><div class="h-full \${over ? 'bg-red-600' : S.running ? 'bg-neutral-800' : 'bg-neutral-400'}" style="width:\${pct}%"></div></div></div>
        <span data-act="rate" tabindex="0" title="min · hora · dia" class="tabular-nums \${mute} hover:text-neutral-900">\${rateText()}</span>\${button()}\`;
    }
    if (popOpen) drawPop();
  }
  // the popover: today per cost center and the total (the DayCost numbers); the running stretch counts live
  const pop = document.createElement('div');
  pop.id = 'money-pop';
  pop.className = 'hidden fixed bottom-7 right-0 z-[9999] min-w-[18rem] px-4 py-3 rounded-t-lg border border-neutral-300 bg-white shadow-2xl font-sans text-sm';
  document.body.appendChild(pop);
  function drawPop() {
    const rows = S.days.map(d => d.id === S.center ? {...d, seconds: secondsNow(), cost: spentNow()} : d).filter(d => d.seconds > 0 || d.id === S.center);
    const row = (n, sec, cost, bud) => \`<div class="grid grid-cols-[8rem_3.5rem_6.5rem_auto] gap-2 py-0.5">
      <span class="\${strong}">\${n}</span><span class="tabular-nums \${dim}">\${hm(sec)}</span>
      <span class="tabular-nums text-right font-semibold \${bud && cost > bud ? 'over' : strong}">\${brl(cost)}</span>
      <span class="tabular-nums \${dim}">\${bud ? 'de ' + brl(bud) : 'investido'}</span></div>\`;
    pop.innerHTML = \`<div class="mb-1 text-[11px] uppercase tracking-widest \${mute}">hoje, por centro de custo</div>\` +
      rows.map(d => row(d.name, d.seconds, d.cost, d.budget_day)).join('') +
      \`<div class="mt-1 pt-1 border-t border-neutral-200 grid grid-cols-[8rem_3.5rem_6.5rem_auto] gap-2">
        <span class="\${mute}">total</span><span class="tabular-nums \${dim}">\${hm(rows.reduce((a, d) => a + d.seconds, 0))}</span>
        <span class="tabular-nums text-right font-semibold \${strong}">\${brl(rows.reduce((a, d) => a + d.cost, 0))}</span></div>\`;
  }
  const togglePop = open => { popOpen = open ?? !popOpen; pop.classList.toggle('hidden', !popOpen); if (popOpen) drawPop(); };
  // after a start, a stop or an enter the clock may run somewhere else now: a module that draws money (the Kanban's
  // Quadro) listens for devconsole-money on document and redraws at once
  const post = (path, body = {}) => fetch(\`\${D.base}/time/\${path}\`, {method: 'POST', body: new URLSearchParams(body)})
    .then(r => r.json()).then(s => { if (s && !s.error) { S = s; t0 = performance.now(); draw(); }
      if (path !== 'beat') document.dispatchEvent(new CustomEvent('devconsole-money', {detail: {path, running: !!(s && s.running)}}));
      return s; }).catch(() => {});
  const stop = (by, trim = 0) => { if (!S.running) return; S.closed_money = spentNow(); S.closed_seconds = secondsNow(); S.running = false; draw(); return post('stop', {ended_by: by, trim_seconds: trim}); };
  const start = () => { entered = true; return post('start').then(() => { last = Date.now(); mine = true; }); };
  const auto = () => !EMB || mine;  // an embed stops, beats and enters only for a stretch its own click started
  const act = el => {
    const a = el && el.closest && el.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'rate') { localStorage.setItem('dc.rate', units[(units.indexOf(unit()) + 1) % 3]); draw(); }
    else if (a.dataset.act === 'center') togglePop();
    else if (S.running) stop('pause'); else start();
  };
  box.addEventListener('click', e => act(e.target));
  box.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { act(e.target); e.preventDefault(); } });
  document.addEventListener('click', e => { if (popOpen && !box.contains(e.target) && !pop.contains(e.target)) togglePop(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && popOpen) togglePop(false); });
  let entered = false;  // the first gesture of a person here ends a stretch running in another domain (agents' clicks are not trusted)
  for (const t of ['keydown', 'click', 'scroll', 'pointermove', 'wheel']) addEventListener(t, e => { last = Date.now();
    if (!EMB && !entered && e.isTrusted) { entered = true; post('enter'); } }, {capture: true, passive: true});
  const idleSeconds = () => (Date.now() - last) / 1000;
  addEventListener('pagehide', () => { leaving = true; });  // navigating inside the domain or reloading: the server keeps the stretch
  addEventListener('pageshow', e => { leaving = false; if (e.persisted && auto()) post('beat'); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && entered && !leaving && auto()) stop('hidden'); });  // only a page a person used
  setInterval(() => {
    const idle = idleSeconds();
    if (S.running && auto() && idle > S.idle_minutes * 60) stop('idle', idle);
    else draw();
  }, 1000);
  setInterval(() => { if (S.running && auto()) post('beat'); }, 10000);
  // a journal changed on disk (a tmux focus switch, a card moved): the modules swap their fragment at once (the event
  // first, no round trip), then the bar reads the clock again
  if (!EMB) { new EventSource('/live/stream').onmessage = ev => {
    const kind = ev.data.split(' ')[0];
    if (kind === 'journal') document.dispatchEvent(new CustomEvent('devconsole-journal'));
    if (kind !== 'costs') return;
    document.dispatchEvent(new CustomEvent('devconsole-money', {detail: {path: 'costs'}}));
    const pushMs = Number(ev.data.split(' ')[1]) || 0;
    fetch(\`\${D.base}/time\`, {cache: 'no-store'}).then(r => r.json()).then(s => { if (s && !s.error) { S = s; t0 = performance.now(); draw();
      fetch('/clock/applied', {method: 'POST', keepalive: true, body: JSON.stringify({push_ms: pushMs})}).catch(() => {}); } }).catch(() => {}); }; }
  draw();
  // a page load never stops the clock (an agent's or a background tab's load is not a person leaving)
}
`;

// `g h` goes home on every page that has the switcher.
const GOTO_HOME_JS = `(() => { let g = 0;
  document.addEventListener('keydown', e => {
    const a = document.activeElement;
    if (e.metaKey || e.ctrlKey || e.altKey || (a && (/INPUT|TEXTAREA|SELECT/.test(a.tagName) || a.isContentEditable))) return;
    if (g && e.key === 'h' && Date.now() - g < 1200) { g = 0; e.preventDefault(); if (location.pathname !== '/') location.href = '/'; return; }
    g = e.key === 'g' ? Date.now() : 0;
  }, true);
})();
`;

// The Agents module's script: it renders every text with textContent, never innerHTML.
const AGENTS_JS = `const KINDS_P = ['prompt', 'cross', 'notification', 'other'];
const SHOW = new Set((Q.get('show') || '').split(',').filter(Boolean));  // chips on: cross, notification, other, side
let view = Q.get('view') === 'log' ? 'log' : 'prompts', session = Q.get('session') || '', paused = Q.get('pause') === '1';
let P = [], L = [], SESS = [], live = false;
const NAME = id => (SESS.find(x => x.session === id) || {}).title || id;  // the /rename name when the session has one
const keep = () => {  // all UI state lives in the query string
  const set = (k, v) => v ? Q.set(k, v) : Q.delete(k);
  set('view', view === 'log' ? 'log' : ''); set('session', session); set('show', [...SHOW].join(',')); set('pause', paused ? '1' : '');
  history.replaceState(null, '', location.pathname + (Q.toString() ? '?' + Q : ''));
};
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const hhmm = iso => { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleTimeString('pt-BR', {hour12: false}) + (d.toDateString() === new Date().toDateString() ? '' : ' ' + d.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'})); };
const pass = e => (!session || e.session.startsWith(session)) && (!e.side || SHOW.has('side'))
  && (view === 'log' ? true : e.kind === 'prompt' || SHOW.has(e.kind));
const KCLS = {prompt: 'text-neutral-900 font-semibold', cross: 'text-sky-600', notification: 'text-neutral-400', other: 'text-amber-600', assistant: 'text-neutral-500', tool: 'text-neutral-400'};
function row(e) {
  const r = el('div', 'agrow px-3 py-1 border-b border-neutral-100 cursor-pointer hover:bg-neutral-50');
  r.dataset.id = e.id;
  const head = el('div', 'flex gap-3 whitespace-nowrap');
  head.append(el('span', 'text-neutral-400 shrink-0', hhmm(e.t)), el('span', 'text-neutral-500 shrink-0', NAME(e.session)),
    el('span', 'text-neutral-500 shrink-0 max-w-[14rem] truncate', e.project), el('span', 'shrink-0 ' + (KCLS[e.kind] || ''), e.kind + (e.side ? '*' : '')), ...(e.queued ? [el('span', 'shrink-0 px-1 rounded border border-neutral-400 text-neutral-500', 'queued')] : []));
  const body = el('div', 'agtext text-neutral-800 truncate', e.text + (e.more ? ' …' : ''));
  r.append(head, body);
  r.onclick = async () => {
    const open = r.classList.toggle('open');
    body.classList.toggle('truncate', !open); body.classList.toggle('whitespace-pre-wrap', open); body.classList.toggle('break-words', open);
    if (open && e.more && !e.full) {
      try { const j = await (await fetch('/agents/api/entry?id=' + encodeURIComponent(e.id))).json(); if (j.text != null) { e.full = true; body.textContent = j.text + (j.more ? ' …' : ''); } } catch (_) {}
    }
  };
  return r;
}
const list = () => $('aglist');
function nearBottom() { const l = list(); return l.scrollHeight - l.scrollTop - l.clientHeight < 80; }
function toBottom() { const l = list(); l.scrollTop = l.scrollHeight; }
function render() {
  const l = list(); l.replaceChildren();
  const src = (view === 'log' ? L : P).filter(pass);
  l.append(...src.slice(-1000).map(row));
  if (!src.length) l.append(el('p', 'px-3 py-6 text-neutral-400', 'nada ainda'));
  toBottom(); chrome();
}
function add(e) {  // a pushed entry: append in place; the page is never reloaded
  L.push(e); if (KINDS_P.includes(e.kind)) P.push(e);
  if (!pass(e)) return;
  const l = list(), stick = !paused && nearBottom();
  if (l.querySelector('p')) l.replaceChildren();
  l.append(row(e));
  while (l.childElementCount > 1000) l.firstChild.remove();
  if (stick) toBottom();
  chrome();
}
function chrome() {
  $('v-prompts').className = 'px-2 cursor-pointer ' + (view === 'prompts' ? 'text-neutral-900 underline' : 'text-neutral-400');
  $('v-log').className = 'px-2 cursor-pointer ' + (view === 'log' ? 'text-neutral-900 underline' : 'text-neutral-400');
  for (const c of ['cross', 'notification', 'other', 'side']) {
    const off = view === 'log' && c !== 'side';  // the log shows every kind: these chips filter the Prompts view only
    const b = $('c-' + c); b.className = 'px-2 rounded border ' + (off ? 'opacity-40 pointer-events-none ' : 'cursor-pointer ')
      + (SHOW.has(c) ? 'border-neutral-500 text-neutral-900' : 'border-transparent text-neutral-400');
    b.title = off ? 'filtra só a visão Prompts' : '';
  }
  $('pause').textContent = paused ? '▶ seguir' : '❚❚ pausar'; $('pause').className = 'ml-auto px-2 cursor-pointer whitespace-nowrap ' + (paused ? 'text-neutral-900 underline' : 'text-neutral-400'); $('live').textContent = live ? '● ao vivo' : '○ reconectando';
  $('live').className = 'whitespace-nowrap ' + (live ? 'text-green-600' : 'text-amber-600');
}
function sessions() {
  const s = $('sess'), cur = session; s.replaceChildren(new Option('todas as sessões', ''));
  for (const x of SESS) s.append(new Option(\`\${x.title ? x.title + ' · ' : ''}\${x.session} · \${x.project} · \${hhmm(x.last)}\`, x.session));
  if (cur && !SESS.some(x => x.session === cur)) s.append(new Option(cur, cur));
  s.value = cur;
}
async function load() {
  const q = session ? '&session=' + encodeURIComponent(session) : '', sd = '&side=1';  // side is filtered on screen by its chip
  const [p, g] = await Promise.all([
    fetch('/agents/api/prompts?limit=300&kinds=' + KINDS_P.join(',') + q + sd).then(r => r.json()),
    fetch('/agents/api/log?limit=600' + q + sd).then(r => r.json())]);
  P = p.entries; L = g.entries; SESS = g.sessions; sessions(); render();
  $('warn').textContent = g.mode === 'poll' ? 'watchfiles indisponível: seguindo por consulta a cada 1 s' : '';
  connect(g.last);
}
let es = null;
function connect(after) {
  if (es) es.close();
  es = new EventSource('/agents/events' + (after ? '?after=' + encodeURIComponent(after) : ''));
  es.onopen = () => { live = true; chrome(); };
  es.onerror = () => { live = false; chrome(); };  // EventSource retries by itself, sending Last-Event-ID
  es.onmessage = m => { try { add(JSON.parse(m.data)); } catch (_) {} };
  es.addEventListener('reset', () => load());  // a log file shrank: its old entries are gone, read the lists again
}
$('v-prompts').onclick = () => { view = 'prompts'; keep(); render(); };
$('v-log').onclick = () => { view = 'log'; keep(); render(); };
for (const c of ['cross', 'notification', 'other', 'side']) $('c-' + c).onclick = () => { SHOW.has(c) ? SHOW.delete(c) : SHOW.add(c); keep(); render(); };
$('pause').onclick = () => { paused = !paused; keep(); if (!paused) toBottom(); chrome(); };
for (const id of ['v-prompts', 'v-log', 'c-cross', 'c-notification', 'c-other', 'c-side', 'pause'])  // spans, not buttons: keys by hand
  $(id).onkeydown = ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); $(id).click(); } };
$('sess').onchange = e => { session = e.target.value; keep(); load(); };
setInterval(() => fetch('/agents/api/log?limit=1').then(r => r.json()).then(j => { SESS = j.sessions; sessions(); }).catch(() => {}), 10000);
load();
`;

// The Home: a grid of placements, redrawn from the SSE of the `home` table.
const HOME_JS = `(() => {
  const grid = document.getElementById('home-grid');
  const BASE = '<style>html{color-scheme:light}body{margin:0;padding:12px;font:13px ui-monospace,monospace;background:#ffffff;color:#171717}</style>';
  const sig = w => JSON.stringify([w.source, w.widget_id, w.content, w.task, w.title, w.span, w.height, w.src, w.chrome]);
  const BORDER = 'border border-neutral-200';
  function inject(el, html) {  // a fragment's <script> tags do not run through innerHTML: re-create them
    el.innerHTML = html;
    el.querySelectorAll('script').forEach(o => { const n = document.createElement('script'); n.textContent = o.textContent; o.replaceWith(n); });
  }
  function frame(w) {
    const f = document.createElement('iframe');
    f.className = 'flex-1 min-h-0 w-full border-0 bg-white';
    if (w.source === 'html') { f.sandbox = 'allow-scripts'; f.srcdoc = BASE + w.content; }
    else { const u = w.src || w.content; if (/^(https?:\\/\\/|\\/(?!\\/))/i.test(u)) f.src = u; }  // a row edited by hand may hold anything
    return f;
  }
  function card(w, kids) {
    const c = document.createElement('section');
    c.dataset.id = w.id; c.dataset.sig = sig(w) + kids.map(k => k.id).join();
    c.className = 'flex flex-col min-h-0 overflow-hidden ' + (w.chrome ? 'rounded-md ' + BORDER : '');
    c.style.gridColumn = 'span ' + w.span;
    if (w.height || !kids.length) c.style.height = (w.height || 360) + 'px';
    if (w.chrome) {
      const h = document.createElement('div');
      h.className = 'h-7 shrink-0 px-3 leading-7 text-neutral-500 border-b border-neutral-200 truncate';
      h.textContent = w.title || w.id;
      c.append(h);
    }
    if (!w.chrome) {  // the logo: the widget's own markup, drawn in place
      const b = document.createElement('div');
      b.className = 'flex-1 min-h-0 flex items-center justify-center text-neutral-800';
      fetch(w.src, {headers: {'HX-Request': 'true'}}).then(r => r.text()).then(t => inject(b, t));
      c.append(b);
    } else if (w.src || w.content) c.append(frame(w));
    if (kids.length) {  // composition: the placements inside this one
      const inner = document.createElement('div');
      inner.className = 'flex-1 min-h-0 overflow-auto grid gap-3 p-3';
      inner.style.cssText = 'grid-template-columns:repeat(auto-fill,minmax(280px,1fr));align-content:start';
      kids.forEach(k => inner.append(k.el));
      c.append(inner);
    }
    return c;
  }
  function build(list) {  // top-level first, each with its children (already ordered by position)
    const kids = new Map();
    list.forEach(w => { const p = w.parent_id || ''; (kids.get(p) || kids.set(p, []).get(p)).push(w); });
    const make = w => { const k = (kids.get(w.id) || []).map(x => ({id: x.id, el: make(x)})); return card(w, k); };
    return (kids.get('') || []).map(w => ({id: w.id, sig: sig(w) + JSON.stringify((kids.get(w.id) || []).map(x => sig(x))), w, make: () => make(w)}));
  }
  function draw(list) {
    const solo = list.length === 1 && !list[0].chrome;  // only the logo: centred in the empty canvas
    grid.style.display = list.length ? (solo ? 'flex' : 'grid') : 'none';
    grid.style.alignItems = solo ? 'center' : ''; grid.style.justifyContent = solo ? 'center' : '';
    const keep = new Map([...grid.children].map(el => [el.dataset.id, el]));
    build(list).forEach((t, i) => {
      let el = keep.get(t.w.id);
      if (!el || el.dataset.tree !== t.sig) { const n = t.make(); n.dataset.tree = t.sig; el ? el.replaceWith(n) : grid.append(n); el = n; }
      keep.delete(t.w.id);
      if (grid.children[i] !== el) grid.insertBefore(el, grid.children[i] || null);
      if (solo) { el.style.height = '160px'; el.style.width = '160px'; } else el.style.width = '';
    });
    keep.forEach(el => el.remove());
    window.__home = list.map(w => w.id);
  }
  const es = new EventSource('/api/home/stream');
  es.onmessage = m => draw(JSON.parse(m.data).widgets);
})();
`;

// The Playground's canvas web (tldraw), served at /playground/web/*.
const PG_CANVAS_JS = `// O canvas do tldraw no centro. A página é dona do desenho: carrega o que o
// servidor guardou e manda cada mudança do usuário em POST /playground/api/canvas/diff.

import * as W from './widgets.js'
import { montarPaleta } from './paleta.js'

// as rotas do dev-console (eram /api/... no design-playground)
const API = '/playground/api'

const TLDRAW = 'https://esm.sh/tldraw@3.15.4?deps=react@18.3.1,react-dom@18.3.1'
const REACT = 'https://esm.sh/react@18.3.1'
const REACT_DOM = 'https://esm.sh/react-dom@18.3.1/client?deps=react@18.3.1'

const raiz = document.getElementById('canvas')

// existe desde já, para quem chamar antes de o editor montar
const playground = {
  editor: null,
  selecao: () => (playground.editor ? playground.editor.getSelectedShapeIds() : []),
}
window.playground = playground

function aviso(titulo, detalhe) {
  raiz.replaceChildren()
  const caixa = document.createElement('div')
  caixa.className = 'canvas-aviso'
  caixa.setAttribute('role', 'alert')
  const t = document.createElement('strong')
  t.textContent = titulo
  caixa.append(t)
  if (detalhe) {
    const d = document.createElement('code')
    d.textContent = detalhe
    caixa.append(d)
  }
  raiz.append(caixa)
}

// ---- diff para o servidor ----
// sem setTimeout: aba em segundo plano tem timer atrasado; microtask não
let put = {}
let remove = {}
let agendado = false

function enviar() {
  agendado = false
  const corpo = { put, remove: Object.keys(remove) }
  const vazio = !Object.keys(put).length && !corpo.remove.length
  put = {}
  remove = {}
  if (vazio) return
  const body = JSON.stringify(corpo)
  fetch(\`\${API}/canvas/diff\`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body,
    // o navegador recusa keepalive acima de 64 KB (ex.: colar uma imagem)
    keepalive: body.length < 60_000,
  }).catch((e) => console.warn('[canvas] diff não enviado', e))
}

function agendar() {
  if (agendado) return
  agendado = true
  queueMicrotask(enviar)
}

// ---- a migração: a forma \`widget\` de kit ({kit, peca}) vira instância ({componente}) ----
// \`via-v12/<p>\` e \`tmp/<p>\` → \`via/<p>\` (CONTRATO, "Migração do canvas"); outro kit fica \`<kit>/<p>\`.
const KIT_PARA_PRODUTO = { 'via-v12': 'via', tmp: 'via' }

function ehWidgetDeKit(r) {
  return r?.typeName === 'shape' && r.type === 'widget' && r.props && ('kit' in r.props || 'peca' in r.props)
}

/** As props antigas ({w, h, kit, peca, dados}) nas novas ({w, h, componente, dados}). */
function migrarProps(props) {
  const { kit, peca, componente, ...resto } = props ?? {}
  const produto = KIT_PARA_PRODUTO[kit] ?? kit
  return {
    w: typeof resto.w === 'number' ? resto.w : 393,
    h: typeof resto.h === 'number' ? resto.h : 80,
    componente: typeof componente === 'string' && componente ? componente : (produto && peca ? \`\${produto}/\${peca}\` : String(peca ?? '')),
    dados: typeof resto.dados === 'string' ? resto.dados : JSON.stringify(resto.dados ?? {}),
  }
}

async function carregar(editor) {
  const migrados = []
  try {
    const r = await fetch(\`\${API}/canvas\`)
    if (!r.ok) throw new Error(\`GET \${API}/canvas \${r.status}\`)
    const { registros } = await r.json()
    // o tldraw valida as props no put: as formas antigas são convertidas antes
    const lista = Object.values(registros ?? {}).map((reg) => {
      if (!ehWidgetDeKit(reg)) return reg
      const novo = { ...reg, props: migrarProps(reg.props) }
      migrados.push(novo)
      return novo
    })
    if (lista.length) editor.store.mergeRemoteChanges(() => editor.store.put(lista))
  } catch (e) {
    console.warn('[canvas] não carregou o canvas salvo', e)
  }
  return migrados
}

/** Manda as formas migradas ao servidor pelo diff de sempre (uma vez: depois disso o canvas salvo já é novo). */
function salvarMigrados(editor, migrados) {
  if (!migrados.length) return
  for (const m of migrados) {
    const atual = editor.store.get(m.id)
    if (atual) { put[atual.id] = atual; delete remove[atual.id] }
  }
  console.info(\`[canvas] \${migrados.length} instância(s) migrada(s) de kit para componente\`)
  agendar()
}

function ouvir(editor) {
  editor.store.listen(({ changes }) => {
    for (const r of Object.values(changes.added)) { put[r.id] = r; delete remove[r.id] }
    for (const [, r] of Object.values(changes.updated)) { put[r.id] = r; delete remove[r.id] }
    for (const r of Object.values(changes.removed)) { remove[r.id] = 1; delete put[r.id] }
    agendar()
  }, { source: 'user', scope: 'document' })
}

// ---- a forma "tela": uma prancheta com nome e o HTML num iframe isolado ----
const CABECA = 28

function criarTelaUtil(React, t) {
  const h = React.createElement
  return class TelaUtil extends t.BaseBoxShapeUtil {
    static type = 'tela'
    static props = { w: t.T.number, h: t.T.number, nome: t.T.string, html: t.T.string }
    getDefaultProps() { return { w: 390, h: 844, nome: 'Tela', html: '' } }
    canEdit() { return true }
    canResize() { return true }
    component(shape) {
      const editando = this.editor.getEditingShapeId() === shape.id
      const { w, h: alt, nome, html } = shape.props
      return h(t.HTMLContainer, { className: 'tela', style: { width: w, height: alt, pointerEvents: editando ? 'all' : 'none' } },
        h('div', { className: 'tela-nome', title: nome }, nome),
        h('iframe', {
          className: 'tela-quadro',
          srcDoc: html,
          sandbox: 'allow-scripts',
          title: nome,
          style: { width: w, height: alt - CABECA },
        }))
    }
    indicator(shape) { return h('rect', { width: shape.props.w, height: shape.props.h }) }
  }
}

// ---- a forma "widget": uma instância de um componente, num shadow DOM com o CSS da definição ----
// A altura acompanha o conteúdo: o ResizeObserver mede o corpo da instância e muda o
// \`h\` da forma quando a diferença passa de 1 px (o corpo não depende do \`h\`, então não há laço).
// Um componente não definido mostra o aviso no lugar, com a altura que a forma já tinha.

function ajustarAltura(editor, id, corpo) {
  if (!corpo.isConnected) return
  const alt = Math.ceil(corpo.offsetHeight)
  if (!alt) return // escondida (fora da vista) ou ainda sem layout
  const s = editor.getShape(id)
  if (!s || s.type !== 'widget' || Math.abs(s.props.h - alt) <= 1) return
  editor.run(() => editor.updateShape({ id, type: 'widget', props: { h: alt } }), { history: 'ignore' })
}

/** A largura do frame que contém a forma (o mais próximo, passando por groups); 0 fora de frame. */
function larguraDoFrame(editor, shape) {
  let id = shape?.parentId
  for (let i = 0; id && String(id).startsWith('shape:') && i < 50; i++) {
    const p = editor.getShape(id)
    if (!p) break
    if (p.type === 'frame') return p.props.w
    id = p.parentId
  }
  return 0
}

function criarWidgetUtil(React, t) {
  const h = React.createElement

  function Instancia({ editor, id, componente, dados, larguraFrame, w, alt }) {
    const host = React.useRef(null)
    const corpoAtual = React.useRef(null)
    const [geracao, setGeracao] = React.useState(0)
    const [estado, setEstado] = React.useState(null)
    // a definição mudou (SSE \`componente\`): redesenha
    React.useEffect(() => W.aoMudar((cid) => { if (cid === componente) setGeracao((g) => g + 1) }), [componente])
    // só a escolha da variante importa, não cada pixel da largura do frame
    const desktop = larguraFrame >= W.LARGURA_DESKTOP
    React.useLayoutEffect(() => {
      const el = host.current
      const raiz = el.shadowRoot ?? el.attachShadow({ mode: 'open' })
      let vivo = true
      let obs = null
      W.desenhar(raiz, { componente, dados, larguraFrame }).then((r) => {
        if (!vivo || !r) return
        setEstado(r.def?.estado ?? null)
        corpoAtual.current = r.definido ? r.corpo : null
        if (!r.definido) return
        obs = new ResizeObserver(() => ajustarAltura(editor, id, r.corpo))
        obs.observe(r.corpo)
        ajustarAltura(editor, id, r.corpo)
      })
      return () => { vivo = false; obs?.disconnect() }
    }, [componente, dados, desktop, geracao])
    // alguém mudou o h (redimensionar, \`mudar\`): volta para a altura do conteúdo
    React.useEffect(() => { if (corpoAtual.current) ajustarAltura(editor, id, corpoAtual.current) }, [w, alt])
    return h(React.Fragment, null,
      h('div', { ref: host, className: 'widget-host', 'data-componente': componente }),
      estado === 'rascunho' ? h('span', { className: 'widget-rascunho', 'aria-label': \`\${componente} é um rascunho\` }, 'rascunho') : null)
  }

  const props = { w: t.T.number, h: t.T.number, componente: t.T.string, dados: t.T.string }
  // um registro antigo que chegue por snapshot ou colagem (com o schema) também migra
  let migrations
  if (t.createShapePropsMigrationIds && t.createShapePropsMigrationSequence) {
    const versoes = t.createShapePropsMigrationIds('widget', { Componente: 1 })
    migrations = t.createShapePropsMigrationSequence({
      sequence: [{
        id: versoes.Componente,
        up(p) {
          if (!('kit' in p) && !('peca' in p)) return
          const novo = migrarProps(p)
          for (const k of Object.keys(p)) delete p[k]
          Object.assign(p, novo)
        },
      }],
    })
  }

  return class WidgetUtil extends t.BaseBoxShapeUtil {
    static type = 'widget'
    static props = props
    static migrations = migrations
    getDefaultProps() { return { w: 393, h: 80, componente: '', dados: '{}' } }
    canEdit() { return true }
    canResize() { return true }
    component(shape) {
      const editando = this.editor.getEditingShapeId() === shape.id
      const { w, h: alt, componente, dados } = shape.props
      const larguraFrame = larguraDoFrame(this.editor, shape)
      return h(t.HTMLContainer, { className: 'widget', style: { width: w, height: alt, pointerEvents: editando ? 'all' : 'none' } },
        h(Instancia, { editor: this.editor, id: shape.id, componente, dados, larguraFrame, w, alt }))
    }
    indicator(shape) { return h('rect', { width: shape.props.w, height: shape.props.h }) }
  }
}

// ---- a pilha: um frame com meta.pilha = true empilha os filhos na vertical ----
// Ordena pelo meio de cada filho em y (com tudo empilhado, é a mesma ordem do y),
// põe x = 0, w = largura do frame e y acumulado, sem espaço. Um group entra como um bloco.
// Com meta.lateral = L, são duas pilhas: a lateral (x = 0, w = L) e a principal
// (x = L, w = largura − L), cada filho com meta.coluna. Um filho fora do x da coluna
// dele (arrastado, ou que acabou de entrar) vai para a lateral se o meio cair em x < L.

const ESTICA = new Set(['widget', 'geo', 'frame', 'tela'])

function ehPilha(s) { return s?.type === 'frame' && s.meta?.pilha === true }

/** A largura da coluna lateral de um frame com pilha; 0 sem lateral. */
function larguraLateral(f) {
  const l = f?.meta?.lateral
  return ehPilha(f) && typeof l === 'number' && l > 0 ? l : 0
}

/** O x e a largura de uma coluna num frame com lateral \`L\`. */
function faixa(f, L, coluna) {
  return coluna === 'lateral' ? { x: 0, w: L } : { x: L, w: Math.max(1, f.props.w - L) }
}

/**
 * A coluna de um filho ({s, b} de filhosOrdenados) num frame com lateral \`L\`: a registrada
 * em meta.coluna enquanto ele está no x dela; senão, pelo meio em x.
 */
function colunaDoFilho({ s, b }, L) {
  const registrada = s.meta?.coluna === 'lateral' ? 'lateral' : 'principal'
  const esquerda = s.x + b.minX
  if (Math.abs(esquerda - (registrada === 'lateral' ? 0 : L)) <= 0.5) return registrada
  return esquerda + b.w / 2 < L ? 'lateral' : 'principal'
}

function filhosOrdenados(editor, frameId) {
  return editor.getSortedChildIdsForParent(frameId)
    .map((id) => editor.getShape(id)).filter(Boolean)
    .map((s, i) => {
      const b = editor.getShapeGeometry(s).bounds
      return { s, b, meio: s.y + b.minY + b.h / 2, i }
    })
    .sort((a, b) => a.meio - b.meio || a.s.x - b.s.x || a.i - b.i)
}

// O groupShapes do tldraw, dentro de um frame fora da origem, cria o group com x/y da
// página e os filhos compensados (ex.: group x = 929, filhos x = -929). Na página fica
// certo, mas o \`ler\` mostraria um x sem sentido: põe a origem do group no canto dos filhos.
function normalizarGrupo(editor, g) {
  const b = editor.getShapeGeometry(g).bounds
  if (Math.abs(b.minX) <= 0.5 && Math.abs(b.minY) <= 0.5) return
  const filhos = editor.getSortedChildIdsForParent(g.id).map((id) => editor.getShape(id)).filter(Boolean)
  editor.updateShapes([
    { id: g.id, type: 'group', x: g.x + b.minX, y: g.y + b.minY },
    ...filhos.map((c) => ({ id: c.id, type: c.type, x: c.x - b.minX, y: c.y - b.minY })),
  ])
}

/** Empilha os filhos de um frame com pilha; \`livres\` são os que estão sendo arrastados. */
function empilhar(editor, frameId, livres) {
  const f = editor.getShape(frameId)
  if (!ehPilha(f)) return 0
  for (const id of editor.getSortedChildIdsForParent(f.id)) {
    const g = editor.getShape(id)
    if (g?.type === 'group' && !livres?.has(g.id) && !g.rotation) normalizarGrupo(editor, g)
  }
  const L = larguraLateral(f)
  const ys = { lateral: 0, principal: 0 }
  const parciais = []
  for (const it of filhosOrdenados(editor, f.id)) {
    const { s, b } = it
    const coluna = L ? colunaDoFilho(it, L) : 'principal'
    const { x: x0, w: largura } = L ? faixa(f, L, coluna) : { x: 0, w: f.props.w }
    if (!livres?.has(s.id)) {
      const p = { id: s.id, type: s.type }
      let mudou = false
      const nx = x0 - b.minX
      const ny = ys[coluna] - b.minY
      if (Math.abs(s.x - nx) > 0.5) { p.x = nx; mudou = true }
      if (Math.abs(s.y - ny) > 0.5) { p.y = ny; mudou = true }
      if (ESTICA.has(s.type) && typeof s.props.w === 'number' && Math.abs(s.props.w - largura) > 0.5) {
        p.props = { w: largura }; mudou = true
      }
      if (L && s.meta?.coluna !== coluna) { p.meta = { ...s.meta, coluna }; mudou = true }
      if (mudou) parciais.push(p)
    }
    ys[coluna] += b.h
  }
  if (parciais.length) editor.updateShapes(parciais)
  return parciais.length
}

function empilharTodas(editor) {
  const pilhas = editor.getCurrentPageShapes().filter(ehPilha)
  if (pilhas.length) editor.run(() => { for (const f of pilhas) empilhar(editor, f.id) })
}

// Recalcula quando um filho entra, sai, muda de tamanho ou é arrastado. Só olha os
// frames tocados; o empilhar não muda nada quando já está certo, então não há laço.
function ouvirPilhas(editor) {
  const sujos = new Set()
  let agendado = false
  let soltarPendente = false

  const marcar = (id) => {
    // a forma e os ancestrais (um filho de um group dentro da pilha muda o bloco do group)
    for (let i = 0; id && String(id).startsWith('shape:') && i < 50; i++) {
      sujos.add(id)
      id = editor.getShape(id)?.parentId
    }
  }

  function rodar() {
    agendado = false
    const arrastando = editor.isIn('select.translating')
    const livres = arrastando ? new Set(editor.getSelectedShapeIds()) : null
    if (arrastando) soltarPendente = true
    const ids = [...sujos]
    sujos.clear()
    const pilhas = ids.map((id) => editor.getShape(id)).filter(ehPilha)
    if (pilhas.length) editor.run(() => { for (const f of pilhas) empilhar(editor, f.id, livres) })
  }

  editor.store.listen(({ changes }) => {
    for (const r of Object.values(changes.added)) if (r.typeName === 'shape') marcar(r.id)
    for (const [antes, depois] of Object.values(changes.updated)) {
      if (depois.typeName !== 'shape') continue
      marcar(depois.id)
      if (antes.parentId !== depois.parentId) marcar(antes.parentId)
    }
    for (const r of Object.values(changes.removed)) if (r.typeName === 'shape') marcar(r.parentId)
    if (sujos.size && !agendado) { agendado = true; queueMicrotask(rodar) }
  }, { source: 'user', scope: 'document' })

  // ao soltar um arrasto, quem estava livre entra no lugar
  function soltar() {
    if (editor.isIn('select.translating')) { setTimeout(soltar, 30); return }
    soltarPendente = false
    empilharTodas(editor)
  }
  editor.on('event', (e) => {
    if (soltarPendente && e?.name === 'pointer_up') queueMicrotask(soltar)
  })

  empilharTodas(editor)
}

function dadosDe(s) {
  try { return JSON.parse(s.props.dados || '{}') } catch { return {} }
}

function propsDaInstancia(def, larguraFrame, dados) {
  const { w, h } = W.tamanho(def, larguraFrame)
  // a instância guarda só os próprios dados; os padrões vêm da definição atual
  return { w, h, componente: def.id, dados: JSON.stringify(dados && typeof dados === 'object' ? dados : {}) }
}

/** Cria a instância dentro de um frame (na \`coluna\`, se ele tem lateral); sem \`indice\` vai para o fim. */
function inserirNoFrame(editor, frameId, def, dados, indice, coluna) {
  const f = editor.getShape(frameId)
  const L = larguraLateral(f)
  if (coluna === 'lateral' && !L) throw new Error(\`a tela \${frameId} não tem coluna lateral\`)
  const col = L ? (coluna === 'lateral' ? 'lateral' : 'principal') : null
  const itens = filhosOrdenados(editor, frameId).filter((it) => !col || colunaDoFilho(it, L) === col)
  let borda = 0 // onde a instância entra: o topo do item no índice, ou o fim
  if (itens.length) {
    const i = indice == null ? itens.length : Math.max(0, Math.min(itens.length, Math.trunc(indice)))
    const it = itens[Math.min(i, itens.length - 1)]
    borda = i < itens.length ? it.s.y + it.b.minY : it.s.y + it.b.maxY
  }
  const props = propsDaInstancia(def, f.props.w, dados)
  const id = T.createShapeId()
  editor.run(() => {
    editor.createShape({
      id, type: 'widget', parentId: frameId, x: col ? faixa(f, L, col).x : 0,
      // o meio da instância cai na borda: fica depois do anterior e antes do seguinte
      y: ehPilha(f) ? borda - props.h / 2 : borda,
      props,
      ...(col ? { meta: { coluna: col } } : {}),
    })
    empilhar(editor, frameId)
  })
  return id
}

function pilhaNoPonto(editor, ponto) {
  const pilhas = editor.getCurrentPageShapesSorted().filter(ehPilha).reverse()
  return pilhas.find((f) => {
    const b = editor.getShapePageBounds(f.id)
    return b && ponto.x >= b.minX && ponto.x <= b.maxX && ponto.y >= b.minY && ponto.y <= b.maxY
  })
}

/** A paleta soltou um componente num ponto da página: dentro de um frame com pilha vira filha dele. */
async function soltarComponente(editor, componenteId, ponto) {
  const def = await W.exigirComponente(componenteId)
  editor.markHistoryStoppingPoint('paleta')
  const f = pilhaNoPonto(editor, ponto)
  const id = T.createShapeId()
  if (f) {
    const local = editor.getPointInShapeSpace(f.id, ponto)
    const props = propsDaInstancia(def, f.props.w)
    const L = larguraLateral(f)
    const col = L ? (local.x < L ? 'lateral' : 'principal') : null
    editor.run(() => {
      editor.createShape({
        id, type: 'widget', parentId: f.id, x: col ? faixa(f, L, col).x : 0, y: local.y - props.h / 2, props,
        ...(col ? { meta: { coluna: col } } : {}),
      })
      empilhar(editor, f.id)
    })
  } else {
    const props = propsDaInstancia(def, 0)
    editor.createShape({ id, type: 'widget', x: ponto.x - props.w / 2, y: ponto.y - props.h / 2, props })
  }
  editor.select(id)
  return id
}

/** Clique na paleta: com um frame com pilha selecionado (ou algo dentro dele), entra no fim; senão, no meio da vista. */
async function clicarComponente(editor, componenteId) {
  const sel = editor.getOnlySelectedShape()
  let f = ehPilha(sel) ? sel : null
  let coluna
  if (!f && sel) {
    const pai = editor.getShape(sel.parentId)
    if (ehPilha(pai)) { f = pai; if (larguraLateral(pai) && sel.meta?.coluna === 'lateral') coluna = 'lateral' }
  }
  if (!f) return soltarComponente(editor, componenteId, editor.getViewportPageBounds().center)
  const def = await W.exigirComponente(componenteId)
  editor.markHistoryStoppingPoint('paleta')
  const id = inserirNoFrame(editor, f.id, def, undefined, undefined, coluna)
  editor.select(id)
  return id
}

// ---- as operações que o agente manda pelo MCP (via SSE, repassado pelo eventos.js) ----
let T = null
const fila = []

function texto(editor, s) {
  const r = s.props?.richText
  if (r && T.renderPlaintextFromRichText) { try { return T.renderPlaintextFromRichText(editor, r) } catch {} }
  return s.props?.text ?? undefined
}

function simples(editor, s) {
  const b = editor.getShapePageBounds(s.id)
  const o = { id: s.id, tipo: s.type, x: Math.round(s.x), y: Math.round(s.y), w: Math.round(b?.w ?? 0), h: Math.round(b?.h ?? 0) }
  if (s.type === 'tela') o.nome = s.props.nome
  else if (s.type === 'frame') { o.nome = s.props.name; o.pilha = ehPilha(s); if (larguraLateral(s)) o.lateral = larguraLateral(s) }
  else if (s.type === 'widget') { o.componente = s.props.componente; o.dados = dadosDe(s) }
  else { const t = texto(editor, s); if (t) o.texto = t }
  if (s.props?.color) o.cor = s.props.color
  if (s.props?.geo) o.geo = s.props.geo
  if (s.parentId && !String(s.parentId).startsWith('page:')) {
    o.pai = s.parentId
    if (larguraLateral(editor.getShape(s.parentId))) o.coluna = s.meta?.coluna === 'lateral' ? 'lateral' : 'principal'
  }
  return o
}

function aDireita(editor) {
  const b = editor.getCurrentPageBounds()
  return b ? { x: b.maxX + 80, y: b.minY } : { x: 0, y: 0 }
}

function focar(editor, ids) {
  const anim = { animation: { duration: 300 } }
  if (ids?.length) {
    const b = T.Box.Common(ids.map((id) => editor.getShapePageBounds(id)).filter(Boolean))
    if (b) editor.zoomToBounds(b, { ...anim, inset: 80, targetZoom: 1 })
  } else editor.zoomToFit(anim)
}

function precisa(editor, id, tipo) {
  const s = editor.getShape(id)
  if (!s) throw new Error(\`não achei a forma \${id}\`)
  if (tipo && s.type !== tipo) throw new Error(\`\${id} é \${s.type}, não \${tipo}\`)
  return s
}

async function aplicar(editor, op) {
  switch (op.tipo) {
    case 'tela_criar': {
      const id = T.createShapeId()
      const pos = op.x != null && op.y != null ? { x: op.x, y: op.y } : aDireita(editor)
      editor.createShape({ id, type: 'tela', x: pos.x, y: pos.y, props: { w: op.w, h: op.h, nome: op.nome, html: op.html } })
      editor.select(id)
      focar(editor, [id])
      return { id }
    }
    case 'tela_mudar': {
      const s = precisa(editor, op.id, 'tela')
      const props = {}
      for (const k of ['html', 'nome', 'w', 'h']) if (op[k] != null) props[k] = op[k]
      editor.updateShape({ id: s.id, type: 'tela', props })
      return { id: s.id }
    }
    case 'tela_ler': {
      const s = precisa(editor, op.id, 'tela')
      return { id: s.id, nome: s.props.nome, w: s.props.w, h: s.props.h, html: s.props.html }
    }
    case 'ler': {
      const formas = op.ids?.length ? op.ids.map((id) => editor.getShape(id)).filter(Boolean) : editor.getCurrentPageShapesSorted()
      return { formas: formas.map((s) => simples(editor, s)), selecao: editor.getSelectedShapeIds() }
    }
    case 'criar': {
      const ids = []
      const formas = op.formas.map((f) => {
        const id = T.createShapeId(); ids.push(id)
        const props = {}
        if (f.cor) props.color = f.cor
        if (f.tipo === 'geo') { props.geo = f.geo ?? 'rectangle'; props.w = f.w ?? 200; props.h = f.h ?? 120; if (f.texto) props.richText = T.toRichText(f.texto) }
        if (f.tipo === 'text') { props.richText = T.toRichText(f.texto ?? ''); if (f.w) { props.w = f.w; props.autoSize = false } }
        if (f.tipo === 'note') props.richText = T.toRichText(f.texto ?? '')
        if (f.tipo === 'frame') { props.w = f.w ?? 400; props.h = f.h ?? 300; if (f.texto) props.name = f.texto; delete props.color }
        return { id, type: f.tipo, x: f.x, y: f.y, props }
      })
      editor.createShapes(formas)
      return { ids }
    }
    case 'mudar': {
      const parciais = op.mudancas.map((m) => {
        const s = precisa(editor, m.id)
        const p = { id: s.id, type: s.type }
        if (m.x != null) p.x = m.x
        if (m.y != null) p.y = m.y
        const props = {}
        if (m.w != null && 'w' in s.props) props.w = m.w
        if (m.h != null && 'h' in s.props) props.h = m.h
        if (m.cor && 'color' in s.props) props.color = m.cor
        if (m.texto != null) {
          if ('richText' in s.props) props.richText = T.toRichText(m.texto)
          else if (s.type === 'frame') props.name = m.texto
          else if (s.type === 'tela') props.nome = m.texto
        }
        if (Object.keys(props).length) p.props = props
        return p
      })
      editor.updateShapes(parciais)
      return { ids: parciais.map((p) => p.id) }
    }
    case 'apagar': {
      const ids = op.ids.filter((id) => editor.getShape(id))
      editor.deleteShapes(ids)
      return { apagadas: ids }
    }
    case 'focar':
      focar(editor, op.ids)
      return { ok: true }
    case 'tela_montar': {
      const resolver = (lista) => Promise.all((lista ?? []).map(async (p) => ({ def: await W.exigirComponente(p.componente), dados: p.dados })))
      const pecas = await resolver(op.pecas)
      const lateral = op.lateral ? await resolver(op.lateral.pecas) : null
      const id = T.createShapeId()
      const pos = op.x != null && op.y != null ? { x: op.x, y: op.y } : aDireita(editor)
      const w = op.w ?? 393
      const L = lateral ? Number(op.lateral.largura) : 0
      if (lateral && !(L > 0 && L < w)) throw new Error(\`lateral.largura \${op.lateral.largura} não cabe numa tela de \${w}\`)
      const ids = []
      const idsLateral = []
      editor.run(() => {
        const meta = lateral ? { pilha: true, lateral: L } : { pilha: true }
        editor.createShape({ id, type: 'frame', x: pos.x, y: pos.y, props: { w, h: op.h ?? 852, name: op.nome ?? 'Tela' }, meta })
        // a variante vem da largura do frame (w), inclusive na coluna lateral
        const coluna = (lista, guardar, nome) => {
          let y = 0
          return lista.map(({ def, dados }) => {
            const pid = T.createShapeId(); guardar.push(pid)
            const props = propsDaInstancia(def, w, dados)
            const forma = { id: pid, type: 'widget', parentId: id, x: nome === 'lateral' ? 0 : L, y, props }
            if (lateral) forma.meta = { coluna: nome }
            y += props.h
            return forma
          })
        }
        const formas = [...(lateral ? coluna(lateral, idsLateral, 'lateral') : []), ...coluna(pecas, ids, 'principal')]
        if (formas.length) editor.createShapes(formas)
        empilhar(editor, id)
      })
      editor.select(id)
      focar(editor, [id])
      return lateral ? { id, pecas: ids, lateral: idsLateral } : { id, pecas: ids }
    }
    case 'instancia_inserir': {
      const f = precisa(editor, op.tela, 'frame')
      const def = await W.exigirComponente(op.componente)
      return { id: inserirNoFrame(editor, f.id, def, op.dados, op.indice, op.coluna) }
    }
    case 'instancia_mudar': {
      const s = precisa(editor, op.id, 'widget')
      const dados = { ...dadosDe(s), ...(op.dados ?? {}) }
      editor.updateShape({ id: s.id, type: 'widget', props: { dados: JSON.stringify(dados) } })
      return { id: s.id }
    }
    case 'agrupar': {
      const ids = (op.ids ?? []).filter((id) => editor.getShape(id))
      if (ids.length < 2) throw new Error('agrupar precisa de pelo menos duas formas que existam')
      const gid = T.createShapeId()
      editor.groupShapes(ids, { groupId: gid, select: true })
      const g = editor.getShape(gid)
      if (!g) throw new Error('o tldraw não agrupou essas formas')
      empilhar(editor, g.parentId)
      return { id: gid }
    }
    default:
      throw new Error(\`operação desconhecida: \${op.tipo}\`)
  }
}

async function responder(pedido, corpo) {
  const body = JSON.stringify({ pedido, ...corpo })
  await fetch(\`\${API}/canvas/resposta\`, { method: 'POST', headers: { 'content-type': 'application/json' }, body, keepalive: body.length < 60_000 })
    .catch((e) => console.warn('[canvas] resposta não enviada', e))
}

async function executar({ pedido, op }) {
  const editor = playground.editor
  if (!editor || !T) { fila.push({ pedido, op }); return }
  let r
  try { r = { ok: true, resultado: await aplicar(editor, op) } } catch (e) { r = { ok: false, erro: String(e?.message ?? e) } }
  responder(pedido, r)
}

window.addEventListener('playground:canvas', (ev) => executar(ev.detail))
// uma definição mudou (o eventos.js repassa o SSE \`componente\`): as instâncias daquele id se redesenham
window.addEventListener('playground:componente', (ev) => { W.receber(ev.detail) })

async function montar() {
  let React, createRoot, Tldraw, TelaUtil, WidgetUtil
  try {
    const [r, rd, t] = await Promise.all([import(REACT), import(REACT_DOM), import(TLDRAW)])
    React = r.default
    createRoot = rd.createRoot
    Tldraw = t.Tldraw
    T = t
    TelaUtil = criarTelaUtil(React, t)
    WidgetUtil = criarWidgetUtil(React, t)
  } catch (e) {
    console.error('[canvas] tldraw não carregou', e)
    aviso('O canvas não carregou.', \`Não deu para baixar o tldraw do esm.sh (\${e?.message ?? e}).\`)
    return
  }

  const caixa = document.createElement('div')
  caixa.className = 'canvas-raiz'
  raiz.replaceChildren(caixa)

  async function onMount(editor) {
    playground.editor = editor
    const migrados = await carregar(editor)
    ouvir(editor)
    salvarMigrados(editor, migrados)
    ouvirPilhas(editor)
    montarPaleta({
      raiz,
      componentes: W.componentes,
      aoMudar: W.aoMudar,
      produtoDe: W.produtoDe,
      soltar: (componente, cliente) => soltarComponente(editor, componente, editor.screenToPage(cliente)),
      clicar: (componente) => clicarComponente(editor, componente),
    })
    for (const item of fila.splice(0)) executar(item)
  }

  try {
    createRoot(caixa).render(React.createElement(Tldraw, { onMount, shapeUtils: [TelaUtil, WidgetUtil] }))
  } catch (e) {
    console.error('[canvas] tldraw não montou', e)
    aviso('O canvas não montou.', String(e?.message ?? e))
  }
}

montar()
`;

// (PG_WIDGETS_JS)
const PG_WIDGETS_JS = `// Os componentes: carrega GET /playground/api/componentes (as definições, com versão), prepara
// o CSS de cada definição (com \`:root\` trocado por \`:host\`) como um CSSStyleSheet
// construível, põe as fontes no <head> e desenha uma instância {componente, dados}
// num shadowRoot aplicando os dados pelos slots (CONTRATO.md, "Componentes e instâncias").

export const LARGURA_DESKTOP = 1024 // a instância num frame com largura >= isto usa variantes.desktop
const ESPERA_RELER_MS = 1000 // um id desconhecido só busca a lista de novo depois disto

const defs = new Map()   // id → Componente (a definição atual)
const folhas = new Map() // \`\${id}@\${versao}:\${variante}\` → CSSStyleSheet
const fontesPostas = new Set()
const ouvintes = new Set() // (id) => void, chamados quando uma definição muda
let pedido = null          // a busca da lista em andamento
let buscadaEm = 0          // quando a última busca terminou
let carregou = false

// a base de cada instância dentro do shadow DOM: o corpo é medido para a altura
const BASE = new CSSStyleSheet()
BASE.replaceSync(\`
:host { display: block; }
.w-sprite { position: absolute; width: 0; height: 0; overflow: hidden; }
.w-corpo { display: flow-root; }
.w-erro { box-sizing: border-box; height: 100%; display: flex; align-items: center; padding: 10px 12px; font: 12px/1.4 system-ui, sans-serif; color: #9f1239; background: #fff1f2; border: 1px dashed #fda4af; }
\`)

// as @font-face do componente não valem dentro de um shadow DOM: vão para o documento
const FONTES_DOC = new CSSStyleSheet()
document.adoptedStyleSheets = [...document.adoptedStyleSheets, FONTES_DOC]

/** O produto de um id: o prefixo antes da barra ("via/cartao" → "via"). */
export function produtoDe(id) {
  const i = String(id).indexOf('/')
  return i > 0 ? String(id).slice(0, i) : String(id)
}

/** Avisa quando a definição de um id muda (o retorno desliga). */
export function aoMudar(fn) {
  ouvintes.add(fn)
  return () => ouvintes.delete(fn)
}

function avisar(id) {
  for (const fn of ouvintes) { try { fn(id) } catch (e) { console.warn('[widgets] ouvinte falhou', e) } }
}

function esquecerFolhas(id, manterVersao) {
  for (const chave of folhas.keys()) {
    if (chave.startsWith(\`\${id}@\`) && chave !== \`\${id}@\${manterVersao}:padrao\` && chave !== \`\${id}@\${manterVersao}:desktop\`) folhas.delete(chave)
  }
}

/** Busca a lista no servidor e troca o cache; devolve os ids que mudaram (novos, de versão nova ou sumidos). */
function buscar() {
  if (pedido) return pedido
  pedido = fetch('/playground/api/componentes', { cache: 'no-store' })
    .then((r) => { if (!r.ok) throw new Error(\`GET /playground/api/componentes \${r.status}\`); return r.json() })
    .then((j) => {
      const lista = Array.isArray(j?.componentes) ? j.componentes : []
      const mudados = []
      const vistos = new Set()
      for (const c of lista) {
        if (!c?.id) continue
        vistos.add(c.id)
        const antes = defs.get(c.id)
        if (!antes || antes.versao !== c.versao || JSON.stringify(antes) !== JSON.stringify(c)) {
          mudados.push(c.id)
          esquecerFolhas(c.id, c.versao)
        }
        defs.set(c.id, c)
      }
      for (const id of [...defs.keys()]) if (!vistos.has(id)) { defs.delete(id); esquecerFolhas(id, -1); mudados.push(id) }
      carregou = true
      return mudados
    })
    .finally(() => { pedido = null; buscadaEm = Date.now() })
  return pedido
}

/**
 * As definições, por ordem de id. \`{ recarregar: true }\` busca de novo; \`fresco\` não
 * aproveita uma busca que já estava em andamento (ela pode ter saído antes da mudança).
 */
export async function componentes({ recarregar = false, fresco = false } = {}) {
  if (!carregou || recarregar) {
    const primeira = !carregou
    if (fresco && pedido) await pedido.catch(() => {})
    const mudados = await buscar()
    if (!primeira) for (const id of mudados) avisar(id)
  }
  return [...defs.values()].sort((a, b) => String(a.id).localeCompare(String(b.id)))
}

/**
 * A definição de um id. Se não conhece, busca a lista de novo (uma vez, sem repetir
 * em menos de 1 s: um canvas com dez instâncias de um id indefinido faz uma busca só).
 * Devolve \`null\` quando o componente não está definido.
 */
export async function acharComponente(id) {
  if (!carregou) await componentes()
  if (defs.has(id)) return defs.get(id)
  if (pedido) await pedido.catch(() => {})
  else if (Date.now() - buscadaEm > ESPERA_RELER_MS) await componentes({ recarregar: true })
  return defs.get(id) ?? null
}

/** Como \`acharComponente\`, mas falha quando não existe (as operações do agente). */
export async function exigirComponente(id) {
  const c = await acharComponente(id)
  if (!c) throw new Error(\`componente \${id} não definido\`)
  return c
}

/**
 * O SSE \`componente\` {id, versao}: busca a definição nova (se a do cache for mais velha);
 * quem desenha instâncias daquele id é avisado pelo \`aoMudar\`.
 */
export async function receber({ id, versao } = {}) {
  if (!id) return
  const atual = defs.get(id)
  if (atual && versao != null && atual.versao >= versao) return
  try { await componentes({ recarregar: true, fresco: true }) } catch (e) { console.warn('[widgets] não releu os componentes', e) }
}

/** A variante que a instância usa: \`desktop\` quando o frame dela tem largura >= 1024 e a definição tem a variante. */
export function variante(def, larguraFrame) {
  return larguraFrame >= LARGURA_DESKTOP && def?.variantes?.desktop ? 'desktop' : 'padrao'
}

/** O tamanho natural da instância (o da variante, se ela for usada). */
export function tamanho(def, larguraFrame) {
  const v = variante(def, larguraFrame) === 'desktop' ? def.variantes.desktop : def
  return { w: Number(v.w) || Number(def.w) || 393, h: Number(v.h) || Number(def.h) || 80 }
}

// \`:root\` → \`:host\` (e \`:root[x]\` → \`:host([x])\`); url() relativa passa a valer a partir da página
function adaptarCss(css) {
  return String(css ?? '')
    .replace(/:root((?:\\[[^\\]]*\\])+)/g, ':host($1)')
    .replace(/:root\\b/g, ':host')
    .replace(/url\\(\\s*(['"]?)([^'")]+)\\1\\s*\\)/g, (todo, aspas, alvo) => {
      if (/^(data:|blob:|https?:|\\/|#)/i.test(alvo.trim())) return todo
      return \`url("\${new URL(alvo.trim(), location.href).href}")\`
    })
}

function porFontes(def) {
  for (const href of def.fontes ?? []) {
    const abs = new URL(href, location.href).href
    if (fontesPostas.has(abs)) continue
    fontesPostas.add(abs)
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = abs
    link.dataset.componente = def.id
    document.head.append(link)
  }
}

const fontFacesPostas = new Set()
function levarFontFaces(folha) {
  for (const regra of folha.cssRules) {
    if (regra instanceof CSSFontFaceRule && !fontFacesPostas.has(regra.cssText)) {
      fontFacesPostas.add(regra.cssText)
      try { FONTES_DOC.insertRule(regra.cssText, FONTES_DOC.cssRules.length) } catch {}
    }
  }
}

function folhaDe(def, qual) {
  const chave = \`\${def.id}@\${def.versao}:\${qual}\`
  let f = folhas.get(chave)
  if (!f) {
    const css = qual === 'desktop' ? def.variantes.desktop.css : def.css
    f = new CSSStyleSheet()
    f.replaceSync(adaptarCss(css))
    levarFontFaces(f)
    folhas.set(chave, f)
  }
  return f
}

function comoTexto(v) { return Array.isArray(v) ? v.join(' ') : String(v ?? '') }

/** Aplica os dados pelos slots, como o CONTRATO diz. */
export function aplicarDados(raiz, slots, dados) {
  for (const slot of slots ?? []) {
    if (!slot?.seletor || !(slot.chave in dados)) continue
    const v = dados[slot.chave]
    const como = String(slot.como ?? 'texto')
    if (como === 'lista') {
      const todos = [...raiz.querySelectorAll(slot.seletor)]
      if (!todos.length) continue
      const modelo = todos[0]
      for (const outro of todos.slice(1)) if (outro.parentNode === modelo.parentNode) outro.remove()
      const itens = Array.isArray(v) ? v : [v]
      modelo.replaceWith(...itens.map((item) => {
        const c = modelo.cloneNode(true)
        const texto = String(item ?? '')
        // [data-texto]: o item vai nesses elementos (" | " separa as partes) e o resto do clone (ícones) fica
        const alvos = c.matches?.('[data-texto]') ? [c] : [...c.querySelectorAll('[data-texto]')]
        if (alvos.length) {
          const partes = texto.split(' | ')
          alvos.forEach((el, i) => { el.textContent = partes[i] ?? '' })
        } else c.textContent = texto
        return c
      }))
      continue
    }
    const el = raiz.querySelector(slot.seletor)
    if (!el) continue
    if (como === 'texto') el.textContent = comoTexto(v)
    else if (como === 'html') el.innerHTML = comoTexto(v)
    else if (como.startsWith('attr:')) el.setAttribute(como.slice(5), comoTexto(v))
    else if (como.startsWith('estilo:')) el.style.setProperty(como.slice(7), comoTexto(v))
  }
}

/** Os dados da instância (objeto ou JSON em string) por cima dos padrões da definição. */
export function juntarDados(def, dados) {
  let proprios = dados
  if (typeof dados === 'string') { try { proprios = JSON.parse(dados || '{}') } catch { proprios = {} } }
  return { ...(def?.dados ?? {}), ...(proprios && typeof proprios === 'object' ? proprios : {}) }
}

const pedidos = new WeakMap() // shadowRoot → número do último pedido (o mais novo vence)

/**
 * Preenche o shadowRoot com a instância: a folha da definição (ou da variante desktop),
 * o sprite, o HTML e os dados. Devolve \`{ corpo, def, definido }\`: \`corpo\` (o \`.w-corpo\`)
 * tem a altura natural; \`definido\` é falso quando o componente não existe (o aviso no lugar).
 * Devolve \`null\` se um pedido mais novo passou na frente.
 */
export async function desenhar(raiz, { componente, dados, larguraFrame = 0 }) {
  const meu = (pedidos.get(raiz) ?? 0) + 1
  pedidos.set(raiz, meu)
  const erro = (texto) => {
    raiz.adoptedStyleSheets = [BASE]
    const corpo = document.createElement('div')
    corpo.className = 'w-corpo w-indefinido'
    corpo.style.height = '100%'
    const caixa = document.createElement('div')
    caixa.className = 'w-erro'
    caixa.setAttribute('role', 'note')
    caixa.textContent = texto
    corpo.append(caixa)
    raiz.replaceChildren(corpo)
    return corpo
  }
  try {
    const def = await acharComponente(componente)
    if (pedidos.get(raiz) !== meu) return null
    if (!def) return { corpo: erro(\`componente \${componente || '(sem id)'} não definido\`), def: null, definido: false }
    const qual = variante(def, larguraFrame)
    porFontes(def)
    raiz.adoptedStyleSheets = [BASE, folhaDe(def, qual)]
    const caixaSprite = document.createElement('div')
    caixaSprite.className = 'w-sprite'
    caixaSprite.setAttribute('aria-hidden', 'true')
    caixaSprite.innerHTML = def.sprite ?? ''
    const corpo = document.createElement('div')
    corpo.className = 'w-corpo'
    corpo.dataset.variante = qual
    corpo.innerHTML = (qual === 'desktop' ? def.variantes.desktop.html : null) ?? def.html ?? ''
    aplicarDados(corpo, def.slots, juntarDados(def, dados))
    raiz.replaceChildren(caixaSprite, corpo)
    return { corpo, def, definido: true }
  } catch (e) {
    if (pedidos.get(raiz) !== meu) return null
    return { corpo: erro(\`\${componente}: \${e?.message ?? e}\`), def: null, definido: false }
  }
}
`;

// (PG_PALETA_JS)
const PG_PALETA_JS = `// A paleta: um painel recolhível no canto superior esquerdo do canvas com os
// componentes de /api/componentes, por produto, com o estado. Arrastar um componente
// e soltar no canvas cria uma instância no ponto (dentro de um frame com pilha, vira
// filha dele); clicar a insere no fim do frame selecionado.

export const TIPO_ARRASTO = 'application/x-playground-componente'
const CHAVE_ABERTA = 'playground:paleta-aberta'

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue
    if (k === 'text') e.textContent = v
    else if (k === 'class') e.className = v
    else e.setAttribute(k, v === true ? '' : v)
  }
  e.append(...filhos.filter(Boolean))
  return e
}

/**
 * @param {{ raiz: HTMLElement,
 *   componentes: (o?: {recarregar?: boolean}) => Promise<any[]>,
 *   aoMudar?: (fn: (id: string) => void) => () => void,
 *   produtoDe: (id: string) => string,
 *   soltar: (componente: string, cliente: {x: number, y: number}) => Promise<unknown>,
 *   clicar: (componente: string) => Promise<unknown> }} opcoes
 */
export function montarPaleta({ raiz, componentes, aoMudar, produtoDe, soltar, clicar }) {
  let aberta = localStorage.getItem(CHAVE_ABERTA) !== '0'

  const botao = el('button', { type: 'button', class: 'paleta-cab', 'aria-controls': 'paleta-corpo' },
    el('span', { class: 'paleta-titulo', text: 'Componentes' }),
    el('span', { class: 'paleta-seta', 'aria-hidden': 'true' }))
  const corpo = el('div', { class: 'paleta-corpo', id: 'paleta-corpo' })
  const painel = el('section', { class: 'paleta', 'aria-label': 'Paleta de componentes' }, botao, corpo)
  raiz.append(painel)

  function mostrarEstado() {
    painel.classList.toggle('is-aberta', aberta)
    botao.setAttribute('aria-expanded', String(aberta))
    corpo.hidden = !aberta
  }

  function aviso(texto) {
    corpo.replaceChildren(el('p', { class: 'paleta-aviso', text: texto }))
  }

  function item(c) {
    const rascunho = c.estado === 'rascunho'
    return el('li', {},
      el('button', {
        type: 'button', class: 'paleta-peca', draggable: 'true',
        'data-componente': c.id,
        title: \`\${c.id}: arraste para o canvas, ou clique com uma tela selecionada\`,
      },
        el('span', { class: 'paleta-peca-linha' },
          el('span', { class: 'paleta-peca-nome', text: c.nome ?? c.id }),
          rascunho ? el('span', { class: 'paleta-selo', text: 'rascunho' }) : null),
        c.descricao ? el('span', { class: 'paleta-peca-desc', text: c.descricao }) : null))
  }

  function desenhar(lista) {
    if (!lista.length) { aviso('Nenhum componente definido ainda.'); return }
    const porProduto = new Map()
    for (const c of lista) {
      const p = produtoDe(c.id)
      if (!porProduto.has(p)) porProduto.set(p, [])
      porProduto.get(p).push(c)
    }
    const produtos = [...porProduto.keys()].sort((a, b) => a.localeCompare(b))
    corpo.replaceChildren(...produtos.map((p) => el('div', { class: 'paleta-kit', 'data-produto': p },
      el('h3', { class: 'paleta-kit-nome', text: p }),
      el('ul', { class: 'paleta-pecas', role: 'list' }, ...porProduto.get(p).map(item)))))
  }

  let carregando = null
  let deNovo = false
  function carregar(recarregar) {
    if (carregando) { deNovo = deNovo || recarregar; return carregando }
    if (!corpo.childElementCount) aviso('Carregando…')
    carregando = componentes({ recarregar })
      .then(desenhar)
      .catch((e) => { console.warn('[paleta] componentes não carregaram', e); aviso('Os componentes não carregaram.') })
      .finally(() => {
        carregando = null
        if (deNovo) { deNovo = false; carregar(false) }
      })
    return carregando
  }

  botao.addEventListener('click', () => {
    aberta = !aberta
    localStorage.setItem(CHAVE_ABERTA, aberta ? '1' : '0')
    mostrarEstado()
    if (aberta) carregar(true)
  })

  const peca = (alvo) => alvo instanceof Element ? alvo.closest('.paleta-peca') : null

  corpo.addEventListener('click', (e) => {
    const b = peca(e.target)
    if (b) clicar(b.dataset.componente).catch((err) => console.warn('[paleta] não inseriu', err))
  })

  corpo.addEventListener('dragstart', (e) => {
    const b = peca(e.target)
    if (!b || !e.dataTransfer) return
    e.dataTransfer.setData(TIPO_ARRASTO, JSON.stringify({ componente: b.dataset.componente }))
    e.dataTransfer.effectAllowed = 'copy'
    b.classList.add('is-arrastando')
  })
  corpo.addEventListener('dragend', (e) => peca(e.target)?.classList.remove('is-arrastando'))

  // o soltar no canvas: na captura, antes do tldraw (que trata arquivos e links soltos)
  const nosso = (e) => e.dataTransfer && [...e.dataTransfer.types].includes(TIPO_ARRASTO)
  raiz.addEventListener('dragover', (e) => {
    if (!nosso(e)) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }, true)
  raiz.addEventListener('drop', (e) => {
    if (!nosso(e)) return
    e.preventDefault()
    e.stopPropagation()
    if (painel.contains(e.target)) return
    let item
    try { item = JSON.parse(e.dataTransfer.getData(TIPO_ARRASTO)) } catch { return }
    if (!item?.componente) return
    soltar(item.componente, { x: e.clientX, y: e.clientY }).catch((err) => console.warn('[paleta] não soltou', err))
  }, true)

  // uma definição nova ou que mudou (o SSE \`componente\` já releu a lista): redesenha sem buscar de novo
  aoMudar?.(() => carregar(false))

  mostrarEstado()
  carregar(false)
  return painel
}
`;

// The small SSE relay between the server and canvas.js.
const PG_EVENTOS_JS = `// A linha viva com o servidor (SSE): repassa ao canvas.js as operações do agente (\`canvas\`) e as definições novas
// de componente (\`componente\`) como eventos da window. Faz o papel que o chat.js fazia, sem o chat.
const ESPERA_RECRIAR_MS = 3000 // quando o EventSource fecha de vez (não reconecta sozinho)

function conectar() {
  const fonte = new EventSource('/playground/api/eventos')
  const repassar = (tipo, nome, chave) => fonte.addEventListener(tipo, (ev) => {
    try {
      const d = JSON.parse(ev.data)
      if (d?.[chave]) window.dispatchEvent(new CustomEvent(nome, { detail: d }))
    } catch (e) { console.warn(\`[eventos] \${tipo} ilegível\`, e) }
  })
  repassar('canvas', 'playground:canvas', 'pedido')
  repassar('componente', 'playground:componente', 'id')
  fonte.onerror = () => { if (fonte.readyState === EventSource.CLOSED) setTimeout(conectar, ESPERA_RECRIAR_MS) }
}

conectar()
`;

// (PG_APP_CSS)
const PG_APP_CSS = `/* O canvas do Playground dentro do dev-console: as variáveis e as formas do design-playground, sem o layout
   (a página é do console) e sem o chat. O canvas é claro. */

:root {
  --fundo: #ffffff;
  --superficie: #f7f7f8;
  --borda: #e4e4e7;
  --texto: #18181b;
  --texto-suave: #71717a;
}

#canvas {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  color-scheme: light;
  color: var(--texto);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

/* o tldraw ocupa todo o centro */
#canvas > .canvas-raiz {
  position: absolute;
  inset: 0;
}

/* aviso quando o canvas não carrega */
.canvas-aviso {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 6px;
  padding: 24px;
  text-align: center;
  color: var(--texto-suave);
  background: var(--superficie);
}

.canvas-aviso strong { color: var(--texto); font-weight: 600; }
.canvas-aviso code {
  font: 12px/1.4 ui-monospace, Menlo, monospace;
  max-width: 60ch;
  word-break: break-word;
}

/* a forma "tela" do canvas: prancheta com nome e o HTML num iframe */
.tela {
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #d5d8de;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.08);
}
.tela-nome {
  height: 28px;
  flex: none;
  display: flex;
  align-items: center;
  padding: 0 10px;
  font: 500 12px/1 system-ui, sans-serif;
  color: #3b3f47;
  background: #f4f5f7;
  border-bottom: 1px solid #e3e5e9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tela-quadro { border: 0; display: block; background: #fff; }

/* a forma "widget": uma instância de componente num shadow DOM (o CSS da definição fica lá dentro) */
.widget { overflow: hidden; background: transparent; }
.widget-host { display: block; width: 100%; height: 100%; }
/* a faixa de rascunho fica fora do shadow DOM: o CSS do componente não a alcança */
.widget-rascunho {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 1;
  padding: 2px 8px 3px;
  border-bottom-left-radius: 6px;
  background: #f59e0b;
  color: #451a03;
  font: 600 10px/1.2 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  pointer-events: none;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.12);
}

/* a paleta: os componentes por produto, no canto superior esquerdo do canvas (abaixo do menu do tldraw) */
.paleta {
  position: absolute;
  top: 52px;
  left: 8px;
  z-index: 400;
  width: 248px;
  max-height: calc(100% - 52px - 72px);
  display: flex;
  flex-direction: column;
  background: var(--fundo);
  border: 1px solid var(--borda);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04), 0 4px 16px rgb(0 0 0 / 0.06);
  overflow: hidden;
  font-size: 13px;
}
.paleta-cab {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 34px;
  padding: 0 12px;
  border: 0;
  background: transparent;
  color: var(--texto);
  font: 600 12px/1 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  letter-spacing: 0.01em;
  cursor: pointer;
}
.paleta-cab:hover { background: var(--superficie); }
.paleta-cab:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
.paleta-seta {
  width: 7px;
  height: 7px;
  border-right: 1.5px solid var(--texto-suave);
  border-bottom: 1.5px solid var(--texto-suave);
  transform: translateY(-2px) rotate(45deg);
  transition: transform 120ms ease;
}
.paleta:not(.is-aberta) .paleta-seta { transform: translateY(1px) rotate(-135deg); }
.paleta-corpo {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  border-top: 1px solid var(--borda);
  padding: 4px 0 6px;
}
.paleta-corpo[hidden] { display: none; }
.paleta-aviso { margin: 0; padding: 10px 12px; color: var(--texto-suave); }
.paleta-kit + .paleta-kit { border-top: 1px solid var(--borda); margin-top: 4px; padding-top: 4px; }
.paleta-kit-nome {
  margin: 0;
  padding: 8px 12px 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--texto-suave);
}
.paleta-pecas { list-style: none; margin: 0; padding: 0 4px; }
.paleta-peca {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--texto);
  font: inherit;
  text-align: left;
  cursor: grab;
}
.paleta-peca:hover { background: var(--superficie); }
.paleta-peca:active { cursor: grabbing; }
.paleta-peca:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
.paleta-peca.is-arrastando { opacity: 0.5; }
.paleta-peca-linha { display: flex; align-items: center; gap: 6px; min-width: 0; }
.paleta-peca-nome { font-weight: 500; line-height: 1.3; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.paleta-selo {
  flex: none;
  padding: 1px 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: 0.02em;
}
.paleta-peca-desc { color: var(--texto-suave); font-size: 12px; line-height: 1.35; }
`;

// ------------------------------------------------------------------------------------------------------------------
// The console's one SQLite file: `widgets` (the catalogue of every domain widget) and `home` (what is on the Home).
// `${DEV_CONSOLE_DB:-~/.local/share/dev-console/dev-console.sqlite}`, WAL mode. Keep it OUTSIDE the folders the
// reloader watches.
//  - `widgets`: one row per widget of every loaded project, identity `<domain>/<event>/<Name>` (the URL of the widget,
//    `devc home --widget`). The project host collects them; the server rewrites the table at start and on every
//    project reload, only when something changed.
//  - `home`: one row per placement on the Home, in `position` order; `parent_id` composes (a placement inside another).
//    Seeded with exactly one row, the logo widget. The server is the only writer from code (routes -> show/remove/clear);
//    the owner may edit rows in any SQLite app, and `homeChanges` notices it (fs.watch on the db and its -wal file).
//  - The old append-only journal `${DEV_CONSOLE_HOME_DIR}/events.jsonl` is archive only: read once, when the `home`
//    table is first created, to migrate its placements, and never written or deleted again.
// ------------------------------------------------------------------------------------------------------------------
export const LOGO_ID = "dev-console/domain.updated/Logo"; // the logo is a real widget of the dev-console's own project
const HOME_SOURCES = ["widget", "html", "url"];
const SAFE_URL = /^(https?:\/\/|\/(?!\/))/i; // never javascript:, data: or a protocol-relative URL in a frame

const SCHEMA = `
CREATE TABLE IF NOT EXISTS widgets (
  id TEXT PRIMARY KEY,           -- identidade: <domínio>/<evento>/<Nome>, a mesma da URL /w/<entidade>/<evento>/<Nome>
  domain TEXT NOT NULL, event TEXT NOT NULL, name TEXT NOT NULL,
  kind TEXT NOT NULL,            -- widget | expected
  position INTEGER, function TEXT, module TEXT, file TEXT, line INTEGER,
  fake INTEGER NOT NULL DEFAULT 0, roles TEXT,  -- roles: JSON (home, module:X, entity_part:Y)
  code TEXT, code_sha256 TEXT, project TEXT, exported_at TEXT NOT NULL);`;
const HOME_SCHEMA = `
CREATE TABLE home (
  id TEXT PRIMARY KEY,           -- placement id: what \`devc home show <id>\` uses
  widget_id TEXT,                -- widgets.id when source = widget; null for raw html/url
  source TEXT NOT NULL CHECK (source IN ('widget','html','url')),
  content TEXT,                  -- the html or the url
  task TEXT,                     -- the entity a widget renders (optional)
  title TEXT,
  position INTEGER NOT NULL,     -- order on the grid
  span INTEGER NOT NULL DEFAULT 1,
  height INTEGER,
  parent_id TEXT,                -- composition: a placement inside another
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT);`;
const WCOLS = ["id", "domain", "event", "name", "kind", "position", "function", "module", "file", "line", "fake", "roles", "code",
  "code_sha256", "project"];

export const dbPath = () => resolve(expand(env("DEV_CONSOLE_DB", "~/.local/share/dev-console/dev-console.sqlite")));
const nowIso = () => {
  const d = new Date(), p = (n: number) => String(n).padStart(2, "0");
  const off = -d.getTimezoneOffset(), a = Math.abs(off);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}` +
    `${off >= 0 ? "+" : "-"}${p(Math.floor(a / 60))}${p(a % 60)}`;
};

function connect(): Database {
  const p = dbPath();
  mkdirSync(dirname(p), { recursive: true });
  const db = new Database(p, { create: true });
  db.exec("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000");
  return db;
}
function withDb<T>(fn: (db: Database) => T): T {
  const db = connect();
  try { return fn(db); } finally { db.close(); }
}

export function legacyJournalPath() {
  return join(resolve(expand(env("DEV_CONSOLE_HOME_DIR", "~/.local/share/dev-console/home"))), "events.jsonl");
}
/** The placements the old journal ends with, in the order they were first shown (read only). */
export function legacyWidgets(): any[] {
  const p = legacyJournalPath();
  const cur = new Map<string, any>();
  if (!isFile(p)) return [];
  for (const line of readText(p).split("\n")) {
    let e: any;
    try { e = JSON.parse(line); } catch { continue; }
    const v = e?.value || {};
    if (e.event === "home.widget.shown" && v.id) {
      const w = { ...v, at: e.at, actor: e.actor };
      cur.set(v.id, cur.has(v.id) ? { ...cur.get(v.id), ...w } : w);
    } else if (e.event === "home.widget.removed") cur.delete(v.id);
    else if (e.event === "home.cleared") cur.clear();
  }
  return [...cur.values()];
}

/** Create the tables. The first time `home` exists it gets the logo row, then the placements of the old JSONL journal. */
export function storeInit(): void {
  withDb((db) => {
    db.exec(SCHEMA);
    if (!db.query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='home'").get()) {
      db.exec(HOME_SCHEMA);
      const t = nowIso();
      db.query("INSERT INTO home (id, widget_id, source, title, position, span, height, created_at, updated_at, actor)" +
        " VALUES ('logo', ?, 'widget', 'dev-console', 0, 1, 160, ?, ?, 'system')").run(LOGO_ID, t, t);
      for (const w of legacyWidgets()) upsert(db, fromLegacy(w), w.actor || "agent", w.at);
    }
  });
}

function fromLegacy(w: any): any {
  const body: any = {};
  for (const k of ["id", "title", "span", "height"]) if (w[k]) body[k] = w[k];
  if (w.kind === "widget") { // /domain/<slug>/w/<task|_>/<event>/<Name>[?task=]
    const [path, , ...rest] = String(w.content ?? "").split(/(\?)/);
    const query = rest.join("");
    const parts = path.replace(/^\/+|\/+$/g, "").split("/");
    if (parts.length === 6 && parts[0] === "domain" && parts[2] === "w") {
      const task = query.startsWith("task=") ? decodeURIComponent(query.slice(5)) : null;
      return { ...body, source: "widget", widget_id: [parts[1], parts[4], parts[5]].map(decodeURIComponent).join("/"), task };
    }
    return { ...body, source: "url", content: w.content };
  }
  return { ...body, source: w.kind, content: w.content };
}

function upsert(db: Database, body: any, actor: string, at?: string): any {
  const wid = String(body.id ?? "").trim();
  let source = body.source || body.kind;
  let content = body.content, widgetId = body.widget_id;
  if (source === "widget" && !widgetId && typeof content === "string") { // an older devc sent the widget's route
    const old = fromLegacy({ id: wid, kind: "widget", content });
    source = old.source; widgetId = old.widget_id; content = old.content;
    body = { ...body, task: body.task || old.task };
  }
  if (!wid || !HOME_SOURCES.includes(source)) throw new Error(`need id and source (${HOME_SOURCES.join("|")})`);
  if (source === "widget" && !widgetId) throw new Error("source widget needs widget_id (<domain>/<event>/<Name>)");
  if (source !== "widget" && !(typeof content === "string" && content)) throw new Error(`source ${source} needs content`);
  if (source === "url" && !SAFE_URL.test(content)) throw new Error("url must be http(s):// or a path starting with /");
  const parent = body.parent_id || null;
  if (parent === wid) throw new Error("parent_id cannot be the placement itself");
  const t = at || nowIso();
  const old: any = db.query("SELECT * FROM home WHERE id=?").get(wid);
  let pos: number;
  if (body.position !== undefined && body.position !== null) pos = Math.trunc(Number(body.position));
  else if (old) pos = old.position;
  else pos = (db.query("SELECT COALESCE(MAX(position), -1) + 1 AS n FROM home").get() as any).n;
  const span = body.span || (old ? old.span : 1), height = body.height || (old ? old.height : null);
  db.query(
    "INSERT INTO home (id, widget_id, source, content, task, title, position, span, height, parent_id, created_at, updated_at, actor)" +
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET widget_id=excluded.widget_id, source=excluded.source," +
    " content=excluded.content, task=excluded.task, title=excluded.title, position=excluded.position, span=excluded.span," +
    " height=excluded.height, parent_id=excluded.parent_id, updated_at=excluded.updated_at, actor=excluded.actor",
  ).run(wid, source === "widget" ? widgetId : null, source, source !== "widget" ? content : null, body.task || null,
    String(body.title || wid), pos, Math.trunc(Number(span)), height ? Math.trunc(Number(height)) : null, parent,
    old ? old.created_at : t, t, actor);
  return db.query("SELECT * FROM home WHERE id=?").get(wid);
}

export const homeShow = (body: any, actor = "agent") => withDb((db) => upsert(db, body, actor || "agent"));

/** Delete a placement and, composed inside it, everything below. */
export function homeRemove(wid: string): boolean {
  return withDb((db) => {
    const gone = new Set<string>(), todo = [wid];
    while (todo.length) {
      const cur = todo.pop()!;
      if (gone.has(cur)) continue;
      gone.add(cur);
      for (const r of db.query("SELECT id FROM home WHERE parent_id=?").all(cur) as any[]) todo.push(r.id);
    }
    let n = 0;
    for (const g of gone) n += db.query("DELETE FROM home WHERE id=?").run(g).changes;
    return n > 0;
  });
}

/** Back to the initial state: only the logo. */
export function homeClear(actor = "agent"): void {
  withDb((db) => {
    const t = nowIso();
    db.exec("DELETE FROM home");
    db.query("INSERT INTO home (id, widget_id, source, title, position, span, height, created_at, updated_at, actor)" +
      " VALUES ('logo', ?, 'widget', 'dev-console', 0, 1, 160, ?, ?, ?)").run(LOGO_ID, t, t, actor || "system");
  });
}

/** The route a widget placement draws: /domain/<slug>/w/<task|_>/<event>/<Name>. */
function srcOf(row: any): string | null {
  const parts = String(row.widget_id || "").split("/");
  if (row.source !== "widget" || parts.length !== 3) return null;
  const q = (s: string) => encodeURIComponent(s);
  const task = row.task || "";
  return `/domain/${q(parts[0])}/w/${q(task || "_")}/${q(parts[1])}/${q(parts[2])}` + (task ? `?task=${q(task)}` : "");
}

/** The placements in grid order. A row edited by hand may point at a parent that is gone or loop: it falls back to the top. */
export function homeList(): any[] {
  const rows: any[] = withDb((db) => db.query("SELECT * FROM home ORDER BY position, rowid").all() as any[]);
  const ids = new Set(rows.map((r) => r.id)), by = new Map(rows.map((r) => [r.id, r]));
  for (const r of rows) {
    const seen = new Set([r.id]);
    let p = r.parent_id;
    while (p) {
      if (!ids.has(p) || seen.has(p)) { r.parent_id = null; break; }
      seen.add(p);
      p = by.get(p).parent_id;
    }
    r.span = Math.max(1, Math.min(3, Number(r.span || 1)));
    r.src = srcOf(r);
    r.chrome = r.widget_id !== LOGO_ID;
  }
  return rows;
}

const sortKeys = (v: any): any => Array.isArray(v) ? v.map(sortKeys)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])])) : v;
export const homeSnapshot = () => JSON.stringify({ widgets: homeList().map(sortKeys) });

/** Make `widgets` mirror the loaded projects. Writes only when something differs; true when it did. */
export function syncWidgets(rows: any[]): boolean {
  return withDb((db) => {
    db.exec(SCHEMA);
    const key = (r: any) => JSON.stringify(WCOLS.map((c) => r[c] ?? null));
    const have = new Map((db.query(`SELECT ${WCOLS.join(",")} FROM widgets`).all() as any[]).map((r) => [r.id, key(r)]));
    const want = new Map(rows.map((r) => [r.id, key(r)]));
    if (have.size === want.size && [...want].every(([k, v]) => have.get(k) === v)) return false;
    const t = nowIso();
    db.transaction(() => {
      db.exec("DELETE FROM widgets");
      const ins = db.query(`INSERT INTO widgets (${WCOLS.join(",")}, exported_at) VALUES (${WCOLS.map(() => "?").join(",")}, ?)`);
      for (const r of rows) ins.run(...WCOLS.map((c) => r[c] ?? null), t);
    })();
    return true;
  });
}

/** The Home as JSON every time it differs: once at the start, then after any write to the db file or its -wal, whoever
 *  made it (a route, or the owner in a SQLite app). fs.watch = FSEvents; the interval only re-checks (safety net). */
export function homeChanges(onSnap: (snap: string) => void): () => void {
  const name = basename(dbPath());
  let last = homeSnapshot();
  onSnap(last);
  let timer: ReturnType<typeof setTimeout> | null = null;
  const check = () => {
    timer = null;
    try { const cur = homeSnapshot(); if (cur !== last) { last = cur; onSnap(cur); } } catch { /* the db is mid-write: the next event retries */ }
  };
  let w: FSWatcher | null = null;
  try {
    w = fsWatch(dirname(dbPath()), (_ev, file) => {
      if (file && !String(file).startsWith(name)) return;
      if (!timer) timer = setTimeout(check, 30);
    });
  } catch { /* no watcher: the safety net still runs */ }
  const net = setInterval(check, 5000);
  return () => { w?.close(); clearInterval(net); if (timer) clearTimeout(timer); };
}

// ------------------------------------------------------------------------------------------------------------------
// The domain module: the domain-model skill's dm_* tables (same SQLite) drawn as Mermaid, live. Read only.
//   /model                 the modeled domains
//   /model/<slug>          the map: at most MAX entities, edges = dm_relation
//   /model/<slug>.mmd      the Mermaid text plus a version; the page polls it and redraws only when the rows change
// The schema lives in skills/domain-model/scripts/models.py. DM_DB overrides the path.
// ------------------------------------------------------------------------------------------------------------------
const MODEL_MAX = 9;
const dmPath = () => env("DM_DB") || join(HOME, ".local/share/dev-console/dev-console.sqlite");
function dmRows(sql: string, ...args: any[]): any[] {
  let db: Database;
  try { db = new Database(dmPath(), { readonly: true }); } catch { return []; }
  try { return db.query(sql).all(...args) as any[]; } catch { return []; } // no dm_* tables yet
  finally { db.close(); }
}
const dmDomains = () => dmRows("select slug, name, purpose, status from dm_domain order by slug");
const dmId = (name: string) => "n_" + name.replace(/\W/g, "_");
const dmLabel = (s: string) => (s || "").replace(/"/g, "'");
const MODEL_TITLES: Record<string, string> = { domain: "Domínio", architecture: "Arquitetura" };
const SHAPES: Record<string, [string, string]> = { value: ['(["', '"])'], aggregate: ['[["', '"]]'], store: ['[("', '")]'], actor: ['(("', '"))'],
  service: ['[/"', '"/]'], ui: ['("', '")'] };

export function modelDiagrams(slug: string): string[] {
  const ds = dmRows('select distinct diagram from "01_overview_diagram" where domain=?', slug).map((r) => r.diagram as string);
  ds.sort((a, b) => (a !== "domain" ? 1 : 0) - (b !== "domain" ? 1 : 0) || (a < b ? -1 : a > b ? 1 : 0));
  return ds.length ? ds : ["domain"];
}
/** One picture of phase 01 (≤ MAX nodes): the domain's entities, or the architecture's parts, and how they connect. */
export function modelMermaid(slug: string, diagram = "domain"): string {
  const phase = dmRows('select * from "01_overview_diagram" where domain=? and diagram=? order by pos', slug, diagram);
  let ents: any[], rels: any[];
  if (phase.length) { // phase 01 is the curated picture: draw it as written
    ents = phase.filter((r) => r.row === "node").map((r) => ({ name: r.item, kind: r.kind || "entity", definition: r.note, status: r.status }));
    rels = phase.filter((r) => r.row === "edge").map((r) => ({ src: r.item, verb: r.verb, dst: r.target, cardinality: r.cardinality }));
  } else if (diagram !== "domain") return 'flowchart LR\n  empty["diagrama vazio"]';
  else { // no phase 01 yet: derive it from dm_entity + dm_relation
    ents = dmRows("select name, kind, definition, status from dm_entity where domain=?", slug);
    rels = dmRows("select src, verb, dst, cardinality from dm_relation where domain=?", slug);
  }
  if (!ents.length) return 'flowchart LR\n  empty["sem entidades ainda"]';
  const degree: Record<string, number> = Object.fromEntries(ents.map((e) => [e.name, 0]));
  for (const r of rels) for (const k of [r.src, r.dst]) if (k in degree) degree[k]++;
  const rank: Record<string, number> = { aggregate: 0, entity: 1, value: 2 };
  const keep = phase.length ? ents.slice(0, MODEL_MAX)
    : [...ents].sort((a, b) => (rank[a.kind] ?? 3) - (rank[b.kind] ?? 3) || degree[b.name] - degree[a.name] || (a.name < b.name ? -1 : 1)).slice(0, MODEL_MAX);
  const names = new Set(keep.map((e) => e.name));
  const out = ["flowchart LR"];
  for (const e of keep) {
    const shape = SHAPES[e.kind] || ['["', '"]'];
    out.push(`  ${dmId(e.name)}${shape[0]}<b>${dmLabel(e.name)}</b><br/><small>${e.kind}</small>${shape[1]}`);
    out.push(`  class ${dmId(e.name)} ${e.kind}`);
    if (e.status === "draft") out.push(`  class ${dmId(e.name)} draft`);
  }
  for (const r of rels) {
    if (names.has(r.src) && names.has(r.dst)) {
      const lab = dmLabel(r.verb) + (r.cardinality ? ` ${r.cardinality}` : "");
      out.push(`  ${dmId(r.src)} -- "${lab}" --> ${dmId(r.dst)}`);
    }
  }
  const hidden = ents.length - keep.length;
  if (hidden > 0) out.push(`  more["+${hidden} entidades fora do mapa"]:::value`);
  out.push(
    "  classDef aggregate fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#111",
    "  classDef entity fill:#dbeafe,stroke:#1d4ed8,color:#111",
    "  classDef value fill:#f3f4f6,stroke:#6b7280,color:#111",
    "  classDef actor fill:#fce7f3,stroke:#be185d,color:#111",
    "  classDef ui fill:#dcfce7,stroke:#15803d,color:#111",
    "  classDef service fill:#e0e7ff,stroke:#4338ca,color:#111",
    "  classDef code fill:#dbeafe,stroke:#1d4ed8,color:#111",
    "  classDef store fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#111",
    "  classDef draft stroke-dasharray:5 4");
  return out.join("\n");
}
const modelVersion = (text: string) => createHash("sha1").update(text).digest("hex").slice(0, 12);

const MODEL_PAGE = (title: string, name: string, purpose: string, src: string) => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title><link rel="icon" href="data:,"><style>
:root{color-scheme:light;--bg:#fafaf9;--fg:#1c1917;--mute:#78716c}
body{margin:0;padding:16px 24px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
h1{font-size:20px;margin:0} p{color:var(--mute);margin:4px 0 16px} h2{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:24px 0 4px} .d svg{max-width:100%;height:auto} .d .node .nodeLabel,.d .node .nodeLabel *{color:#111!important;fill:#111!important}
#v{font:12px ui-monospace,monospace;color:var(--mute)} a{color:inherit}
</style></head><body>
<h1>${name} <span id="v"></span></h1><p>${purpose}</p><div id="all"></div>
<p>tracejado = draft, contínuo = real · máx. ${MODEL_MAX} itens por diagrama</p>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad:false, securityLevel:'loose', theme:'default', flowchart:{htmlLabels:true}});
let cur = '', n = 0;
async function tick(){
  try {
    const r = await fetch('${src}', {cache:'no-store'}); const j = await r.json();
    if (j.version !== cur) {
      cur = j.version; let html = '';
      for (const d of j.diagrams) { const {svg} = await mermaid.render('g' + (n++), d.mermaid);
        html += \`<h2>\${d.title}</h2><div class="d">\${svg}</div>\`; }
      document.getElementById('all').innerHTML = html; document.getElementById('v').textContent = j.version;
    }
  } catch (e) { console.log('[model]', e); }
}
tick(); setInterval(tick, 1500);
</script></body></html>`;

// ------------------------------------------------------------------------------------------------------------------
// The Agents module: what the owner typed to the agents, and the agents' session logs, in real time.
// Three parts:
//  - a SOURCE (discovery + a line normalizer): Claude Code today; pi (~/.pi/agent/sessions) and Hermes
//    (~/.hermes/profiles/*/sessions) are added by writing another object with the same three methods and listing it in SOURCES;
//  - the HUB: one tailer for every client. The trigger is an EVENT: fs.watch (FSEvents on macOS) says which .jsonl
//    changed and the hub reads it from its stored byte offset. A safety net rescans the roots and checks every file
//    every ~5 s. If the watcher cannot start the hub polls every ~1 s instead and says so (`mode` = "poll", one warning
//    line on the page). Two in-memory rings. Nothing is written to disk and no entry text is ever printed or logged:
//    these logs hold the owner's private prompts;
//  - the page script (AGENTS_JS), which renders every text with textContent, never innerHTML.
// Entry (normalized): {id, t (ISO), session (short), project, kind, text (short), more (bool), side (bool), queued}; `id`
// is `<file-key>:<byte offset of the line>`, so a client can resume after a reload (SSE Last-Event-ID).
// kind: prompt | cross | notification | other | assistant | tool.
// ------------------------------------------------------------------------------------------------------------------
export const ENV_DIRS = "DEV_CONSOLE_AGENTS_DIRS";
export const MAX_LINE = 1_000_000; // above this a line is an api-request-blob: skipped, never parsed
export const SHORT = 600; // the text a list row carries; the whole text comes from /agents/api/entry
const FULL = 50_000; // cap of the whole text of one entry
export const PROMPT_KINDS = ["prompt", "cross", "notification", "other"]; // what the Prompts view may show
const BACKFILL_FILES = () => Number(env("DEV_CONSOLE_AGENTS_BACKFILL_FILES") || 150); // newest files the backfill may read
const DEDUPE_WINDOW = 120; // seconds: the same text of the same session within this window is one entry
const DEDUPE_CHARS = 200;
const WANT_PROMPTS = 200, WANT_LOG = 500; // the backfill reads the tail of the newest files until it has about this many
const RING_PROMPTS = 2000, RING_LOG = 5000;
const TICK = 1000, RESCAN = 5000, KEEPALIVE = 15000;
const READ_CAP = 4_000_000; // bytes read from one file per tick (a bigger burst continues on the next tick)

export const isoFromTs = (ts: number) => new Date(ts * 1000).toISOString();
function clip(s: string, n: number): [string, boolean] {
  if (s.length <= n) return [s, false];
  let cut = s.slice(0, n);
  const last = cut.charCodeAt(cut.length - 1);
  if (last >= 0xd800 && last <= 0xdbff) cut = cut.slice(0, -1); // never half a surrogate pair
  return [cut, true];
}
function blocksText(content: any[]): string {
  const out: string[] = [];
  for (const b of content) {
    if (b && typeof b === "object" && b.type === "text" && typeof b.text === "string") out.push(b.text);
    else if (b && typeof b === "object") out.push(`[${b.type ?? "block"}]`);
  }
  return out.join("\n");
}
// What a tool call is about, beside its name: a log row that says only "Bash" tells nothing about the work.
const TOOL_ARG: Record<string, string> = { Bash: "command", Read: "file_path", Edit: "file_path", Write: "file_path", NotebookEdit: "notebook_path",
  Grep: "pattern", Glob: "pattern", Agent: "description", Skill: "skill", SendMessage: "to", WebFetch: "url", WebSearch: "query", Monitor: "description" };
/** `Name: detail` for one tool_use block; a path keeps only its last two parts, a command its first line. */
function toolLabel(b: any): string {
  const name = String(b.name ?? "tool");
  const inp = b.input && typeof b.input === "object" ? b.input : {};
  let arg = inp[TOOL_ARG[name] ?? ""];
  if (typeof arg !== "string" || !arg.trim()) return name;
  arg = arg.trim().split(/\r?\n/)[0];
  if ((TOOL_ARG[name] ?? "").endsWith("path")) arg = arg.replace(/\/+$/, "").split("/").slice(-2).join("/");
  return `${name}: ${arg.slice(0, 120)}`;
}

export type FileState = {
  path: string; key: string; source: string; session: string; project: string; sideFile: boolean;
  offset: number; seenSize: number; seenMtime: number; resync: boolean; gone: boolean; mtime: number; title: string;
};

function peerText(origin: any, text: string): string {
  const who = ["name", "from"].map((k) => origin[k]).find((v) => typeof v === "string") || "";
  return (who ? `${who}: ` : "") + (typeof origin.body === "string" ? origin.body : text);
}
/** The allow-list: a `prompt` is exactly origin.kind == "human" with promptSource "typed", or "queued" (typed while the
 *  agent was busy: still the person's own prompt, marked `queued`). peer and task-notification have their own kinds;
 *  anything unknown (a human without promptSource included) is `other`, never `prompt`. */
function userKind(d: any, content: any): [string | null, string, boolean] {
  const origin = d.origin && typeof d.origin === "object" ? d.origin : null;
  const okind = origin?.kind;
  let text: string;
  if (typeof content === "string") text = content;
  else if (Array.isArray(content)) {
    if (content.some((b) => b && typeof b === "object" && b.type === "tool_result")) return [null, "", false]; // a tool's answer: noise
    text = blocksText(content);
  } else return [null, "", false];
  if (okind === "human" && (d.promptSource === "typed" || d.promptSource === "queued")) return ["prompt", text, d.promptSource === "queued"];
  if (okind === "peer") return ["cross", peerText(origin, text), false];
  if (okind === "task-notification") return ["notification", text, false];
  return ["other", text, false];
}
/** A message that arrived while the agent was busy is logged as an ATTACHMENT, not as a user line:
 *  {"type":"attachment","attachment":{"type":"queued_command","commandMode":"prompt","origin":{"kind":...},"prompt":...}}.
 *  origin human -> prompt (queued), peer -> cross, task-notification -> notification, any other origin -> other.
 *  A missing or malformed prompt is dropped (null), never an error. */
function queuedKind(att: any): [string | null, string, boolean] {
  if (!att || typeof att !== "object" || att.type !== "queued_command" || att.commandMode !== "prompt") return [null, "", false];
  const raw = att.prompt;
  let text: string;
  if (typeof raw === "string") text = raw;
  else if (Array.isArray(raw)) text = blocksText(raw);
  else return [null, "", false];
  const origin = att.origin && typeof att.origin === "object" ? att.origin : {};
  if (origin.kind === "human") return ["prompt", text, true];
  if (origin.kind === "peer") return ["cross", peerText(origin, text), false];
  if (origin.kind === "task-notification") return ["notification", text, false];
  return ["other", text, false];
}

/** Claude Code: ~/.claude/projects/<project-dir>/<session-id>.jsonl (one JSON object per line). */
export const ClaudeSource = {
  name: "claude",
  discover(roots: string[]): string[] {
    const out: string[] = [];
    for (const root of roots) {
      try {
        for (const proj of readdirSync(root, { withFileTypes: true })) {
          if (!proj.isDirectory()) continue;
          for (const f of readdirSync(join(root, proj.name), { withFileTypes: true }))
            if (f.name.endsWith(".jsonl") && f.isFile()) out.push(join(root, proj.name, f.name));
        }
      } catch { continue; }
    }
    return out;
  },
  describe(path: string): [string, string, boolean] {
    const stem = basename(path).replace(/\.jsonl$/, "");
    const side = stem.startsWith("agent-");
    return [side ? "ag:" + stem.slice(6, 12) : stem.slice(0, 8), basename(dirname(path)), side];
  },
  /** One log line -> an entry, or null (noise, a garbled line, a line above MAX_LINE). Never throws. */
  normalize(raw: Buffer, offset: number, fs: FileState, full = false): any | null {
    if (raw.length > MAX_LINE) return null;
    let d: any;
    try { d = JSON.parse(raw.toString("utf8")); } catch { return null; }
    if (!d || typeof d !== "object" || Array.isArray(d)) return null;
    const typ = d.type;
    if (typ === "custom-title" || typ === "agent-name") { // /rename: the name a person knows the session by
      const name = typ === "custom-title" ? d.customTitle : d.agentName;
      if (typeof name === "string" && name.trim() && (typ === "custom-title" || !fs.title)) fs.title = name.trim().slice(0, 60);
      return null;
    }
    if (typeof d.cwd === "string" && d.cwd) fs.project = d.cwd.replace(/\/+$/, "").split("/").pop() || d.cwd;
    const msg = d.message && typeof d.message === "object" ? d.message : {};
    const content = msg.content;
    const cap = full ? FULL : SHORT;
    let kind: string | null, text: string, queued: boolean;
    if (typ === "user") {
      [kind, text, queued] = userKind(d, content);
      if (kind === null) return null;
    } else if (typ === "attachment") {
      [kind, text, queued] = queuedKind(d.attachment);
      if (kind === null) return null;
    } else if (typ === "assistant" && Array.isArray(content)) {
      queued = false;
      const texts = content.filter((b: any) => b && typeof b === "object" && b.type === "text" && typeof b.text === "string").map((b: any) => b.text);
      const tools = content.filter((b: any) => b && typeof b === "object" && b.type === "tool_use").map(toolLabel);
      if (texts.length) { kind = "assistant"; text = texts.join("\n"); }
      else if (tools.length) { kind = "tool"; text = tools.join(", "); }
      else return null;
    } else return null;
    const [clipped, more] = clip(text, cap);
    let ts = d.timestamp;
    if (typ === "attachment" && typeof ts !== "string" && d.attachment && typeof d.attachment === "object") ts = d.attachment.timestamp;
    return { id: `${fs.key}:${offset}`, t: typeof ts === "string" ? ts : isoFromTs(fs.mtime || Date.now() / 1000), session: fs.session,
      project: fs.project, kind, text: clipped, more, side: !!d.isSidechain || fs.sideFile, queued };
  },
};
export const SOURCES: Record<string, typeof ClaudeSource> = { claude: ClaudeSource }; // pi and Hermes: one object each, added here

/** The configured roots, deduplicated by realpath (~/.claude-mukutu/projects is a symlink to ~/.claude/projects). */
export function rootsFromEnv(): string[] {
  const raw = env(ENV_DIRS) || join(HOME, ".claude", "projects");
  const seen = new Set<string>(), out: string[] = [];
  for (const p of raw.split(delimiter)) {
    if (!p) continue;
    let r: string;
    try { r = realpathSync(expand(p)); } catch { continue; }
    if (!seen.has(r) && isDir(r)) { seen.add(r); out.push(r); }
  }
  return out;
}

type Sub = (e: any) => void;
export class Hub {
  roots: string[];
  files = new Map<string, FileState>(); // key -> state
  byReal = new Map<string, string>(); // realpath -> key (the dedupe)
  prompts: any[] = [];
  log: any[] = []; // every entry and the reset markers, in arrival order
  seq = 0;
  isReady = false;
  lastScan = 0;
  subs = new Set<Sub>();
  recent = new Map<string, number>(); // dedupe: (session, kind, text head) -> time of the entry shown
  mode = "start"; // "watch" (events) or "poll" (the watcher could not start)
  private watchers: FSWatcher[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private stopped = false;
  ready: Promise<void>;
  private resolveReady!: () => void;
  constructor(roots: string[], public sources: Record<string, typeof ClaudeSource> = SOURCES) {
    this.roots = roots.map((r) => realpathSync(r));
    this.ready = new Promise((ok) => (this.resolveReady = ok));
  }

  // --- discovery ---
  /** Register files not seen yet. A new file is read from its start; at the first scan files only get an offset. */
  rescan(): FileState[] {
    const fresh: FileState[] = [];
    for (const [sname, src] of Object.entries(this.sources)) {
      for (const p of src.discover(this.roots)) {
        let real: string, st;
        try { real = realpathSync(p); if (this.byReal.has(real)) continue; st = statSync(real); } catch { continue; }
        if (!this.roots.some((r) => real === r || real.startsWith(r + sep))) continue; // never read outside the roots
        const key = createHash("sha1").update(real).digest("hex").slice(0, 8);
        const [sess, proj, side] = src.describe(real);
        const fs: FileState = { path: real, key, source: sname, session: sess, project: proj, sideFile: side, offset: 0, seenSize: -1,
          seenMtime: 0, resync: false, gone: false, mtime: st.mtimeMs / 1000, title: "" };
        this.files.set(key, fs);
        this.byReal.set(real, key);
        fresh.push(fs);
      }
    }
    this.lastScan = Date.now();
    return fresh;
  }

  // --- reading ---
  private read(fs: FileState, start: number, end: number): Buffer {
    const fd = openSync(fs.path, "r");
    try {
      const buf = Buffer.alloc(Math.max(0, end - start));
      const n = readSync(fd, buf, 0, buf.length, start);
      return buf.subarray(0, n);
    } finally { closeSync(fd); }
  }
  /** Complete lines with their absolute offsets, and the offset where the unfinished last line (if any) starts. */
  private lines(data: Buffer, base: number): [[number, Buffer][], number] {
    const out: [number, Buffer][] = [];
    let pos = 0;
    for (;;) {
      const nl = data.indexOf(10, pos);
      if (nl < 0) return [out, base + pos]; // a partial last line is kept for the next read, never parsed
      if (nl > pos) out.push([base + pos, data.subarray(pos, nl)]);
      pos = nl + 1;
    }
  }
  /** The tail of one file: windows from the end, growing, until it holds enough entries. Sets the offset. */
  backfillFile(fs: FileState, wantPrompts: number, wantLog: number): any[] {
    let st;
    try { st = statSync(fs.path); } catch { fs.gone = true; return []; }
    const size = st.size;
    let win = 256 * 1024, entries: any[] = [], tailOff = 0;
    for (;;) {
      let start = Math.max(0, size - win);
      let data = this.read(fs, start, size);
      if (start > 0) { // the window began mid-line: drop that piece
        const cut = data.indexOf(10);
        if (cut < 0) { data = Buffer.alloc(0); start = size; } else { data = data.subarray(cut + 1); start += cut + 1; }
      }
      const [lines, off] = this.lines(data, start);
      tailOff = off;
      entries = lines.map(([o, r]) => this.sources[fs.source].normalize(r, o, fs)).filter(Boolean);
      const nP = entries.filter((e) => e.kind === "prompt").length;
      if (start === 0 || win >= 8 * 1024 * 1024 || nP >= wantPrompts || entries.length >= wantLog) break;
      win *= 4;
    }
    fs.offset = tailOff; fs.seenSize = size; fs.seenMtime = st.mtimeMs / 1000; fs.resync = false;
    return entries;
  }
  /** Newest files first, tail only, until about WANT_PROMPTS prompts and WANT_LOG entries. Older files get only an
   *  offset at their end (new activity in them will still be tailed). */
  async backfill(): Promise<void> {
    const order = [...this.files.values()].sort((a, b) => b.mtime - a.mtime);
    let gotP = 0, gotL = 0;
    const everything: any[] = [];
    for (let i = 0; i < order.length; i++) {
      const fs = order[i];
      if ((gotP >= WANT_PROMPTS && gotL >= WANT_LOG) || i >= BACKFILL_FILES()) { this.park(fs); continue; }
      const es = this.backfillFile(fs, WANT_PROMPTS - gotP, WANT_LOG - gotL);
      gotP += es.filter((e) => e.kind === "prompt").length;
      gotL += es.length;
      everything.push(...es);
      if (i % 10 === 9) await sleep(0); // let the server answer while a big backfill runs
    }
    everything.sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
    for (const e of everything) this.publish(e);
    this.isReady = true;
    this.resolveReady();
  }
  /** Not read: its offset is its end; resync when that end is not at a line start. */
  private park(fs: FileState): void {
    try {
      const st = statSync(fs.path);
      fs.offset = st.size; fs.seenSize = st.size; fs.seenMtime = st.mtimeMs / 1000;
      if (st.size) fs.resync = this.read(fs, st.size - 1, st.size)[0] !== 10;
    } catch { fs.gone = true; }
  }
  private static epoch(t: string): number | null {
    const ms = Date.parse(t);
    return Number.isNaN(ms) ? null : ms / 1000;
  }
  /** A queued message is logged as an attachment and often again as a user line: same session, same kind and the same
   *  first ~200 characters (whitespace-normalized) within ~2 minutes is one entry, the earliest. Two equal prompts
   *  further apart than the window (the owner repeating "go on") stay two. */
  private isDuplicate(e: any): boolean {
    if (!PROMPT_KINDS.includes(e.kind)) return false;
    const at = Hub.epoch(e.t);
    if (at === null) return false;
    const key = JSON.stringify([e.session, e.kind, e.text.split(/\s+/).filter(Boolean).join(" ").slice(0, DEDUPE_CHARS)]);
    const seen = this.recent.get(key);
    this.recent.set(key, seen === undefined || Math.abs(at - seen) > DEDUPE_WINDOW ? at : Math.min(at, seen));
    if (this.recent.size > 5000) for (const [k, v] of this.recent) if (at - v > DEDUPE_WINDOW) this.recent.delete(k);
    return seen !== undefined && Math.abs(at - seen) <= DEDUPE_WINDOW;
  }
  private publish(e: any): void {
    if (this.isDuplicate(e)) return;
    this.seq++;
    const full = { ...e, _seq: this.seq, _f: String(e.id).split(":", 1)[0] };
    this.log.push(full);
    if (this.log.length > RING_LOG) this.log.shift();
    if (PROMPT_KINDS.includes(full.kind)) { this.prompts.push(full); if (this.prompts.length > RING_PROMPTS) this.prompts.shift(); }
    this.notify(full);
  }
  private notify(e: any): void { for (const s of [...this.subs]) { try { s(e); } catch { this.subs.delete(s); } } }

  /** A client's callback, and the backlog after the entry `after` (nothing for an unknown or empty id: from now). */
  subscribe(after: string, sub: Sub): any[] {
    const cursor = after ? [...this.log].reverse().find((e) => e.id === after)?._seq : undefined;
    const backlog = cursor !== undefined ? this.log.filter((e) => e._seq > cursor) : [];
    this.subs.add(sub);
    return backlog;
  }
  unsubscribe(sub: Sub): void { this.subs.delete(sub); }

  // --- tailing ---
  /** Check every known file (the polling mode, and the safety net of the watch mode). Returns new entries. */
  tick(): number { let n = 0; for (const fs of [...this.files.values()]) n += this.check(fs); return n; }
  /** One file: compare size and mtime with what was read, read from the offset to the end. */
  check(fs: FileState): number {
    if (fs.gone) return 0;
    let st;
    try { st = statSync(fs.path); } catch { fs.gone = true; return 0; } // the file disappeared: its past entries stay
    fs.mtime = st.mtimeMs / 1000;
    if (st.size < fs.offset) this.reset(fs); // shrank (rewritten): forget its entries, read it again, tell the clients
    if (st.size === fs.seenSize && st.mtimeMs / 1000 === fs.seenMtime) return 0;
    return this.advance(fs, st);
  }
  /** The watcher's event for one path: register the file if it is new (inside the roots), then read it. */
  touch(path: string): number {
    let real: string;
    try { real = realpathSync(path); } catch { return 0; }
    if (!real.endsWith(".jsonl")) return 0;
    let key = this.byReal.get(real);
    if (key === undefined) { this.rescan(); key = this.byReal.get(real); } // a new file (maybe in a new folder), born after the backfill
    return key ? this.check(this.files.get(key)!) : 0;
  }
  private reset(fs: FileState): void {
    this.log = this.log.filter((e) => e._f !== fs.key);
    this.prompts = this.prompts.filter((e) => e._f !== fs.key);
    this.recent = new Map(); // the file is read again: its prompts must not look like duplicates of themselves
    this.seq++;
    const mark = { _seq: this.seq, _f: fs.key, kind: "reset", id: `${fs.key}:reset${this.seq}`, session: fs.session };
    this.log.push(mark);
    this.notify(mark);
    fs.offset = 0; fs.resync = false;
  }
  private advance(fs: FileState, st: ReturnType<typeof statSync>): number {
    const end = st.size;
    let start = fs.offset;
    let data = this.read(fs, start, Math.min(end, start + READ_CAP));
    const readEnd = start + data.length;
    if (fs.resync) { // the offset was mid-line: skip to the first line start
      const cut = data.indexOf(10);
      if (cut < 0) { fs.seenSize = end; fs.seenMtime = st.mtimeMs / 1000; return 0; }
      data = data.subarray(cut + 1); start += cut + 1; fs.resync = false;
    }
    const [lines, off] = this.lines(data, start);
    fs.offset = off;
    if (readEnd < end) fs.seenSize = -1; // a burst bigger than READ_CAP: the next tick continues
    else { fs.seenSize = end; fs.seenMtime = st.mtimeMs / 1000; }
    const src = this.sources[fs.source];
    const es = lines.map(([o, r]) => src.normalize(r, o, fs)).filter(Boolean);
    for (const e of es) this.publish(e);
    return es.length;
  }

  /** Backfill once, then follow by events (or by polling when the watcher cannot start). */
  async run(): Promise<void> {
    this.rescan();
    await this.backfill();
    if (this.stopped) return;
    this.tick(); // what was written between the backfill and the watcher's start
    this.mode = "watch";
    for (const root of this.roots) {
      try {
        this.watchers.push(fsWatch(root, { recursive: true }, (_ev, file) => { if (file && String(file).endsWith(".jsonl")) { try { this.touch(join(root, String(file))); } catch { /* one bad pass never kills the tailer */ } } }));
      } catch { this.mode = "poll"; }
    }
    if (!this.watchers.length) this.mode = "poll";
    // the net (watch mode) or the engine (poll mode): new files and every file, in case an event was lost
    this.timer = setInterval(() => {
      try {
        if (this.mode === "poll" || Date.now() - this.lastScan >= RESCAN) { if (Date.now() - this.lastScan >= RESCAN) this.rescan(); this.tick(); }
      } catch { /* no text is logged */ }
    }, TICK);
  }
  start(): Hub { void this.run(); return this; }
  shutdown(): void {
    this.stopped = true;
    for (const w of this.watchers) w.close();
    this.watchers = [];
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.subs.clear();
  }

  // --- reads (the routes' logic) ---
  static pub(e: any): any { return Object.fromEntries(Object.entries(e).filter(([k]) => !k.startsWith("_"))); }
  private select(ring: any[], limit: number, session: string, kinds: string[] | null, side: boolean): any[] {
    const kset = kinds && kinds.length ? new Set(kinds) : null;
    const out = ring.filter((e) => e.kind !== "reset" && (!kset || kset.has(e.kind)) && (side || !e.side) && (!session || e.session.startsWith(session)));
    return out.slice(-Math.max(1, Math.min(limit, 5000))).map(Hub.pub);
  }
  getPrompts(limit = 200, session = "", kinds: string[] = ["prompt"], side = false) {
    return { entries: this.select(this.prompts, limit, session, kinds, side), last: this.lastId(), sessions: this.sessions(), mode: this.mode };
  }
  getLog(limit = 500, session = "", side = false) {
    return { entries: this.select(this.log, limit, session, null, side), last: this.lastId(), sessions: this.sessions(), mode: this.mode };
  }
  lastId(): string { return this.log.length ? this.log[this.log.length - 1].id : ""; }
  /** One row per session (sub-agent files folded under their own `ag:` ids), newest activity first. */
  sessions(): any[] {
    const rows = [...this.files.values()].map((f) => ({ session: f.session, title: f.title, project: f.project, last: isoFromTs(f.mtime), side: f.sideFile }));
    rows.sort((a, b) => (a.last < b.last ? 1 : a.last > b.last ? -1 : 0));
    return rows.slice(0, 200);
  }
  since(seq: number): any[] { return this.log.filter((e) => e._seq > seq); }
  seqOf(eid: string): number | null { return [...this.log].reverse().find((e) => e.id === eid)?._seq ?? null; }
  curSeq(): number { return this.seq; }
  /** The whole text of one entry (capped): re-read its line from the file; only known files, only at that offset. */
  getEntry(eid: string): any | null {
    const [key, off] = [eid.split(":")[0], eid.includes(":") ? eid.slice(eid.indexOf(":") + 1) : ""];
    const fs = this.files.get(key);
    if (!fs || !/^\d+$/.test(off) || fs.gone) return null;
    const offset = Number(off);
    try {
      const fd = openSync(fs.path, "r");
      try {
        const buf = Buffer.alloc(MAX_LINE + 1);
        const n = readSync(fd, buf, 0, buf.length, offset);
        let line = buf.subarray(0, n);
        const nl = line.indexOf(10);
        if (nl >= 0) line = line.subarray(0, nl);
        return this.sources[fs.source].normalize(line, offset, fs, true);
      } finally { closeSync(fd); }
    } catch { return null; }
  }
}

let HUB: Hub | null = null;
/** The one hub of the process, started by the first request (the roots are read from the env then). */
export function getHub(): Hub { return (HUB ??= new Hub(rootsFromEnv()).start()); }
export function stopHub(): void { HUB?.shutdown(); HUB = null; }
/** Host names the whole console answers to. A page on another domain pointed at 127.0.0.1 (DNS rebinding) sends its own
 *  Host, so it gets a 400 and cannot read the prompts. DEV_CONSOLE_ALLOWED_HOSTS (comma-separated) extends the list. */
export function allowedHosts(): string[] {
  const extra = env("DEV_CONSOLE_ALLOWED_HOSTS").split(",").map((h) => h.trim()).filter(Boolean);
  return ["127.0.0.1", "localhost", ...extra];
}
const sseFrame = (e: any) => e.kind === "reset"
  ? `event: reset\nid: ${e.id}\ndata: ${JSON.stringify({ session: e.session })}\n\n`
  : `id: ${e.id}\ndata: ${JSON.stringify(Hub.pub(e))}\n\n`;

/** Server-sent events for one client: `retry:`, the backlog after `after` (the Last-Event-ID header or ?after=; an unknown
 *  id resumes from now), then each new entry as `id: <entry id>` + `data: <json>`. The tailer pushes into this client's
 *  callback, so nothing polls; the 15 s timer only emits the keep-alive comment. Unsubscribed when the client goes. */
export function agentsSse(hub: Hub, after: string, signal?: AbortSignal, keepalive = KEEPALIVE): Response {
  const enc = new TextEncoder();
  let sub: Sub | null = null, ka: ReturnType<typeof setInterval> | null = null;
  const stop = () => { if (sub) hub.unsubscribe(sub); if (ka) clearInterval(ka); sub = null; ka = null; };
  const body = new ReadableStream({
    start(ctl) {
      const send = (s: string) => { try { ctl.enqueue(enc.encode(s)); } catch { stop(); } };
      send("retry: 3000\n\n");
      sub = (e: any) => send(sseFrame(e));
      for (const e of hub.subscribe(after, sub)) send(sseFrame(e));
      ka = setInterval(() => send(": keep-alive\n\n"), keepalive);
      signal?.addEventListener("abort", () => { stop(); try { ctl.close(); } catch { /* closed */ } });
    },
    cancel() { stop(); },
  });
  return new Response(body, { headers: { "content-type": "text/event-stream", "cache-control": "no-cache", "x-accel-buffering": "no" } });
}

// ------------------------------------------------------------------------------------------------------------------
// The Playground's server side, absorbed from the design-playground (Bun/TS): the canvas mirror, the component
// definitions, the operations the page runs for an agent, and the HTTP API the canvas web calls.
// Each operation is a plain function or method here, never code inside a route handler. Data lives in one folder
// (DEV_CONSOLE_PLAYGROUND_DIR, default ~/.local/state/dev-console/playground), in the format the design-playground wrote:
//   canvas.json                       {"registros": {id: tldraw record}}
//   componentes/<produto>/<peça>.json one definition each, with `versao`
// ------------------------------------------------------------------------------------------------------------------
const PG_PREFIX = "/playground";
const PG_API = `${PG_PREFIX}/api`;
const OPERACAO_S = 15; // how long an operation waits for the open page to answer

export const playgroundDir = () => resolve(expand(env("DEV_CONSOLE_PLAYGROUND_DIR", "~/.local/state/dev-console/playground")));

/** Temp file and rename, so a reader never sees a half-written file. */
function writeAtomic(path: string, text: string): void {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.${Date.now()}.tmp`;
  writeFileSync(tmp, text, "utf8");
  renameSync(tmp, path);
}
const isObj = (v: any) => v !== null && typeof v === "object" && !Array.isArray(v);
const isTexto = (v: any) => typeof v === "string" && v.trim() !== "";
const isListaDeTextos = (v: any) => Array.isArray(v) && v.every((x) => typeof x === "string");
const isMedida = (v: any) => typeof v === "number" && v > 0 && v <= 20_000;

// ---------- the canvas mirror: the page owns the drawing, this is its copy ----------
export class Canvas {
  file: string;
  registros: Record<string, any> = {};
  constructor(folder: string) {
    this.file = join(folder, "canvas.json");
    try {
      const dados = JSON.parse(readText(this.file));
      if (isObj(dados.registros)) this.registros = dados.registros;
    } catch { /* no file yet, or unreadable: start empty */ }
  }
  ler() { return { ...this.registros }; }
  aplicar(put?: Record<string, any> | null, remove?: string[] | null): void {
    Object.assign(this.registros, put || {});
    for (const id of remove || []) delete this.registros[id];
    writeAtomic(this.file, JSON.stringify({ registros: this.registros }));
  }
}

// ---------- the components ----------
const KEBAB = "[a-z0-9]+(?:-[a-z0-9]+)*";
const ID_COMPONENTE = new RegExp(`^${KEBAB}/${KEBAB}$`);
const COMO_VALIDO = /^(?:texto|html|lista|attr:[A-Za-z_:][-\w:.]*|estilo:-{0,2}[A-Za-z][-\w]*)$/;
const MAIOR_ARQUIVO = 4 * 1024 * 1024; // a wrapper's real CSS passes 70 KB
const ARQUIVOS_DO_WRAPPER = { json: "componente.json", html: "peca.html", css: "peca.css", desktop: "desktop.css", sprite: "sprite.svg" };

function problemaDaVariante(v: any, onde: string): string | null {
  if (!isObj(v)) return `${onde} precisa ser um objeto { css, w, h, html? }`;
  if (typeof v.css !== "string") return `${onde}.css ausente (ou ponha um desktop.css na pasta do wrapper)`;
  if ("html" in v && !isTexto(v.html)) return `${onde}.html, quando vem, precisa ser texto`;
  if (!isMedida(v.w) || !isMedida(v.h)) return `${onde}.w e .h precisam ser números positivos`;
  return null;
}
/** The first problem of the value as a component definition (the `versao` aside, the tool gives it), or null.
 *  The message is for the model to read and fix. */
export function problemaDoComponente(v: any): string | null {
  if (!isObj(v)) return "o componente precisa ser um objeto JSON";
  if (typeof v.id !== "string" || !ID_COMPONENTE.test(v.id))
    return `id inválido ${JSON.stringify(v.id)}: use "<produto>/<peça>" em kebab-case, ex.: "via/cartao-imovel"`;
  if (!isTexto(v.nome)) return "nome ausente";
  if (typeof v.descricao !== "string") return "descricao ausente (para que serve a peça)";
  if (v.estado !== "rascunho" && v.estado !== "real") return 'estado precisa ser "rascunho" ou "real"';
  if (v.estado === "real" && !("fonte" in v))
    return 'estado "real" exige fonte { repo, arquivo, simbolo?, commit, receita }: de onde no código do produto a peça saiu. Sem fonte, use estado "rascunho".';
  if (v.estado === "rascunho" && "fonte" in v)
    return 'um rascunho não tem fonte: tire o campo fonte, ou use estado "real" se a peça já existe no código do produto';
  if (!isTexto(v.html)) return "html ausente (ou ponha um peca.html na pasta do wrapper)";
  if (typeof v.css !== "string") return 'css ausente (ou ponha um peca.css na pasta do wrapper); use "" se a peça não tem CSS';
  if (!isMedida(v.w) || !isMedida(v.h)) return "w e h precisam ser números positivos (o tamanho natural no celular, 393 de largura)";
  if ("variantes" in v) {
    const vr = v.variantes;
    if (!isObj(vr)) return "variantes precisa ser um objeto { desktop? }";
    const estranhas = Object.keys(vr).filter((k) => k !== "desktop");
    if (estranhas.length) return `variantes só aceita "desktop" (veio ${estranhas.join(", ")})`;
    if ("desktop" in vr) { const p = problemaDaVariante(vr.desktop, "variantes.desktop"); if (p) return p; }
  }
  if (!Array.isArray(v.slots)) return "slots precisa ser uma lista (pode ser vazia)";
  for (let i = 0; i < v.slots.length; i++) {
    const s = v.slots[i], onde = `slots[${i}]`;
    if (!isObj(s) || !isTexto(s.chave) || !isTexto(s.seletor)) return `${onde} precisa de chave e seletor`;
    if (typeof s.como !== "string" || !COMO_VALIDO.test(s.como)) return `${onde}.como inválido: use texto, html, lista, attr:<atributo> ou estilo:<propriedade>`;
  }
  if (!isObj(v.dados)) return "dados precisa ser um objeto chave → texto (ou lista de textos)";
  for (const [chave, valor] of Object.entries(v.dados))
    if (typeof valor !== "string" && !isListaDeTextos(valor)) return `dados.${chave} precisa ser texto ou lista de textos`;
  if ("fonte" in v) {
    const f = v.fonte;
    if (!isObj(f)) return "fonte precisa ser um objeto { repo, arquivo, simbolo?, commit, receita }";
    if (!isTexto(f.repo) || !isTexto(f.arquivo) || !isTexto(f.commit)) return "fonte precisa de repo, arquivo e commit";
    if ("simbolo" in f && !isTexto(f.simbolo)) return "fonte.simbolo, quando vem, precisa ser texto";
    if (f.receita !== "executar" && f.receita !== "copiar") return 'fonte.receita precisa ser "executar" ou "copiar"';
  }
  if ("fontes" in v && !isListaDeTextos(v.fontes)) return "fontes precisa ser uma lista de URLs de folhas de estilo";
  if ("sprite" in v && typeof v.sprite !== "string") return "sprite precisa ser o SVG (texto) com os <symbol>";
  return null;
}
/** Only the contract's fields, in its order (extras are dropped). */
function limpar(c: any, versao: number): any {
  const out: any = { id: c.id, nome: c.nome, descricao: c.descricao, estado: c.estado, versao, html: c.html, css: c.css, w: c.w, h: c.h,
    slots: c.slots.map((s: any) => ({ chave: s.chave, seletor: s.seletor, como: s.como })), dados: c.dados };
  const d = c.variantes?.desktop;
  if (d) out.variantes = { desktop: "html" in d ? { html: d.html, css: d.css, w: d.w, h: d.h } : { css: d.css, w: d.w, h: d.h } };
  if (c.fonte) {
    const f = c.fonte;
    out.fonte = { repo: f.repo, arquivo: f.arquivo, ...("simbolo" in f ? { simbolo: f.simbolo } : {}), commit: f.commit, receita: f.receita };
  }
  if (c.fontes?.length) out.fontes = c.fontes;
  if ("sprite" in c) out.sprite = c.sprite;
  return out;
}
/** The keys an instance accepts in `dados`: the slots' and the default data's. */
export const chavesDe = (c: any): string[] => [...new Set([...c.slots.map((s: any) => s.chave), ...Object.keys(c.dados)])];

/** Read a wrapper folder: componente.json and, where the JSON lacks the field, peca.html (html), peca.css (css),
 *  desktop.css (variantes.desktop.css) and sprite.svg (sprite). Absolute path; no file may leave the folder (a symlink
 *  out is refused). Does not validate: returns the assembled object for `problemaDoComponente`. Throws with a clear message. */
export function lerPasta(pasta: string): any {
  if (typeof pasta !== "string" || pasta.includes("\0")) throw new Error("pasta inválida");
  if (!isAbsolute(pasta)) throw new Error(`a pasta precisa ser um caminho absoluto (veio "${pasta}")`);
  if (pasta.split(/[\\/]/).includes("..")) throw new Error(`a pasta não pode ter ".." no caminho (veio "${pasta}")`);
  let raiz: string;
  try { raiz = realpathSync(pasta); } catch { throw new Error(`a pasta não existe: ${pasta}`); }
  if (!isDir(raiz)) throw new Error(`não é uma pasta: ${pasta}`);
  const ler = (nome: string): string | null => {
    const caminho = join(raiz, nome);
    let isLink = false;
    try { isLink = lstatSync(caminho).isSymbolicLink(); } catch { /* absent */ }
    if (!isLink && !existsSync(caminho)) return null;
    let real: string;
    try { real = realpathSync(caminho); } catch { throw new Error(`${nome} aponta para um arquivo que não existe`); }
    if (!real.startsWith(raiz + sep)) throw new Error(`${nome} aponta para fora da pasta do wrapper (recusado)`);
    if (!isFile(real)) throw new Error(`${nome} não é um arquivo`);
    if (statSync(real).size > MAIOR_ARQUIVO) throw new Error(`${nome} passa de ${MAIOR_ARQUIVO / 1024 / 1024} MB`);
    return readText(real);
  };
  const texto = ler(ARQUIVOS_DO_WRAPPER.json);
  if (texto === null) throw new Error(`a pasta não tem ${ARQUIVOS_DO_WRAPPER.json}: ${pasta}`);
  let bruto: any;
  try { bruto = JSON.parse(texto); } catch (e) { throw new Error(`${ARQUIVOS_DO_WRAPPER.json} não é JSON válido: ${(e as Error).message}`); }
  if (!isObj(bruto)) throw new Error(`${ARQUIVOS_DO_WRAPPER.json} precisa ser um objeto`);
  const c: any = { ...bruto };
  for (const [campo, arquivo] of [["html", "html"], ["css", "css"]] as const) {
    if (!(campo in c)) { const lido = ler(ARQUIVOS_DO_WRAPPER[arquivo]); if (lido !== null) c[campo] = lido; }
  }
  if (!("sprite" in c)) { const sprite = ler(ARQUIVOS_DO_WRAPPER.sprite); if (sprite !== null) c.sprite = sprite; }
  const variantes = isObj(c.variantes) ? { ...c.variantes } : c.variantes;
  const desktop = isObj(variantes) && isObj(variantes.desktop) ? { ...variantes.desktop } : null;
  if (desktop !== null) {
    if (!("css" in desktop)) { const css = ler(ARQUIVOS_DO_WRAPPER.desktop); if (css !== null) desktop.css = css; }
    c.variantes = { ...variantes, desktop };
  } else if (variantes === undefined || variantes === null) { // a desktop.css in the folder is the web variant (1280), with the phone's height
    const css = ler(ARQUIVOS_DO_WRAPPER.desktop);
    if (css !== null) c.variantes = { desktop: { css, w: 1280, h: c.h } };
  }
  return c;
}

export class Componentes {
  dir: string;
  constructor(folder: string, public aoDefinir?: (c: any) => void) { this.dir = join(folder, "componentes"); }
  private arquivo(id: string) { const [produto, peca] = id.split("/"); return join(this.dir, produto, `${peca}.json`); }
  /** Validate and write a definition with the next version. Throws with the problem. */
  definir(entrada: any): any {
    const problema = problemaDoComponente(entrada);
    if (problema) throw new Error(problema);
    const anterior = this.ler(entrada.id);
    const componente = limpar(entrada, (anterior ? anterior.versao : 0) + 1);
    writeAtomic(this.arquivo(entrada.id), JSON.stringify(componente, null, 2) + "\n");
    try { this.aoDefinir?.(componente); } catch { /* a failed notice never loses the definition */ }
    return componente;
  }
  definirDaPasta(pasta: string) { return this.definir(lerPasta(pasta)); }
  ler(id: string): any | null {
    if (!ID_COMPONENTE.test(id)) return null;
    const a = this.arquivo(id);
    return existsSync(a) ? Componentes.lerArquivo(a, id) : null;
  }
  static lerArquivo(arquivo: string, idEsperado?: string): any | null {
    let bruto: any;
    try { bruto = JSON.parse(readText(arquivo)); } catch { return null; }
    if (problemaDoComponente(bruto) || (idEsperado !== undefined && bruto.id !== idEsperado)) return null;
    const v = bruto.versao;
    return { ...bruto, versao: Number.isInteger(v) && v > 0 ? v : 1 };
  }
  /** Every valid definition in id order; one product's only, if asked. */
  todos(produto?: string): any[] {
    let produtos: string[];
    try { produtos = readdirSync(this.dir, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort(); } catch { return []; }
    if (produto !== undefined) produtos = produtos.filter((p) => p === produto);
    const saida: any[] = [];
    for (const p of produtos) {
      for (const a of readdirSync(join(this.dir, p)).filter((n) => n.endsWith(".json")).sort()) {
        const c = Componentes.lerArquivo(join(this.dir, p, a), `${p}/${a.slice(0, -".json".length)}`);
        if (c) saida.push(c);
      }
    }
    return saida;
  }
  /** The summary for the model: no HTML, no CSS. */
  listar(produto?: string) {
    return this.todos(produto).map((c) => ({ id: c.id, nome: c.nome, descricao: c.descricao, estado: c.estado, versao: c.versao, w: c.w, h: c.h,
      chaves: chavesDe(c), dados: c.dados }));
  }
  /** Check the component exists and the keys of `dados` are its own. The error message for the model, or null. */
  conferir(id: string, dados?: Record<string, any>): string | null {
    const c = this.ler(id);
    if (!c) {
      const produto = id.split("/")[0], todos = this.todos();
      const doProduto = todos.filter((x) => x.id.split("/")[0] === produto);
      const lista = (doProduto.length ? doProduto : todos).map((x) => x.id);
      const existentes = lista.length ? lista.join(", ") : "nenhum ainda";
      const onde = doProduto.length ? `do produto ${produto}` : "definidos";
      return `não existe o componente "${id}" (${onde}: ${existentes}). Defina com componente_definir: a pasta do wrapper da skill design, ou o JSON com estado "rascunho" para uma peça nova.`;
    }
    const chaves = chavesDe(c), estranhas = Object.keys(dados || {}).filter((k) => !chaves.includes(k));
    if (estranhas.length) return `o componente "${id}" não tem as chaves ${estranhas.join(", ")} (chaves: ${chaves.join(", ") || "nenhuma"})`;
    return null;
  }
}

// ---------- the live line to the open page (the SSE) and the operations on it ----------
type Assinante = (tipo: string, dados: any) => void;
/** The open pages' SSE connections. `publicar` reaches all; `paraUm` the newest page only (the canvas operations). */
export class Eventos {
  assinantes: Assinante[] = [];
  assinar(fn: Assinante): () => void {
    this.assinantes.push(fn);
    return () => { this.assinantes = this.assinantes.filter((x) => x !== fn); };
  }
  get ouvintes() { return this.assinantes.length; }
  publicar(tipo: string, dados: any) { for (const a of [...this.assinantes]) a(tipo, dados); }
  paraUm(tipo: string, dados: any): boolean {
    if (!this.assinantes.length) return false;
    this.assinantes[this.assinantes.length - 1](tipo, dados);
    return true;
  }
}
/** The server does not draw: it sends the operation to the open page (SSE `canvas`), which applies it with the tldraw
 *  editor and answers on POST /canvas/resposta. Each operation waits for the answer, with a time limit. */
export class Operacoes {
  pendentes = new Map<string, { ok: (v: any) => void; no: (e: Error) => void }>();
  constructor(public eventos: Eventos, public limiteS = OPERACAO_S) {}
  executar(op: any): Promise<any> {
    if (!this.eventos.ouvintes) return Promise.reject(new Error("a Web não está aberta: abra o /playground do dev-console e espere a página carregar"));
    const pedido = randomUUID();
    return new Promise((ok, no) => {
      const timer = setTimeout(() => { this.pendentes.delete(pedido); no(new Error("a página não respondeu a tempo (o canvas carregou?)")); }, this.limiteS * 1000);
      this.pendentes.set(pedido, { ok: (v) => { clearTimeout(timer); ok(v); }, no: (e) => { clearTimeout(timer); no(e); } });
      this.eventos.paraUm("canvas", { pedido, op });
    });
  }
  /** The page's answer. False if the request does not exist (it expired). */
  responder(pedido: string, ok: boolean, resultado?: any, erro?: string | null): boolean {
    const p = this.pendentes.get(pedido);
    if (!p) return false;
    this.pendentes.delete(pedido);
    if (ok) p.ok(resultado); else p.no(new Error(erro || "a página recusou a operação"));
    return true;
  }
}
export class Playground {
  dir: string; canvas: Canvas; eventos = new Eventos(); operacoes: Operacoes; componentes: Componentes;
  constructor(folder?: string) {
    this.dir = folder || playgroundDir();
    this.canvas = new Canvas(this.dir);
    this.operacoes = new Operacoes(this.eventos);
    // each definition tells every tab: they fetch the new one and redraw that id's instances
    this.componentes = new Componentes(this.dir, (c) => this.eventos.publicar("componente", { id: c.id, versao: c.versao }));
  }
}

const NOCACHE = { "cache-control": "no-store" };
const pgErro = (status: number, msg: string) => jsonResponse({ erro: msg }, status, NOCACHE);

/** Mount the routes under /playground on the Hono app. */
export function mountPlayground(app: Hono, pg: Playground): void {
  app.get(`${PG_API}/canvas`, () => jsonResponse({ registros: pg.canvas.ler() }, 200, NOCACHE));
  app.post(`${PG_API}/canvas/diff`, async (c) => {
    const corpo = await c.req.json().catch(() => null);
    if (!isObj(corpo)) return pgErro(400, "corpo precisa ser JSON { put?, remove? }");
    const { put, remove } = corpo;
    if (put !== undefined && put !== null && !isObj(put)) return pgErro(400, "put precisa ser um objeto id → registro");
    if (remove !== undefined && remove !== null && !isListaDeTextos(remove)) return pgErro(400, "remove precisa ser uma lista de ids");
    pg.canvas.aplicar(put, remove);
    return new Response(null, { status: 204 });
  });
  app.post(`${PG_API}/canvas/resposta`, async (c) => {
    const corpo = await c.req.json().catch(() => null);
    if (!isObj(corpo) || typeof corpo.pedido !== "string") return pgErro(400, "corpo precisa ser { pedido, ok, resultado?, erro? }");
    const achou = pg.operacoes.responder(corpo.pedido, corpo.ok === true, corpo.resultado, typeof corpo.erro === "string" ? corpo.erro : null);
    return achou ? new Response(null, { status: 204 }) : pgErro(404, "pedido desconhecido ou vencido");
  });
  app.get(`${PG_API}/componentes`, () => jsonResponse({ componentes: pg.componentes.todos() }, 200, NOCACHE));
  app.get(`${PG_API}/eventos`, (c) => {
    const enc = new TextEncoder();
    let soltar: (() => void) | null = null, ping: ReturnType<typeof setInterval> | null = null;
    const stop = () => { soltar?.(); if (ping) clearInterval(ping); soltar = null; ping = null; };
    const body = new ReadableStream({
      start(ctl) {
        const send = (s: string) => { try { ctl.enqueue(enc.encode(s)); } catch { stop(); } };
        send("retry: 2000\n\n");
        soltar = pg.eventos.assinar((tipo, dados) => send(`event: ${tipo}\ndata: ${JSON.stringify(dados)}\n\n`));
        ping = setInterval(() => send(": ping\n\n"), 15000); // keeps proxies and the browser from closing an idle line
        c.req.raw.signal.addEventListener("abort", () => { stop(); try { ctl.close(); } catch { /* closed */ } });
      },
      cancel: stop,
    });
    return new Response(body, { headers: { "content-type": "text/event-stream", "cache-control": "no-store", "x-accel-buffering": "no" } });
  });
  const web: Record<string, [string, string]> = {
    "canvas.js": [PG_CANVAS_JS, "text/javascript"], "widgets.js": [PG_WIDGETS_JS, "text/javascript"], "paleta.js": [PG_PALETA_JS, "text/javascript"],
    "eventos.js": [PG_EVENTOS_JS, "text/javascript"], "app.css": [PG_APP_CSS, "text/css"],
  };
  app.on(["GET", "HEAD"], `${PG_PREFIX}/web/:file{.+}`, (c) => {
    const hit = web[c.req.param("file")];
    return hit ? new Response(hit[0], { headers: { "content-type": `${hit[1]}; charset=utf-8`, ...NOCACHE } }) : pgErro(404, "não encontrado");
  });
}

/** `console.sh playground import`: copy canvas.json and componentes/ from a design-playground `dados` folder.
 *  Refuses to overwrite without `force`. */
export function importarPlayground(origem: string, destino: string, force = false): string[] {
  const itens = ["canvas.json", "componentes"].filter((n) => existsSync(join(origem, n)));
  if (!itens.length) throw new Error(`nada para importar em ${origem} (sem canvas.json nem componentes/)`);
  const ja = itens.filter((n) => existsSync(join(destino, n)));
  if (ja.length && !force) throw new Error(`${destino} já tem ${ja.join(", ")}; use --force para sobrescrever`);
  mkdirSync(destino, { recursive: true });
  for (const n of itens) {
    const alvo = join(destino, n);
    if (isDir(join(origem, n))) { rmSync(alvo, { recursive: true, force: true }); cpSync(join(origem, n), alvo, { recursive: true }); }
    else cpSync(join(origem, n), alvo);
  }
  return itens;
}

// ------------------------------------------------------------------------------------------------------------------
// The pages. Every page is the same shell (head libraries, light theme, the one CSS) around a body that is a flex column:
// the module on top, the status line at the bottom, the ⌘K switcher overlay. Markup is built here; text is escaped.
// ------------------------------------------------------------------------------------------------------------------
// the switcher script is the main page's own, cut out of JS (one copy), plus the names it needs
const SWITCHER_JS = JS.slice(JS.indexOf("// --- Switcher overlay"), JS.indexOf("function wireRows"));
const PLAYGROUND_JS = `
const $ = id => document.getElementById(id);
const D = JSON.parse($('data').textContent), Q = new URLSearchParams(location.search);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
D.module = '/playground';  // the current module, for ⌘P's "· atual"
let tab = '';
const COUNT = {}, KEYS = {};  // the switcher's tags exist on a domain page only
const show = () => {};  // a module with no href is a tab: the Playground has none
` + SWITCHER_JS;

const LIVE_SCRIPT = `
(() => { if (!window.EventSource) return; let seen = false;  // the server restarted or a project changed: reload when it answers again
  const es = new EventSource('/__live');
  es.onmessage = e => { if (e.data === 'reload') location.reload(); else seen = true; };
  es.onerror = () => { if (!seen) return; es.close(); const t = setInterval(() => fetch('/api/domains').then(r => { if (r.ok) { clearInterval(t); location.reload(); } }).catch(() => {}), 700); };
})();`;

// What the MonsterUI "neutral" theme and FastHTML's default headers brought to every page, light only: the widgets the
// projects write (Python, FastHTML + MonsterUI components, Tailwind classes) are drawn against exactly this.
const LIBS = `
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light">
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.7/dist/htmx.js"></script>
<script src="https://cdn.jsdelivr.net/gh/answerdotai/fasthtml-js@1.0.13/fasthtml.js"></script>
<script src="https://cdn.jsdelivr.net/gh/answerdotai/surreal@main/surreal.js"></script>
<script src="https://cdn.jsdelivr.net/gh/gnat/css-scope-inline@main/script.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@anyblades/pico@2.5.0/css/pico.min.css">
<style>:root { --pico-font-size: 100%; color-scheme: light; }</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/franken-ui@2.0.0/dist/css/core.min.css">
<script type="module" src="https://cdn.jsdelivr.net/npm/franken-ui@2.0.0/dist/js/core.iife.js"></script>
<script src="https://cdn.tailwindcss.com/3.4.17"></script>
<script>tailwind.config = { darkMode: 'selector' }  // the dark class is never set: this console is light only</script>
<script type="module" src="https://cdn.jsdelivr.net/npm/franken-ui@2.0.0/dist/js/icon.iife.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@4.12.24/dist/full.min.css">
<style>:root { --b1: from hsl(var(--background)) l c h; --bc: from hsl(var(--foreground)) l c h; --m: from hsl(var(--muted)) l c h;
  --mc: from hsl(var(--muted-foreground)) l c h; --po: from hsl(var(--popover)) l c h; --poc: from hsl(var(--popover-foreground)) l c h;
  --b2: from hsl(var(--card)) l c h; --b2c: from hsl(var(--card-foreground)) l c h; --br: from hsl(var(--border)) l c h;
  --in: from hsl(var(--input)) l c h; --p: from hsl(var(--primary)) l c h; --pc: from hsl(var(--primary-foreground)) l c h;
  --s: from hsl(var(--secondary)) l c h; --sc: from hsl(var(--secondary-foreground)) l c h; --a: from hsl(var(--accent)) l c h;
  --ac: from hsl(var(--accent-foreground)) l c h; --er: from hsl(var(--destructive)) l c h; --erc: from hsl(var(--destructive-foreground)) l c h;
  --b3: from hsl(var(--ring)) l c h; --rd: var(--radius); }</style>`;

let LIVE = true;
type Shell = { title: string; body: string; head?: string; cls?: string };
/** A whole page. `cls` is the body's own wrapper (the three-part column of the console pages). */
function shell({ title, body, head = "" }: Shell): string {
  return `<!doctype html><html lang="pt-BR" data-theme="light" class="uk-theme-neutral uk-radii-sm uk-shadows-sm uk-font-sm"><head>${LIBS}
<title>${esc(title)}</title><link rel="icon" href="data:,"><style>${CSS}</style>${head}</head><body>${body}${LIVE ? `<script>${LIVE_SCRIPT}</script>` : ""}</body></html>`;
}
const COLUMN = "h-screen flex flex-col font-mono text-xs bg-white";
const dataScript = (payload: unknown) => `<script type="application/json" id="data">${JSON.stringify(payload).replace(/<\//g, "<\\/")}</script>`;
const LINE = "border-neutral-200";

/** The status line at the bottom of every page (VS Code, vim): the hour, the thread in focus, the name (click = ⌘K),
 *  · module (click = ⌘P; the page's JS fills #mod-name), the money bar, the Claude limits, a faint hint. One markup, so
 *  the pages cannot drift. */
function statusBar(name: string, money: boolean, module = true): string {
  const clockJs = "(()=>{const e=document.getElementById('bar-clock');if(!e)return;const t=()=>{e.textContent=" +
    "new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})};t();" +
    "setTimeout(()=>{t();setInterval(t,60000)},60000-Date.now()%60000)})()";
  const threadJs = "(()=>{const e=document.getElementById('bar-thread');if(!e)return;const f=()=>fetch('/api/focus',{cache:'no-store'})" +
    ".then(r=>r.json()).then(d=>{const t=d.thread||'';e.textContent=t?'⑂ '+t:'';e.classList.toggle('hidden',!t);" +
    "e.classList.toggle('flex',!!t)}).catch(()=>{});f();if(window.EventSource){new EventSource('/live/stream')" +
    ".onmessage=ev=>{if(ev.data.split(' ')[0]==='focus')f()}}})()";
  const claudeJs = "(()=>{const e=document.getElementById('bar-claude');if(!e)return;const f=async()=>{try{const d=await(await " +
    "fetch('/api/claude-usage',{cache:'no-store'})).json();e.innerHTML=(d.accounts||[]).map(a=>a.error?a.name+' —':" +
    "(a.week>=100?'<span class=\"text-[#800020] font-semibold\">':'<span>')+a.name+' '+a.week+'%</span>')" +
    ".join(' · ');e.title='limite semanal do Claude · '+(d.accounts||[]).map(a=>a.name+(a.resets?' volta '+new Date(a.resets)" +
    ".toLocaleString('pt-BR',{weekday:'short',hour:'2-digit',minute:'2-digit'}):'')).join(' · ')}catch(_){}};f();setInterval(f,60000)})()";
  return `<div id="bar" class="h-7 shrink-0 flex items-center border-t ${LINE} text-neutral-500">
<span id="bar-clock" title="hora" class="shrink-0 h-full flex items-center px-3 tabular-nums font-semibold text-neutral-800 border-r ${LINE}"></span><script>${clockJs}</script>
<span id="bar-thread" title="thread em foco no tmux" class="shrink-0 h-full items-center px-3 font-semibold text-[#800020] border-r ${LINE} hidden"></span><script>${threadJs}</script>
<span id="dom-open" data-ov="domain" title="trocar de domínio (⌘K)" class="shrink-0 pl-3 pr-1 max-w-[16rem] truncate font-semibold text-neutral-800">${esc(name)}</span>
${module ? `<span id="mod-open" data-ov="module" title="trocar de módulo (⌘P)" class="shrink-0 px-1 text-neutral-500"><span class="mr-1 text-neutral-400">·</span><span id="mod-name"></span></span>` : ""}
<div id="keyhint" class="shrink-0 w-8 text-neutral-400"></div>
${money ? `<div id="money" class="shrink-0 h-full flex items-center gap-3 px-3 whitespace-nowrap border-l ${LINE}"></div>` : ""}
<span id="bar-claude" title="limite semanal das contas do Claude" class="ml-auto shrink-0 px-3 tabular-nums whitespace-nowrap text-neutral-400"></span><script>${claudeJs}</script>
<div class="shrink-0 pr-3 whitespace-nowrap text-neutral-300">⌘K domínio · ⌘P módulo</div></div>`;
}

/** The Domain Switcher overlay: a fuzzy finder (fzf, the editors' command palette) over a dim layer. */
function switcher(): string {
  return `<div id="dom" class="hidden fixed inset-0 z-[10001] items-start justify-center pt-[16vh] bg-black/40 backdrop-blur-[1px]">
<div class="w-[min(560px,92vw)] rounded-lg border border-neutral-300 bg-white shadow-2xl">
<input id="dom-q" autocomplete="off" spellcheck="false" placeholder="domínio…" class="w-full h-11 px-4 bg-transparent border-0 border-b border-neutral-200 font-mono text-sm text-neutral-900 outline-none">
<div id="dom-list" class="max-h-[50vh] overflow-y-auto py-1"></div>
<div class="px-4 h-8 leading-8 border-t border-neutral-200 text-neutral-400">↑↓ escolher · Enter abrir · Esc fechar</div></div></div><script>${GOTO_HOME_JS}</script>`;
}

// --- the module model: what ⌘P lists, one list for every page ---
const AGENTS_MODULE = { name: "Agents", href: "/agents" }; // listed by ⌘P beside Domain and Playground
const BROWSER_MODULE = { name: "Browser", href: "/browser" }; // a page an agent is running (a landing, a dev server), inside
// Model is not a page of its own: the Browser is the base module, and Model opens it on the live diagram
const MODEL_MODULE = { name: "Model", href: "/browser?url=" + encodeURIComponent("/model") };

type Ctx = { domains: DomainInfo[]; host: Host; hub?: () => Hub; playground: Playground };
const homeModule = (c: Ctx): [string, string] | null => { const d = c.domains.find((x) => x.console_home); return d ? [d.slug, d.console_home!] : null; };
const firstDomain = (c: Ctx) => c.domains[0].slug;
/** The one module model both pages ship as D.modules, listed by ⌘P: `{name, href}`. On a domain page: Domain and the
 *  project's TABS (href null: shown in place), then Playground (href: navigates). On the Playground: Domain (the first
 *  domain; "/" is the home now) and Playground. ⌘K never lists these: it lists domains only. */
export function modulesOf(c: Ctx, tabs?: string[] | null): { name: string; href: string | null }[] {
  const home = homeModule(c);
  // the home module (CONSOLE_HOME) is listed on every page, first; on its own domain page it is already a tab
  const lead = home && !(tabs || []).includes(home[1]) ? [{ name: home[1], href: `/domain/${home[0]}?tab=${encodeURIComponent(home[1])}` }] : [];
  if (!tabs) return [...lead, { name: "Domain", href: `/domain/${firstDomain(c)}` }, { name: "Playground", href: "/playground" }, AGENTS_MODULE, BROWSER_MODULE, MODEL_MODULE];
  return [...lead, ...tabs.map((n) => ({ name: n, href: null })), { name: "Playground", href: "/playground" }, AGENTS_MODULE, BROWSER_MODULE, MODEL_MODULE];
}
const domainsOf = (c: Ctx) => c.domains.map((d) => ({ slug: d.slug, name: d.name, entity: d.entity }));
const pagePayload = (c: Ctx, name: string, extra: any = {}) =>
  ({ ...extra, base: `/domain/${PLAYGROUND_SLUG}`, name, domains: domainsOf(c), modules: modulesOf(c) });

function homePage(c: Ctx): string {
  const gridStyle = "grid-template-columns:repeat(auto-fill,minmax(420px,1fr));grid-auto-flow:dense;align-content:start";
  return shell({ title: "dev-console", body: `<div class="${COLUMN}">
<div id="home-grid" style="display:none;${gridStyle}" class="flex-1 min-h-0 overflow-auto grid gap-3 p-3"></div>
${statusBar("Home", false, false)}${switcher()}${dataScript(pagePayload(c, "Home"))}
<script type="module">${PLAYGROUND_JS.replace("'/playground'", "'/'")}</script><script>${HOME_JS}</script></div>` });
}

function agentsPage(c: Ctx): string {
  const btn = "px-2 rounded border border-transparent cursor-pointer";
  // spans without role="button": MonsterUI paints <button> and role="button" as blue filled buttons
  const chip = (k: string) => `<span id="c-${k}" tabindex="0" class="${btn}">${k}</span>`;
  const tools = `<div class="h-9 shrink-0 flex items-center gap-2 px-3 border-b ${LINE} text-neutral-500">
<span id="v-prompts" tabindex="0" class="px-2 cursor-pointer">Prompts</span><span id="v-log" tabindex="0" class="px-2 cursor-pointer">Log</span>
<select id="sess" class="h-6 max-w-[28rem] bg-transparent border border-neutral-300 rounded px-1"></select>
${chip("cross")}${chip("notification")}${chip("other")}${chip("side")}
<span id="pause" tabindex="0" class="ml-auto px-2 cursor-pointer whitespace-nowrap"></span><span id="live" class="whitespace-nowrap"></span></div>`;
  // the module's own script reuses the Playground's preamble + the one switcher script, with ⌘P's current module set
  const pre = PLAYGROUND_JS.replace("'/playground'", "'/agents'");
  return shell({ title: "dev-console · Agents", body: `<div class="${COLUMN}">${tools}
<div id="warn" class="px-3 text-amber-600 empty:hidden"></div><div id="aglist" class="flex-1 min-h-0 overflow-y-auto"></div>
${statusBar("Agents", false, false)}${switcher()}${dataScript(pagePayload(c, "Agents"))}<script type="module">${pre + AGENTS_JS}</script></div>` });
}

/** The Browser module: an address line and the page in a frame filling the console, above the status line. An agent opens
 *  it with `devc browse <url>` (a local dev server, a landing to validate); the owner types another address in the line.
 *  Pages that forbid frames (X-Frame-Options) show blank: open those in the Mac's browser. */
function browserPage(c: Ctx, url: string): string {
  const js = `
    const f = document.getElementById('bframe'), a = document.getElementById('baddr');
    const go = u => { if (!u) return; if (!/^[a-z]+:\\/\\//i.test(u)) u = 'http://' + u;
      f.src = u; a.value = u; history.replaceState(null, '', '/browser?url=' + encodeURIComponent(u)); };
    a.addEventListener('keydown', e => { if (e.key === 'Enter') go(a.value.trim()); });
    document.getElementById('breload').addEventListener('click', () => { f.src = f.src; });
    document.getElementById('bout').addEventListener('click', () => window.open(f.src, '_blank'));`;
  const btn = "px-2 cursor-pointer text-neutral-500 hover:text-neutral-900";
  const pre = PLAYGROUND_JS.replace("'/playground'", "'/browser'");
  return shell({ title: "dev-console · Browser", body: `<div class="${COLUMN}">
<div class="h-9 shrink-0 flex items-center gap-2 px-3 border-b ${LINE}"><span id="breload" title="recarregar" tabindex="0" class="${btn}">↻</span>
<input id="baddr" spellcheck="false" placeholder="endereço (localhost:4321)" value="${esc(url)}" class="flex-1 h-6 bg-transparent border ${LINE} rounded px-2 text-neutral-800">
<span id="bout" title="abrir no navegador do Mac" tabindex="0" class="${btn}">↗</span></div>
<iframe id="bframe" ${url ? `src="${esc(url)}" ` : ""}class="flex-1 min-h-0 w-full bg-white" ${url ? 'allow="clipboard-read; clipboard-write; fullscreen"' : ""}></iframe>
${statusBar("Browser", false, false)}${switcher()}${dataScript(pagePayload(c, "Browser"))}<script type="module">${pre}</script><script>${js}</script></div>` });
}

async function playgroundPage(c: Ctx): Promise<string> {
  const money = await c.host.call("money_bar", { slug: PLAYGROUND_SLUG }).catch(() => null); // loading never ends a stretch
  return shell({ title: "dev-console · Playground",
    head: `<link rel="stylesheet" href="https://unpkg.com/tldraw@3.15.4/tldraw.css"><link rel="stylesheet" href="${PG_PREFIX}/web/app.css">`,
    body: `<div class="${COLUMN}"><div id="canvas" class="flex-1 min-h-0"></div>${statusBar("Playground", !!money, false)}${switcher()}
${dataScript(pagePayload(c, "Playground", { money }))}<script type="module">${PLAYGROUND_JS}</script><script type="module">${MONEY_JS}</script>
<script type="module" src="${PG_PREFIX}/web/canvas.js"></script><script type="module" src="${PG_PREFIX}/web/eventos.js"></script></div>` });
}

/** A domain page: the entity rail, the module in place, the inspector, the popup, the switcher and the page's data. */
async function domainPage(c: Ctx, d: DomainInfo, tid: string, embed: string): Promise<string | null> {
  const money = embed === "" || embed === "money" ? await c.host.call("money_bar", { slug: d.slug }).catch(() => null) : null; // an embed neither runs the clock nor ends another domain's stretch
  const data = await c.host.call("page", { slug: d.slug, tid });
  if (!data) return null;
  const { rail, title, entity, entity_plural, sub: _sub, ...rest } = data;
  const payload = { money, ...rest, modules: modulesOf(c, data.tabs), domains: domainsOf(c) };
  delete (payload as any).rail;
  const base = data.base;
  const head = `px-4 pt-3 pb-1 text-[11px] uppercase tracking-widest text-neutral-500`;
  const railHtml = (rail as any[]).map((t) => {
    const on = t.id === tid;
    const subline = [t.status, t.event_count !== null && t.event_count !== undefined ? `${t.event_count} eventos` : ""].filter(Boolean).join(" · ");
    return `<div onclick="location.href='${esc(base)}/t/${esc(encodeURIComponent(t.id))}'+location.search" class="px-4 py-2 cursor-pointer border-l-2 ${on ? "border-neutral-900 bg-neutral-100" : "border-transparent hover:bg-neutral-100"}">` +
      `<div class="truncate ${on ? "font-semibold text-neutral-900" : "text-neutral-600"}">${esc(t.title)}</div><div class="text-neutral-400">${esc(subline)}</div></div>`;
  }).join("");
  return shell({ title: `dev-console · ${title}`, body: `<div class="${COLUMN}">
<div id="work" class="flex-1 min-h-0 flex">
<div id="rail" class="w-56 shrink-0 overflow-y-auto border-r ${LINE}"><div class="${head}">${esc(entity_plural)}</div>${railHtml}</div>
<div id="main" class="flex-1 min-w-0 min-h-0 overflow-y-auto"></div>
<div id="side" class="w-80 shrink-0 overflow-y-auto border-l ${LINE}"><div class="${head}">inspector</div><div id="inspector" class="px-4 pb-4 whitespace-pre-wrap break-words text-neutral-600"></div></div></div>
${statusBar(data.name, !!money)}
<div id="pop" class="hidden fixed inset-0 z-[10000] items-center justify-center bg-black/40 backdrop-blur-[1px]">
<div class="w-[min(860px,92vw)] max-h-[82vh] flex flex-col rounded-lg border border-neutral-300 bg-white shadow-2xl">
<div class="shrink-0 flex items-start justify-between gap-4 px-6 pt-5 pb-3 border-b border-neutral-200">
<div class="min-w-0"><div id="pop-name" class="font-sans text-lg font-semibold text-neutral-900"></div><div id="pop-sub" class="text-neutral-400"></div></div>
<div id="pop-mode" title="SIMULADO: os botões funcionam, nada é gravado nem enviado" class="ml-auto mr-3 shrink-0 flex rounded border border-neutral-300 text-[11px] tracking-widest">
<span data-mode="real" class="mode px-2.5 h-7 leading-7 cursor-pointer select-none">REAL</span><span data-mode="sim" class="mode px-2.5 h-7 leading-7 cursor-pointer select-none">SIMULADO</span></div>
<div id="pop-close" title="Esc" class="shrink-0 px-2 cursor-pointer text-neutral-400 hover:text-neutral-900">✕</div></div>
<div id="pop-body" class="flex-1 min-h-0 overflow-y-auto px-6 py-5"></div></div></div>
${switcher()}${dataScript(payload)}
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/layout-base@2.0.1/layout-base.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cose-base@2.2.0/cose-base.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-fcose@2.2.0/cytoscape-fcose.js"></script>
<script type="module">${JS}</script><script type="module">${MONEY_JS}</script></div>` });
}

/** What a widget route answers: a fragment for HTMX (the popup, the home), a whole page for a plain request (an iframe). */
const fragment = (c: any, html: string) => c.req.header("hx-request")
  ? c.html(html)
  : c.html(shell({ title: "dev-console", body: html }));
const notFoundPage = (msg: string) => shell({ title: "não encontrado", body: `<div class="p-8 font-mono text-sm">${esc(msg)}</div>` });

// ------------------------------------------------------------------------------------------------------------------
// The routes. Same paths, same JSON shapes and same ports as the FastHTML console: devc, console.sh, check.sh and the
// skills that call the console (interview, thread, widgets, kanban) keep working. Reading is open; writing stays
// `PROJECT.ACTIONS` at /domain/<slug>/do/<eid>/<name> (the project's own code, run by the project host).
// ------------------------------------------------------------------------------------------------------------------
export type App = Ctx & { liveClients: number; onLive: Set<(msg: string) => void>; instanceOrigin: Record<string, string> };

/** One JSON line in the clock's log (the same file and shape costs.py writes); never throws. */
function clockLog(hop: string, fields: Record<string, unknown> = {}): void {
  try {
    const p = CLOCK_LOG();
    mkdirSync(dirname(p), { recursive: true });
    const ms = Date.now(), d = new Date(ms), pad = (n: number, w = 2) => String(n).padStart(w, "0");
    const ts = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(ms % 1000, 3)}`;
    appendFileSync(p, JSON.stringify({ ts, ms, hop, ...fields }) + "\n");
  } catch { /* never raises */ }
}

/** A Server-Sent-Events response whose producer returns its own cleanup. */
function sse(signal: AbortSignal, start: (send: (s: string) => void) => (() => void) | void, headers: Record<string, string> = {}): Response {
  const enc = new TextEncoder();
  let cleanup: (() => void) | void, done = false;
  const body = new ReadableStream({
    start(ctl) {
      const finish = () => { if (done) return; done = true; try { (cleanup as any)?.(); } catch { /* gone */ } try { ctl.close(); } catch { /* closed */ } };
      const send = (s: string) => { try { ctl.enqueue(enc.encode(s)); } catch { finish(); } };
      cleanup = start(send);
      signal.addEventListener("abort", finish);
    },
    cancel() { done = true; try { (cleanup as any)?.(); } catch { /* gone */ } },
  });
  return new Response(body, { headers: { "content-type": "text/event-stream", "cache-control": "no-cache", "x-accel-buffering": "no", ...headers } });
}

function pageDataOf(app: App, data: any, money: any = null): any {
  const { rail: _r, title: _t, entity: _e, entity_plural: _p, sub: _s, base, name, tabs, journal_types, events, state, model, entities, home,
    module_aliases, module_widgets, entity_parts } = data;
  return { money, base, name, tabs, modules: modulesOf(app, tabs), domains: domainsOf(app), journal_types, events, state, model, entities, home,
    module_aliases, module_widgets, entity_parts };
}

export function createApp(app: App): Hono {
  const h = new Hono();
  const domain = (slug: string) => app.domains.find((d) => d.slug === slug);
  const q = (c: any, k: string, d = "") => c.req.query(k) ?? d;
  const hostCall = (op: string, args: any) => app.host.call(op, args);

  // DNS rebinding: a page on another domain pointed at 127.0.0.1 would otherwise read /agents/api/prompts. Any other Host
  // gets a 400. No CORS is configured anywhere, on purpose: the console is read by its own pages only.
  h.use("*", async (c, next) => {
    const host = (c.req.header("host") || "").split(":")[0];
    const allowed = allowedHosts();
    if (!allowed.includes("*") && !allowed.includes(host)) return c.text("Invalid host header", 400);
    await next();
  });
  h.onError((err, c) => {
    console.error(`dev-console: ${c.req.method} ${c.req.path}: ${err.message}`);
    return c.text(`erro: ${err.message}`, 500);
  });

  // --- live reload (a project changed, or this server came back) ---
  h.get("/__live", (c) => sse(c.req.raw.signal, (send) => {
    send("data: hello\n\n");
    const fn = (msg: string) => send(`data: ${msg}\n\n`);
    app.onLive.add(fn);
    const ka = setInterval(() => send(": keepalive\n\n"), 15000);
    return () => { app.onLive.delete(fn); clearInterval(ka); };
  }));

  // --- the home ---
  h.get("/", (c) => c.html(homePage(app)));
  h.get("/api/home", () => jsonResponse({ widgets: homeList() }));
  h.post("/api/home/show", async (c) => {
    try {
      const raw = await c.req.text();
      const body = raw ? JSON.parse(raw) : {};
      if (!isObj(body)) throw new Error("body must be a JSON object");
      return jsonResponse(homeShow(body, c.req.header("x-devc-actor") || "agent"));
    } catch (e) { return jsonResponse({ error: (e as Error).message }, 400); }
  });
  h.post("/api/home/rm", async (c) => {
    const raw = await c.req.text();
    const ok = homeRemove(String((raw ? JSON.parse(raw) : {}).id || ""));
    return jsonResponse({ removed: ok }, ok ? 200 : 404);
  });
  h.post("/api/home/clear", (c) => { homeClear(c.req.header("x-devc-actor") || "agent"); return jsonResponse({ cleared: true }); });
  h.get("/api/home/stream", (c) => sse(c.req.raw.signal, (send) => {
    const stop = homeChanges((snap) => send(`data: ${snap}\n\n`));
    const ka = setInterval(() => send(": keepalive\n\n"), 15000);
    return () => { stop(); clearInterval(ka); };
  }));

  // --- small reads ---
  h.get("/api/claude-usage", () => {
    // The weekly limit of the owner's Claude accounts (claude-usage.sh's cache). Refreshed in the background when it is
    // over 5 minutes old, so a page load never waits on Anthropic.
    const out = resolve(expand("~/.local/state/dev-console/claude-usage.json")), script = join(HERE, "claude-usage.sh");
    const age = Date.now() / 1000 - mtimeOf(out);
    if ((mtimeOf(out) === 0 || age > 300) && isFile(script)) {
      try { Bun.spawn(["bash", script], { stdin: "ignore", stdout: "ignore", stderr: "ignore" }).unref(); } catch { /* no bash: the bar stays as it is */ }
    }
    try { return new Response(readText(out), { headers: { "content-type": "application/json" } }); }
    catch { return new Response('{"accounts":[]}', { headers: { "content-type": "application/json" } }); }
  });
  h.post("/clock/applied", async (c) => {
    // The page's beacon: it swapped the new clock in (push_ms = the push it reacts to).
    let push = 0;
    try { push = Number((JSON.parse((await c.req.text()) || "{}")).push_ms) || 0; } catch { push = 0; }
    clockLog("page_applied", { push_ms: push || null, lag_ms: push ? Date.now() - push : null });
    return new Response(null, { status: 204 });
  });
  h.get("/api/focus", () => {
    // The focused thread, folded from the tmux focus stream (its last event): {"thread": topic | "", "session", "ms"}.
    try {
      const last = readText(FOCUS_LOG()).trim().split("\n").pop()!;
      if (!last) throw new Error("empty");
      return new Response(last, { headers: { "content-type": "application/json" } });
    } catch { return new Response('{"thread": ""}', { headers: { "content-type": "application/json" } }); }
  });
  h.get("/live/stream", (c) => {
    // One line the instant a journal is written: `costs` (the Costs journal or running.json, COSTS_DIR), `focus` (the tmux
    // focus stream) or `journal` (a folder a project lists in `LIVE_DIRS()`, the Kanban's). fs.watch follows them with no
    // debounce (FSEvents on macOS), so the page swaps its fragment within milliseconds. The pages' own 10 s refresh stays.
    const folders = new Map<string, string>([[COSTS_DIR(), "costs"], [dirname(FOCUS_LOG()), "focus"]]);
    for (const d of app.domains) for (const f of d.live_dirs) if (!folders.has(f)) folders.set(f, "journal");
    return sse(c.req.raw.signal, (send) => {
      app.liveClients++;
      send("data: hello\n\n");
      const watchers: FSWatcher[] = [];
      const lastPush = new Map<string, number>();
      for (const [dir, kind] of folders) {
        if (!isDir(dir)) continue;
        try {
          watchers.push(fsWatch(dir, (_ev, file) => {
            const f = String(file || "");
            if (!(f.endsWith(".jsonl") || f.endsWith(".json"))) return;
            const now = Date.now();
            if (now - (lastPush.get(kind) || 0) < 20) return; // a write is often two events
            lastPush.set(kind, now);
            clockLog("console_pushed", { kind, clients: app.liveClients });
            send(`data: ${kind} ${now}\n\n`);
          }));
        } catch { /* a folder that cannot be watched is skipped */ }
      }
      const ka = setInterval(() => send(": keepalive\n\n"), 5000);
      return () => { app.liveClients--; for (const w of watchers) w.close(); clearInterval(ka); };
    });
  });

  // --- agents ---
  const hub = () => (app.hub ? app.hub() : getHub());
  const agentArgs = (c: any, limit: number) => ({ limit: Math.trunc(Number(q(c, "limit", String(limit)))) || limit, session: q(c, "session"), side: ["1", "true"].includes(q(c, "side")) });
  const ready = async () => { const hb = hub(); await Promise.race([hb.ready, sleep(15000)]); return hb; };
  h.get("/agents/api/prompts", async (c) => {
    const a = agentArgs(c, 200);
    return jsonResponse((await ready()).getPrompts(a.limit, a.session, q(c, "kinds", "prompt").split(",").filter(Boolean), a.side));
  });
  h.get("/agents/api/log", async (c) => { const a = agentArgs(c, 500); return jsonResponse((await ready()).getLog(a.limit, a.session, a.side)); });
  h.get("/agents/api/entry", async (c) => {
    const e = (await ready()).getEntry(q(c, "id"));
    return jsonResponse(e || { error: "unknown entry" }, e ? 200 : 404);
  });
  h.get("/agents/events", async (c) => agentsSse(await ready(), c.req.header("last-event-id") || q(c, "after"), c.req.raw.signal));
  h.get("/agents", (c) => c.html(agentsPage(app)));

  // --- the money bar: the Costs journal is the only storage; the project host owns the Python writer (cost-track) ---
  const money = (action: string) => async (c: any) => {
    const slug = c.req.param("slug");
    const known = domain(slug) || (slug === PLAYGROUND_SLUG);
    if (!known) return jsonResponse({ error: "no such domain" }, 404);
    const r = await hostCall("money", { slug, action, ended_by: q(c, "ended_by", "pause"), trim_seconds: Number(q(c, "trim_seconds", "0")) || 0 });
    return jsonResponse(r.body, r.status);
  };
  h.all("/domain/:slug/time", money("state"));
  h.post("/domain/:slug/time/enter", money("enter"));
  h.post("/domain/:slug/time/start", money("start"));
  h.post("/domain/:slug/time/beat", money("beat"));
  h.post("/domain/:slug/time/stop", money("stop"));

  // --- a domain: widgets, actions, media, state, page ---
  h.all("/domain/:slug/do/:eid/:name", async (c) => {
    const slug = c.req.param("slug");
    if (!domain(slug)) return fragment(c, `<p class="text-neutral-500">${esc(`domínio ${slug} não existe`)}</p>`);
    const html = await hostCall("action", { slug, eid: c.req.param("eid"), name: c.req.param("name"), mode: q(c, "mode", "real"), step: Number(q(c, "step", "0")) || 0 });
    return fragment(c, html);
  });
  h.get("/domain/:slug/w/:tid/:event/:name", async (c) => {
    const slug = c.req.param("slug");
    if (!domain(slug)) return fragment(c, `<p class="text-neutral-400">${esc(`domínio ${slug} não existe`)}</p>`);
    const html = await hostCall("widget", { slug, tid: c.req.param("tid"), event: c.req.param("event"), name: c.req.param("name"),
      e: q(c, "e"), mode: q(c, "mode", "real"), domain: q(c, "domain"), task: q(c, "task") });
    return fragment(c, html);
  });
  h.get("/domain/:slug/w/:tid/:event", async (c) => {
    const slug = c.req.param("slug");
    if (!domain(slug)) return fragment(c, `<p class="text-neutral-400">${esc(`domínio ${slug} não existe`)}</p>`);
    return fragment(c, await hostCall("widget_list", { slug, tid: c.req.param("tid"), event: c.req.param("event"), e: q(c, "e") }));
  });
  h.get("/domain/:slug/media", (c) => {
    // A file the domain keeps with its records (MEDIA in the project file: pictures of a run), never outside it.
    const d = domain(c.req.param("slug"));
    const root = resolve(expand(d?.media || "/nonexistent"));
    let file = "";
    try { file = realpathSync(join(root, q(c, "f"))); } catch { /* missing */ }
    const rootReal = (() => { try { return realpathSync(root); } catch { return root; } })();
    if (!d || !file.startsWith(rootReal + sep) || !isFile(file)) return c.text("não encontrado", 404);
    return new Response(Bun.file(file));
  });
  h.get("/domain/:slug/source/stream", (c) => {
    // The real model again whenever the domain's SOURCE (or its draft) changes on disk.
    const d = domain(c.req.param("slug"));
    if (!d) return c.text("domínio não existe", 404);
    return sse(c.req.raw.signal, (send) => {
      let last = "", busy = false;
      const tick = async () => {
        if (busy) return;
        const m = `${mtimeOf(d.source)}:${mtimeOf(d.draft)}`;
        if (m === last) return;
        busy = true;
        try { const model = await hostCall("model", { slug: d.slug }); last = m; send(`data: ${JSON.stringify(model)}\n\n`); }
        catch { /* the source is mid-save: the next tick retries */ }
        finally { busy = false; }
      };
      void tick();
      const t = setInterval(tick, 1000);
      return () => clearInterval(t);
    });
  });
  h.get("/api/domains", () => jsonResponse(app.domains.map((d) => ({ slug: d.slug, name: d.name, path: d.path, origin: d.origin }))));
  h.get("/api/domains/:slug/actions", (c) => {
    const d = domain(c.req.param("slug"));
    return d ? jsonResponse(d.actions) : jsonResponse({ error: `domain ${c.req.param("slug")} does not exist` }, 404);
  });
  h.get("/domain/:slug/state.json", async (c) => {
    const slug = c.req.param("slug");
    if (!domain(slug)) return jsonResponse({ error: `domain ${slug} does not exist`, domains: app.domains.map((d) => d.slug) }, 404);
    const data = await hostCall("state", { slug, task: q(c, "task") });
    return data ? jsonResponse(pageDataOf(app, data)) : jsonResponse({ error: "no such entity (or an empty journal)" }, 404);
  });
  h.get("/domain/:slug/t/:tid", async (c) => {
    const d = domain(c.req.param("slug"));
    if (!d) return c.redirect("/", 303);
    const page = await domainPage(app, d, c.req.param("tid"), q(c, "embed"));
    return c.html(page ?? notFoundPage(`${d.entity} não encontrado(a).`));
  });
  h.get("/domain/:slug", async (c) => {
    const slug = c.req.param("slug");
    if (slug === PLAYGROUND_SLUG && !domain(slug)) return c.redirect("/playground", 303);
    const d = domain(slug);
    if (!d) return c.html(shell({ title: "não encontrado", body: `<div class="p-8 font-mono text-sm">${esc(`Domínio ${slug} não existe. Há: ${app.domains.map((x) => x.slug).join(", ")}.`)}</div>` }));
    const r = await hostCall("default_entity", { slug });
    if (r.empty) return c.html(shell({ title: d.name, body: `<div class="p-8 font-mono text-sm">${esc(`Nenhum(a) ${d.entity} no diário.`)}</div>` }));
    const qs = new URL(c.req.url).search; // keep the view (?tab=…&ev=…) across the redirect
    return c.redirect(`/domain/${slug}/t/${encodeURIComponent(r.id)}${qs}`, 303);
  });

  // --- the Browser, the Model, the Playground ---
  h.get("/browser", (c) => c.html(browserPage(app, q(c, "url"))));
  h.get("/model", (c) => {
    const ds = dmDomains();
    if (ds.length === 1) return c.redirect(`/model/${ds[0].slug}`);
    const items = ds.map((d) => `<li><a href="/model/${esc(d.slug)}">${esc(d.name)}</a> · ${esc(d.status)}</li>`).join("") || "<li>nenhum domínio modelado (skill domain-model)</li>";
    return c.html(`<!doctype html><meta charset=utf-8><title>Modelos</title><style>body{font:15px system-ui;padding:16px 24px;background:#fafaf9;color:#1c1917}a{color:inherit}</style><h1>Modelos</h1><ul>${items}</ul>`);
  });
  h.get("/model/:file{[^/]+\\.mmd}", (c) => {
    const slug = c.req.param("file").slice(0, -4);
    const ds = modelDiagrams(slug).map((diagram) => ({ diagram, title: MODEL_TITLES[diagram] || diagram, mermaid: modelMermaid(slug, diagram) }));
    return jsonResponse({ slug, version: modelVersion(ds.map((x) => x.mermaid).join("")), diagrams: ds, mermaid: ds[0].mermaid });
  });
  h.get("/model/:slug", (c) => {
    const slug = c.req.param("slug");
    const d = dmDomains().find((x) => x.slug === slug);
    if (!d) return c.html(`domínio ${esc(slug)} não está em dm_domain`, 404);
    return c.html(MODEL_PAGE(esc(d.name), esc(d.name), esc(d.purpose || ""), `/model/${esc(slug)}.mmd`));
  });
  mountPlayground(h, app.playground);
  h.get("/playground", async (c) => c.html(await playgroundPage(app)));
  return h;
}

// ------------------------------------------------------------------------------------------------------------------
// Start-up, project reload and the command line.
// ------------------------------------------------------------------------------------------------------------------
/** What the watcher ignores (the defaults of the old watchfiles filter): caches, VCS, editor swap files. */
const IGNORED = /(^|\/)(__pycache__|\.git|node_modules|\.venv|\.mypy_cache|\.pytest_cache)(\/|$)|\.(pyc|pyo|swp|swo|tmp)$|~$|\.DS_Store$|(^|\/)\.#/;

/** Start the project host, mirror its widgets in SQLite and return the pieces `createApp` needs. */
export async function boot(flags: string[], live: boolean) {
  LIVE = live;
  storeInit();
  const extra = registered().filter((p) => !flags.includes(p));
  const host = new Host(flags, extra);
  const info = await host.start();
  syncWidgets(info.catalog);
  const app: App = { domains: info.domains, host, playground: new Playground(), liveClients: 0, onLive: new Set(), instanceOrigin: {} };
  return app;
}

/** Restart the project host (a project folder or the registry changed): a new process is a clean reload, nothing is purged.
 *  The pages are told to reload when `live`. */
export async function reloadHost(app: App, flags: string[], live: boolean): Promise<void> {
  const next = new Host(flags, registered().filter((p) => !flags.includes(p)));
  let info: Ready;
  try { info = await next.start(); }
  catch (e) { console.error(`dev-console: reload failed, keeping the old projects: ${(e as Error).message}`); next.stop(); return; }
  const old = app.host;
  app.host = next;
  app.domains = info.domains;
  try { syncWidgets(info.catalog); } catch (e) { console.error(`dev-console: widgets table: ${(e as Error).message}`); }
  old.stop();
  if (live) for (const fn of [...app.onLive]) fn("reload");
}

/** Watch the project folders (and the registry file); on a change, reload after a short quiet moment. */
function watchProjects(app: App, flags: string[], live: boolean): () => void {
  let watchers: FSWatcher[] = [], watched = "", timer: ReturnType<typeof setTimeout> | null = null, busy = false, again = false;
  const registry = REGISTRY();
  const fire = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(async () => {
      if (busy) { again = true; return; }
      busy = true;
      try { await reloadHost(app, flags, live); arm(); } finally { busy = false; if (again) { again = false; fire(); } }
    }, 100);
  };
  const arm = () => {
    const dirs = [...new Set(app.host.info.watch)].sort();
    if (dirs.join("\n") === watched) return;
    for (const w of watchers) w.close();
    watched = dirs.join("\n");
    watchers = dirs.map((d) => { try { return fsWatch(d, { recursive: true }, (_ev, f) => { if (f && !IGNORED.test(String(f)) && !String(f).endsWith(".ts")) fire(); }); } catch { return null; } }).filter(Boolean) as FSWatcher[];
    try { // a new domain: the registry file changed (only that file; its folder holds other writers' files)
      watchers.push(fsWatch(dirname(registry), (_ev, f) => { if (f && join(dirname(registry), String(f)) === registry) fire(); }));
    } catch { /* no registry folder yet */ }
  };
  arm();
  return () => { for (const w of watchers) w.close(); };
}

export function parseArgs(argv: string[]) {
  const projects: string[] = [];
  let port = 5057, noLive = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--project") projects.push(argv[++i]);
    else if (a.startsWith("--project=")) projects.push(a.slice(10));
    else if (a === "--port") port = Number(argv[++i]);
    else if (a.startsWith("--port=")) port = Number(a.slice(7));
    else if (a === "--no-live") noLive = true;
    else if (a === "-h" || a === "--help") return { help: true, projects, port, noLive };
    else throw new Error(`unknown argument: ${a}`);
  }
  const fromEnv = env("DEV_CONSOLE_PROJECT").split(delimiter).filter(Boolean);
  // `bun --cwd <skill>` moves the process; the shell's own folder is still $PWD, so a relative --project means that one
  const here = env("PWD") || process.cwd();
  const abs = (p: string) => { const x = expand(p); return isAbsolute(x) ? x : resolve(here, x); };
  const all = [...new Set([...projects, ...fromEnv].map((p) => { try { return realpathSync(abs(p)); } catch { return abs(p); } }))];
  return { help: false, projects: all, port, noLive: noLive || env("DEV_CONSOLE_LIVE", "1") === "0" };
}

const USAGE = `dev-console: a read-only console for an event-sourced project in development
usage: bun dev-console.ts --project <path/to/dev_console_project.py> [--project <...>] [--port 5057] [--no-live]
       bun dev-console.ts playground import [<dados dir>] [--force]
  --project   one dev_console_project.py per domain (repeat), or DEV_CONSOLE_PROJECT (':'-separated), plus the registry
  --no-live   never reload the open pages on a save (a second instance that one agent drives)`;

export async function main(argv: string[]): Promise<void> {
  if (argv[0] === "playground") { // console.sh playground import [<dados dir>] [--force]
    const rest = argv.slice(1), force = rest.includes("--force"), pos = rest.filter((a) => a !== "--force");
    if (pos[0] !== "import" && rest[0] !== "import") { console.error("usage: dev-console.ts playground import [<dados dir>] [--force]"); process.exit(2); }
    const src = resolve(expand(pos[1] || "~/biliboss/dev/design-playground/dados")), dst = playgroundDir();
    try { console.log(`importei ${importarPlayground(src, dst, force).join(", ")} de ${src} para ${dst}`); }
    catch (e) { console.error((e as Error).message); process.exit(1); }
    return;
  }
  const args = parseArgs(argv);
  if (args.help) { console.log(USAGE); return; }
  if (!args.projects.length && !registered().length) {
    console.error("dev-console: pass --project <path/to/dev_console_project.py> (or set DEV_CONSOLE_PROJECT)");
    process.exit(2);
  }
  const live = !args.noLive;
  const app = await boot(args.projects, live);
  const hono = createApp(app);
  let server: ReturnType<typeof Bun.serve>;
  try { server = Bun.serve({ port: args.port, hostname: "127.0.0.1", fetch: hono.fetch, idleTimeout: 0 }); }
  catch (e) { console.error(`dev-console: cannot listen on 127.0.0.1:${args.port}: ${(e as Error).message}`); app.host.stop(); process.exit(1); }
  const unwatch = watchProjects(app, args.projects, live);
  console.log(`dev-console on http://127.0.0.1:${server.port}/ (${app.domains.map((d) => d.slug).join(", ")})${live ? "" : " [no live reload]"}`);
  const bye = () => { unwatch(); stopHub(); app.host.stop(); server.stop(true); process.exit(0); };
  process.on("SIGINT", bye);
  process.on("SIGTERM", bye);
  process.on("exit", () => app.host.stop());
}

if (import.meta.main) await main(process.argv.slice(2));

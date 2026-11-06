/**
 * Tests of dev-console.ts (bun test). Everything runs against temp folders and a temp database (DEV_CONSOLE_DB,
 * DEV_CONSOLE_REGISTRY, COSTS_DIR, DEV_CONSOLE_PLAYGROUND_DIR); never the owner's. The live part starts a real console
 * on a test port (env DEVC_TEST_PORT, default 5097) with the dev-console's own project, an empty registry and a temp
 * costs dir.
 * Run:  tmux/scripts/run.sh start dev-console-test --low --slot -- bun --cwd <skill> test scripts/dev-console.test.ts
 */
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { Database } from "bun:sqlite";
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, statSync, symlinkSync, unlinkSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import * as C from "./dev-console";

const HERE = import.meta.dir;
const tmp = (p = "dc-test-") => mkdtempSync(join(tmpdir(), p));
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function until<T>(fn: () => T | Promise<T>, ms = 5000): Promise<T> {
  const end = Date.now() + ms;
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() > end) throw new Error("timed out waiting");
    await sleep(20);
  }
}

// ---------------------------------------------------------------------------------------------------- the normalizer
const SRC = C.SOURCES.claude;
const fsFor = (name = "abcdef12-0000.jsonl"): C.FileState => ({ path: `/x/proj/${name}`, key: "k1", source: "claude", session: name.slice(0, 8), project: "proj",
  sideFile: name.startsWith("agent-"), offset: 0, seenSize: -1, seenMtime: 0, resync: false, gone: false, mtime: 0, title: "" });
const line = (kw: any = {}) => Buffer.from(JSON.stringify({ type: "user", timestamp: "2026-01-02T03:04:05.000Z", cwd: "/w/demo", isSidechain: false, ...kw }));
const norm = (raw: Buffer, off = 0, fs = fsFor()) => SRC.normalize(raw, off, fs);
const human = (content: any, extra: any = {}) => line({ message: { content }, origin: { kind: "human" }, promptSource: "typed", ...extra });

describe("normalizer", () => {
  test("a typed string is a prompt", () => {
    const e = norm(line({ message: { content: "hello" }, origin: { kind: "human" }, promptSource: "typed", turnOrigin: "human" }), 42);
    expect([e.kind, e.text, e.more, e.id, e.project, e.session]).toEqual(["prompt", "hello", false, "k1:42", "demo", "abcdef12"]);
  });
  test("a queued human line is a prompt with a mark; queued peer stays cross", () => {
    const e = norm(line({ message: { content: "while busy" }, origin: { kind: "human" }, promptSource: "queued" }));
    expect([e.kind, e.queued]).toEqual(["prompt", true]);
    expect(norm(human("x")).queued).toBe(false);
    expect(norm(line({ message: { content: "x" }, origin: { kind: "peer" }, promptSource: "queued" })).kind).toBe("cross");
  });
  test("a queued_command attachment is read by origin", () => {
    const att = (origin: any, prompt: any = "mid-turn") => line({ type: "attachment", timestamp: "2026-01-02T03:04:06.000Z",
      attachment: { type: "queued_command", commandMode: "prompt", prompt, ...(origin ? { origin } : {}) } });
    const e = norm(att({ kind: "human" }), 7);
    expect([e.kind, e.queued, e.text, e.id, e.t]).toEqual(["prompt", true, "mid-turn", "k1:7", "2026-01-02T03:04:06.000Z"]);
    const p = norm(att({ kind: "peer", name: "other" }));
    expect([p.kind, p.text, p.queued]).toEqual(["cross", "other: mid-turn", false]);
    expect(norm(att({ kind: "task-notification" })).kind).toBe("notification");
    for (const o of [{ kind: "weird" }, {}, null]) expect(norm(att(o)).kind).toBe("other");
    expect(norm(att({ kind: "human" }, [{ type: "text", text: "blocks" }, { type: "image" }])).text).toBe("blocks\n[image]");
  });
  test("malformed attachments and other types are dropped", () => {
    for (const a of [{ type: "queued_command", commandMode: "prompt" }, { type: "queued_command", commandMode: "prompt", prompt: 5 },
      { type: "queued_command", commandMode: "bash", prompt: "x", origin: { kind: "human" } }, { type: "something_else", prompt: "x" }, "text", null, [1]])
      expect(norm(line({ type: "attachment", attachment: a }))).toBeNull();
    expect(norm(line({ type: "attachment" }))).toBeNull();
  });
  test("a big text is capped, a huge line skipped", () => {
    const att = { type: "queued_command", commandMode: "prompt", origin: { kind: "human" }, prompt: "a".repeat(5000) };
    const e = norm(line({ type: "attachment", attachment: att }));
    expect([e.text.length, e.more]).toEqual([C.SHORT, true]);
    expect(norm(line({ type: "attachment", attachment: { ...att, prompt: "a".repeat(C.MAX_LINE + 5) } }))).toBeNull();
    const full = SRC.normalize(human("a".repeat(1000)), 0, fsFor(), true);
    expect(full.text.length).toBe(1000);
  });
  test("array content shows its text and a marker for the image", () => {
    const e = norm(human([{ type: "text", text: "look" }, { type: "image", source: {} }]));
    expect([e.kind, e.text]).toEqual(["prompt", "look\n[image]"]);
  });
  test("peer and task-notification have their own kinds", () => {
    const a = norm(line({ message: { content: "raw" }, origin: { kind: "peer", name: "other", body: "hi" }, promptSource: "system" }));
    expect([a.kind, a.text]).toEqual(["cross", "other: hi"]);
    const b = norm(line({ message: { content: "done" }, origin: { kind: "task-notification" }, promptSource: "system" }));
    expect([b.kind, b.text]).toEqual(["notification", "done"]);
  });
  test("the allow-list: anything unknown is other, never prompt", () => {
    for (const extra of [{}, { origin: { kind: "human" } }, { origin: { kind: "human" }, promptSource: "other-thing" },
      { origin: { kind: "weird" }, promptSource: "typed" }, { promptSource: "typed" }])
      expect(norm(line({ message: { content: "x" }, ...extra })).kind).toBe("other");
  });
  test("tool results are noise; sidechain and agent files are flagged", () => {
    expect(norm(line({ message: { content: [{ type: "tool_result", content: "x" }] } }))).toBeNull();
    expect(norm(human("x", { isSidechain: true })).side).toBe(true);
    expect(norm(human("x"), 0, fsFor("agent-abc123.jsonl")).side).toBe(true);
  });
  test("assistant text, tool use and what the call is about", () => {
    expect(norm(line({ type: "assistant", message: { content: [{ type: "text", text: "ok" }, { type: "tool_use", name: "Bash" }] } })).kind).toBe("assistant");
    expect(norm(line({ type: "assistant", message: { content: [{ type: "tool_use", name: "Bash" }, { type: "tool_use", name: "Read" }] } })).text).toBe("Bash, Read");
    const e = norm(line({ type: "assistant", message: { content: [
      { type: "tool_use", name: "Bash", input: { command: "git status\nsecond line" } },
      { type: "tool_use", name: "Edit", input: { file_path: "/w/demo/pkg/app.py" } },
      { type: "tool_use", name: "Skill", input: { skill: "tmux" } },
      { type: "tool_use", name: "Unknown", input: { x: 1 } }] } }));
    expect(e.text).toBe("Bash: git status, Edit: pkg/app.py, Skill: tmux, Unknown");
  });
  test("/rename names the session and is not an entry", () => {
    const fs = fsFor();
    expect(norm(line({ type: "agent-name", agentName: "ag-fallback" }), 0, fs)).toBeNull();
    expect(fs.title).toBe("ag-fallback");
    expect(norm(line({ type: "custom-title", customTitle: "bili" }), 0, fs)).toBeNull();
    expect(fs.title).toBe("bili");
    norm(line({ type: "agent-name", agentName: "other" }), 0, fs);
    expect(fs.title).toBe("bili");
  });
  test("noise types and garbled lines never throw", () => {
    for (const t of ["attachment", "api-request", "last-prompt", "permission-mode", "mode"]) expect(norm(line({ type: t }))).toBeNull();
    for (const raw of ['{"type":"user","message":{"cont', "not json", "[1,2]", "", "null", '{"type":"user","message":5}'])
      expect(norm(Buffer.from(raw))).toBeNull();
    expect(norm(Buffer.from(`{"type":"api-request-blob","blob":"${"x".repeat(C.MAX_LINE + 10)}"}`))).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------- the tailer
const typed = (text: string, ts = "2026-01-02T03:04:05.000Z") => Buffer.concat([human(text, { timestamp: ts }), Buffer.from("\n")]);
const att = (text: string, ts: string, origin = "human") => Buffer.concat([line({ type: "attachment", timestamp: ts,
  attachment: { type: "queued_command", commandMode: "prompt", origin: { kind: origin }, prompt: text } }), Buffer.from("\n")]);
const queuedUser = (text: string, ts: string) => Buffer.concat([line({ message: { content: text }, origin: { kind: "human" }, promptSource: "queued", timestamp: ts }), Buffer.from("\n")]);

describe("tailer", () => {
  let dir: string, root: string, f: string, hub: C.Hub;
  const texts = () => hub.getPrompts().entries.map((e: any) => e.text);
  const bump = () => { const st = statSync(f); utimesSync(f, st.atimeMs / 1000, st.mtimeMs / 1000 + 2); };
  const setup = async () => {
    dir = tmp(); root = join(dir, "root"); mkdirSync(join(root, "proj"), { recursive: true });
    f = join(root, "proj", "11112222-aaaa.jsonl");
    writeFileSync(f, typed("one"));
    hub = new C.Hub([root]);
    hub.rescan();
    await hub.backfill();
  };

  test("backfill reads the existing tail", async () => { await setup(); expect(texts()).toEqual(["one"]); });
  test("an append gives exactly one new entry", async () => {
    await setup();
    const seq = hub.curSeq();
    appendFileSync(f, typed("two"));
    expect(hub.tick()).toBe(1);
    expect(hub.tick()).toBe(0);
    expect(texts()).toEqual(["one", "two"]);
    expect(hub.since(seq).map((e) => e.text)).toEqual(["two"]);
  });
  test("a partial last line waits for its newline", async () => {
    await setup();
    const whole = typed("three");
    appendFileSync(f, whole.subarray(0, 30));
    expect(hub.tick()).toBe(0);
    appendFileSync(f, whole.subarray(30, -1));
    bump();
    expect(hub.tick()).toBe(0);
    appendFileSync(f, "\n");
    expect(hub.tick()).toBe(1);
    expect(texts()).toEqual(["one", "three"]);
  });
  test("a garbled line in the middle is skipped", async () => {
    await setup();
    appendFileSync(f, Buffer.concat([Buffer.from('{"type":"user","mess\n'), typed("after")]));
    expect(hub.tick()).toBe(1);
    expect(texts()).toEqual(["one", "after"]);
  });
  test("a shrinking file resets and says so", async () => {
    await setup();
    appendFileSync(f, typed("two"));
    hub.tick();
    const seq = hub.curSeq();
    writeFileSync(f, typed("new"));
    bump();
    hub.tick();
    expect(texts()).toEqual(["new"]);
    expect(hub.since(seq).filter((e) => e.kind === "reset").length).toBe(1);
  });
  test("a new file is picked up on rescan", async () => {
    await setup();
    mkdirSync(join(root, "other"));
    writeFileSync(join(root, "other", "33334444-bbbb.jsonl"), typed("fresh"));
    expect(hub.tick()).toBe(0);
    hub.rescan();
    expect(hub.tick()).toBe(1);
    expect(texts()).toEqual(["one", "fresh"]);
    expect(hub.sessions().map((s) => s.session)).toContain("33334444");
  });
  test("a disappearing file keeps the past and does not throw", async () => { await setup(); unlinkSync(f); hub.tick(); expect(texts()).toEqual(["one"]); });
  test("a symlinked root is deduplicated", async () => {
    await setup();
    const link = dir + "-link";
    symlinkSync(root, link);
    process.env[C.ENV_DIRS] = [root, link].join(delimiter);
    try { expect(C.rootsFromEnv().length).toBe(1); } finally { delete process.env[C.ENV_DIRS]; unlinkSync(link); }
  });
  test("prompts filters and the side default", async () => {
    await setup();
    appendFileSync(f, Buffer.concat([line({ message: { content: "peer" }, origin: { kind: "peer" }, promptSource: "system" }), Buffer.from("\n"),
      human("sub", { isSidechain: true }), Buffer.from("\n")]));
    hub.tick();
    expect(texts()).toEqual(["one"]);
    expect(hub.getPrompts(200, "", ["cross"]).entries.map((e: any) => e.text)).toEqual(["peer"]);
    expect(hub.getPrompts(200, "", ["prompt"], true).entries.map((e: any) => e.text)).toEqual(["one", "sub"]);
    expect(hub.getPrompts(200, "zzz").entries).toEqual([]);
  });
  test("the whole text by id, and unknown ids", async () => {
    await setup();
    appendFileSync(f, typed("z".repeat(2000)));
    hub.tick();
    const e = hub.getPrompts().entries.at(-1);
    expect(e.more).toBe(true);
    expect(hub.getEntry(e.id).text.length).toBe(2000);
    expect(hub.getEntry("nokey:0")).toBeNull();
    expect(hub.getEntry("../../etc/passwd")).toBeNull();
  });
  test("an attachment then a user line with the same text is one entry (the earliest)", async () => {
    await setup();
    appendFileSync(f, Buffer.concat([att("  go   on please ", "2026-01-02T04:00:00.000Z"), queuedUser("go on please", "2026-01-02T04:00:40.000Z")]));
    hub.tick();
    const es = hub.getPrompts().entries.filter((e: any) => e.text.split(/\s+/).filter(Boolean).join(" ") === "go on please");
    expect(es.length).toBe(1);
    expect(es[0].queued).toBe(true);
    expect(es[0].t).toBe("2026-01-02T04:00:00.000Z");
  });
  test("the same text beyond the window is two entries; another session is not a duplicate", async () => {
    await setup();
    appendFileSync(f, Buffer.concat([att("repeat", "2026-01-02T04:00:00.000Z"), queuedUser("repeat", "2026-01-02T04:05:00.000Z")]));
    writeFileSync(join(root, "proj", "99990000-eeee.jsonl"), att("same", "2026-01-02T04:00:00.000Z"));
    appendFileSync(f, att("same", "2026-01-02T04:00:10.000Z"));
    hub.rescan();
    hub.tick();
    const t = texts();
    expect(t.filter((x: string) => x === "repeat").length).toBe(2);
    expect(t.filter((x: string) => x === "same").length).toBe(2);
  });
  test("a malformed attachment does not stop the tailer", async () => {
    await setup();
    appendFileSync(f, Buffer.concat([line({ type: "attachment", attachment: { type: "queued_command", commandMode: "prompt" } }), Buffer.from("\n"),
      Buffer.from('{"type":"attachment","attachment":\n'), typed("still alive", "2026-01-02T05:00:00.000Z")]));
    hub.tick();
    expect(texts()).toEqual(["one", "still alive"]);
  });
  test("a reset does not make the re-read prompts look duplicated", async () => {
    await setup();
    appendFileSync(f, typed("pad pad pad pad pad pad"));
    hub.tick();
    writeFileSync(f, typed("one"));
    bump();
    hub.tick();
    expect(texts()).toEqual(["one"]);
  });
  test("seqOf resumes after an id", async () => {
    await setup();
    const first = hub.lastId();
    appendFileSync(f, typed("two"));
    hub.tick();
    expect(hub.since(hub.seqOf(first)!).map((e) => e.text)).toEqual(["two"]);
    expect(hub.seqOf("gone:1")).toBeNull();
  });
  test("running by events: an append arrives fast, a new folder is picked up", async () => {
    await setup();
    hub.start();
    await hub.ready;
    await until(() => hub.mode === "watch");
    const seen: any[] = [];
    hub.subscribe("", (e) => seen.push(e));
    const t0 = Date.now();
    appendFileSync(f, typed("by event"));
    await until(() => seen.some((e) => e.text === "by event"), 3000);
    expect(Date.now() - t0).toBeLessThan(900); // the safety net runs every 5 s: this was the watcher
    mkdirSync(join(root, "newdir"));
    writeFileSync(join(root, "newdir", "55556666-cccc.jsonl"), typed("new folder"));
    await until(() => seen.some((e) => e.text === "new folder"), 7000);
    hub.shutdown();
  });
});

describe("sse", () => {
  test("resumes after an id, replays only what follows, and sends the keep-alive", async () => {
    const dir = tmp(), root = join(dir, "r");
    mkdirSync(join(root, "p"), { recursive: true });
    const f = join(root, "p", "aaaabbbb-1.jsonl");
    writeFileSync(f, Buffer.concat([typed("a"), typed("b")]));
    const hub = new C.Hub([root]);
    hub.rescan();
    await hub.backfill();
    const first = hub.getPrompts().entries[0].id;
    const ctl = new AbortController();
    const res = C.agentsSse(hub, first, ctl.signal, 100);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const reader = res.body!.getReader(), dec = new TextDecoder();
    let buf = "";
    await until(async () => { const { value } = await reader.read(); buf += dec.decode(value); return buf.includes(": keep-alive"); }, 3000);
    expect(buf).toContain("retry: 3000");
    expect(buf).toContain('"text":"b"');
    expect(buf).not.toContain('"text":"a"');
    ctl.abort();
    expect(hub.subs.size).toBe(0);
  });
  test("the allowed hosts: default and env", () => {
    delete process.env.DEV_CONSOLE_ALLOWED_HOSTS;
    expect(C.allowedHosts()).toEqual(["127.0.0.1", "localhost"]);
    process.env.DEV_CONSOLE_ALLOWED_HOSTS = "a.test, b.test";
    try { expect(C.allowedHosts()).toEqual(["127.0.0.1", "localhost", "a.test", "b.test"]); } finally { delete process.env.DEV_CONSOLE_ALLOWED_HOSTS; }
  });
});

// ---------------------------------------------------------------------------------------------------- the home table
describe("home", () => {
  const fresh = () => { const t = tmp(); process.env.DEV_CONSOLE_DB = join(t, "db", "dev-console.sqlite"); process.env.DEV_CONSOLE_HOME_DIR = join(t, "home"); return t; };
  const ids = () => C.homeList().map((w) => w.id);

  test("the first creation seeds exactly the logo", () => {
    fresh(); C.storeInit();
    expect(ids()).toEqual(["logo"]);
    const [logo] = C.homeList();
    expect([logo.widget_id, logo.chrome, logo.src]).toEqual([C.LOGO_ID, false, "/domain/dev-console/w/_/domain.updated/Logo"]);
    C.storeInit(); // not a second time
    expect(ids()).toEqual(["logo"]);
  });
  test("show, replace, rm and clear", () => {
    fresh(); C.storeInit();
    C.homeShow({ id: "a", source: "html", content: "<p>a</p>", title: "A" });
    C.homeShow({ id: "b", source: "url", content: "/domain/x" });
    expect(ids()).toEqual(["logo", "a", "b"]);
    C.homeShow({ id: "a", source: "html", content: "<p>a2</p>" });
    expect(ids()).toEqual(["logo", "a", "b"]);
    expect(C.homeRemove("a")).toBe(true);
    expect(C.homeRemove("a")).toBe(false);
    C.homeClear();
    expect(ids()).toEqual(["logo"]);
  });
  test("source, validation and the safe url rule", () => {
    fresh(); C.storeInit();
    const bad = (b: any) => expect(() => C.homeShow(b)).toThrow();
    bad({ id: "x", source: "nope" }); bad({ source: "html", content: "x" }); bad({ id: "x", source: "html" });
    bad({ id: "x", source: "widget" }); bad({ id: "x", source: "url", content: "javascript:alert(1)" }); bad({ id: "x", source: "url", content: "//evil.test" });
    bad({ id: "x", source: "html", content: "y", parent_id: "x" });
    C.homeShow({ id: "w", source: "widget", widget_id: "tensions/management.created/TensionDetail", task: "t 1" });
    const w = C.homeList().find((r) => r.id === "w");
    expect(w.src).toBe("/domain/tensions/w/t%201/management.created/TensionDetail?task=t%201");
  });
  test("position, span and parent composition (a parent gone or a loop falls back to the top)", () => {
    fresh(); C.storeInit();
    C.homeShow({ id: "a", source: "html", content: "a" });
    C.homeShow({ id: "b", source: "html", content: "b", position: -1, span: 9 });
    expect(ids()).toEqual(["b", "logo", "a"]);
    expect(C.homeList()[0].span).toBe(3);
    C.homeShow({ id: "c", source: "html", content: "c", parent_id: "a" });
    expect(C.homeList().find((r) => r.id === "c").parent_id).toBe("a");
    const db = new Database(C.dbPath());
    db.run("UPDATE home SET parent_id='ghost' WHERE id='c'");
    db.run("UPDATE home SET parent_id='a' WHERE id='b'"); db.run("UPDATE home SET parent_id='b' WHERE id='a'");
    db.close();
    const parents = Object.fromEntries(C.homeList().map((r) => [r.id, r.parent_id]));
    expect(parents.c).toBeNull(); // its parent is gone
    expect([parents.a, parents.b].filter(Boolean)).toHaveLength(1); // the loop a <-> b is cut: one of them is top-level
    C.homeShow({ id: "d", source: "html", content: "d", parent_id: "c" });
    C.homeRemove("c"); // removes what is composed inside it
    expect(ids()).not.toContain("d");
  });
  test("the old journal migrates once and stays untouched", () => {
    const t = fresh();
    mkdirSync(join(t, "home"), { recursive: true });
    const ev = (event: string, value: any) => JSON.stringify({ event, value, at: "2026-01-01T00:00:00Z", actor: "old" });
    const text = [ev("home.widget.shown", { id: "h1", kind: "html", content: "<b>x</b>" }),
      ev("home.widget.shown", { id: "w1", kind: "widget", content: "/domain/tensions/w/_/management.created/TensionDetail?task=T9" }),
      ev("home.widget.shown", { id: "gone", kind: "html", content: "z" }), ev("home.widget.removed", { id: "gone" })].join("\n") + "\n";
    writeFileSync(join(t, "home", "events.jsonl"), text);
    C.storeInit();
    expect(ids()).toEqual(["logo", "h1", "w1"]);
    expect(C.homeList().find((r) => r.id === "w1").widget_id).toBe("tensions/management.created/TensionDetail");
    C.homeClear(); C.storeInit();
    expect(ids()).toEqual(["logo"]); // not migrated again
    expect(Bun.file(join(t, "home", "events.jsonl")).size).toBe(text.length);
  });
  test("the widgets table mirrors what the host collects and writes only on a change", () => {
    fresh(); C.storeInit();
    const row = (id: string, extra: any = {}) => ({ id, domain: "d", event: "e.x", name: id, kind: "widget", position: 0, function: id, module: "m", file: "f.py", line: 1,
      fake: 0, roles: "[]", code: "def x(): ...", code_sha256: "h", project: "p.py", ...extra });
    expect(C.syncWidgets([row("A"), row("B")])).toBe(true);
    expect(C.syncWidgets([row("A"), row("B")])).toBe(false);
    expect(C.syncWidgets([row("A")])).toBe(true);
    const db = new Database(C.dbPath());
    expect((db.query("select count(*) n from widgets").get() as any).n).toBe(1);
    db.close();
  });
  test("a write from another process reaches the stream", async () => {
    fresh(); C.storeInit();
    const snaps: string[] = [];
    const stop = C.homeChanges((s) => snaps.push(s));
    C.homeShow({ id: "ext", source: "html", content: "x" });
    await until(() => snaps.some((s) => s.includes('"ext"')));
    const db = new Database(C.dbPath()); // the owner, in a SQLite app
    db.run("UPDATE home SET position=-5 WHERE id='ext'"); db.close();
    await until(() => JSON.parse(snaps.at(-1)!).widgets[0].id === "ext");
    stop();
  });
});

// ---------------------------------------------------------------------------------------------------- the model page
describe("model", () => {
  test("phase 01 is drawn as written; no tables is an empty diagram", () => {
    const t = tmp(), p = join(t, "dm.sqlite");
    process.env.DM_DB = p;
    expect(C.modelMermaid("x")).toContain("sem entidades ainda");
    const db = new Database(p);
    db.run('create table "01_overview_diagram" (domain, diagram, pos, row, item, kind, note, status, verb, target, cardinality)');
    db.run(`insert into "01_overview_diagram" values ('x','domain',1,'node','Order','aggregate','n','real',null,null,null),
      ('x','domain',2,'node','Line','entity','n','draft',null,null,null), ('x','domain',3,'edge','Order',null,null,null,'has','Line','1..*')`);
    db.close();
    const m = C.modelMermaid("x");
    expect(m).toContain('n_Order[["<b>Order</b>');
    expect(m).toContain('n_Order -- "has 1..*" --> n_Line');
    expect(m).toContain("class n_Line draft");
    expect(C.modelDiagrams("x")).toEqual(["domain"]);
    delete process.env.DM_DB;
  });
});

// ---------------------------------------------------------------------------------------------------- the playground
const comp = (extra: any = {}) => ({ id: "via/cartao", nome: "Cartão", descricao: "d", estado: "rascunho", html: "<div class=a></div>", css: "", w: 393, h: 200,
  slots: [{ chave: "titulo", seletor: ".a", como: "texto" }], dados: { titulo: "x" }, ...extra });

describe("playground", () => {
  test("validation messages are for the model to fix", () => {
    expect(C.problemaDoComponente(comp())).toBeNull();
    expect(C.problemaDoComponente(comp({ id: "Via/Cartao" }))).toContain("kebab-case");
    expect(C.problemaDoComponente(comp({ estado: "real" }))).toContain("exige fonte");
    expect(C.problemaDoComponente(comp({ fonte: { repo: "r" } }))).toContain("rascunho não tem fonte");
    expect(C.problemaDoComponente(comp({ w: 0 }))).toContain("w e h");
    expect(C.problemaDoComponente(comp({ slots: [{ chave: "a", seletor: ".a", como: "magia" }] }))).toContain("como inválido");
    expect(C.problemaDoComponente(comp({ variantes: { mobile: {} } }))).toContain('só aceita "desktop"');
    expect(C.problemaDoComponente("x")).toContain("objeto JSON");
  });
  test("definir writes the next version and tells every tab; listar has no html", () => {
    const pg = new C.Playground(tmp());
    const told: any[] = [];
    pg.eventos.assinar((tipo, d) => told.push([tipo, d]));
    expect(pg.componentes.definir(comp()).versao).toBe(1);
    expect(pg.componentes.definir(comp({ nome: "Cartão 2" })).versao).toBe(2);
    expect(told).toEqual([["componente", { id: "via/cartao", versao: 1 }], ["componente", { id: "via/cartao", versao: 2 }]]);
    const [s] = pg.componentes.listar();
    expect([s.chaves, "html" in s]).toEqual([["titulo"], false]);
    expect(pg.componentes.conferir("via/cartao", { titulo: "a" })).toBeNull();
    expect(pg.componentes.conferir("via/cartao", { nada: "a" })).toContain("não tem as chaves nada");
    expect(pg.componentes.conferir("via/outro")).toContain("do produto via: via/cartao");
    expect(() => pg.componentes.definir({ ...comp(), nome: "" })).toThrow("nome ausente");
  });
  test("a wrapper folder is read, and nothing may leave it", () => {
    const pg = new C.Playground(tmp()), wrap = tmp("wrap-");
    const { html, css, ...json } = comp();
    writeFileSync(join(wrap, "componente.json"), JSON.stringify(json));
    writeFileSync(join(wrap, "peca.html"), html); writeFileSync(join(wrap, "peca.css"), "a{}"); writeFileSync(join(wrap, "desktop.css"), "b{}");
    const c = pg.componentes.definirDaPasta(wrap);
    expect([c.html, c.css, c.variantes.desktop.w]).toEqual([html, "a{}", 1280]);
    const evil = tmp("wrap-"), secret = join(tmp("sec-"), "s.html");
    writeFileSync(secret, "<x>");
    writeFileSync(join(evil, "componente.json"), JSON.stringify(json)); symlinkSync(secret, join(evil, "peca.html"));
    expect(() => C.lerPasta(evil)).toThrow("fora da pasta");
    expect(() => C.lerPasta("relativa")).toThrow("absoluto");
    expect(() => C.lerPasta("/tmp/../etc")).toThrow('".."');
    expect(() => C.lerPasta(join(wrap, "nada"))).toThrow("não existe");
  });
  test("the canvas mirror survives a restart", () => {
    const d = tmp();
    const a = new C.Canvas(d);
    a.aplicar({ "shape:1": { x: 1 }, "shape:2": { x: 2 } }, null);
    a.aplicar(null, ["shape:1"]);
    expect(new C.Canvas(d).ler()).toEqual({ "shape:2": { x: 2 } });
  });
  test("an operation waits for the open page's answer", async () => {
    const pg = new C.Playground(tmp());
    await expect(pg.operacoes.executar({ op: "x" })).rejects.toThrow("Web não está aberta");
    pg.eventos.assinar((tipo, d) => { if (tipo === "canvas") queueMicrotask(() => pg.operacoes.responder(d.pedido, true, { feito: d.op.op })); });
    expect(await pg.operacoes.executar({ op: "desenhar" })).toEqual({ feito: "desenhar" });
    const slow = new C.Operacoes(pg.eventos, 0.05);
    pg.eventos.assinar(() => {});
    await expect(slow.executar({ op: "z" })).rejects.toThrow("não respondeu a tempo");
    expect(pg.operacoes.responder("nope", true)).toBe(false);
  });
  test("import copies once and refuses to overwrite without force", () => {
    const from = tmp(), to = tmp();
    writeFileSync(join(from, "canvas.json"), "{}"); mkdirSync(join(from, "componentes", "via"), { recursive: true }); writeFileSync(join(from, "componentes", "via", "a.json"), "{}");
    expect(C.importarPlayground(from, to)).toEqual(["canvas.json", "componentes"]);
    expect(existsSync(join(to, "componentes", "via", "a.json"))).toBe(true);
    expect(() => C.importarPlayground(from, to)).toThrow("--force");
    expect(C.importarPlayground(from, to, true).length).toBe(2);
    expect(() => C.importarPlayground(tmp(), tmp())).toThrow("nada para importar");
  });
});

// ---------------------------------------------------------------------------------------------------- the command line
describe("args", () => {
  test("flags, the env and --no-live", () => {
    const p = join(HERE, "dev_console_project.py");
    expect(C.parseArgs(["--project", p, "--port", "5099", "--no-live"])).toMatchObject({ projects: [p], port: 5099, noLive: true });
    expect(C.parseArgs(["--project=" + p]).port).toBe(5057);
    expect(() => C.parseArgs(["--bogus"])).toThrow("unknown argument");
    expect(C.parseArgs(["--help"]).help).toBe(true);
  });
});

// ---------------------------------------------------------------------------------------------------- a real console
const PORT = Number(process.env.DEVC_TEST_PORT || 5097);
const BASE = `http://127.0.0.1:${PORT}`;
describe("live console", () => {
  let proc: ReturnType<typeof Bun.spawn>, dir: string;
  const get = (p: string, init?: RequestInit) => fetch(BASE + p, init);
  const post = (p: string, body: any, headers: any = {}) => fetch(BASE + p, { method: "POST", body: JSON.stringify(body), headers });

  beforeAll(async () => {
    dir = tmp();
    mkdirSync(join(dir, "reg")); writeFileSync(join(dir, "reg", "domains.txt"), "");
    proc = Bun.spawn(["bun", "--cwd", resolve(HERE, ".."), join(HERE, "dev-console.ts"), "--project", join(HERE, "dev_console_project.py"), "--port", String(PORT)], {
      cwd: dir, stdout: "ignore", stderr: "inherit",
      env: { ...process.env, DEV_CONSOLE_REGISTRY: join(dir, "reg", "domains.txt"), COSTS_DIR: join(dir, "costs"), DEV_CONSOLE_DB: join(dir, "db", "dev-console.sqlite"),
        DEV_CONSOLE_HOME_DIR: join(dir, "home"), DEV_CONSOLE_PLAYGROUND_DIR: join(dir, "pg"), DEV_CONSOLE_AGENTS_DIRS: join(dir, "agents"), DM_DB: join(dir, "dm.sqlite"), PWD: dir },
    });
    await until(async () => { if (proc.exitCode !== null) throw new Error("console exited before answering"); try { return (await get("/api/home")).ok; } catch { return false; } }, 90_000);
  }, 100_000);
  afterAll(() => { proc?.kill(); rmSync(dir, { recursive: true, force: true }); });

  test("the domains and the actions, for agents", async () => {
    const ds = await (await get("/api/domains")).json();
    expect(ds).toHaveLength(1);
    expect(ds[0]).toMatchObject({ slug: "dev-console", name: "dev-console", origin: "--project" });
    expect(await (await get("/api/domains/dev-console/actions")).json()).toEqual([]);
    expect((await get("/api/domains/nope/actions")).status).toBe(404);
  });
  test("state.json is what the page is drawn from", async () => {
    const s = await (await get("/domain/dev-console/state.json")).json();
    expect(Object.keys(s).sort()).toEqual(["base", "domains", "entities", "entity_parts", "events", "home", "journal_types", "model", "module_aliases",
      "module_widgets", "modules", "money", "name", "state", "tabs"]);
    expect(s.model.root).toBe("domain.designed");
    expect(s.model.layout).toBeTruthy();
    expect((await get("/domain/dev-console/state.json?task=nope")).status).toBe(404);
    expect((await get("/domain/nope/state.json")).status).toBe(404);
  });
  test("the domain page is light, with the graph and the data", async () => {
    const r = await get("/domain/dev-console", { redirect: "manual" });
    expect(r.status).toBe(303);
    expect(r.headers.get("location")).toBe("/domain/dev-console/t/dev-console");
    const html = await (await get("/domain/dev-console/t/dev-console")).text();
    expect(html).toContain('data-theme="light"');
    expect(html).toContain("cytoscape");
    expect(html).not.toMatch(/prefers-color-scheme: dark/);
    expect(html).not.toMatch(/dark:[a-z]/);
    const data = JSON.parse(html.match(/<script type="application\/json" id="data">(.*?)<\/script>/s)![1]);
    expect(data.domains[0].slug).toBe("dev-console");
    expect((await get("/domain/nope/t/x", { redirect: "manual" })).status).toBe(303);
  });
  test("the palette lists the modules of every page, the home module first when a domain names one", async () => {
    const modules = async (path: string) => JSON.parse((await (await get(path)).text()).match(/<script type="application\/json" id="data">(.*?)<\/script>/s)![1]).modules;
    for (const path of ["/playground", "/agents", "/browser", "/"]) {
      const names = (await modules(path)).map((m: any) => m.name);
      expect(names).toEqual(["Domain", "Playground", "Agents", "Browser", "Model"]);
    }
    const onDomain = await modules("/domain/dev-console/t/dev-console");
    expect(onDomain.map((m: any) => [m.name, m.href])).toEqual([["Domain", null], ["Playground", "/playground"], ["Agents", "/agents"], ["Browser", "/browser"],
      ["Model", "/browser?url=%2Fmodel"]]);
  });
  test("widgets: a fragment for HTMX, a whole page otherwise", async () => {
    const frag = await (await get("/domain/dev-console/w/_/domain.updated/Logo", { headers: { "HX-Request": "true" } })).text();
    expect(frag.startsWith("<div")).toBe(true);
    expect(frag).toContain("<svg");
    expect(await (await get("/domain/dev-console/w/_/domain.updated/Logo")).text()).toContain("<!doctype html>");
    expect(await (await get("/domain/dev-console/w/_/domain.updated", { headers: { "HX-Request": "true" } })).text()).toContain("DomainView");
    expect(await (await get("/domain/nope/w/_/a.b/C", { headers: { "HX-Request": "true" } })).text()).toContain("não existe");
    expect((await get("/domain/dev-console/media?f=../x")).status).toBe(404);
  });
  test("the home: routes, the stream, an external edit and the widgets catalogue", async () => {
    const ids = async () => (await (await get("/api/home")).json()).widgets.map((w: any) => w.id);
    expect(await ids()).toEqual(["logo"]);
    await post("/api/home/show", { id: "a", source: "html", content: "<p>a</p>" }, { "X-Devc-Actor": "tester" });
    await post("/api/home/show", { id: "b", source: "html", content: "<p>b</p>" });
    expect(await ids()).toEqual(["logo", "a", "b"]);
    expect((await post("/api/home/show", { id: "x", source: "url", content: "javascript:1" })).status).toBe(400);
    const res = await get("/api/home/stream");
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const reader = res.body!.getReader(), dec = new TextDecoder();
    let buf = "";
    const snap = async () => { while (!buf.includes("\n\n")) buf += dec.decode((await reader.read()).value); const i = buf.indexOf("\n\n"); const s = buf.slice(0, i); buf = buf.slice(i + 2); return JSON.parse(s.slice(6)).widgets.map((w: any) => w.id); };
    expect(await snap()).toEqual(["logo", "a", "b"]);
    const db = new Database(join(dir, "db", "dev-console.sqlite")); // the owner, in a SQLite app: move b to the top
    db.run("UPDATE home SET position=-1 WHERE id='b'");
    expect(await snap()).toEqual(["b", "logo", "a"]);
    const n = (db.query("SELECT count(*) n FROM widgets WHERE domain='dev-console'").get() as any).n;
    db.close();
    reader.cancel();
    expect(n).toBeGreaterThanOrEqual(9);
    expect((await (await post("/api/home/rm", { id: "a" })).json()).removed).toBe(true);
    expect((await post("/api/home/rm", { id: "a" })).status).toBe(404);
    await post("/api/home/clear", {});
    expect(await ids()).toEqual(["logo"]);
  });
  test("the money routes answer 404 for a domain with no cost center, and 404 for an unknown one", async () => {
    expect((await get("/domain/nope/time")).status).toBe(404);
    expect([200, 404]).toContain((await post("/domain/dev-console/time/start", {})).status);
  });
  test("agents: the API reads only inside the roots and the host header is checked", async () => {
    mkdirSync(join(dir, "agents", "p"), { recursive: true });
    const r = await get("/agents/api/prompts");
    expect((await r.json()).entries).toEqual([]);
    expect((await get("/agents/api/entry?id=nokey:0")).status).toBe(404);
    expect((await get("/agents/api/log")).headers.get("access-control-allow-origin")).toBeNull();
    const evil = await fetch(BASE + "/agents/api/prompts", { headers: { Host: "evil.test" } });
    expect(evil.status).toBe(400);
    expect((await fetch(BASE + "/api/home", { headers: { Host: "localhost:" + PORT } })).status).toBe(200);
  });
  test("the playground: the API, the web files and an operation with no page open", async () => {
    const page = await (await get("/playground")).text();
    expect(page).toContain("/playground/web/canvas.js");
    for (const f of ["canvas.js", "widgets.js", "paleta.js", "eventos.js", "app.css"]) expect((await get("/playground/web/" + f)).status).toBe(200);
    expect((await get("/playground/web/nada.js")).status).toBe(404);
    expect(await (await get("/playground/api/canvas")).json()).toEqual({ registros: {} });
    expect((await post("/playground/api/canvas/diff", { put: { "shape:1": { x: 1 } } })).status).toBe(204);
    expect(await (await get("/playground/api/canvas")).json()).toEqual({ registros: { "shape:1": { x: 1 } } });
    expect((await post("/playground/api/canvas/diff", { put: [] })).status).toBe(400);
    expect((await post("/playground/api/canvas/resposta", { pedido: "x", ok: true })).status).toBe(404);
    expect(await (await get("/playground/api/componentes")).json()).toEqual({ componentes: [] });
    const sse = await get("/playground/api/eventos");
    expect(sse.headers.get("content-type")).toContain("text/event-stream");
    sse.body!.cancel();
    expect((await get("/domain/playground", { redirect: "manual" })).headers.get("location")).toBe("/playground");
  });
  test("the browser page carries the address and the model page answers", async () => {
    expect(await (await get("/browser?url=http%3A%2F%2Flocalhost%3A4321")).text()).toContain('src="http://localhost:4321"');
    expect((await get("/model/nada.mmd")).status).toBe(200);
    expect((await get("/model/nada")).status).toBe(404);
  });
  test("the live-reload stream says hello", async () => {
    const res = await get("/__live");
    const reader = res.body!.getReader();
    expect(new TextDecoder().decode((await reader.read()).value)).toContain("hello");
    await reader.cancel();
  });
});

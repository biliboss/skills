import test from "node:test";
import assert from "node:assert/strict";
import { pageMode, nativeCaps, hasWeb, viewId, isLight, webUrl, ensureServer, serverUp, wantsServer } from "../mod/pagemode.js";

const WEB = { interface: "native-view/0", platform: "macos", available: true, kinds: [{ kind: "web", actions: ["browser.reload"] }, { kind: "pdf", actions: [] }] };
const PDF_ONLY = { interface: "native-view/0", available: true, kinds: [{ kind: "pdf", actions: [] }] };

test("API absent: Markdown panel, nothing else", () => {
  assert.deepEqual(pageMode({ hasHtml: true, hasMd: true, caps: null, choice: null }), { mode: "blocks", canToggle: false, hint: null });
  assert.equal(pageMode({ hasHtml: true, hasMd: false, caps: null, choice: null }).mode, "empty");
  assert.equal(nativeCaps({}), null);
  assert.equal(nativeCaps({ nativeViewCapabilities: () => WEB }), null, "needs nativeView.new too");
  assert.equal(nativeCaps(undefined), null);
});

test("capabilities without web: Markdown panel", () => {
  assert.equal(pageMode({ hasHtml: true, hasMd: true, caps: PDF_ONLY, choice: null }).mode, "blocks");
  assert.equal(hasWeb({ available: false, kinds: [{ kind: "web" }] }), false);
  assert.equal(hasWeb({ kinds: "web" }), false);
});

test("capabilities with web and page.html: page", () => {
  const r = pageMode({ hasHtml: true, hasMd: true, caps: WEB, choice: null });
  assert.deepEqual(r, { mode: "page", canToggle: true, hint: null });
});

test("no page.html: Markdown even with web", () => {
  assert.equal(pageMode({ hasHtml: false, hasMd: true, caps: WEB, choice: "page" }).mode, "blocks");
});

test("no page.md (HTML source): page, no toggle, no hint (comments go through the server)", () => {
  const r = pageMode({ hasHtml: true, hasMd: false, caps: WEB, choice: "blocks" });
  assert.deepEqual(r, { mode: "page", canToggle: false, hint: null });
});

test("owner's choice switches between page and blocks", () => {
  assert.equal(pageMode({ hasHtml: true, hasMd: true, caps: WEB, choice: "blocks" }).mode, "blocks");
  assert.equal(pageMode({ hasHtml: true, hasMd: true, caps: WEB, choice: "page" }).mode, "page");
  assert.equal(pageMode({ hasHtml: true, hasMd: true, caps: WEB, choice: "blocks" }).canToggle, true);
});

test("nativeCaps survives a throwing host and returns caps otherwise", () => {
  assert.equal(nativeCaps({ nativeView: { new() {} }, nativeViewCapabilities() { throw new Error("x"); } }), null);
  assert.deepEqual(nativeCaps({ nativeView: { new() {} }, nativeViewCapabilities: () => WEB }), WEB);
});

test("view id is stable per panel and bot, unique across panels", () => {
  assert.equal(viewId("b1", "p1"), viewId("b1", "p1"));
  assert.notEqual(viewId("b1", "p1"), viewId("b2", "p1"));
  assert.notEqual(viewId("b1", "p1"), viewId("b1", "p2"));
});

test("isLight reads hex colors", () => {
  assert.equal(isLight("#ffffff"), true); assert.equal(isLight("#fafafa"), true);
  assert.equal(isLight("#101010"), false); assert.equal(isLight("#111"), false);
  assert.equal(isLight(undefined), true);
});

test("webUrl is loopback with the bot and theme", () => {
  assert.equal(webUrl(47836, "via-assinatura", true), "http://127.0.0.1:47836/via-assinatura/?theme=light");
  assert.equal(webUrl(1, "a b", false), "http://127.0.0.1:1/a%20b/?theme=dark");
});

const fakeExec = ({ upAfter = 0, startFails = false } = {}) => {
  const calls = [];
  let probes = 0;
  const exec = async (cmd, args) => {
    calls.push([cmd, ...args]);
    if (cmd === "curl") { probes++; return probes > upAfter ? { code: 0, stdout: "200", stderr: "" } : { code: 7, stdout: "000", stderr: "" }; }
    if (startFails) throw new Error("not found");
    return { code: 0, stdout: "{}", stderr: "" };
  };
  return { exec, calls };
};

test("ensureServer: already up starts nothing", async () => {
  const f = fakeExec();
  assert.deepEqual(await ensureServer({ exec: f.exec, port: 5, bin: "/x/canvas" }), { ok: true, started: false, note: null });
  assert.equal(f.calls.length, 1);
});

test("ensureServer: down -> starts once with serve --detach, probes again", async () => {
  const f = fakeExec({ upAfter: 1 });
  const r = await ensureServer({ exec: f.exec, port: 5, bin: "/x/canvas" });
  assert.equal(r.ok, true); assert.equal(r.started, true);
  assert.deepEqual(f.calls.filter(c => c[0] !== "curl"), [["/x/canvas", "serve", "--detach"]]);
});

test("ensureServer: failure to start or answer gives a one-line note, no throw", async () => {
  const a = await ensureServer({ exec: fakeExec({ upAfter: 99, startFails: true }).exec, port: 5, bin: "b" });
  assert.equal(a.ok, false); assert.match(a.note, /página sem comentários/);
  const b = await ensureServer({ exec: fakeExec({ upAfter: 99 }).exec, port: 5, bin: "b" });
  assert.equal(b.ok, false); assert.equal(b.started, true);
  assert.equal(await serverUp(async () => { throw new Error("x"); }, 5), false);
});

test("wantsServer: only with page.html and web support", () => {
  assert.equal(wantsServer({ hasHtml: true, caps: WEB }), true);
  assert.equal(wantsServer({ hasHtml: false, caps: WEB }), false);
  assert.equal(wantsServer({ hasHtml: true, caps: null }), false);
  assert.equal(wantsServer({ hasHtml: true, caps: PDF_ONLY }), false);
  assert.equal(wantsServer({ hasHtml: true, caps: { available: false, kinds: [{ kind: "web" }] } }), false);
  assert.equal(wantsServer({}), false);
});

test("ensureServer: a second call finds it up and starts nothing more", async () => {
  const f = fakeExec({ upAfter: 1 });
  await ensureServer({ exec: f.exec, port: 5, bin: "/x/canvas" });
  const r = await ensureServer({ exec: f.exec, port: 5, bin: "/x/canvas" });
  assert.equal(r.started, false);
  assert.equal(f.calls.filter(c => c[0] !== "curl").length, 1);
});

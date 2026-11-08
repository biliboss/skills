import test from "node:test";
import assert from "node:assert/strict";
import { pageMode, nativeCaps, hasWeb, viewId } from "../mod/pagemode.js";

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

test("no page.md: page, no toggle, one-line hint", () => {
  const r = pageMode({ hasHtml: true, hasMd: false, caps: WEB, choice: "blocks" });
  assert.equal(r.mode, "page"); assert.equal(r.canToggle, false); assert.match(r.hint, /page\.md/);
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

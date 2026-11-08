// Prints what the JS side (blocks.js, store.js, notify.js) makes of a Markdown file, as JSON.
// skills/herdr-canvas/scripts/test_parity.py compares it with canvaslib.py (the CLI/server side).
import { readFileSync } from "node:fs";
import { splitMarkdown } from "../mod/blocks.js";
import { makeEntry, toMarkdown } from "../mod/store.js";
import { buildMessage } from "../mod/notify.js";

const blocks = splitMarkdown(readFileSync(process.argv[2], "utf8"));
const pick = blocks[Math.min(2, blocks.length - 1)];
const now = new Date("2026-11-08T12:34:56.789Z");
const entry = makeEntry({ body: "olá\nmundo " + "x".repeat(300), block: pick, version: "sha1:abc", now, id: "c_test1" });
const done = { ...entry, id: "c_test2", resolved: "2026-11-08T13:00:00Z" };
console.log(JSON.stringify({
  blocks: blocks.map(({ id, index, kind, heading }) => ({ id, index, kind, heading })),
  pickIndex: pick.index, entry,
  message: buildMessage(entry, { id: "b1", folder: "/x/b1" }),
  markdown: toMarkdown([entry, done]),
}));

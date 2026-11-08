import test from "node:test";
import assert from "node:assert/strict";
import { appendComment, readComments, toMarkdown, makeEntry, writeCommentsMarkdown } from "../mod/store.js";
import { splitMarkdown } from "../mod/blocks.js";

function memIO(files = {}, failFirstWrite = false) {
  let failed = false;
  return {
    files,
    read: async p => files[p] ?? null,
    write: async (p, t, e) => {
      if (failFirstWrite && !failed) {
        failed = true;
        files[p] = (files[p] ?? "") + '{"id":"c_other"}\n';
        throw new Error("stale");
      }
      if ((files[p] ?? null) !== e) throw new Error("stale");
      files[p] = t;
    },
  };
}
const block = splitMarkdown("# T\n\nAssinatura mensal sem fidelidade")[1];
const entry = (body, id) => makeEntry({ body, block, version: "sha1:x", now: new Date("2026-11-08T14:02:11.123Z"), id });

test("append creates and appends one line per entry", async () => {
  const io = memIO();
  await appendComment(io, "/c.jsonl", entry("um", "c_1"));
  await appendComment(io, "/c.jsonl", entry("dois", "c_2"));
  const lines = io.files["/c.jsonl"].trim().split("\n");
  assert.equal(lines.length, 2);
  const e = JSON.parse(lines[0]);
  assert.equal(e.created, "2026-11-08T14:02:11Z");
  assert.equal(e.target.blockId, block.id);
  assert.equal(e.target.selector[0].exact, "Assinatura mensal sem fidelidade");
});

test("CAS conflict: retries once on the fresh content, keeps the other writer's line", async () => {
  const io = memIO({ "/c.jsonl": '{"id":"c_0"}\n' }, true);
  await appendComment(io, "/c.jsonl", entry("novo", "c_3"));
  const ids = io.files["/c.jsonl"].trim().split("\n").map(l => JSON.parse(l).id);
  assert.deepEqual(ids, ["c_0", "c_other", "c_3"]);
});

test("second conflict surfaces the error", async () => {
  const io = { read: async () => "", write: async () => { throw new Error("stale"); } };
  await assert.rejects(appendComment(io, "/c.jsonl", entry("x", "c_9")), /stale/);
});

test("resolve lines mark comments; markdown lists open first, resolved struck", () => {
  const text = [JSON.stringify(entry("abrir", "c_1")), JSON.stringify(entry("fechar", "c_2")), JSON.stringify({ resolve: "c_2", at: "2026-11-08T15:00:00Z" }), "lixo"].join("\n");
  const list = readComments(text);
  assert.equal(list.length, 2);
  assert.equal(list[1].resolved, "2026-11-08T15:00:00Z");
  const md = toMarkdown(list);
  assert.ok(md.indexOf("Abertos (1)") < md.indexOf("Resolvidos (1)"));
  assert.match(md, /~~`c_2`/);
  assert.match(md, /`c_1` bloco 2/);
});

test("writeCommentsMarkdown writes comments.md", async () => {
  const io = memIO();
  await writeCommentsMarkdown(io, "/d", readComments(JSON.stringify(entry("a", "c_1"))));
  assert.match(io.files["/d/comments.md"], /Comentários do canvas/);
});

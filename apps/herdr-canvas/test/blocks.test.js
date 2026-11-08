import test from "node:test";
import assert from "node:assert/strict";
import { splitMarkdown } from "../mod/blocks.js";

const DOC = "# Proposta\n\n## Assinatura\nTexto um.\nainda o mesmo parágrafo\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```js\nconst x = 1;\n\nconst y = 2;\n```\n\n> citação\n\n---\n";

test("splits kinds, keeps fenced blank lines in one block", () => {
  const b = splitMarkdown(DOC);
  assert.deepEqual(b.map(x => x.kind), ["heading", "heading", "paragraph", "list", "table", "code", "quote", "hr"]);
  assert.match(b[5].text, /const y = 2/);
  assert.equal(b[2].text.split("\n").length, 2);
});

test("heading path and index", () => {
  const b = splitMarkdown(DOC);
  assert.deepEqual(b[2].heading, ["Proposta", "Assinatura"]);
  assert.deepEqual(b[0].heading, ["Proposta"]);
  assert.equal(b[7].index, 8);
});

test("a heading with no blank line ends the paragraph", () => {
  const b = splitMarkdown("texto\n# Título\nmais");
  assert.deepEqual(b.map(x => x.kind), ["paragraph", "heading", "paragraph"]);
});

test("ids are stable and shaped cv-xxxxxx; changing a block keeps the earlier ids", () => {
  const a = splitMarkdown(DOC), b = splitMarkdown(DOC);
  assert.deepEqual(a.map(x => x.id), b.map(x => x.id));
  assert.ok(a.every(x => /^cv-[0-9a-f]{6}$/.test(x.id)));
  assert.equal(new Set(a.map(x => x.id)).size, a.length);
  const c = splitMarkdown(DOC.replace("citação", "outra citação"));
  assert.deepEqual(a.slice(0, 6).map(x => x.id), c.slice(0, 6).map(x => x.id));
});

test("empty and CRLF input", () => {
  assert.deepEqual(splitMarkdown(""), []);
  assert.equal(splitMarkdown("a\r\n\r\nb").length, 2);
});

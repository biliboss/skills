// The pure part of the comment mode: the same file (page.js) that canvaslib.py inlines into page.html.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { sentenceAt, quoteAt, quoteForRange, MAX, CTX } = require('../../../skills/herdr-canvas/scripts/page.js');

const T = 'Primeira frase aqui. A segunda frase é esta! E a terceira? Fim sem ponto';

test('sentenceAt picks the phrase around the offset', () => {
  const r = sentenceAt(T, T.indexOf('segunda'));
  assert.equal(T.slice(r.start, r.end), 'A segunda frase é esta!');
  const first = sentenceAt(T, 3);
  assert.equal(T.slice(first.start, first.end), 'Primeira frase aqui.');
  const last = sentenceAt(T, T.length - 2);
  assert.equal(T.slice(last.start, last.end), 'Fim sem ponto');
});

test('a click on the terminator or on the blank after it stays in a sentence', () => {
  assert.equal(quoteAt(T, T.indexOf('aqui.') + 4).exact, 'Primeira frase aqui.');
  assert.equal(quoteAt(T, T.indexOf('aqui.') + 5).exact, 'A segunda frase é esta!');
});

test('decimals and abbreviations without a following blank do not split', () => {
  const t = 'Custa R$ 1.299,00 por mês. Outra.';
  assert.equal(quoteAt(t, 12).exact, 'Custa R$ 1.299,00 por mês.');
});

test('a newline ends a phrase', () => {
  assert.equal(quoteAt('linha um\nlinha dois', 12).exact, 'linha dois');
});

test('long phrases are cut to MAX chars and keep the clicked spot', () => {
  const long = 'palavra '.repeat(60).trim() + '.';
  const q = quoteAt(long, 300);
  assert.ok(q.exact.length <= MAX && q.exact.length > 100, String(q.exact.length));
  const off = quoteAt(long, long.length - 3);
  assert.ok(off.exact.length <= MAX);
  assert.ok(long.includes(off.exact));
});

test('prefix and suffix are at most CTX chars and normalise blanks', () => {
  const t = 'x'.repeat(100) + '  \n  alvo aqui. ' + 'y'.repeat(100);
  const q = quoteAt(t, t.indexOf('alvo') + 1);
  assert.equal(q.exact, 'alvo aqui.');
  assert.ok(q.prefix.length <= CTX && q.suffix.length <= CTX);
  assert.ok(q.prefix.endsWith('x '));
  assert.ok(q.suffix.startsWith(' y'));
});

test('quoteForRange uses the selection, trims and clips', () => {
  const q = quoteForRange(T, T.indexOf('segunda') - 2, T.indexOf('segunda') + 7);
  assert.equal(q.exact, 'A segunda');
  assert.equal(quoteForRange('a'.repeat(500), 0, 500).exact.length, MAX);
  assert.equal(quoteForRange(T, 9, 3).exact, 'meira');
});

test('empty or blank text gives no quote', () => {
  assert.equal(quoteAt('', 0), null);
  assert.equal(quoteAt('   \n  ', 2), null);
  assert.equal(quoteForRange('abc', 1, 1), null);
});

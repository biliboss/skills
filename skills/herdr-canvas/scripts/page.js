/* Script of the Canvas page (comment mode). canvaslib.py inlines this file into page.html;
   `node --test` loads the same file for the pure functions (module.exports). No DOM access before the guard. */
(function () {
  'use strict';
  var MAX = 120, CTX = 32;

  // ---- pure: the quote of a click or selection --------------------------------------------------
  function norm(s) { return String(s).replace(/\s+/g, ' '); }
  function isSpace(c) { return c === undefined || /\s/.test(c); }

  function trimRange(t, s, e) {
    while (s < e && /\s/.test(t[s])) s++;
    while (e > s && /\s/.test(t[e - 1])) e--;
    return { start: s, end: e };
  }

  // The sentence around `offset` in t, at most MAX chars, as {start, end} (end exclusive); empty when only blanks.
  function sentenceAt(t, offset) {
    t = String(t);
    var o = Math.max(0, Math.min(offset | 0, t.length)), start = 0, end = t.length, k;
    for (k = o - 1; k >= 0; k--) {
      if (t[k] === '\n' || (/[.!?]/.test(t[k]) && isSpace(t[k + 1]))) { start = k + 1; break; }
    }
    for (k = o; k < t.length; k++) {
      if (t[k] === '\n') { end = k; break; }
      if (/[.!?]/.test(t[k]) && isSpace(t[k + 1])) { end = k + 1; break; }
    }
    var r = trimRange(t, start, Math.max(start, end));
    if (r.end - r.start > MAX) {
      var s = Math.max(r.start, Math.min(o - 40, r.end - MAX));
      r = trimRange(t, s, Math.min(r.end, s + MAX));
    }
    return r;
  }

  function build(t, s, e) {
    var exact = norm(t.slice(s, e)).trim();
    if (!exact) return null;
    return { exact: exact, prefix: norm(t.slice(Math.max(0, s - CTX * 2), s)).slice(-CTX), suffix: norm(t.slice(e, e + CTX * 2)).slice(0, CTX) };
  }

  // Phrase under a click: offset is a position in t (the text of the block body).
  function quoteAt(t, offset) {
    t = String(t);
    var r = sentenceAt(t, offset);
    return build(t, r.start, r.end);
  }

  // The owner's own selection [start, end) in t, clipped to MAX chars.
  function quoteForRange(t, start, end) {
    t = String(t);
    var r = trimRange(t, Math.max(0, Math.min(start, end)), Math.min(t.length, Math.max(start, end)));
    if (r.end - r.start > MAX) r = trimRange(t, r.start, r.start + MAX);
    return build(t, r.start, r.end);
  }

  if (typeof module === 'object' && module && module.exports) module.exports = { sentenceAt: sentenceAt, quoteAt: quoteAt, quoteForRange: quoteForRange, MAX: MAX, CTX: CTX };
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  // ---- the page ---------------------------------------------------------------------------------
  var CV = window.CV;
  if (!CV || !CV.token) return;                       // file:// or no server: a clean page, no toggle
  document.body.classList.remove('cv-static');

  var KEY = 'cv-comment-mode';
  var on = false, pop = null, hovered = null, picked = null;
  CV.comments = CV.comments || [];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function store(v) { try { window.sessionStorage.setItem(KEY, v ? '1' : '0'); } catch (e) { /* ignored */ } }
  function stored() { try { return window.sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; } }
  function bodyOf(block) { return block.querySelector('.cv-body'); }

  // toggle
  var label = el('label', 'cv-toggle');
  var box = el('input', 'toggle toggle-sm cv-toggle-input'); box.type = 'checkbox';
  label.appendChild(el('span', 'cv-toggle-text', 'Comentar'));
  label.appendChild(box);
  label.appendChild(el('kbd', 'kbd kbd-sm', 'c'));
  document.body.appendChild(label);

  // hover / pick marks
  function mark(block, cls) {
    document.querySelectorAll('.' + cls).forEach(function (n) { if (n !== block) n.classList.remove(cls); });
    if (block) block.classList.add(cls);
  }
  function setHover(block) { if (block !== hovered) { hovered = block; mark(block, 'cv-hover'); } }

  // popover
  function closePop() {
    if (pop) { pop.remove(); pop = null; }
    picked = null; mark(null, 'cv-picked');
  }
  function place() {
    if (!pop || !picked) return;
    var r = picked.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = window.innerHeight, m = 8;
    var w = Math.min(352, vw - 2 * m);
    pop.style.width = w + 'px';
    var left = Math.max(m, Math.min(r.left, vw - w - m));
    var h = pop.offsetHeight, top = r.bottom + 6;
    if (top + h > vh - m) top = r.top - h - 6;
    top = Math.max(m, Math.min(top, vh - h - m));
    pop.style.left = left + 'px'; pop.style.top = top + 'px';
  }
  function openPop(block, node) {
    closePop();
    picked = block; mark(block, 'cv-picked');
    pop = node; pop.classList.add('cv-pop');
    document.body.appendChild(pop);
    place();
  }

  function offsetIn(body, node, off) {
    if (!body.contains(node)) return -1;
    var r = document.createRange(); r.selectNodeContents(body);
    try { r.setEnd(node, off); } catch (e) { return -1; }
    return r.toString().length;
  }
  function caretAt(x, y) {
    if (document.caretRangeFromPoint) { var r = document.caretRangeFromPoint(x, y); return r ? { node: r.startContainer, offset: r.startOffset } : null; }
    if (document.caretPositionFromPoint) { var p = document.caretPositionFromPoint(x, y); return p ? { node: p.offsetNode, offset: p.offset } : null; }
    return null;
  }
  // Taken at the click that fixes the pick: later the selection may be gone.
  function quoteOfClick(block, ev) {
    var body = bodyOf(block); if (!body) return null;
    var text = body.textContent, sel = window.getSelection && window.getSelection();
    if (sel && !sel.isCollapsed && sel.rangeCount) {
      var r = sel.getRangeAt(0), a = offsetIn(body, r.startContainer, r.startOffset), b = offsetIn(body, r.endContainer, r.endOffset);
      if (a >= 0 && b >= 0 && a !== b) return quoteForRange(text, a, b);
    }
    var c = caretAt(ev.clientX, ev.clientY); if (!c) return null;
    var o = offsetIn(body, c.node, c.offset);
    return o < 0 ? null : quoteAt(text, o);
  }

  // pins
  function openOf(blockId) { return CV.comments.filter(function (c) { return c.blockId === blockId && !c.resolved; }); }
  function renderPins() {
    document.querySelectorAll('.cv-pin').forEach(function (n) { n.remove(); });
    if (!on) return;
    document.querySelectorAll('[data-block]').forEach(function (block) {
      var n = openOf(block.getAttribute('data-block')).length; if (!n) return;
      var pin = el('button', 'badge badge-primary badge-sm cv-pin', String(n));
      pin.type = 'button'; pin.setAttribute('aria-label', n + (n === 1 ? ' comentário aberto' : ' comentários abertos'));
      block.appendChild(pin);
    });
  }
  function openPinPop(block) {
    var list = openOf(block.getAttribute('data-block')); if (!list.length) return;
    var node = el('div');
    node.appendChild(el('div', 'cv-pop-title', list.length + (list.length === 1 ? ' comentário aberto' : ' comentários abertos')));
    list.forEach(function (c) {
      var item = el('div', 'cv-item');
      if (c.quote) item.appendChild(el('div', 'cv-quote-line', '“' + c.quote + '”'));
      item.appendChild(el('div', 'cv-item-body', c.body));
      node.appendChild(item);
    });
    var row = el('div', 'cv-row'), close = el('button', 'btn btn-sm btn-ghost', 'Fechar'); close.type = 'button';
    close.onclick = closePop; row.appendChild(close); node.appendChild(row);
    openPop(block, node);
  }

  // comment form
  function openForm(block, quote) {
    var id = block.getAttribute('data-block');
    var node = el('div');
    var head = el('div', 'cv-pop-title', 'Comentar o bloco ' + (block.getAttribute('data-index') || ''));
    var q = el('div', 'cv-quote-line', quote ? '“' + quote.exact + '”' : 'Sem trecho: o comentário vale para o bloco inteiro.');
    var area = el('textarea', 'textarea w-full cv-area'); area.rows = 3;
    area.placeholder = 'Enter envia · Shift+Enter quebra a linha · Esc fecha';
    var row = el('div', 'cv-row');
    var go = el('button', 'btn btn-sm btn-primary', 'Enviar'); go.type = 'button';
    var no = el('button', 'btn btn-sm btn-ghost', 'Cancelar'); no.type = 'button';
    var err = el('div', 'cv-err'); err.setAttribute('role', 'alert');
    var busy = false;
    function send() {
      var text = area.value.trim(); if (!text || busy) return;
      busy = true; go.disabled = true; err.textContent = '';
      var payload = { blockId: id, body: text, version: CV.version };
      if (quote) payload.quote = quote;
      fetch(CV.post, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Canvas-Token': CV.token }, body: JSON.stringify(payload) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); })
        .then(function (j) {
          CV.comments.push({ id: j.id, blockId: id, body: text, quote: quote ? quote.exact : '' });
          closePop(); renderPins();
        })
        .catch(function (e) { busy = false; go.disabled = false; err.textContent = 'Não enviou: ' + e.message; place(); });
    }
    go.onclick = send; no.onclick = closePop;
    area.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    });
    row.appendChild(go); row.appendChild(no);
    [head, q, area, row, err].forEach(function (n) { node.appendChild(n); });
    openPop(block, node);
    area.focus({ preventScroll: true });
  }

  // mode
  function setMode(v) {
    on = !!v; box.checked = on; store(on);
    document.body.classList.toggle('cv-mode', on);
    if (!on) { closePop(); setHover(null); }
    renderPins();
  }
  box.addEventListener('change', function () { setMode(box.checked); box.blur(); });

  function editable(t) {
    if (!t || !t.tagName) return false;
    if (t.classList && t.classList.contains('cv-toggle-input')) return false;
    return /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable;
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (pop) { e.preventDefault(); e.stopPropagation(); closePop(); }
      else if (on) { e.preventDefault(); setMode(false); }
      return;
    }
    if ((e.key === 'c' || e.key === 'C') && !e.metaKey && !e.ctrlKey && !e.altKey && !e.repeat && !editable(e.target) && !editable(document.activeElement)) {
      e.preventDefault(); setMode(!on);
    }
  }, true);

  document.addEventListener('mousemove', function (e) {
    if (!on || picked || (pop && pop.contains(e.target))) return;
    setHover(e.target.closest ? e.target.closest('[data-block]') : null);
  });
  document.addEventListener('mouseout', function (e) { if (!e.relatedTarget && !picked) setHover(null); });

  document.addEventListener('click', function (e) {
    if (!on || !e.target.closest) return;
    if (e.target.closest('.cv-pop, .cv-toggle')) return;
    var pin = e.target.closest('.cv-pin');
    var block = e.target.closest('[data-block]');
    if (!block) return;
    e.preventDefault(); e.stopPropagation();          // links do not navigate in comment mode
    var typed = pop && pop.querySelector('textarea');  // never drop what the owner already wrote
    if (typed && typed.value.trim()) { typed.focus({ preventScroll: true }); return; }
    if (pin) { openPinPop(block); return; }
    openForm(block, quoteOfClick(block, e));
  }, true);

  window.addEventListener('resize', place);
  window.addEventListener('scroll', place, true);

  setMode(stored());
})();

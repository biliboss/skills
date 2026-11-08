// Splits Markdown into blocks with stable ids and the heading path above each one.
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const HR = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const FENCE = /^\s{0,3}(```|~~~)/;

function fnv1a(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h >>> 0;
}

export function blockId(index, kind, text) {
  const hash = fnv1a(`${index}:${kind}:${text.slice(0, 40)}`) & 0xffffff;
  return "cv-" + hash.toString(16).padStart(6, "0");
}

function kindOf(first, lines) {
  if (FENCE.test(first)) return "code";
  if (HR.test(first) && lines.length === 1) return "hr";
  if (/^\s{0,3}>/.test(first)) return "quote";
  if (/^\s*([-*+]|\d+[.)])\s+/.test(first)) return "list";
  if (/^\s*\|/.test(first) && lines.length > 1 && /^\s*\|?\s*:?-{2,}/.test(lines[1])) return "table";
  return "paragraph";
}

export function splitMarkdown(md) {
  const raw = [];
  let cur = [], fence = null;
  const flush = () => { if (cur.length) raw.push(cur); cur = []; };
  for (const line of String(md ?? "").replace(/\r\n?/g, "\n").split("\n")) {
    const f = FENCE.exec(line);
    if (fence) { cur.push(line); if (f && f[1] === fence) { fence = null; flush(); } continue; }
    if (f) { flush(); fence = f[1]; cur.push(line); continue; }
    if (!line.trim()) { flush(); continue; }
    if (HEADING.test(line)) { flush(); cur.push(line); flush(); continue; }
    cur.push(line);
  }
  flush();
  const blocks = [], path = [];
  raw.forEach((lines, index) => {
    const text = lines.join("\n"), m = HEADING.exec(lines[0]);
    const kind = m && lines.length === 1 ? "heading" : kindOf(lines[0], lines);
    if (kind === "heading") { path.length = m[1].length - 1; path[m[1].length - 1] = m[2]; }
    const headings = path.filter(Boolean);
    blocks.push({ id: blockId(index, kind, text), index: index + 1, kind, text, heading: headings });
  });
  return blocks;
}

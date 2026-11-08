// Comments live in <bot>/canvas/comments.jsonl, one JSON object per line. io = { read(path), write(path, text, expected) }.
export function newCommentId(now = Date.now(), rand = Math.random) {
  return "c_" + now.toString(36).slice(-5) + Math.floor(rand() * 36 ** 3).toString(36).padStart(3, "0");
}

export function makeEntry({ body, block, version, now = new Date(), id }) {
  const quote = block.text.replace(/\s+/g, " ").trim();
  return {
    id: id ?? newCommentId(now.getTime()), type: "Annotation", created: now.toISOString().replace(/\.\d+Z$/, "Z"),
    creator: "owner", resolved: null,
    body: { type: "TextualBody", value: body },
    target: { source: "canvas/page.md", version: version ?? null, blockId: block.id, index: block.index, kind: block.kind,
      heading: block.heading, selector: [{ type: "TextQuoteSelector", exact: quote.slice(0, 120), prefix: "", suffix: "" }] },
  };
}

async function writeLine(io, path, line, tries = 2) {
  for (let i = 0; i < tries; i++) {
    const cur = await io.read(path);
    try { await io.write(path, (cur ?? "") + line + "\n", cur); return; }
    catch (e) { if (i === tries - 1) throw e; }
  }
}

export const appendComment = (io, path, entry) => writeLine(io, path, JSON.stringify(entry));
export const appendLog = (io, path, text) => writeLine(io, path, text);

// Applies resolve lines; returns annotations with `resolved` set.
export function readComments(text) {
  const list = [], resolved = new Map();
  for (const line of String(text ?? "").split("\n")) {
    if (!line.trim()) continue;
    let o; try { o = JSON.parse(line); } catch { continue; }
    if (o.resolve) resolved.set(o.resolve, o.at ?? true); else if (o.id) list.push(o);
  }
  return list.map(c => resolved.has(c.id) ? { ...c, resolved: resolved.get(c.id) } : c);
}

export function toMarkdown(comments) {
  const open = comments.filter(c => !c.resolved), done = comments.filter(c => c.resolved);
  const one = (c, strike) => {
    const t = c.target ?? {}, where = [`bloco ${t.index ?? "?"}`, ...(t.heading?.length ? [t.heading.join(" › ")] : [])].join(" · ");
    const body = String(c.body?.value ?? "").replace(/\n/g, "\n  ");
    const quote = t.selector?.[0]?.exact ? `\n  > ${t.selector[0].exact}` : "";
    return `- ${strike ? "~~" : ""}\`${c.id}\` ${where}${strike ? "~~" : ""}${quote}\n  ${strike ? "~~" + body + "~~" : body}`;
  };
  const parts = ["# Comentários do canvas", "", `## Abertos (${open.length})`, "", ...(open.length ? open.map(c => one(c, false)) : ["Nenhum."])];
  if (done.length) parts.push("", `## Resolvidos (${done.length})`, "", ...done.map(c => one(c, true)));
  return parts.join("\n") + "\n";
}

export async function writeCommentsMarkdown(io, dir, comments) {
  const path = dir + "/comments.md", text = toMarkdown(comments);
  for (let i = 0; i < 2; i++) {
    const cur = await io.read(path);
    try { await io.write(path, text, cur); return; } catch (e) { if (i === 1) throw e; }
  }
}

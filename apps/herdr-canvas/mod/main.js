// Canvas: a bot's page.md in numbered blocks; click a block, comment, Enter sends it to the bot.
// Never moves focus: no pane.focus, agent.focus, layout.show or layout.select here (see test/nofocus.test.js).
import { View, div } from "gpui-kit";
import { v_flex, h_flex, TextView, TextareaState, Textarea } from "gpui-base";
import { home, props, readTextFile, writeTextFile, watchFolder, hc, agents, panes, notify, theme } from "herdr";
import { splitMarkdown } from "./blocks.js";
import { appendComment, appendLog, readComments, writeCommentsMarkdown, makeEntry } from "./store.js";
import { buildMessage, sendToBot } from "./notify.js";

// FALLBACK: true draws each block as plain text (headings bold) instead of TextView.markdown.
// Also available as the prop "plain": true in the layout, and as the "Texto" button in the header.
const PLAIN = false;

const io = { read: p => readTextFile(p), write: (p, t, e) => writeTextFile(p, t, e) };

export default class Canvas extends View {
  init(_props, cx) {
    this.bots = []; this.bot = null; this.blocks = []; this.comments = []; this.version = null; this.error = null;
    this.selected = null; this.hover = null; this.plain = props()?.plain ?? PLAIN; this.sent = null;
    this.area = TextareaState.new({ placeholder: "Comentário · Enter envia, Shift+Enter quebra linha", rows: 3 });
    this.area.set_auto_grow(3, 8);
    this.area.on("submit", (e, cx) => this.onSubmit(e, cx));
    this.handle = cx.focus_handle();
    this.loadBots(cx);
    cx.timer.every(15000, cx => this.loadBots(cx));
  }

  registry() { return props()?.registry ?? `${home()}/agents/bots.json`; }
  dir(bot = this.bot) { return `${bot.folder}/canvas`; }

  loadBots(cx) {
    cx.spawn(async cx => {
      try {
        const reg = JSON.parse((await readTextFile(this.registry())) ?? "{}"), found = [];
        for (const b of reg.bots ?? []) if ((await readTextFile(`${b.folder}/canvas/page.md`)) !== null) found.push({ id: b.id, name: b.name ?? b.id, folder: b.folder });
        this.bots = found; this.error = found.length ? null : "Nenhum bot tem canvas/page.md. Use: canvas publish <bot> <arquivo.md>";
        // `canvas open <bot>` writes "<bot>\t<timestamp>" here; a new line switches the shown bot once.
        const req = (await readTextFile(`${home()}/.local/state/herdr-canvas/bot`))?.trim() ?? null;
        let want = this.bot?.id ?? props()?.bot;
        if (req && req !== this.lastReq) { this.lastReq = req; want = req.split("\t")[0]; }
        const next = found.find(b => b.id === want) ?? found[0] ?? null;
        if (next && next.id !== this.bot?.id) this.pick(next, cx); else if (!next) this.bot = null;
      } catch (e) { this.error = "Cadastro de bots ilegível: " + e; }
      finally { cx.notify(); }
    });
  }

  pick(bot, cx) {
    this.bot = bot; this.selected = null; this.area.set_value("");
    const mine = bot; this.watching = bot.id;
    this.reload(cx);
    cx.spawn(async cx => {
      try { while (this.watching === mine.id) { await watchFolder(this.dir(mine)); if (this.watching === mine.id) this.reload(cx); } }
      catch { /* the 15 s timer in loadBots is enough */ }
    });
  }

  reload(cx) {
    const bot = this.bot; if (!bot) return;
    cx.spawn(async cx => {
      try {
        const [page, jsonl, version] = await Promise.all([readTextFile(`${this.dir(bot)}/page.md`), readTextFile(`${this.dir(bot)}/comments.jsonl`), readTextFile(`${this.dir(bot)}/version`)]);
        if (this.bot?.id !== bot.id) return;
        this.blocks = splitMarkdown(page ?? ""); this.comments = readComments(jsonl); this.version = (version ?? "").trim() || null;
        if (this.selected && !this.blocks.some(b => b.id === this.selected)) this.selected = null;
        this.error = null;
      } catch (e) { this.error = "Não consegui ler o canvas: " + e; }
      finally { cx.notify(); }
    });
  }

  select(block, cx) {
    this.selected = this.selected === block.id ? null : block.id;
    if (this.selected) { this.area.set_value(""); this.area.focus(); }
    cx.notify();
  }

  cancel(cx) { this.selected = null; this.area.set_value(""); cx.notify(); }

  onSubmit(e, cx) {
    // Enter sends; Shift+Enter is a new line; Cmd+Enter always sends (reserve if Enter behaves differently).
    if (e?.shift && !e?.secondary) { this.area.set_value(this.area.value() + "\n"); return; }
    this.send(cx);
  }

  send(cx) {
    const block = this.blocks.find(b => b.id === this.selected), bot = this.bot, body = this.area.value().trim();
    if (!block || !bot || !body) return;
    const entry = makeEntry({ body, block, version: this.version });
    this.area.set_value("");
    cx.spawn(async cx => {
      try {
        const dir = this.dir(bot);
        await appendComment(io, `${dir}/comments.jsonl`, entry);
        const all = readComments(await readTextFile(`${dir}/comments.jsonl`));
        this.comments = all;
        await writeCommentsMarkdown(io, dir, all);
        const address = this.addressOf(bot);
        if (address) {
          await sendToBot({ hc, after: (ms, fn) => cx.timer.after(ms, fn), log: t => appendLog(io, `${dir}/notify.log`, t), address, text: buildMessage(entry, bot) });
          notify({ title: "Canvas", body: "Comentário enviado", level: "success" });
        } else {
          await appendLog(io, `${dir}/notify.log`, `${new Date().toISOString()} sem terminal aberto em ${bot.folder}; comentário só em comments.md`);
          notify({ title: "Canvas", body: "Comentário salvo; o bot não tem terminal aberto", level: "warning" });
        }
        this.selected = null;
      } catch (e) { this.error = "Falha ao salvar o comentário: " + e; }
      finally { cx.notify(); }
    });
  }

  addressOf(bot) {
    const pane = panes().find(p => p.terminal && p.cwd === bot.folder);
    return agents().find(a => a.pane === pane?.pane)?.address ?? pane?.terminal ?? null;
  }

  body(block, t) {
    if (!this.plain) return TextView.markdown(`tv-${block.id}`, block.text).selectable(true);
    const heading = block.kind === "heading";
    return div().whitespace_normal().text_size(heading ? 15 : 13).when(heading, el => el.font_semibold()).child(block.text);
  }

  row(block, t) {
    const mine = this.comments.filter(c => c.target?.blockId === block.id), open = mine.filter(c => !c.resolved);
    const on = this.selected === block.id, pick = (_e, cx) => this.select(block, cx);
    return v_flex().id(`row-${block.id}`).flex_none().gap(4).p(4).rounded(8).border_1().border_color(on ? t.selected : t.border)
      .child(h_flex().gap(6).items_start()
        .child(v_flex().id(`gutter-${block.id}`).w(28).flex_none().items_center().cursor_pointer().rounded(6).text_size(11).text_color(on ? t.foreground : t.muted)
          .hover(s => s.bg(t.hover)).on_click(pick)
          .child(String(block.index)).when(open.length > 0, el => el.child(div().text_color(t.accent).child("●"))))
        .child(div().id(`body-${block.id}`).flex_1().min_w(0).cursor_pointer().on_click(pick).child(this.body(block, t))))
      .children(mine.map(c => div().pl(34).text_size(11.5).text_color(c.resolved ? t.dim : t.muted).child((c.resolved ? "✓ " : "● ") + String(c.body?.value ?? ""))))
      .when(on, el => el.child(v_flex().pl(34).gap(6).child(Textarea.new(this.area).p(6).rounded(8).border_1().border_color(t.border).bg(t.background).text_size(12.5))
        .child(h_flex().gap(8).items_center()
          .child(div().id("canvas-send").px(12).h(28).flex().items_center().rounded(7).bg(t.solid).text_color(t.solid_foreground).text_size(12).cursor_pointer().on_click((_e, cx) => this.send(cx)).child("Enviar"))
          .child(div().id("canvas-cancel").px(8).h(28).flex().items_center().text_size(12).text_color(t.muted).cursor_pointer().on_click((_e, cx) => this.cancel(cx)).child("Esc"))
          .child(div().text_size(11).text_color(t.dim).child("Enter envia · Shift+Enter nova linha · Cmd+Enter envia")))));
  }

  render(cx) {
    const t = theme(), openCount = this.comments.filter(c => !c.resolved).length;
    const chip = (id, label, active, fn) => div().id(id).px(8).h(24).flex().items_center().rounded(6).flex_none().text_size(12).cursor_pointer()
      .bg(active ? t.selected : t.raised).text_color(active ? t.foreground : t.muted).hover(s => s.bg(t.hover)).on_click(fn).child(label);
    return v_flex().id("canvas").track_focus(this.handle).size_full().min_h(0).rounded(10).overflow_hidden().bg(t.background).border_1().border_color(t.border).text_color(t.foreground).text_size(13)
      .on_key_down((e, cx) => { if (e.key === "escape" && this.selected) { this.cancel(cx); cx.stop_propagation(); } })
      .child(h_flex().h(42).flex_none().px(14).gap(8).items_center().border_b(1).border_color(t.border)
        .child(div().font_semibold().child("Canvas"))
        .child(div().flex_1().min_w(0).truncate().text_size(12).text_color(t.dim).child(this.bot ? `${this.bot.name} · ${openCount} aberto${openCount === 1 ? "" : "s"}` : ""))
        .child(chip("canvas-plain", "Texto", this.plain, (_e, cx) => { this.plain = !this.plain; cx.notify(); }))
        .child(chip("canvas-reload", "↻", false, (_e, cx) => { this.loadBots(cx); this.reload(cx); })))
      .when(this.bots.length > 1, el => el.child(h_flex().id("canvas-bots").flex_none().px(10).py(6).gap(6).overflow_x_scrollbar().border_b(1).border_color(t.border)
        .children(this.bots.map(b => chip(`bot-${b.id}`, b.name, b.id === this.bot?.id, (_e, cx) => this.pick(b, cx))))))
      .child(v_flex().id("canvas-blocks").flex_1().min_h(0).overflow_y_scrollbar().p(8).gap(4)
        .children(this.blocks.map(b => this.row(b, t)))
        .when(Boolean(this.error) || !this.blocks.length, el => el.child(div().p(8).text_size(12).text_color(t.dim).child(this.error || "Página vazia"))));
  }
}

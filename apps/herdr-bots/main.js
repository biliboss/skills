import { View, div, svg } from 'gpui-kit';
import { v_flex, h_flex } from 'gpui-base';
import { exec, readTextFile, home, theme, layout, props, setShared, focused, nextCommand, spaces, run } from 'herdr';

function find(node, id) {
  if (!node) return null;
  if (node.id === id) return node;
  for (const child of node.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
}

function botStatus(bot) {
  return spaces().find(space => space.id === bot.space_id)?.status ?? null;
}

export default class Bots extends View {
  init(_props, cx) {
    this.bots = [];
    this.busy = new Set();
    this.error = '';
    this.loading = false;
    this.optionHeld = false;
    setShared('bili.optionHints', false);
    if (props()?.optionState) cx.spawn(async cx => {
      let state = -1;
      for (;;) {
        try {
          const result = await exec(props().optionState, [String(state)]);
          if (result.code !== 0) break;
          state = Number(result.stdout.trim());
          const held = state === 1;
          if (held !== this.optionHeld) {
            this.optionHeld = held;
            setShared('bili.optionHints', held);
            cx.notify();
          }
        } catch { break; }
      }
      this.optionHeld = false;
      setShared('bili.optionHints', false);
      cx.notify();
    });
    this.reload(cx);
    cx.spawn(async cx => {
      for (;;) {
        const command = await nextCommand();
        const match = /^select-([1-9])$/.exec(command);
        if (!match) continue;
        const index = Number(match[1]) - 1;
        if (index < this.bots.length) this.open(this.bots[index], cx);
        else {
          const hidden = new Set(this.bots.map(bot => bot.space_id));
          const target = spaces().filter(space => !hidden.has(space.id))[index - this.bots.length];
          if (target) run('space.select', { id: target.id });
        }
      }
    });
    cx.timer.every(5000, cx => this.reload(cx));
  }
  reload(cx) {
    if (this.loading) return;
    this.loading = true;
    cx.spawn(async cx => {
      try {
        const path = props().registry ?? `${home()}/agents/bots.json`;
        const raw = await readTextFile(path);
        if (raw === null) throw new Error(`Cadastro ausente: ${path}`);
        const result = await exec('env', [`AG_HOME=${props().dataHome}`, `AG_BOTS_FILE=${path}`, props().opener, '--list']);
        if (result.code !== 0) throw new Error(result.stderr || 'Cadastro inválido');
        this.bots = JSON.parse(result.stdout).bots;
        setShared('bili.botSpaces', this.bots.map(bot => bot.space_id));
        this.configError = '';
      } catch (error) { this.bots = []; this.configError = String(error); }
      finally { this.loading = false; cx.notify(); }
    });
  }
  open(bot, cx) {
    if (this.busy.has(bot.id)) return;
    this.busy.add(bot.id);
    this.error = '';
    cx.notify();
    cx.spawn(async cx => {
      try {
        const result = await exec('env', [`AG_HOME=${props().dataHome}`, `AG_BOTS_FILE=${props().registry}`, props().opener, bot.id]);
        if (result.code !== 0) throw new Error(result.stderr || result.stdout);
      } catch (error) { this.error = String(error); }
      finally { this.busy.delete(bot.id); cx.notify(); }
    });
  }
  render() {
    const t = theme();
    const narrow = (find(layout(), 'sidebar')?.size?.px ?? 268) < 160;
    const error = this.configError || this.error || this.bots.map(bot => bot.last_error).filter(Boolean).join('\n');
    return v_flex().size_full().bg(t.chrome).px(narrow ? 4 : 8).gap(3)
      .when(!narrow, el => el.child(div().px(8).pt(10).pb(4).text_size(11.5).text_color(t.dim).child('Bots')))
      .child(v_flex().id('bot-list').flex_1().min_h(0).overflow_y_scrollbar().children(this.bots.map((bot, index) =>
        h_flex().id(`bot-${bot.id}`).h(32).flex_none().px(8).gap(9).items_center().rounded(8)
          .text_size(13).text_color(t.foreground).when(focused()?.space === bot.space_id, el => el.bg(t.selected)).cursor_pointer().hover(el => el.bg(t.hover))
          .tooltip(this.busy.has(bot.id) ? `Abrindo ${bot.name}…` : bot.name)
          .on_click((_event, cx) => this.open(bot, cx))
          .child(svg('icons/agent.svg').size(16).flex_none().text_color(t.muted))
          .when(!narrow, el => el.child(div().flex_1().truncate().child(this.busy.has(bot.id) ? `${bot.name}…` : bot.name)))
          .when(botStatus(bot) === 'working', el => el.child(svg('mods/workspace-chrome/spinner.svg').size(12).flex_none().text_color(t.working).spin(900)))
          .when(botStatus(bot) === 'blocked' || botStatus(bot) === 'done', el => el.child(div().size(6).flex_none().rounded(3).bg(t[botStatus(bot)])))
          .when(this.optionHeld && index < 9, el => el.child(div().flex_none().text_size(11).text_color(t.dim).child(`⌥${index + 1}`))))))
      .when(Boolean(error), el => el.child(div().text_size(11).text_color(t.blocked).tooltip(error).child(narrow ? '!' : error)));
  }
}

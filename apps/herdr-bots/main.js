import { View } from 'gpui-kit';
import { theme, props, setShared, focused, nextCommand, spaces, run, exec } from 'herdr';
import { isNarrow } from './lib/layout.js';
import { loadBots, openBot } from './lib/registry.js';
import { BotsPanel } from './widgets/BotsPanel.js';

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
        this.bots = await loadBots();
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
      try { await openBot(bot); }
      catch (error) { this.error = String(error); }
      finally { this.busy.delete(bot.id); cx.notify(); }
    });
  }
  render() {
    const t = theme();
    const rows = this.bots.map(bot => ({
      bot,
      status: botStatus(bot),
      busy: this.busy.has(bot.id),
      selected: focused()?.space === bot.space_id,
    }));
    const error = this.configError || this.error || this.bots.map(bot => bot.last_error).filter(Boolean).join('\n');
    return BotsPanel({
      rows,
      narrow: isNarrow(),
      hints: this.optionHeld,
      error,
      onOpen: (bot, cx) => this.open(bot, cx),
    }, t);
  }
}

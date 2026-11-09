import { h_flex } from 'gpui-base';
import { BotIcon } from './BotIcon.js';
import { BotName } from './BotName.js';
import { StatusMark } from './StatusMark.js';
import { ShortcutHint } from './ShortcutHint.js';

export function BotRow({ row, index, narrow, hints, onOpen }, t) {
  const { bot, status, busy, selected } = row;
  const mark = StatusMark({ status }, t);
  return h_flex().id(`bots.row:${bot.id}`).h(32).flex_none().px(8).gap(9).items_center().rounded(8)
    .text_size(13).text_color(t.foreground).when(selected, el => el.bg(t.selected)).cursor_pointer().hover(el => el.bg(t.hover))
    .tooltip(busy ? `Abrindo ${bot.name}…` : bot.name)
    .on_click((_event, cx) => onOpen(bot, cx))
    .child(BotIcon(t))
    .when(!narrow, el => el.child(BotName({ name: bot.name, busy })))
    .when(mark != null, el => el.child(mark))
    .when(hints && index < 9, el => el.child(ShortcutHint({ index }, t)));
}

import { v_flex } from 'gpui-base';
import { BotRow } from './BotRow.js';

export function BotList({ rows, narrow, hints, onOpen }, t) {
  return v_flex().id('bots.list').flex_1().min_h(0).overflow_y_scrollbar()
    .children(rows.map((row, index) => BotRow({ row, index, narrow, hints, onOpen }, t)));
}

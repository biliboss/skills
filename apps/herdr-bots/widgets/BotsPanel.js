import { v_flex } from 'gpui-base';
import { PanelTitle } from './PanelTitle.js';
import { BotList } from './BotList.js';
import { ErrorLine } from './ErrorLine.js';

export function BotsPanel({ rows, narrow, hints, error, onOpen }, t) {
  return v_flex().id('bots.panel').size_full().bg(t.chrome).px(narrow ? 4 : 8).gap(3)
    .when(!narrow, el => el.child(PanelTitle(t)))
    .child(BotList({ rows, narrow, hints, onOpen }, t))
    .when(Boolean(error), el => el.child(ErrorLine({ error, narrow }, t)));
}

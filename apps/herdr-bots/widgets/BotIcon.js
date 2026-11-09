import { svg } from 'gpui-kit';

export function BotIcon(t) {
  return svg('icons/agent.svg').size(16).flex_none().text_color(t.muted);
}

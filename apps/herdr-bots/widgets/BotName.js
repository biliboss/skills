import { div } from 'gpui-kit';

export function BotName({ name, busy }) {
  return div().flex_1().truncate().child(busy ? `${name}…` : name);
}

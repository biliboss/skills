import { div } from 'gpui-kit';

export function ShortcutHint({ index }, t) {
  return div().flex_none().text_size(11).text_color(t.dim).child(`⌘${index + 1}`);
}
